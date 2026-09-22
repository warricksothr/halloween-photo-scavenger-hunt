"""Focused regression tests for the application's cross-boundary invariants."""

from __future__ import annotations

import asyncio
import re
import shutil
import sqlite3
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import ASGITransport, AsyncClient
from support import arm_csrf
from test_evidence import make_jpeg
from test_mod import _mod, _submit
from test_mod import _party as mod_party
from test_teams import _invite, _party

from app import db as db_module
from app import events, mod, players, submissions, teams
from app import evidence as evidence_module
from app.audit import Action
from app.main import create_app
from app.sse import SseBroker, _stream


def test_concurrent_invite_redemptions_consume_one_token_once(admin, client):
    """The conditional invite update wins one redemption and rolls back the other."""
    party = _party(admin, client)
    batman = party["players"]["Batman"]["client"]
    token = _invite(batman)

    async def redeem_pair():
        start_barrier = asyncio.Barrier(2)
        transport = ASGITransport(app=client.app)
        async with (
            AsyncClient(transport=transport, base_url="http://test") as robin,
            AsyncClient(transport=transport, base_url="http://test") as oracle,
        ):
            arm_csrf(robin, client.app)
            arm_csrf(oracle, client.app)

            async def redeem(player, display_name):
                await start_barrier.wait()
                return await player.post(
                    f"/api/team/invites/{token}/redeem",
                    json={"display_name": display_name},
                )

            return await asyncio.gather(
                redeem(robin, "Robin"), redeem(oracle, "Oracle")
            )

    responses = asyncio.run(redeem_pair())

    assert sorted(response.status_code for response in responses) == [201, 410]
    assert (
        sum(response.json().get("error") == "invite_closed" for response in responses)
        == 1
    )

    conn = client.app.state.db
    invite = conn.execute(
        "SELECT redeemed_by FROM team_invite WHERE token = ?", (token,)
    ).fetchone()
    assert invite["redeemed_by"] is not None
    members = conn.execute(
        "SELECT display_name FROM player WHERE team_id = ? ORDER BY created_at, id",
        (party["players"]["Batman"]["team_id"],),
    ).fetchall()
    assert {member["display_name"] for member in members} in (
        {"Batman", "Robin"},
        {"Batman", "Oracle"},
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM audit_event"
            " WHERE action = 'team_invite.redeemed' AND entity_id = ?",
            (token,),
        ).fetchone()[0]
        == 1
    )


class _ObservedLock:
    """The app's reentrant lock, reporting how many threads are parked on
    it. A test can then tell "the lock serialized my peer" from "my peer
    never showed up" — the difference between a real race and a
    rendezvous that quietly timed out."""

    def __init__(self, lock):
        self._lock = lock
        self._local = threading.local()
        self._guard = threading.Lock()
        self.waiting = 0

    def __enter__(self):
        depth = getattr(self._local, "depth", 0)
        if depth == 0:
            with self._guard:
                self.waiting += 1
        try:
            self._lock.acquire()
        finally:
            if depth == 0:
                with self._guard:
                    self.waiting -= 1
        self._local.depth = depth + 1
        return self

    def __exit__(self, *exc):
        self._local.depth -= 1
        return self._lock.release()


def test_concurrent_inappropriate_verdicts_advance_one_rung_each(
    admin, client, monkeypatch
):
    """Two moderators flagging two of one player's photos take the next
    rung each, not the same one.

    The handler derives the strike level before its transaction, and the
    conditional UPDATE is per-submission — so without the request lock
    both moderators read the same strike count and both insert the same
    level, skipping a rung of the ladder. The barrier makes both
    derivations land before either write, which is the interleaving the
    lock rules out.

    The lock serializes the two requests, so the peer can never reach the
    barrier. That is the expected outcome, but a peer that simply never
    arrived would look the same, so the timeout path confirms the peer is
    parked on the request lock before proceeding: a rendezvous that never
    happened fails the test instead of passing it.
    """
    party = mod_party(admin, client, riddles=("R1", "R2"))
    second_evidence = client.post(
        "/api/evidence", files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")}
    ).json()["id"]
    first = _submit(client, party["riddle_ids"][0], party["evidence_id"])
    second = _submit(client, party["riddle_ids"][1], second_evidence)

    mod_a = _mod(client, party["mod_code"])
    mod_b = _mod(client, party["mod_code"])

    observed_lock = _ObservedLock(client.app.state.db_lock)
    monkeypatch.setattr(client.app.state, "db_lock", observed_lock)

    real_derive = mod.derive_restriction
    arrived = threading.Barrier(2, timeout=1)
    serialized = threading.Event()

    def blocking_derive(conn, player_id):
        if not serialized.is_set():
            try:
                arrived.wait()
            except threading.BrokenBarrierError:
                deadline = time.monotonic() + 5
                while observed_lock.waiting == 0 and time.monotonic() < deadline:
                    time.sleep(0.01)
                assert observed_lock.waiting >= 1, (
                    "the peer neither reached the barrier nor parked on the"
                    " request lock: the race was not exercised"
                )
                serialized.set()
        return real_derive(conn, player_id)

    monkeypatch.setattr(mod, "derive_restriction", blocking_derive)

    async def race():
        start_barrier = asyncio.Barrier(2)
        transport = ASGITransport(app=client.app)
        async with (
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(mod_a.cookies),
            ) as mod_a_api,
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(mod_b.cookies),
            ) as mod_b_api,
        ):
            arm_csrf(mod_a_api, client.app)
            arm_csrf(mod_b_api, client.app)

            async def flag(api, submission_id):
                await start_barrier.wait()
                return await api.post(
                    f"/api/mod/queue/{submission_id}/inappropriate",
                    json={"note": ""},
                )

            return await asyncio.gather(
                flag(mod_a_api, first["id"]), flag(mod_b_api, second["id"])
            )

    try:
        responses = asyncio.run(race())
    finally:
        mod_a.close()
        mod_b.close()

    assert [response.status_code for response in responses] == [200, 200]

    conn = client.app.state.db
    levels = [
        row["level"]
        for row in conn.execute(
            "SELECT level FROM strike WHERE player_id = ? ORDER BY level",
            (party["player_id"],),
        ).fetchall()
    ]
    assert levels == [1, 2], "the ladder skipped a rung under concurrency"


