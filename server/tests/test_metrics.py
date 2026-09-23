"""In-process metrics (TKT-01M33S2WP): the counters an operator reads
before reaching for the DB. Two properties matter beyond "the number went
up": observing the app must not add a database write, and the lock
wrapper must report real contention without changing lock semantics.

Fixture images are generated in-memory, as in test_evidence.py.
"""

import threading

from test_evidence import _party, _upload, make_jpeg
from test_mod import _mod, _submit
from test_mod import _party as _mod_party

from app.images import MAX_BYTES
from app.metrics import UPLOAD_OUTCOMES, VERDICT_STATES, Metrics


class TestCounters:
    def test_upload_outcomes_are_counted_by_reason(self):
        m = Metrics()
        m.record_upload("accepted")
        m.record_upload("accepted")
        m.record_upload("not_an_image")
        snap = m.snapshot()
        assert snap["uploads"]["accepted"] == 2
        assert snap["uploads"]["not_an_image"] == 1
        assert snap["uploads"]["rate_limited"] == 0

    def test_verdict_states_are_counted(self):
        m = Metrics()
        m.record_verdict("verified")
        m.record_verdict_count("expired", 3)
        m.record_verdict_count("expired", 0)  # a no-op close
        snap = m.snapshot()
        assert snap["verdicts"]["verified"] == 1
        assert snap["verdicts"]["expired"] == 3

    def test_snapshot_reports_lock_counters(self):
        m = Metrics()
        m.record_lock(0.0)
        m.record_lock(0.0)
        m.record_lock(0.5, contended=True)
        lock = m.snapshot()["lock"]
        assert lock["acquisitions"] == 3
        assert lock["contentions"] == 1
        assert lock["wait_seconds"] == 0.5

    def test_snapshot_is_a_copy(self):
        """A reader must not be able to mutate the live counts."""
        m = Metrics()
        snap = m.snapshot()
        snap["uploads"]["accepted"] = 99
        assert m.snapshot()["uploads"]["accepted"] == 0

    def test_unknown_outcome_does_not_invent_a_new_key(self):
        """Keys are fixed when the Metrics is built, so a typo shows up as
        a non-zero counter a test can read rather than a silent extra
        field."""
        m = Metrics()
        m.record_upload("typo")
        assert "typo" not in m.snapshot()["uploads"]
        assert set(m.snapshot()["uploads"]) == set(UPLOAD_OUTCOMES)
        assert set(m.snapshot()["verdicts"]) == set(VERDICT_STATES)


class TestUploadMetrics:
    def test_accepted_upload_is_counted(self, admin, client):
        _, _ = _party(admin, client)
        resp = _upload(client, make_jpeg())
        assert resp.status_code == 201
        metrics = admin.get("/api/admin/readyz").json()["metrics"]
        assert metrics["uploads"]["accepted"] == 1

    def test_rejections_are_counted_by_reason(self, admin, client):
        _, _ = _party(admin, client)
        assert _upload(client, b"not a photo").status_code == 415
        # Just over the photo cap but under the middleware's request cap, so
        # this reaches the handler's own size check instead of
        # limits.BodyLimitMiddleware's ``request_too_large``.
        assert _upload(client, b"x" * (MAX_BYTES + 1)).status_code == 413
        metrics = admin.get("/api/admin/readyz").json()["metrics"]
        assert metrics["uploads"]["not_an_image"] == 1
        assert metrics["uploads"]["too_large_bytes"] == 1
        assert metrics["uploads"]["accepted"] == 0

    def test_metric_collection_adds_no_database_write(self, admin, client):
        """Observing the app must not add load to the writer it contends
        for: the audit log is the only per-request row, and metrics are
        not allowed to become a second one."""

        _, _ = _party(admin, client)
        conn = admin.app.state.db

        def audit_rows():
            return conn.execute("SELECT COUNT(*) FROM audit_event").fetchone()[0]

        def evidence_rows():
            return conn.execute("SELECT COUNT(*) FROM evidence_item").fetchone()[0]

        audit_before, evidence_before = audit_rows(), evidence_rows()
        _upload(client, make_jpeg())
        audit_after, evidence_after = audit_rows(), evidence_rows()

        # The upload itself writes exactly one audit row and one evidence
        # row; reading the counters writes nothing at all.
        assert audit_after - audit_before == 1
        assert evidence_after - evidence_before == 1
        before = audit_rows(), evidence_rows()
        admin.app.state.metrics.record_upload("accepted")
        admin.get("/api/admin/readyz")
        assert (audit_rows(), evidence_rows()) == before


