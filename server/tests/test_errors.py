"""Error reporting: inert without a DSN, scrubbed with one
(TKT-01M33S2WQF2NZ254EHK0M6S8NJ)."""

from __future__ import annotations

import json

import pytest

from app import errors
from app import logging as app_logging
from app.errors import Scrubber, init_error_reporting

DSN = "https://public-key:secret-key@bugsink.example/1"
JOIN_CODE = "JOIN234"


@pytest.mark.parametrize("dsn", [None, ""])
def test_init_is_inert_without_a_dsn(dsn):
    assert init_error_reporting(dsn) is False


def test_dsn_wires_the_scrubbers(monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(errors.sentry_sdk, "init", lambda **kw: captured.update(kw))

    assert init_error_reporting(DSN) is True

    assert captured["dsn"] == DSN
    assert captured["send_default_pii"] is False
    assert captured["before_send"] is not None
    assert captured["before_breadcrumb"] is not None


def test_request_credentials_never_survive():
    event = {
        "request": {
            "url": f"https://hunt.example/api/join/{JOIN_CODE}?invite=tok123",
            "query_string": "invite=tok123",
            "headers": {"Cookie": "arkham_player=SESSIONVALUE"},
            "cookies": {"arkham_player": "SESSIONVALUE"},
            "data": {"join_code": JOIN_CODE},
            "env": {"SERVER_NAME": "hunt.example"},
        }
    }

    scrubbed = Scrubber().scrub_event(event)
    blob = json.dumps(scrubbed)

    assert JOIN_CODE not in blob
    assert "tok123" not in blob
    assert "SESSIONVALUE" not in blob
    # The route stays readable; only the bearer segment and the query go.
    assert scrubbed["request"]["url"] == (
        "https://hunt.example/api/join/<redacted>?<redacted>"
    )
    for dropped in ("headers", "cookies", "data", "env"):
        assert dropped not in scrubbed["request"]


def test_dsn_secret_and_local_variables_never_serialize():
    event = {
        "extra": {"dsn": DSN, "key": "public-key"},
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [{"vars": {"dsn": DSN, "join_code": JOIN_CODE}}]
                    }
                }
            ]
        },
    }

    blob = json.dumps(Scrubber.for_dsn(DSN).scrub_event(event))

    assert DSN not in blob
    assert "public-key" not in blob
    assert "secret-key" not in blob
    assert JOIN_CODE not in blob


def test_request_id_becomes_a_tag():
    token = app_logging._request_id.set("req-abc123")
    try:
        scrubbed = Scrubber().scrub_event({"message": "boom"})
    finally:
        app_logging._request_id.reset(token)

    assert scrubbed["tags"]["request_id"] == "req-abc123"


def test_breadcrumb_url_and_headers_are_scrubbed():
    crumb = {
        "category": "navigation",
        "data": {
            "url": f"https://hunt.example/m/{JOIN_CODE}",
            "from": "/",
            "headers": {"Cookie": "SESSIONVALUE"},
        },
        "headers": {"Cookie": "SESSIONVALUE"},
    }

    scrubbed = Scrubber().scrub_breadcrumb(crumb)
    blob = json.dumps(scrubbed)

    assert JOIN_CODE not in blob
    assert "SESSIONVALUE" not in blob
    assert "headers" not in scrubbed
    assert "headers" not in scrubbed["data"]


def test_event_embedded_breadcrumbs_are_scrubbed():
    event = {
        "breadcrumbs": {
            "values": [
                {"data": {"url": f"https://hunt.example/api/mod/join/{JOIN_CODE}"}}
            ]
        }
    }

    blob = json.dumps(Scrubber().scrub_event(event))

    assert JOIN_CODE not in blob
