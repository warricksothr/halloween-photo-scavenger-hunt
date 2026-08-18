"""Deployment & ops tests (increment 10).

Two surfaces:
- Event purge: host-only, closed-only, name-confirm, and TOTAL — every
  row and every photo file of the event is gone afterwards, while a
  neighboring event is untouched (the FK cascade map is load-bearing
  here: submission/verdict/strike/audit_event do NOT cascade and are
  deleted explicitly, in order).
- Static SPA serving: hashed assets immutable, shell files no-cache,
  /j//m/ fallback to index.html, unmatched /api paths 404 in JSON.
"""

from fastapi.testclient import TestClient

from app.main import create_app
from app.security import hash_password
from test_evidence import make_jpeg
from test_leaderboard import _multi_party, _upload_and_solve
from test_mod import _mod

ADMIN_USER, ADMIN_PASSWORD = "admin", "pw"


def _app(tmp_path, static_dir=None):
    """The purge tests need the real app factory (the conftest fixtures
    don't exercise static_dir).

    TestClient must be entered as a context manager: the app's state
    (db, admin_config, broker) is populated by the lifespan, which only
    runs on __enter__. A bare TestClient(app) would 500 on the first
    request with AttributeError on app.state."""
    client = TestClient(create_app(
        tmp_path / "api.db",
        admin_config=(ADMIN_USER, hash_password(ADMIN_PASSWORD)),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=static_dir,
    ))
    client.__enter__()
    return client


def _login(client):
    resp = client.post("/api/admin/login",
                       json={"username": ADMIN_USER,
                             "password": ADMIN_PASSWORD})
    assert resp.status_code == 200


def _event_counts(conn, event_id):
    """Row counts for every table the event owns, for assertions."""
    def n(sql, *args):
        return conn.execute(sql, args).fetchone()[0]

    return {
        "event": n("SELECT COUNT(*) FROM event WHERE id = ?", event_id),
        "riddle": n("SELECT COUNT(*) FROM riddle WHERE event_id = ?",
                    event_id),
        "team": n("SELECT COUNT(*) FROM team WHERE event_id = ?",
                  event_id),
        "submission": n(
            "SELECT COUNT(*) FROM submission WHERE riddle_id IN"
            " (SELECT id FROM riddle WHERE event_id = ?)", event_id),
        "verdict": n(
            "SELECT COUNT(*) FROM verdict WHERE submission_id IN"
            " (SELECT s.id FROM submission s JOIN riddle r"
            "  ON r.id = s.riddle_id WHERE r.event_id = ?)", event_id),
        "audit": n("SELECT COUNT(*) FROM audit_event WHERE event_id = ?",
                   event_id),
        "moderator": n("SELECT COUNT(*) FROM moderator WHERE event_id = ?",
                       event_id),
    }


class TestPurge:
    def test_purge_removes_everything_but_other_events(self, tmp_path):
        """The whole night disappears — rows AND photo files — and the
        second event on the same server is untouched."""
        client = _app(tmp_path)
        _login(client)
        p = _multi_party(client, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        batman = p["players"]["Batman"]["client"]
        _upload_and_solve(client, batman, p["riddle_ids"][0], mod)

        # A second, living event that must survive the purge.
        other = client.post("/api/admin/events", json={"name": "Other"}).json()

        # Photo files exist on disk before the purge.
        photos_dir = tmp_path / "photos"
        derivatives = list((photos_dir / "derivatives").iterdir())
        originals = list((photos_dir / "originals").iterdir())
        assert derivatives and originals

        client.post(f"/api/admin/events/{p['event_id']}/close")
        resp = client.post(f"/api/admin/events/{p['event_id']}/purge",
                           json={"confirm": "Standings Party"})
        assert resp.status_code == 200
        assert resp.json()["purged"] == {"submissions": 1, "evidence": 1}

        conn = client.app.state.db
        assert all(v == 0 for v in _event_counts(conn, p["event_id"]).values())
        # The other event is intact.
        assert conn.execute("SELECT COUNT(*) FROM event WHERE id = ?",
                            (other["id"],)).fetchone()[0] == 1
        # Photo files are gone too.
        assert list((photos_dir / "derivatives").iterdir()) == []
        assert list((photos_dir / "originals").iterdir()) == []

    def test_purge_requires_closed_event_and_matching_name(self, tmp_path):
        client = _app(tmp_path)
        _login(client)
        p = _multi_party(client, client, ("Batman",))

        # Open event: purging a live round is not a reachable state.
        resp = client.post(f"/api/admin/events/{p['event_id']}/purge",
                           json={"confirm": "Standings Party"})
        assert resp.status_code == 409
        assert resp.json()["error"] == "event_not_closed"

        client.post(f"/api/admin/events/{p['event_id']}/close")
        # Wrong name: the host must name the thing they're destroying.
        resp = client.post(f"/api/admin/events/{p['event_id']}/purge",
                           json={"confirm": "Not The Name"})
        assert resp.status_code == 409
        assert resp.json()["error"] == "confirm_mismatch"

    def test_purge_is_host_only(self, tmp_path):
        client = _app(tmp_path)
        _login(client)
        p = _multi_party(client, client, ("Batman",))
        mod = _mod(client, p["mod_code"])
        client.post(f"/api/admin/events/{p['event_id']}/close")

        # Moderators manage queues, not events (api.md).
        assert mod.post(f"/api/admin/events/{p['event_id']}/purge",
                        json={"confirm": "Standings Party"}
                        ).status_code == 401
        assert TestClient(client.app).post(
            f"/api/admin/events/{p['event_id']}/purge",
            json={"confirm": "Standings Party"}).status_code == 401


class TestStaticServing:
    def test_spa_fallback_assets_and_api_404(self, tmp_path):
        dist = tmp_path / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<html>shell</html>")
        (dist / "sw.js").write_text("// sw")
        (dist / "assets" / "index-abc123.js").write_text("// bundle")

        client = _app(tmp_path, static_dir=dist)

        # The shell at /, and on the link paths the QR codes encode.
        for path in ("/", "/j/ABC123", "/m/XYZ789", "/some/spa/route"):
            resp = client.get(path)
            assert resp.status_code == 200, path
            assert resp.text == "<html>shell</html>"
            assert resp.headers["cache-control"] == "no-cache"

        # Real files serve with the right cache policy: hashed assets
        # immutable, shell files revalidate.
        asset = client.get("/assets/index-abc123.js")
        assert asset.status_code == 200
        assert "immutable" in asset.headers["cache-control"]
        sw = client.get("/sw.js")
        assert sw.headers["cache-control"] == "no-cache"

        # A real API route still wins over the catch-all…
        assert client.get("/api/health").json()["status"] == "ok"
        # …and an unmatched /api path is a JSON 404, never the shell.
        resp = client.get("/api/nope")
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_path_traversal_falls_back_to_shell(self, tmp_path):
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html>shell</html>")
        secret = tmp_path / "secret.txt"
        secret.write_text("nope")

        client = _app(tmp_path, static_dir=dist)
        # ../ escapes are resolved and refused: the response is the
        # shell (or a 404 from the router), never the file.
        resp = client.get("/../secret.txt")
        assert resp.status_code in (200, 404)
        assert "nope" not in resp.text

    def test_no_dist_means_no_static(self, tmp_path):
        """Dev mode: web/dist doesn't exist → no static mount, / is a
        404 JSON (Vite serves the app on its own port there)."""
        client = _app(tmp_path, static_dir=tmp_path / "nonexistent")
        resp = client.get("/")
        assert resp.status_code == 404