def test_auth_read_cannot_commit_another_requests_mutation(
    admin, client, tmp_path, monkeypatch
):
    """A throttled last_seen_at write must not commit a peer's in-flight
    mutation without its audit row (ADR 0004).

    The mutation is parked between its INSERT and its log_action call; the
    auth read that would otherwise commit it must block on the shared
    lock instead. A fresh connection must still see nothing, and the
    mutation and its audit row must land together."""
    party = mod_party(admin, client)

    reader = arm_csrf(TestClient(client.app))
    reader_join = reader.post(
        f"/api/join/{party['join_code']}", json={"display_name": "Robin"}
    )
    assert reader_join.status_code == 201, reader_join.text

    # Age Robin's session so their next read takes the throttled
    # last_seen_at write path (the write that used to commit a peer).
    conn = client.app.state.db
    conn.execute(
        "UPDATE session SET last_seen_at = 0 WHERE player_id = ?",
        (reader_join.json()["player"]["id"],),
    )
    conn.commit()

    mutation_written = threading.Event()
    release = threading.Event()
    real_log_action = submissions.log_action

    def blocking_log_action(*args, **kwargs):
        mutation_written.set()
        assert release.wait(timeout=5), "mutation was never released"
        return real_log_action(*args, **kwargs)

    monkeypatch.setattr(submissions, "log_action", blocking_log_action)

    def count_submissions():
        # A separate connection: the shared one is mid-transaction and
        # would see its own uncommitted INSERT.
        observer = db_module.connect(tmp_path / "api.db")
        try:
            return observer.execute("SELECT COUNT(*) FROM submission").fetchone()[0]
        finally:
            observer.close()

    async def interleave():
        transport = ASGITransport(app=client.app)
        async with (
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(client.cookies),
            ) as mutator_api,
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(reader.cookies),
            ) as reader_api,
        ):
            arm_csrf(mutator_api, client.app)
            arm_csrf(reader_api, client.app)
            mutation = asyncio.create_task(
                mutator_api.post(
                    "/api/submissions",
                    json={
                        "riddle_id": party["riddle_ids"][0],
                        "evidence_item_id": party["evidence_id"],
                    },
                )
            )
            assert await asyncio.to_thread(mutation_written.wait, 5)

            reader_task = asyncio.create_task(reader_api.get("/api/evidence"))
            # With the bug the reader's commit lands here and finishes;
            # with the lock it parks behind the mutator and stays pending.
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 1.0
            while not reader_task.done() and loop.time() < deadline:
                await asyncio.sleep(0.02)
            mid_flight = count_submissions()

            release.set()
            mutation_response = await mutation
            await reader_task
            return mutation_response, mid_flight

    try:
        mutation_response, mid_flight = asyncio.run(interleave())
    finally:
        reader.close()

    assert mutation_response.status_code == 201, mutation_response.text
    assert mid_flight == 0, "mutation was visible before its audit row committed"
    assert count_submissions() == 1
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM audit_event WHERE action = 'submission.created'"
        ).fetchone()[0]
        == 1
    )


def test_unlocked_read_does_not_see_another_requests_uncommitted_write(
    admin, client, monkeypatch
):
    """An unlocked read runs on its own connection, so it cannot observe a
    peer's open transaction (ADR 0013).

    The mutation parks between its INSERT and its log_action. A queue read
    on a fresh moderator session — whose last_seen_at is too recent for the
    throttled write, so the read stays genuinely unlocked — must complete
    while the write is still open and must not contain the parked
    submission. On the shared connection it would both complete and see the
    uncommitted row (the dirty read this ticket reproduced)."""
    party = mod_party(admin, client)
    moderator = _mod(client, party["mod_code"])

    mutation_written = threading.Event()
    release = threading.Event()
    real_log_action = submissions.log_action

    def blocking_log_action(*args, **kwargs):
        mutation_written.set()
        assert release.wait(timeout=5), "mutation was never released"
        return real_log_action(*args, **kwargs)

    monkeypatch.setattr(submissions, "log_action", blocking_log_action)

    async def interleave():
        transport = ASGITransport(app=client.app)
        async with (
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(client.cookies),
            ) as mutator_api,
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(moderator.cookies),
            ) as reader_api,
        ):
            arm_csrf(mutator_api, client.app)
            arm_csrf(reader_api, client.app)
            mutation = asyncio.create_task(
                mutator_api.post(
                    "/api/submissions",
                    json={
                        "riddle_id": party["riddle_ids"][0],
                        "evidence_item_id": party["evidence_id"],
                    },
                )
            )
            assert await asyncio.to_thread(mutation_written.wait, 5)

            # Unlocked read: /api/mod/queue is not behind
            # hold_request_lock, so it must not park on the writer.
            queue_response = await asyncio.wait_for(
                reader_api.get("/api/mod/queue"), timeout=5
            )
            mid_flight = queue_response.json()

            release.set()
            mutation_response = await mutation
            after = (await reader_api.get("/api/mod/queue")).json()
            return mutation_response, mid_flight, after

    try:
        mutation_response, mid_flight, after = asyncio.run(interleave())
    finally:
        moderator.close()

    assert mutation_response.status_code == 201, mutation_response.text
    assert mid_flight == [], "the read saw the peer's uncommitted submission"
    assert [item["id"] for item in after] == [mutation_response.json()["id"]]


