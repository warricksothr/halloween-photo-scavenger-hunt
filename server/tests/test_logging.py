"""Request logging: one structured line per request, with the bearer codes
redacted out of the path (TKT-01M33S2WJJCKSDJ9T12S5AGFSJ)."""

from __future__ import annotations

import logging
import re

import pytest
from fastapi import Request
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


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/join/ABC234", ("ABC234",)),
        ("/api/mod/join/MOD234/extra", ("MOD234",)),
        ("/api/team/invites/tok123/redeem", ("tok123",)),
        ("/j/ABC234", ("ABC234",)),
        ("/m/MOD234/", ("MOD234",)),
        # The same prefix rules as ``redact_path``: no credential, none back.
        ("/api/leaderboard", ()),
        ("/api/join/", ()),
        ("/api/joinfake/x", ()),
    ],
)
def test_bearer_secrets_returns_the_credential(path, expected):
    assert app_logging.bearer_secrets(path) == expected


def test_request_secrets_collects_the_requests_own_values():
    secrets = app_logging._request_secrets(
        {
            "path": "/api/team/invites/tok123/redeem",
            "query_string": b"code=querysecret",
            "headers": [
                (b"authorization", b"Bearer topsecrettoken"),
                (b"cookie", b"arkham_session=cookiesecret; theme=dark"),
            ],
        }
    )

    assert set(secrets) >= {
        "tok123",
        "querysecret",
        "topsecrettoken",
        "cookiesecret",
    }
    # Below the floor: replacing a short ordinary word would mangle the
    # message it is meant to protect.
    assert "dark" not in secrets
    # Longest first, so a secret containing another cannot leave a fragment.
    assert list(secrets) == sorted(secrets, key=len, reverse=True)


def test_scrub_secrets_replaces_the_longest_first():
    scrubbed = app_logging._scrub_secrets("a abcdef abc", ("abc", "abcdef"))
    assert scrubbed == "a <redacted> <redacted>"


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


def test_body_secrets_reads_json_and_form_values():
    assert set(
        app_logging._body_secrets(
            "application/json",
            b'{"display_name": "Bruce Wayne", "password": "hunter2"}',
        )
    ) == {"Bruce Wayne", "hunter2"}

    assert set(
        app_logging._body_secrets(
            "application/x-www-form-urlencoded", b"code=JOIN234&password=hunter2"
        )
    ) == {"JOIN234", "hunter2"}

    # A repeated field keeps every value, not just the last: the app can
    # read them all through the form's multi-value interface.
    assert set(
        app_logging._body_secrets(
            "application/x-www-form-urlencoded",
            b"password=firstsecret&password=secondsecret",
        )
    ) == {"firstsecret", "secondsecret"}


def test_body_secrets_skips_binary_and_malformed_bodies():
    # A photo upload is not text; mining it would redact noise.
    assert app_logging._body_secrets("image/jpeg", b"\xff\xd8\xff\xe0topsecret") == ()
    # A body that does not parse yields nothing rather than raising.
    assert app_logging._body_secrets("application/json", b"{not json") == ()


def test_unhandled_exception_logs_one_correlated_traceback(tmp_path, caplog):
    """TKT-01M33S2WK: one traceback, tied to the request, without the
    cookie, the Authorization header, or the body.

    The route raises with a value the request carried in each place a
    secret can enter — the path, a header, and the JSON body — so the
    assertions show the scrubber at work, not merely that an unused value
    was left out.
    """
    app = create_app(
        tmp_path / "boom.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )

    @app.post("/api/team/invites/{token}/boom")
    def boom(token: str, request: Request, payload: dict):
        raise RuntimeError(
            f"kaboom token={token} auth={request.headers['authorization']} "
            f"password={payload['password']}"
        )

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
    assert record.exception_type == "RuntimeError"

    text = _rendered(caplog)
    assert "kaboom" in text
    assert "Traceback" in text
    assert app_logging.REDACTED in text
    assert "SUPERSECRETCODE" not in text
    assert "topsecrettoken" not in text
    # The body value the route raised with, and one it did not: the whole
    # JSON body's strings are scrubbed, not just the field named password.
    assert "hunter2" not in text
    assert "Bruce Wayne" not in text


def test_a_truncated_body_drops_the_exception_message(tmp_path, caplog, monkeypatch):
    """The safe path for a body the scrubber could not inspect whole.

    ``_BUFFERED_BODY_BYTES`` is shrunk so a small body exercises it. The
    route raises with a value from a body the scrubber saw only in part,
    so the frames are logged and the message is left out rather than
    logged unscanned.
    """
    monkeypatch.setattr(app_logging, "_BUFFERED_BODY_BYTES", 64)
    app = create_app(
        tmp_path / "truncated.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )

    @app.post("/api/team/invites/{token}/boom")
    def boom(payload: dict):
        raise RuntimeError(f"kaboom password={payload['password']}")

    caplog.set_level(logging.INFO)
    with TestClient(app, raise_server_exceptions=False) as c:
        arm_csrf(c, app)
        caplog.clear()
        resp = c.post(
            "/api/team/invites/SUPERSECRETCODE/boom",
            json={"padding": "x" * 200, "password": "hunter2"},
        )

    assert resp.status_code == 500
    records = [
        r for r in caplog.records if getattr(r, "event", None) == "unhandled_exception"
    ]
    assert len(records) == 1
    assert records[0].exception_type == "RuntimeError"
    assert records[0].message_included is False

    text = _rendered(caplog)
    # The frames survive; the message that could quote the unscanned body
    # does not, and neither does the header ``format_exception`` adds.
    assert ", in boom" in text
    assert "Traceback" not in text
    assert "RuntimeError: kaboom" not in text
    assert "hunter2" not in text


def test_a_repeated_form_value_is_scrubbed(tmp_path, caplog):
    """A form field the app reads past the last is still scrubbed.

    The route raises with the *first* of two fields sharing a name, which
    a dict parse would have dropped from the scrub set.
    """
    app = create_app(
        tmp_path / "duplicate-form.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )

    @app.post("/api/team/invites/{token}/boom")
    async def boom(request: Request):
        form = await request.form()
        raise RuntimeError(f"kaboom password={form.getlist('password')[0]}")

    caplog.set_level(logging.INFO)
    with TestClient(app, raise_server_exceptions=False) as c:
        arm_csrf(c, app)
        caplog.clear()
        resp = c.post(
            "/api/team/invites/SUPERSECRETCODE/boom",
            data={"password": ["firstsecret", "secondsecret"]},
        )

    assert resp.status_code == 500
    text = _rendered(caplog)
    assert "firstsecret" not in text
    assert "secondsecret" not in text


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