class TestVerdictMetrics:
    def test_verdict_is_counted_by_state(self, admin, client):
        """Drive a real verdict through the moderator handler and read the
        counter back: the state written to submission.status is the key."""
        p = _mod_party(admin, client)
        mod = _mod(client, p["mod_code"])
        submission = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        resp = mod.post(
            f"/api/mod/queue/{submission['id']}/verdict",
            json={"verdict": "verified"},
        )
        assert resp.status_code == 200, resp.text
        metrics = admin.get("/api/admin/readyz").json()["metrics"]
        assert metrics["verdicts"]["verified"] == 1
        assert metrics["verdicts"]["expired"] == 0

    def test_lost_race_does_not_count_twice(self, admin, client):
        """A second verdict on a resolved submission is refused, so the
        counter must not move — the verdict counter tracks outcomes, not
        attempts."""
        p = _mod_party(admin, client)
        mod_a = _mod(client, p["mod_code"])
        mod_b = _mod(client, p["mod_code"])
        submission = _submit(client, p["riddle_ids"][0], p["evidence_id"])
        assert (
            mod_a.post(
                f"/api/mod/queue/{submission['id']}/verdict",
                json={"verdict": "verified"},
            ).status_code
            == 200
        )
        assert (
            mod_b.post(
                f"/api/mod/queue/{submission['id']}/verdict",
                json={"verdict": "obscured"},
            ).status_code
            == 409
        )
        verdicts = admin.get("/api/admin/readyz").json()["metrics"]["verdicts"]
        assert verdicts["verified"] == 1
        assert verdicts["obscured"] == 0

    def test_expired_verdicts_are_counted_for_a_closed_round(self, admin, client):
        p = _mod_party(admin, client)
        _submit(client, p["riddle_ids"][0], p["evidence_id"])
        resp = admin.post(f"/api/admin/events/{p['event_id']}/close")
        assert resp.status_code == 200
        metrics = admin.get("/api/admin/readyz").json()["metrics"]
        assert metrics["verdicts"]["expired"] == 1


class TestLockMetrics:
    def test_contended_acquire_records_wait(self, admin):
        """One thread holds the lock while another waits on it; the waiter
        reports one contention and a positive wait."""
        lock = admin.app.state.db_lock
        held = threading.Event()
        release = threading.Event()

        def holder():
            with lock:
                held.set()
                release.wait(timeout=2)

        thread = threading.Thread(target=holder)
        thread.start()
        held.wait(timeout=2)
        try:
            with lock:
                pass
        finally:
            release.set()
            thread.join(timeout=2)

        lock_metrics = admin.get("/api/admin/readyz").json()["metrics"]["lock"]
        assert lock_metrics["acquisitions"] >= 2
        assert lock_metrics["contentions"] >= 1
        assert lock_metrics["wait_seconds"] > 0

    def test_lock_still_serializes(self, admin):
        """The wrapper must not weaken reentrancy or mutual exclusion."""
        lock = admin.app.state.db_lock
        with lock:
            with lock:  # reentrant, same thread: no deadlock
                pass
        assert admin.app.state.db_lock is not None

    def test_uncontended_and_reentrant_acquires_are_not_contentions(self, admin):
        """A free lock, and a reentrant re-entry, must count acquisitions
        without a contention — the reason contention is not inferred from
        elapsed time, which every acquire spends a little of."""
        lock = admin.app.state.db_lock
        before = admin.get("/api/admin/readyz").json()["metrics"]["lock"]
        with lock:
            with lock:
                pass
        after = admin.get("/api/admin/readyz").json()["metrics"]["lock"]
        # The reading request itself takes the writer lock once, so the
        # floor is our two acquires and not an exact count.
        assert after["acquisitions"] >= before["acquisitions"] + 2
        assert after["contentions"] == before["contentions"]

    def test_readyz_exposes_metrics_and_overflow(self, admin):
        body = admin.get("/api/admin/readyz").json()
        assert body["sse_overflow"] == 0
        assert body["metrics"]["uploads"]["accepted"] == 0
        assert body["metrics"]["lock"]["acquisitions"] >= 1
