"""Error reporting: inert without a DSN, scrubbed with one
(TKT-01M33S2WQF2NZ254EHK0M6S8NJ)."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app import errors
from app import logging as app_logging
from app.errors import REDACTED, Scrubber, init_error_reporting
from app.main import create_app
from app.security import hash_password

DSN = "https://public-key:secret-key@bugsink.example/1"
JOIN_CODE = "JOIN234"


@pytest.mark.parametrize("dsn", [None, ""])
def test_init_is_inert_without_a_dsn(dsn):
    assert init_error_reporting(dsn) is False


@pytest.mark.parametrize("dsn", ["not a dsn", "ftp://key@host/1", "https://["])
def test_init_is_inert_with_a_malformed_dsn(dsn, caplog):
    """A typo in the DSN is a misconfiguration, not a crash.

    The last case is the one the SDK never sees: an unmatched IPv6
    bracket makes ``urlsplit`` raise before ``sentry_sdk.init`` runs.
    """
    caplog.set_level(logging.WARNING)
    caplog.clear()

    assert init_error_reporting(dsn) is False

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "error_reporting_disabled" in text
    # The reason is recorded; the DSN, which carries a key, is not.
    assert dsn not in text


@pytest.mark.parametrize("dsn", ["not a dsn", "https://["])
def test_malformed_dsn_does_not_stop_the_app(tmp_path, monkeypatch, dsn):
    """The finding: an unguarded ``sentry_sdk.init`` would raise ``BadDsn``
    through ``create_app`` and the server would never start."""
    monkeypatch.setenv("ARKHAM_ERROR_DSN", dsn)

    app = create_app(
        tmp_path / "bad-dsn.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200


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
        "extra": {
            "dsn": DSN,
            "key": "public-key",
            # A tuple serializes as a JSON array, so a secret can ride one.
            "values": (DSN, ("secret-key", "public-key")),
        },
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


def test_secrets_in_mapping_keys_never_serialize():
    """A mapping's keys serialize too, so a secret used as one must go.

    Collapsing two secret keys onto ``<redacted>`` keeps the first and
    drops the second; the point of the test is that neither leaks.
    """
    event = {
        "extra": {
            DSN: {"nested": "kept"},
            "public-key": "kept too",
        },
        "contexts": {"secret-key": {"value": f"prefix {DSN}"}},
    }

    scrubbed = Scrubber.for_dsn(DSN).scrub_event(event)
    blob = json.dumps(scrubbed)

    assert DSN not in blob
    assert "public-key" not in blob
    assert "secret-key" not in blob
    # Both secret keys in ``extra`` collapse onto the same redaction, so
    # the first survives and its value is kept.
    assert scrubbed["extra"][REDACTED]["nested"] == "kept"
    assert scrubbed["contexts"][REDACTED]["value"] == f"prefix {REDACTED}"


def test_replacing_a_secret_does_not_rescan_the_marker():
    """A secret inside ``<redacted>`` must not survive the next pass.

    ``redact`` is a substring of the marker, so a second sequential
    replace would rewrite the marker and keep the key in the output.
    """
    scrubbed = Scrubber(["hunter2", "redact"]).scrub_event(
        {"extra": {"value": "hunter2 redact"}}
    )

    assert scrubbed["extra"]["value"] == f"{REDACTED} {REDACTED}"


def test_request_id_becomes_a_tag():
    token = app_logging._request_id.set("req-abc123")
    try:
        scrubbed = Scrubber().scrub_event({"message": "boom"})
    finally:
        app_logging._request_id.reset(token)

    assert scrubbed["tags"]["request_id"] == "req-abc123"


def test_breadcrumb_url_headers_and_cookies_are_scrubbed():
    crumb = {
        "category": "navigation",
        "url": f"https://hunt.example/m/{JOIN_CODE}?invite=tok123",
        "query_string": "invite=tok123",
        "data": {
            "url": f"https://hunt.example/m/{JOIN_CODE}",
            "from": "/",
            "headers": {"Cookie": "arkham_player=SESSIONVALUE"},
            "cookies": {"arkham_player": "SESSIONVALUE"},
        },
        "headers": {"Cookie": "arkham_player=SESSIONVALUE"},
        "cookies": {"arkham_player": "SESSIONVALUE"},
    }

    scrubbed = Scrubber().scrub_breadcrumb(crumb)
    blob = json.dumps(scrubbed)

    assert JOIN_CODE not in blob
    assert "tok123" not in blob
    # The session is in no scrub set: only the drop removes it.
    assert "SESSIONVALUE" not in blob
    # Both the crumb and its data keep the route but lose the credential
    # and the query.
    assert scrubbed["url"] == "https://hunt.example/m/<redacted>?<redacted>"
    assert scrubbed["query_string"] == "<redacted>"
    for dropped in ("headers", "cookies"):
        assert dropped not in scrubbed
        assert dropped not in scrubbed["data"]


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
