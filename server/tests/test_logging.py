"""Request logging: one structured line per request, with the bearer codes
redacted out of the path (TKT-01M33S2WJJCKSDJ9T12S5AGFSJ)."""

from __future__ import annotations

import logging
import re

import pytest
from fastapi.testclient import TestClient
from support import arm_csrf

from app import logging as app_logging
from app.main import create_app
from app.security import hash_password


def _rendered(caplog) -> str:
    """Format the app's records the way its handler would.

    Scoped to the ``arkham`` logger: the test client's own httpx logger
    writes the full URL, which is a test artifact, not a server sink.
    ``caplog.text`` would also use pytest's formatter, hiding whether a
    field the formatter writes leaks the code.
    """
    formatter = app_logging.JsonFormatter()
    return "\n".join(
        formatter.format(record)
        for record in caplog.records
        if record.name.startswith(app_logging.LOGGER_NAME)
    )


def _request_lines(caplog):
    return [r for r in caplog.records if getattr(r, "event", None) == "request"]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/join/ABC234", "/api/join/<redacted>"),
        ("/api/mod/join/MOD234", "/api/mod/join/<redacted>"),
        ("/api/team/invites/tok123", "/api/team/invites/<redacted>"),
        ("/api/team/invites/tok123/revoke", "/api/team/invites/<redacted>/revoke"),
        ("/api/team/invites/tok123/redeem", "/api/team/invites/<redacted>/redeem"),
        ("/j/ABC234", "/j/<redacted>"),
        ("/m/MOD234", "/m/<redacted>"),
        # A malformed request still reaches the middleware, so the bearer
        # segment has to be redacted by prefix, not by the exact route.
        ("/api/join/ABC234/", "/api/join/<redacted>/"),
        ("/api/mod/join/MOD234/extra", "/api/mod/join/<redacted>/extra"),
        (
            "/api/team/invites/tok123/redeem/",
            "/api/team/invites/<redacted>/redeem/",
        ),
        ("/api/team/invites/tok123/unknown", "/api/team/invites/<redacted>/unknown"),
        ("/j/ABC234/", "/j/<redacted>/"),
        # No credential, and a prefix must end at a path boundary.
        ("/api/join/", "/api/join/"),
        ("/api/joinfake/x", "/api/joinfake/x"),
        ("/api/leaderboard", "/api/leaderboard"),
        ("/api/team/invites", "/api/team/invites"),
        ("/api/events/ev1", "/api/events/ev1"),
    ],
)
def test_redact_path(path, expected):
    assert app_logging.redact_path(path) == expected


def test_every_request_logs_one_structured_line(client, caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()

    resp = client.get("/api/health")

    assert resp.status_code == 200
    lines = _request_lines(caplog)
    assert len(lines) == 1
    line = lines[0]
    assert line.method == "GET"
    assert line.path == "/api/health"
    assert line.status == 200
    assert line.duration_ms >= 0
    assert line.request_id
    assert resp.headers["X-Request-ID"] == line.request_id


def test_join_code_never_reaches_the_logs(admin, caplog):
    created = admin.post("/api/admin/events", json={"name": "Redaction Party"})
    join_code = created.json()["join_code"]

    caplog.set_level(logging.INFO)
    caplog.clear()
    joined = admin.post(f"/api/join/{join_code}", json={"display_name": "Bruce Wayne"})

    assert joined.status_code == 201
    text = _rendered(caplog)
    assert join_code not in text
    assert f"/api/join/{app_logging.REDACTED}" in text


def test_trailing_slash_join_code_never_reaches_the_logs(client, caplog):
    """A path the router would redirect or 404 still passes the middleware."""
    caplog.set_level(logging.INFO)
    caplog.clear()

    client.post("/api/join/SECRETJOIN42/", json={"display_name": "Bruce Wayne"})

    text = _rendered(caplog)
    assert "SECRETJOIN42" not in text
    assert f"/api/join/{app_logging.REDACTED}" in text


def test_unhandled_error_still_echoes_the_request_id(tmp_path, caplog):
    """ServerErrorMiddleware builds the 500 outside this middleware, so the
    id has to reach the response through the app's exception handler."""
    app = create_app(
        tmp_path / "boom.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )

    @app.get("/api/boom")
    def boom():
        raise RuntimeError("kaboom")

    caplog.set_level(logging.INFO)
    with TestClient(app, raise_server_exceptions=False) as c:
        caplog.clear()
        resp = c.get("/api/boom")

    assert resp.status_code == 500
    assert resp.headers.get(app_logging.REQUEST_ID_HEADER)
    line = _request_lines(caplog)[-1]
    assert line.status == 500
    assert line.request_id == resp.headers[app_logging.REQUEST_ID_HEADER]


def test_unhandled_exception_logs_one_correlated_traceback(tmp_path, caplog):
    """TKT-01M33S2WK: one traceback, tied to the request, without the
    cookie, the Authorization header, or the body."""
    app = create_app(
        tmp_path / "boom.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )

    @app.post("/api/team/invites/{token}/boom")
    def boom(token: str, payload: dict):
        raise RuntimeError("kaboom")

    caplog.set_level(logging.INFO)
    with TestClient(app, raise_server_exceptions=False) as c:
        arm_csrf(c, app)
        caplog.clear()
        resp = c.post(
            "/api/team/invites/SUPERSECRETCODE/boom",
            json={"display_name": "Bruce Wayne", "password": "hunter2"},
            headers={"Authorization": "Bearer topsecrettoken"},
        )

    request_id = resp.headers[app_logging.REQUEST_ID_HEADER]
    assert resp.status_code == 500
    assert resp.json() == {
        "error": "internal_error",
        "message": "Something went wrong.",
        "request_id": request_id,
    }

    records = [
        r for r in caplog.records if getattr(r, "event", None) == "unhandled_exception"
    ]
    assert len(records) == 1
    record = records[0]
    assert record.request_id == request_id
    assert record.method == "POST"
    assert record.path == "/api/team/invites/<redacted>/boom"

    text = _rendered(caplog)
    assert "kaboom" in text
    assert "Traceback" in text
    assert "SUPERSECRETCODE" not in text
    assert "hunter2" not in text
    assert "topsecrettoken" not in text


def test_query_string_is_redacted(client, caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()

    client.get("/api/health", params={"secret": "hunter2"})

    text = _rendered(caplog)
    assert "hunter2" not in text
    assert app_logging.REDACTED in text


def test_inbound_request_id_is_echoed(client, caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()

    resp = client.get(
        "/api/health", headers={app_logging.REQUEST_ID_HEADER: "trace-42"}
    )

    assert resp.headers[app_logging.REQUEST_ID_HEADER] == "trace-42"
    assert _request_lines(caplog)[-1].request_id == "trace-42"


def test_unsafe_inbound_request_id_is_replaced(client, caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()

    resp = client.get(
        "/api/health", headers={app_logging.REQUEST_ID_HEADER: "not a token"}
    )

    echoed = resp.headers[app_logging.REQUEST_ID_HEADER]
    assert echoed != "not a token"
    assert re.fullmatch(r"[0-9a-f]{16}", echoed)


def test_uvicorn_access_log_is_dropped(client, caplog):
    """The filter is installed by ``create_app``; the fixture builds one."""
    caplog.set_level(logging.INFO)
    caplog.clear()

    logging.getLogger("uvicorn.access").info(
        '%s - "%s %s HTTP/%s" %d', "1.2.3.4", "POST", "/api/join/ABC234", "1.1", 201
    )

    assert not [r for r in caplog.records if r.name == "uvicorn.access"]
