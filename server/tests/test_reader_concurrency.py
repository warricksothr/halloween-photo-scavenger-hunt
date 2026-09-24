"""The reader connection under concurrent requests (ADR 0030).

Every handler SELECT goes through one reader connection, and sync handlers
and dependencies run on the threadpool. Two threads stepping statements on
one sqlite3 connection at once corrupt each other: Python's statement cache
hands both threads the same prepared statement for the same SQL, so one
thread's execute resets the statement the other is reading. The symptom
was a moderator photo answering 500 (``InterfaceError: bad parameter or
other API misuse``) or 401 (the session row read back as missing).
"""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

from httpx2 import ASGITransport, AsyncClient
from support import arm_csrf
from test_mod import _mod
from test_mod import _party as mod_party

from app import db as db_module

THREADS = 16
ROUNDS = 200


def test_reader_serves_concurrent_threads_the_same_statement(client):
    """Many threads run the same SQL on the reader at once, which is what
    every request's auth lookup does. Each must get its own complete
    result; none may raise."""
    request = SimpleNamespace(app=client.app)
    expected = [
        tuple(row)
        for row in db_module.reader(request)
        .execute("SELECT version FROM schema_migrations WHERE version >= ?", (1,))
        .fetchall()
    ]
    assert expected, "the fixture database has no migrations recorded"
    start = threading.Barrier(THREADS)
    failures: list[str] = []

    def hammer() -> None:
        start.wait()
        for _ in range(ROUNDS):
            try:
                rows = (
                    db_module.reader(request)
                    .execute(
                        "SELECT version FROM schema_migrations WHERE version >= ?",
                        (1,),
                    )
                    .fetchall()
                )
                got = [tuple(row) for row in rows]
            except Exception as exc:  # noqa: BLE001 - the failure is the finding
                failures.append(f"{type(exc).__name__}: {exc}")
                return
            if got != expected:
                failures.append(f"wrong rows: {got}")
                return

    workers = [threading.Thread(target=hammer) for _ in range(THREADS)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
    assert failures == []


def test_concurrent_moderator_requests_all_authenticate(admin, client):
    """The console's first load: the queue and every thumbnail at once, on
    one moderator session. Each request authenticates on the reader, so a
    race there shows up as a 401 or a 500 for a valid cookie."""
    party = mod_party(admin, client)
    submitted = client.post(
        "/api/submissions",
        json={
            "riddle_id": party["riddle_ids"][0],
            "evidence_item_id": party["evidence_id"],
        },
    )
    assert submitted.status_code == 201, submitted.text
    moderator = _mod(client, party["mod_code"])
    photo = f"/api/mod/evidence/{party['evidence_id']}/photo"

    async def burst():
        async with AsyncClient(
            transport=ASGITransport(app=client.app),
            base_url="http://test",
            cookies=dict(moderator.cookies),
        ) as api:
            arm_csrf(api, client.app)
            paths = ["/api/mod/queue", "/api/mod/state", photo] * 20
            return await asyncio.gather(*(api.get(path) for path in paths))

    try:
        responses = asyncio.run(burst())
    finally:
        moderator.close()

    statuses = sorted({(r.request.url.path, r.status_code) for r in responses})
    assert all(code == 200 for _, code in statuses), statuses