def test_only_db_and_main_touch_the_connections_directly():
    """Handlers read through ``db.reader`` and write through
    ``db.locked_transaction``; naming ``app.state.db`` or
    ``app.state.read_db`` in a handler bypasses that rule (ADR 0013)."""
    app_dir = Path(db_module.__file__).parent
    direct = re.compile(r"state\.(?:read_db|db)\b(?!_)")
    offenders = {
        path.name: [
            line_number
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            )
            if direct.search(line)
        ]
        for path in sorted(app_dir.glob("*.py"))
        if path.name not in {"db.py", "main.py"}
    }
    assert {name: hits for name, hits in offenders.items() if hits} == {}


def test_write_after_a_session_revocation_commits_is_rejected(
    admin, client, monkeypatch
):
    """A write authenticated from the pre-revocation snapshot must not land
    after the revocation commits (ADR 0013).

    Auth reads the session on the reader, which serves the last committed
    snapshot: a logout that commits after that read is invisible there. The
    logout is parked inside its transaction (holding the writer) while a
    submission authenticates; when logout commits, the submission's writer
    transaction re-checks the session and refuses the write."""
    party = mod_party(admin, client)

    revoke_written = threading.Event()
    release = threading.Event()
    real_revoke = players.auth.revoke_player_session

    def blocking_revoke(conn, session_id):
        real_revoke(conn, session_id)
        revoke_written.set()
        assert release.wait(timeout=5), "logout was never released"

    monkeypatch.setattr(players.auth, "revoke_player_session", blocking_revoke)

    async def interleave():
        transport = ASGITransport(app=client.app)
        cookies = dict(client.cookies)
        async with (
            AsyncClient(
                transport=transport, base_url="http://test", cookies=cookies
            ) as revoker,
            AsyncClient(
                transport=transport, base_url="http://test", cookies=cookies
            ) as writer,
        ):
            arm_csrf(revoker, client.app)
            arm_csrf(writer, client.app)
            logout = asyncio.create_task(revoker.post("/api/logout"))
            assert await asyncio.to_thread(revoke_written.wait, 5)

            submission = asyncio.create_task(
                writer.post(
                    "/api/submissions",
                    json={
                        "riddle_id": party["riddle_ids"][0],
                        "evidence_item_id": party["evidence_id"],
                    },
                )
            )
            # The submission authenticates against the pre-revocation
            # snapshot (the reader cannot see the open logout) and then
            # parks on the writer lock the logout holds.
            await asyncio.sleep(0.3)
            assert not submission.done(), "submission did not wait for the writer"

            release.set()
            logout_response = await logout
            return logout_response, await submission

    logout_response, submission_response = asyncio.run(interleave())

    assert logout_response.status_code == 200, logout_response.text
    assert submission_response.status_code == 401, submission_response.text
    assert (
        client.app.state.db.execute(
            "SELECT COUNT(*) FROM submission WHERE submitted_by = ?",
            (party["player_id"],),
        ).fetchone()[0]
        == 0
    )


def test_create_riddle_after_the_event_is_purged_is_not_a_500(
    admin, client, monkeypatch
):
    """The reader serves committed state, so an event can vanish before a
    dependent write's transaction. ``create_riddle`` re-checks the event on
    the writer and answers 404, where an unchecked INSERT would fail its
    foreign key and surface as a server error (ADR 0013)."""
    event = admin.post("/api/admin/events", json={"name": "Purge Race"}).json()
    riddle = admin.post(
        f"/api/admin/events/{event['id']}/riddles",
        json={"text": "Q1", "sort_order": 1},
    )
    assert riddle.status_code == 201, riddle.text
    assert admin.post(f"/api/admin/events/{event['id']}/open").status_code == 200
    assert admin.post(f"/api/admin/events/{event['id']}/close").status_code == 200

    purge_written = threading.Event()
    release_purge = threading.Event()
    real_log_action = events.log_action

    def blocking_log_action(*args, **kwargs):
        if kwargs.get("action") == Action.EVENT_PURGED:
            purge_written.set()
            assert release_purge.wait(timeout=5), "purge was never released"
        return real_log_action(*args, **kwargs)

    reader_read = threading.Event()
    release_create = threading.Event()
    gate = {"open": False}
    real_get_event = events._get_event

    def gated_get_event(conn, event_id):
        row = real_get_event(conn, event_id)
        if gate["open"]:
            gate["open"] = False
            reader_read.set()
            assert release_create.wait(timeout=5), "create was never released"
        return row

    monkeypatch.setattr(events, "log_action", blocking_log_action)
    monkeypatch.setattr(events, "_get_event", gated_get_event)

    async def interleave():
        transport = ASGITransport(app=client.app)
        cookies = dict(admin.cookies)
        async with (
            AsyncClient(
                transport=transport, base_url="http://test", cookies=cookies
            ) as purger,
            AsyncClient(
                transport=transport, base_url="http://test", cookies=cookies
            ) as creator,
        ):
            arm_csrf(purger, client.app)
            arm_csrf(creator, client.app)
            purge = asyncio.create_task(
                purger.post(
                    f"/api/admin/events/{event['id']}/purge",
                    json={"confirm": event["name"]},
                )
            )
            assert await asyncio.to_thread(purge_written.wait, 5)

            # create_riddle's reader check sees the event (purge is still
            # uncommitted) and parks before its write transaction.
            gate["open"] = True
            create = asyncio.create_task(
                creator.post(
                    f"/api/admin/events/{event['id']}/riddles",
                    json={"text": "Q2", "sort_order": 2},
                )
            )
            assert await asyncio.to_thread(reader_read.wait, 5)

            release_purge.set()
            purge_response = await purge
            release_create.set()
            return purge_response, await create

    purge_response, create_response = asyncio.run(interleave())

    assert purge_response.status_code == 200, purge_response.text
    assert create_response.status_code == 404, create_response.text
    assert create_response.json()["error"] == "event_not_found"


def test_event_close_and_verdict_leave_one_terminal_submission(admin, client):
    """Close and verdict serialize without leaving a pending submission."""
    party = mod_party(admin, client)
    moderator = _mod(client, party["mod_code"])
    submission = _submit(client, party["riddle_ids"][0], party["evidence_id"])

    async def race():
        start_barrier = asyncio.Barrier(2)
        transport = ASGITransport(app=client.app)
        async with (
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(admin.cookies),
            ) as admin_api,
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(moderator.cookies),
            ) as moderator_api,
        ):
            arm_csrf(admin_api, client.app)
            arm_csrf(moderator_api, client.app)

            async def close_event():
                await start_barrier.wait()
                return await admin_api.post(
                    f"/api/admin/events/{party['event_id']}/close"
                )

            async def issue_verdict():
                await start_barrier.wait()
                return await moderator_api.post(
                    f"/api/mod/queue/{submission['id']}/verdict",
                    json={"verdict": "verified"},
                )

            return await asyncio.gather(close_event(), issue_verdict())

    try:
        close_response, verdict_response = asyncio.run(race())
    finally:
        moderator.close()

    assert close_response.status_code == 200
    assert verdict_response.status_code in (200, 409)

    conn = client.app.state.db
    event = conn.execute(
        "SELECT status FROM event WHERE id = ?", (party["event_id"],)
    ).fetchone()
    row = conn.execute(
        "SELECT status FROM submission WHERE id = ?", (submission["id"],)
    ).fetchone()
    verdicts = conn.execute(
        "SELECT COUNT(*) FROM verdict WHERE submission_id = ?", (submission["id"],)
    ).fetchone()[0]
    closed_audits = conn.execute(
        "SELECT COUNT(*) FROM audit_event"
        " WHERE event_id = ? AND action = 'event.closed'",
        (party["event_id"],),
    ).fetchone()[0]
    verdict_audits = conn.execute(
        "SELECT COUNT(*) FROM audit_event"
        " WHERE event_id = ? AND action = 'verdict.issued'",
        (party["event_id"],),
    ).fetchone()[0]

    assert event["status"] == "closed"
    assert row["status"] in ("expired", "verified")
    assert (row["status"] == "verified") == (verdicts == 1 == verdict_audits)
    assert closed_audits == 1


def test_sse_player_routing_and_stream_cleanup():
    """Player deltas target one player and disconnects unregister subscribers."""
    loop = asyncio.new_event_loop()
    broker = SseBroker(loop)
    owner = broker.subscribe(
        event_id="event-1", role="player", team_id="team-1", player_id="player-1"
    )
    teammate = broker.subscribe(
        event_id="event-1", role="player", team_id="team-1", player_id="player-2"
    )
    other_event = broker.subscribe(
        event_id="event-2", role="player", team_id="team-1", player_id="player-1"
    )

    async def read_one_frame():
        stream = _stream(broker, owner)
        broker.publish(
            "event-1",
            "strike",
            {"level": 1},
            to="player",
            player_id="player-1",
        )
        frame = await asyncio.wait_for(anext(stream), timeout=1)
        await stream.aclose()
        return frame

    try:
        frame = loop.run_until_complete(read_one_frame())
    finally:
        loop.close()

    assert frame == b'event: strike\ndata: {"level": 1}\n\n'
    assert owner not in broker._subscribers
    assert teammate.queue.empty()
    assert other_event.queue.empty()


def test_migrated_database_preserves_rows_and_constraints(tmp_path):
    """A copied database can rerun migrations without losing its schema."""
    source_path = tmp_path / "source.db"
    source = db_module.connect(source_path)
    assert db_module.apply_migrations(source) == [1]
    source.execute(
        "INSERT INTO event (id, name, join_code, mod_code, created_at)"
        " VALUES ('event-1', 'Persisted Party', 'JOIN1', 'MOD1', 1)"
    )
    source.commit()
    source.close()

    migrated_path = tmp_path / "migrated.db"
    shutil.copy2(source_path, migrated_path)
    migrated = db_module.connect(migrated_path)
    assert db_module.apply_migrations(migrated) == []
    assert migrated.execute("SELECT name FROM event WHERE id = 'event-1'").fetchone()[
        0
    ] == ("Persisted Party")
    assert migrated.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(
            "INSERT INTO team (id, event_id, created_at)"
            " VALUES ('team-1', 'missing-event', 1)"
        )
    migrated.close()


def test_startup_requires_admin_credentials(monkeypatch, tmp_path):
    """The factory refuses to build an app without an admin credential pair."""
    monkeypatch.delenv("ARKHAM_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ARKHAM_ADMIN_PASSWORD_HASH", raising=False)

    with pytest.raises(RuntimeError, match="Admin credentials not configured"):
        create_app(tmp_path / "missing-admin.db")


def test_cross_event_and_cross_team_reads_hide_foreign_data(admin, client):
    """Player and moderator reads stay inside their event and team scope."""
    first = mod_party(admin, client)
    first_mod = _mod(client, first["mod_code"])
    first_submission = _submit(client, first["riddle_ids"][0], first["evidence_id"])

    second_event = admin.post("/api/admin/events", json={"name": "Second Party"}).json()
    second_riddle = admin.post(
        f"/api/admin/events/{second_event['id']}/riddles",
        json={"text": "Second clue", "sort_order": 1},
    ).json()
    admin.post(f"/api/admin/events/{second_event['id']}/open")
    second_player = arm_csrf(TestClient(client.app))
    second_join = second_player.post(
        f"/api/join/{second_event['join_code']}",
        json={"display_name": "Robin"},
    ).json()
    second_evidence = second_player.post(
        "/api/evidence", files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")}
    ).json()
    second_mod = _mod(client, second_event["mod_code"])

    assert (
        second_player.get(f"/api/evidence/{first['evidence_id']}/photo").status_code
        == 404
    )
    assert all(
        item["id"] != first["evidence_id"]
        for item in second_player.get("/api/evidence").json()
    )
    foreign_submit = second_player.post(
        "/api/submissions",
        json={
            "riddle_id": second_riddle["id"],
            "evidence_item_id": first["evidence_id"],
        },
    )
    assert foreign_submit.status_code == 404
    assert (
        second_mod.get(f"/api/mod/evidence/{first['evidence_id']}/photo").status_code
        == 404
    )
    assert second_mod.get(f"/api/mod/players/{first['player_id']}").status_code == 404
    assert all(
        item["id"] != first_submission["id"]
        for item in second_mod.get("/api/mod/queue").json()
    )

    conn = client.app.state.db
    first_audit_ids = {
        row["id"]
        for row in conn.execute(
            "SELECT id FROM audit_event WHERE event_id = ?", (first["event_id"],)
        ).fetchall()
    }
    second_audit = second_mod.get("/api/mod/audit").json()
    assert second_audit
    assert first_audit_ids.isdisjoint(row["id"] for row in second_audit)

    # The reciprocal moderator boundary is checked too: event A cannot read
    # event B's photo, player history, queue item, or audit timeline.
    assert (
        first_mod.get(f"/api/mod/evidence/{second_evidence['id']}/photo").status_code
        == 404
    )
    assert (
        first_mod.get(f"/api/mod/players/{second_join['player']['id']}").status_code
        == 404
    )
    assert all(
        item["id"] != second_evidence["id"]
        for item in first_mod.get("/api/mod/queue").json()
    )
    first_mod_audit = first_mod.get("/api/mod/audit").json()
    assert all(row["id"] in first_audit_ids for row in first_mod_audit)
    second_player.close()
    first_mod.close()
    second_mod.close()


def test_upload_after_a_strike_commits_is_rejected(admin, client, monkeypatch):
    """A strike committed after the upload's reader check must still block
    the write (ADR 0013).

    The upload reads the restriction on the reader, then does its slow
    Pillow work, then re-reads the restriction on the writer before the
    INSERT. The reader call here commits a level-3 strike behind it, so
    the writer re-check is the only gate left standing."""
    party = mod_party(admin, client)
    submission = _submit(client, party["riddle_ids"][0], party["evidence_id"])
    moderator = _mod(client, party["mod_code"])
    conn = client.app.state.db
    moderator_id = conn.execute(
        "SELECT id FROM moderator WHERE event_id = ?", (party["event_id"],)
    ).fetchone()["id"]

    real_derive = evidence_module.derive_restriction

    def strike_after_the_reader_read(c, player_id):
        restriction = real_derive(c, player_id)
        if c is client.app.state.read_db:
            conn.execute(
                "INSERT INTO strike (id, player_id, event_id, level,"
                " submission_id, issued_by, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "strike-banned",
                    party["player_id"],
                    party["event_id"],
                    3,
                    submission["id"],
                    moderator_id,
                    int(time.time()),
                ),
            )
            conn.commit()
        return restriction

    monkeypatch.setattr(
        evidence_module, "derive_restriction", strike_after_the_reader_read
    )

    try:
        response = client.post(
            "/api/evidence", files={"photo": ("c.jpg", make_jpeg(), "image/jpeg")}
        )
    finally:
        moderator.close()

    assert response.status_code == 403, response.text
    assert response.json()["error"] == "upload_restricted"
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM evidence_item WHERE uploaded_by = ?",
            (party["player_id"],),
        ).fetchone()[0]
        == 1
    )


def _join_after_the_event_vanishes(client, monkeypatch, path, payload, event_id):
    """Fire a join that reads the event, delete the event before the join's
    writer transaction runs, and return the response.

    The join's reader read happens before it parks on the writer lock, so
    holding that lock from this thread pins the stale snapshot while the
    event row goes away (a purge that committed after the read). Without
    the writer-side re-check the dependent INSERT fails its event foreign
    key and surfaces as a server error."""
    observed = _ObservedLock(client.app.state.db_lock)
    monkeypatch.setattr(client.app.state, "db_lock", observed)
    observed.__enter__()
    released = False

    def release():
        nonlocal released
        if not released:
            released = True
            observed.__exit__(None, None, None)

    async def interleave():
        transport = ASGITransport(app=client.app)
        async with AsyncClient(transport=transport, base_url="http://test") as joiner:
            arm_csrf(joiner, client.app)
            join = asyncio.create_task(joiner.post(path, json=payload))
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 5
            while observed.waiting == 0 and loop.time() < deadline:
                await asyncio.sleep(0.01)
            assert observed.waiting >= 1, "the join never parked on the writer"
            # A purge deletes the event's audit rows first (no cascade);
            # the join read the event while it was still open.
            db = client.app.state.db
            db.execute("DELETE FROM audit_event WHERE event_id = ?", (event_id,))
            db.execute("DELETE FROM event WHERE id = ?", (event_id,))
            db.commit()
            release()
            return await join

    try:
        return asyncio.run(interleave())
    finally:
        release()


def test_player_join_after_the_event_is_purged_is_not_a_500(admin, client, monkeypatch):
    """A player join that read an open event re-checks it on the writer, so
    a purge that commits first answers 404 instead of a foreign-key 500."""
    party = mod_party(admin, client)
    response = _join_after_the_event_vanishes(
        client,
        monkeypatch,
        f"/api/join/{party['join_code']}",
        {"display_name": "Robin"},
        party["event_id"],
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"] == "bad_join_code"


def test_mod_join_after_the_event_is_purged_is_not_a_500(admin, client, monkeypatch):
    """The moderator join shares the player join's re-check: a purged event
    answers 404 rather than failing the moderator INSERT's foreign key."""
    party = mod_party(admin, client)
    response = _join_after_the_event_vanishes(
        client,
        monkeypatch,
        f"/api/mod/join/{party['mod_code']}",
        {},
        party["event_id"],
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"] == "bad_mod_code"


def test_revoke_after_a_concurrent_redemption_is_closed(admin, client, monkeypatch):
    """A revoke that read an open invite must not stamp a token that was
    redeemed before its transaction (ADR 0013).

    The redemption commits while the revoke is parked on the writer, so
    the revoke's conditional UPDATE finds the invite closed and answers
    409 rather than writing a revoked_at onto a used token."""
    party = _party(admin, client)
    batman = party["players"]["Batman"]["client"]
    token = _invite(batman)

    redeemed_written = threading.Event()
    release = threading.Event()
    real_log_action = teams.log_action

    def blocking_log_action(*args, **kwargs):
        if kwargs.get("action") == Action.TEAM_INVITE_REDEEMED:
            redeemed_written.set()
            assert release.wait(timeout=5), "redemption was never released"
        return real_log_action(*args, **kwargs)

    monkeypatch.setattr(teams, "log_action", blocking_log_action)

    async def interleave():
        transport = ASGITransport(app=client.app)
        async with (
            AsyncClient(transport=transport, base_url="http://test") as robin,
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(batman.cookies),
            ) as owner,
        ):
            arm_csrf(robin, client.app)
            arm_csrf(owner, client.app)
            redeem = asyncio.create_task(
                robin.post(
                    f"/api/team/invites/{token}/redeem",
                    json={"display_name": "Robin"},
                )
            )
            assert await asyncio.to_thread(redeemed_written.wait, 5)

            revoke = asyncio.create_task(
                owner.post(f"/api/team/invites/{token}/revoke")
            )
            await asyncio.sleep(0.3)
            assert not revoke.done(), "revoke did not wait for the writer"

            release.set()
            return await redeem, await revoke

    redeem_response, revoke_response = asyncio.run(interleave())

    assert redeem_response.status_code == 201, redeem_response.text
    assert revoke_response.status_code == 409, revoke_response.text
    assert revoke_response.json()["error"] == "invite_closed"
    invite = client.app.state.db.execute(
        "SELECT redeemed_by, revoked_at FROM team_invite WHERE token = ?", (token,)
    ).fetchone()
    assert invite["redeemed_by"] is not None
    assert invite["revoked_at"] is None


def test_purge_after_a_concurrent_purge_is_not_a_second_delete(
    admin, client, monkeypatch
):
    """A second purge that read a closed event re-checks it on the writer:
    the first purge commits while the second is parked, and the second
    answers 404 instead of logging an audit row for a deleted event (whose
    foreign key would fail, surfacing as a 500)."""
    event = admin.post("/api/admin/events", json={"name": "Double Purge"}).json()
    assert (
        admin.post(
            f"/api/admin/events/{event['id']}/riddles",
            json={"text": "Q1", "sort_order": 1},
        ).status_code
        == 201
    )
    assert admin.post(f"/api/admin/events/{event['id']}/open").status_code == 200
    assert admin.post(f"/api/admin/events/{event['id']}/close").status_code == 200

    purged_written = threading.Event()
    release = threading.Event()
    real_log_action = events.log_action

    def blocking_log_action(*args, **kwargs):
        if kwargs.get("action") == Action.EVENT_PURGED:
            purged_written.set()
            assert release.wait(timeout=5), "purge was never released"
        return real_log_action(*args, **kwargs)

    monkeypatch.setattr(events, "log_action", blocking_log_action)

    async def interleave():
        transport = ASGITransport(app=client.app)
        cookies = dict(admin.cookies)
        async with (
            AsyncClient(
                transport=transport, base_url="http://test", cookies=cookies
            ) as first,
            AsyncClient(
                transport=transport, base_url="http://test", cookies=cookies
            ) as second,
        ):
            arm_csrf(first, client.app)
            arm_csrf(second, client.app)
            purge_one = asyncio.create_task(
                first.post(
                    f"/api/admin/events/{event['id']}/purge",
                    json={"confirm": event["name"]},
                )
            )
            assert await asyncio.to_thread(purged_written.wait, 5)

            purge_two = asyncio.create_task(
                second.post(
                    f"/api/admin/events/{event['id']}/purge",
                    json={"confirm": event["name"]},
                )
            )
            await asyncio.sleep(0.3)
            assert not purge_two.done(), "second purge did not wait for the writer"

            release.set()
            return await purge_one, await purge_two

    first_response, second_response = asyncio.run(interleave())

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 404, second_response.text
    assert second_response.json()["error"] == "event_not_found"


def test_resolve_flag_after_a_concurrent_resolve_is_not_found(
    admin, client, monkeypatch
):
    """Two moderators resolving one open flag: the second re-checks the
    flag on the writer and answers 404, so the audit log holds exactly one
    resolution (ADR 0013)."""
    party = mod_party(admin, client)
    other = arm_csrf(TestClient(client.app))
    other.post(f"/api/join/{party['join_code']}", json={"display_name": "Robin"})
    flagged = other.post(
        "/api/evidence", files={"photo": ("b.jpg", make_jpeg(), "image/jpeg")}
    ).json()["id"]

    mod_a = _mod(client, party["mod_code"])
    mod_b = _mod(client, party["mod_code"])

    resolved_written = threading.Event()
    release = threading.Event()
    real_log_action = mod.log_action

    def blocking_log_action(*args, **kwargs):
        if kwargs.get("action") == Action.DUPLICATE_FLAG_RESOLVED:
            resolved_written.set()
            assert release.wait(timeout=5), "resolve was never released"
        return real_log_action(*args, **kwargs)

    monkeypatch.setattr(mod, "log_action", blocking_log_action)

    async def interleave():
        transport = ASGITransport(app=client.app)
        async with (
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(mod_a.cookies),
            ) as api_a,
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(mod_b.cookies),
            ) as api_b,
        ):
            arm_csrf(api_a, client.app)
            arm_csrf(api_b, client.app)
            first = asyncio.create_task(
                api_a.post(
                    f"/api/mod/flags/{flagged}/resolve",
                    json={"resolution": "cleared"},
                )
            )
            assert await asyncio.to_thread(resolved_written.wait, 5)

            second = asyncio.create_task(
                api_b.post(
                    f"/api/mod/flags/{flagged}/resolve",
                    json={"resolution": "cleared"},
                )
            )
            await asyncio.sleep(0.3)
            assert not second.done(), "second resolve did not wait for the writer"

            release.set()
            return await first, await second

    try:
        first_response, second_response = asyncio.run(interleave())
    finally:
        mod_a.close()
        mod_b.close()
        other.close()

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 404, second_response.text
    assert (
        client.app.state.db.execute(
            "SELECT COUNT(*) FROM audit_event WHERE action = 'duplicate_flag.resolved'"
        ).fetchone()[0]
        == 1
    )


def test_remove_member_after_a_concurrent_remove_is_not_found(
    admin, client, monkeypatch
):
    """Two moderators removing one player: the second re-checks the
    player's team on the writer and answers 404, so only one parking team
    and one audit row are created (ADR 0013)."""
    party = mod_party(admin, client)
    moderator_a = _mod(client, party["mod_code"])
    moderator_b = _mod(client, party["mod_code"])
    team_id = client.app.state.db.execute(
        "SELECT team_id FROM player WHERE id = ?", (party["player_id"],)
    ).fetchone()["team_id"]

    removed_written = threading.Event()
    release = threading.Event()
    real_log_action = mod.log_action

    def blocking_log_action(*args, **kwargs):
        if kwargs.get("action") == Action.TEAM_MEMBER_REMOVED:
            removed_written.set()
            assert release.wait(timeout=5), "remove was never released"
        return real_log_action(*args, **kwargs)

    monkeypatch.setattr(mod, "log_action", blocking_log_action)

    async def interleave():
        transport = ASGITransport(app=client.app)
        async with (
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(moderator_a.cookies),
            ) as api_a,
            AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=dict(moderator_b.cookies),
            ) as api_b,
        ):
            arm_csrf(api_a, client.app)
            arm_csrf(api_b, client.app)
            first = asyncio.create_task(
                api_a.post(f"/api/mod/teams/{team_id}/remove/{party['player_id']}")
            )
            assert await asyncio.to_thread(removed_written.wait, 5)

            second = asyncio.create_task(
                api_b.post(f"/api/mod/teams/{team_id}/remove/{party['player_id']}")
            )
            await asyncio.sleep(0.3)
            assert not second.done(), "second remove did not wait for the writer"

            release.set()
            return await first, await second

    try:
        first_response, second_response = asyncio.run(interleave())
    finally:
        moderator_a.close()
        moderator_b.close()

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 404, second_response.text
    conn = client.app.state.db
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM audit_event WHERE action = 'team.member_removed'"
        ).fetchone()[0]
        == 1
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM team WHERE event_id = ?", (party["event_id"],)
        ).fetchone()[0]
        == 2
    )


def test_notice_ack_derives_the_pending_strike_on_the_writer(
    admin, client, monkeypatch
):
    """The ack must derive its pending strike in the same transaction that
    writes the acknowledgement (ADR 0013): a reader read could name a
    strike that a concurrent reversal had already cleared."""
    party = mod_party(admin, client)
    submission = _submit(client, party["riddle_ids"][0], party["evidence_id"])
    moderator = _mod(client, party["mod_code"])
    conn = client.app.state.db
    moderator_id = conn.execute(
        "SELECT id FROM moderator WHERE event_id = ?", (party["event_id"],)
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO strike (id, player_id, event_id, level, submission_id,"
        " issued_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "strike-warned",
            party["player_id"],
            party["event_id"],
            1,
            submission["id"],
            moderator_id,
            int(time.time()),
        ),
    )
    conn.commit()

    seen_on = []
    real_derive = players.derive_restriction

    def recording_derive(c, player_id):
        seen_on.append(c is conn)
        return real_derive(c, player_id)

    monkeypatch.setattr(players, "derive_restriction", recording_derive)

    try:
        response = client.post("/api/me/notice-ack")
    finally:
        moderator.close()

    assert response.status_code == 200, response.text
    assert seen_on == [True], "the ack derived the pending strike off the writer"
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM audit_event WHERE action = 'notice.acknowledged'"
        ).fetchone()[0]
        == 1
    )


def test_rename_no_op_is_decided_after_a_peer_rename_commits(
    admin, client, monkeypatch
):
    """The rename no-op must be decided under the writer lock (ADR 0013):
    a peer rename that commits while this request waits on the lock has to
    be visible to the decision. Two requests ask for the same name; the
    second must see the first's commit and no-op, not write a second
    rename row off a stale reader snapshot."""
    party = _party(admin, client)
    batman = party["players"]["Batman"]["client"]
    team_id = party["players"]["Batman"]["team_id"]
    conn = client.app.state.db

    assert batman.post("/api/team/rename", json={"name": "Alpha"}).status_code == 200
    renames_before = conn.execute(
        "SELECT COUNT(*) FROM audit_event WHERE action = 'team.renamed'"
    ).fetchone()[0]

    renamed_written = threading.Event()
    release = threading.Event()
    real_log_action = teams.log_action

    def blocking_log_action(*args, **kwargs):
        if kwargs.get("action") == Action.TEAM_RENAMED:
            renamed_written.set()
            assert release.wait(timeout=5), "rename was never released"
        return real_log_action(*args, **kwargs)

    monkeypatch.setattr(teams, "log_action", blocking_log_action)

    async def interleave():
        transport = ASGITransport(app=client.app)
        cookies = dict(batman.cookies)
        async with (
            AsyncClient(
                transport=transport, base_url="http://test", cookies=cookies
            ) as api_a,
            AsyncClient(
                transport=transport, base_url="http://test", cookies=cookies
            ) as api_b,
        ):
            arm_csrf(api_a, client.app)
            arm_csrf(api_b, client.app)
            first = asyncio.create_task(
                api_a.post("/api/team/rename", json={"name": "Beta"})
            )
            assert await asyncio.to_thread(renamed_written.wait, 5)

            second = asyncio.create_task(
                api_b.post("/api/team/rename", json={"name": "Beta"})
            )
            await asyncio.sleep(0.3)
            assert not second.done(), "second rename did not wait for the writer"

            release.set()
            return await first, await second

    first_response, second_response = asyncio.run(interleave())

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    assert (
        conn.execute("SELECT name FROM team WHERE id = ?", (team_id,)).fetchone()[
            "name"
        ]
        == "Beta"
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM audit_event WHERE action = 'team.renamed'"
        ).fetchone()[0]
        - renames_before
        == 1
    ), "the no-op rename decided off a stale snapshot and logged a second rename"
