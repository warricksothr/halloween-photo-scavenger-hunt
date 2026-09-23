"""Error/trace reporting: inert without a DSN; scrubbers keep credentials
out (TKT-01M35T4X7NSYTE036FN9E159XR, ADR 0018)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app import errors
from app import logging as app_logging
from app.main import create_app
from app.security import hash_password

DSN = "https://publickey@glitchtip.nulloctet.com/1"


class FakeTransport(Transport):
    """Collects envelopes instead of posting them (no network in tests)."""

    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list = []

    def capture_envelope(self, envelope) -> None:
        self.envelopes.append(envelope)


@pytest.fixture(autouse=True)
def _isolate_client():
    """A Sentry client is process-global; do not leak one between tests."""
    errors.sentry_sdk.init(dsn="")
    yield
    errors.sentry_sdk.get_client().close(timeout=0)
    errors.sentry_sdk.init(dsn="")


def _config(**overrides) -> errors.ErrorConfig:
    values = {"dsn": DSN, "traces_sample_rate": 0.0}
    values.update(overrides)
    return errors.ErrorConfig(**values)


def _send(client, transport) -> list:
    client.flush()
    return transport.envelopes


def test_from_env_is_none_without_a_dsn():
    assert errors.ErrorConfig.from_env({}) is None
    assert errors.ErrorConfig.from_env({errors.DSN_ENV: "  "}) is None


def test_from_env_reads_the_optional_fields():
    config = errors.ErrorConfig.from_env(
        {
            errors.DSN_ENV: DSN,
            errors.TRACES_SAMPLE_RATE_ENV: "0.25",
            errors.ENVIRONMENT_ENV: "production",
            errors.RELEASE_ENV: "abc123",
        }
    )
    assert config is not None
    assert config.dsn == DSN
    assert config.traces_sample_rate == 0.25
    assert config.environment == "production"
    assert config.release == "abc123"


@pytest.mark.parametrize("raw", ["", "nope", "-1", "2", "1.5"])
def test_sample_rate_falls_back_when_unusable(raw):
    env = {errors.DSN_ENV: DSN, errors.TRACES_SAMPLE_RATE_ENV: raw}
    config = errors.ErrorConfig.from_env(env)
    assert config is not None
    assert config.traces_sample_rate == errors.DEFAULT_TRACES_SAMPLE_RATE


def test_init_is_inert_without_a_dsn():
    assert errors.init_error_reporting(errors.ErrorConfig.from_env({})) is False
    assert errors.init_error_reporting(None) is False
    assert errors.init_error_reporting("") is False


@pytest.mark.parametrize("dsn", ["not a dsn", "ftp://key@host/1", "https://["])
def test_init_is_inert_with_a_malformed_dsn(dsn, caplog):
    """A typo in the DSN is a misconfiguration, not a crash.

    The last case is the one the SDK never sees: an unmatched IPv6
    bracket makes ``urlsplit`` raise before ``sentry_sdk.init`` runs.
    """
    caplog.set_level(logging.WARNING)
    caplog.clear()

    assert errors.init_error_reporting(dsn) is False

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "error_reporting_disabled" in text
    # The reason is recorded; the DSN, which carries a key, is not.
    assert dsn not in text


@pytest.mark.parametrize("dsn", ["not a dsn", "https://["])
def test_malformed_dsn_does_not_stop_the_app(tmp_path, monkeypatch, dsn):
    """A malformed DSN must not raise ``BadDsn`` through ``create_app``."""
    monkeypatch.setenv(errors.DSN_ENV, dsn)

    app = create_app(
        tmp_path / "bad-dsn.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200


def test_init_reports_when_configured():
    transport = FakeTransport()
    assert errors.init_error_reporting(_config(), transport=transport) is True


def test_dsn_wires_the_scrubbers(monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(errors.sentry_sdk, "init", lambda **kw: captured.update(kw))

    assert errors.init_error_reporting(_config()) is True

    assert captured["dsn"] == DSN
    assert captured["send_default_pii"] is False
    assert captured["before_send"] is not None
    assert captured["before_breadcrumb"] is not None
    assert captured["before_send_transaction"] is not None


def test_dsn_secret_and_local_variables_never_serialize():
    """The deep-scrub net removes the DSN's own key and secret anywhere."""
    dsn = "https://public-key:secret-key@bugsink.example/1"
    join_code = "JOIN234"
    event = {
        "extra": {
            "dsn": dsn,
            "key": "public-key",
            # A tuple serializes as a JSON array, so a secret can ride one.
            "values": (dsn, ("secret-key", "public-key")),
        },
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [{"vars": {"dsn": dsn, "join_code": join_code}}]
                    }
                }
            ]
        },
    }

    blob = json.dumps(errors.Scrubber.for_dsn(dsn).scrub_event(event))

    assert dsn not in blob
    assert "public-key" not in blob
    assert "secret-key" not in blob
    assert join_code not in blob


def test_secrets_in_mapping_keys_never_serialize():
    """A mapping's keys serialize too, so a secret used as one must go."""
    dsn = "https://public-key:secret-key@bugsink.example/1"
    event = {
        "extra": {
            dsn: {"nested": "kept"},
            "public-key": "kept too",
        },
        "contexts": {"secret-key": {"value": f"prefix {dsn}"}},
    }

    scrubbed = errors.Scrubber.for_dsn(dsn).scrub_event(event)
    blob = json.dumps(scrubbed)

    assert dsn not in blob
    assert "public-key" not in blob
    assert "secret-key" not in blob
    # Both secret keys in ``extra`` collapse onto the same redaction, so
    # the first survives and its value is kept.
    assert scrubbed["extra"][errors.REDACTED]["nested"] == "kept"
    assert scrubbed["contexts"][errors.REDACTED]["value"] == (
        f"prefix {errors.REDACTED}"
    )


def test_replacing_a_secret_does_not_rescan_the_marker():
    """A secret inside ``<redacted>`` must not survive the next pass.

    ``redact`` is a substring of the marker, so a second sequential
    replace would rewrite the marker and keep the key in the output.
    """
    scrubbed = errors.Scrubber(["hunter2", "redact"]).scrub_event(
        {"extra": {"value": "hunter2 redact"}}
    )

    assert scrubbed["extra"]["value"] == f"{errors.REDACTED} {errors.REDACTED}"


def test_secrets_in_a_set_never_serialize():
    """A set is not JSON, but the SDK normalizes one to an array."""
    dsn = "https://public-key:secret-key@bugsink.example/1"
    event = {"extra": {"tags": {dsn, "public-key"}}}

    scrubbed = errors.Scrubber.for_dsn(dsn).scrub_event(event)
    blob = json.dumps(scrubbed)

    assert dsn not in blob
    assert "public-key" not in blob
    assert scrubbed["extra"]["tags"] == [errors.REDACTED, errors.REDACTED]


def test_request_id_becomes_a_tag_on_a_bare_scrubber():
    token = app_logging._request_id.set("req-abc123")
    try:
        scrubbed = errors.Scrubber().scrub_event({"message": "boom"})
    finally:
        app_logging._request_id.reset(token)

    assert scrubbed["tags"]["request_id"] == "req-abc123"


def test_a_malformed_url_is_replaced_not_raised_on():
    """``urlsplit`` raises on ``https://[``; the hooks must not."""
    event = {
        "request": {"url": "https://["},
        "breadcrumbs": {"values": [{"data": {"url": "https://["}}]},
    }

    scrubbed = errors.Scrubber().scrub_event(event)

    assert scrubbed["request"]["url"] == errors.REDACTED
    assert scrubbed["breadcrumbs"]["values"][0]["data"]["url"] == errors.REDACTED

    crumb = errors.Scrubber().scrub_breadcrumb({"data": {"url": "https://["}})

    assert crumb["data"]["url"] == errors.REDACTED


def test_scrubber_breadcrumb_drops_headers_cookies_and_scrubs_url():
    crumb = {
        "category": "navigation",
        "url": "https://hunt.example/m/MODCODE?invite=tok123",
        "query_string": "invite=tok123",
        "data": {
            "url": "https://hunt.example/m/MODCODE",
            "from": "/",
            "headers": {"Cookie": "arkham_player=SESSIONVALUE"},
            "cookies": {"arkham_player": "SESSIONVALUE"},
        },
        "headers": {"Cookie": "arkham_player=SESSIONVALUE"},
        "cookies": {"arkham_player": "SESSIONVALUE"},
    }

    scrubbed = errors.Scrubber().scrub_breadcrumb(crumb)
    blob = json.dumps(scrubbed)

    assert "MODCODE" not in blob
    assert "tok123" not in blob
    # The session is in no scrub set: only the drop removes it.
    assert "SESSIONVALUE" not in blob
    # The crumb keeps its own keys but scrubs the URL and drops the query.
    assert scrubbed["url"] == "https://hunt.example/m/<redacted>"
    for dropped in ("headers", "cookies"):
        assert dropped not in scrubbed
        assert dropped not in scrubbed["data"]


def test_bind_request_id_tags_the_scope():
    transport = FakeTransport()
    errors.init_error_reporting(_config(), transport=transport)
    errors.bind_request_id("req-123")
    errors.sentry_sdk.capture_exception(RuntimeError("boom"))
    envelopes = _send(errors.sentry_sdk.get_client(), transport)
    assert len(envelopes) == 1
    event = envelopes[0].get_event()
    assert event["tags"]["request_id"] == "req-123"


def test_scrub_url_redacts_the_bearer_and_drops_the_query():
    scrubbed = errors.scrub_url("https://hunt.example/api/join/SECRET?token=abc#frag")
    assert scrubbed == "https://hunt.example/api/join/<redacted>"


def test_scrub_url_drops_url_user_info():
    # A DSN is a URL with the key in the user-info, so the authority cannot
    # be kept whole.
    assert (
        errors.scrub_url("https://key@hunt.example/api/state")
        == "https://hunt.example/api/state"
    )
    assert (
        errors.scrub_url("https://user:pass@hunt.example:8443/api/state")
        == "https://hunt.example:8443/api/state"
    )


def test_scrub_url_drops_a_query_on_a_host_only_url():
    assert (
        errors.scrub_url("https://key@hunt.example?token=SECRET")
        == "https://hunt.example"
    )
    assert errors.scrub_url("https://hunt.example#SECRET") == "https://hunt.example"


def test_scrub_text_drops_user_info_in_an_absolute_url():
    assert (
        errors.scrub_text("post to https://key@hunt.example/api/state failed")
        == "post to https://hunt.example/api/state failed"
    )


def test_scrub_text_redacts_path_like_tokens():
    assert errors.scrub_text("GET /api/join/SECRET") == "GET /api/join/<redacted>"
    assert errors.scrub_text("GET /api/state") == "GET /api/state"
    # A credential can arrive inside an absolute URL rather than a bare
    # path; the same scrubber has to reach it.
    assert (
        errors.scrub_text("GET https://hunt.example/api/join/SECRET")
        == "GET https://hunt.example/api/join/<redacted>"
    )
    assert (
        errors.scrub_text("GET https://hunt.example/api/state")
        == "GET https://hunt.example/api/state"
    )


def test_scrub_text_reaches_a_path_wrapped_in_prose():
    # A leading quote, an assignment, or a newline must not hide the path —
    # the credential sits in the path, not in the surrounding punctuation.
    assert (
        errors.scrub_text("request to '/api/join/SECRET' failed")
        == "request to '/api/join/<redacted>' failed"
    )
    assert errors.scrub_text("url=/api/join/SECRET,") == "url=/api/join/<redacted>,"
    assert (
        errors.scrub_text("GET\n/api/join/SECRET\nfailed")
        == "GET\n/api/join/<redacted>\nfailed"
    )


def test_scrub_text_drops_a_query_or_fragment_on_an_ordinary_path():
    # The credential need not be in the path: a query string or fragment
    # can carry it, and redact_path alone would leave it in place.
    assert (
        errors.scrub_text("request failed at /api/state?token=SECRET")
        == "request failed at /api/state"
    )
    assert (
        errors.scrub_text("see /some/path#credential for detail")
        == "see /some/path for detail"
    )
    assert (
        errors.scrub_text("GET https://hunt.example/api/state?token=SECRET")
        == "GET https://hunt.example/api/state"
    )


def test_scrub_event_strips_request_secrets_and_keeps_the_url_redacted():
    event = {
        "request": {
            "url": "https://hunt.example/api/join/SECRET?x=1",
            "query_string": "x=1",
            "headers": {"Cookie": "session=abc"},
            "cookies": {"session": "abc"},
            "data": {"password": "hunter2"},
        },
        "transaction": "GET /api/mod/join/MODSECRET",
        "user": {"id": "player1", "ip_address": "203.0.113.9"},
        "breadcrumbs": {
            "values": [
                {
                    "message": "GET /t/INVITESECRET",
                    "data": {"url": "https://hunt.example/j/JOINCODE"},
                }
            ]
        },
    }
    cleaned = errors.scrub_event(event)
    request = cleaned["request"]
    assert request["url"] == "https://hunt.example/api/join/<redacted>"
    assert "query_string" not in request
    assert "headers" not in request
    assert "cookies" not in request
    assert "data" not in request
    assert cleaned["transaction"] == "GET /api/mod/join/<redacted>"
    assert "ip_address" not in cleaned["user"]
    breadcrumb = cleaned["breadcrumbs"]["values"][0]
    assert breadcrumb["message"] == "GET /t/<redacted>"
    assert breadcrumb["data"]["url"] == "https://hunt.example/j/<redacted>"


def test_scrub_transaction_scrubs_spans():
    event = {
        "transaction": "/api/join/SECRET",
        "spans": [
            {
                "description": "GET /api/team/invites/TOKEN",
                "data": {
                    "http.url": "https://hunt.example/m/MODCODE",
                    "path": "/j/CODE",
                },
            },
            {
                "description": "GET https://hunt.example/api/join/ABS_SECRET",
                "data": {},
            },
        ],
    }
    cleaned = errors.scrub_transaction(event)
    span = cleaned["spans"][0]
    assert span["description"] == "GET /api/team/invites/<redacted>"
    assert span["data"]["http.url"] == "https://hunt.example/m/<redacted>"
    assert span["data"]["path"] == "/j/<redacted>"
    assert cleaned["spans"][1]["description"] == (
        "GET https://hunt.example/api/join/<redacted>"
    )


def test_scrub_transaction_drops_a_query_or_fragment_in_span_data():
    # The credential can ride in a query string or fragment on an ordinary
    # path, under any span-data key — not only an allowlisted URL key.
    event = {
        "spans": [
            {
                "data": {
                    "path": "/api/state?token=SECRET",
                    "http.url": "https://hunt.example/api/state?x=1",
                    "note": "see /some/path#credential",
                }
            }
        ]
    }

    cleaned = errors.scrub_transaction(event)

    data = cleaned["spans"][0]["data"]
    assert data["path"] == "/api/state"
    assert data["http.url"] == "https://hunt.example/api/state"
    assert data["note"] == "see /some/path"


def test_scrub_transaction_drops_nested_sensitive_span_data():
    event = {
        "spans": [
            {
                "data": {
                    "response": {
                        "headers": {"Set-Cookie": "session=abc"},
                        "url": "https://hunt.example/api/state?token=SECRET",
                    },
                    "request": {"cookies": {"session": "abc"}, "env": {"SECRET": "x"}},
                    "query_string": "token=SECRET",
                }
            }
        ]
    }

    cleaned = errors.scrub_transaction(event)

    data = cleaned["spans"][0]["data"]
    assert "headers" not in data["response"]
    assert data["response"]["url"] == "https://hunt.example/api/state"
    assert "cookies" not in data["request"]
    assert "env" not in data["request"]
    assert "query_string" not in data


def test_scrub_span_and_breadcrumb_data_scrub_bearer_paths_in_prose():
    # A data value can be prose that embeds a bearer path; scrub_url alone
    # would leave it, because the value does not start with the path.
    transaction = {"spans": [{"data": {"note": "request to /api/join/SECRET failed"}}]}
    error = {
        "breadcrumbs": {
            "values": [{"message": "x", "data": {"note": "see /t/TOKEN now"}}]
        }
    }

    cleaned = errors.scrub_transaction(transaction)
    cleaned_error = errors.scrub_event(error)

    assert cleaned["spans"][0]["data"]["note"] == (
        "request to /api/join/<redacted> failed"
    )
    assert cleaned_error["breadcrumbs"]["values"][0]["data"]["note"] == (
        "see /t/<redacted> now"
    )


def test_scrub_data_reaches_bearer_paths_inside_tuples_and_sets():
    # A tuple or a set serializes as a JSON array, so a bearer path inside
    # one must be scrubbed like any list element — not skipped because the
    # container is neither a dict nor a list.
    event = {
        "breadcrumbs": {
            "values": [
                {
                    "data": {
                        "attempts": ("/api/join/SECRET",),
                        "tokens": {"/t/TOKEN"},
                        "nested": {"more": ["/j/CODE"]},
                    }
                }
            ]
        }
    }

    cleaned = errors.scrub_event(event)
    data = cleaned["breadcrumbs"]["values"][0]["data"]

    assert data["attempts"] == ["/api/join/<redacted>"]
    assert data["tokens"] == ["/t/<redacted>"]
    assert data["nested"]["more"] == ["/j/<redacted>"]


def test_scrub_event_scrubs_top_level_message():
    event = {"message": "GET /api/join/SECRET failed"}
    cleaned = errors.scrub_event(event)
    assert cleaned["message"] == "GET /api/join/<redacted> failed"


def test_scrub_event_scrubs_exception_message_and_logentry():
    event = {
        "exception": {
            "values": [
                {
                    "type": "HTTPStatusError",
                    "value": "GET https://hunt.example/api/join/SECRET failed",
                }
            ]
        },
        "logentry": {"message": "GET /api/mod/join/MODSECRET failed"},
    }
    cleaned = errors.scrub_event(event)
    assert cleaned["exception"]["values"][0]["value"] == (
        "GET https://hunt.example/api/join/<redacted> failed"
    )
    assert cleaned["logentry"]["message"] == "GET /api/mod/join/<redacted> failed"


def test_scrub_breadcrumb_scrubs_from_and_to():
    crumb = {
        "message": "navigation",
        "data": {"from": "/m/MODCODE", "to": "/t/TOKEN"},
    }
    cleaned = errors.scrub_breadcrumb(crumb)
    assert cleaned["data"] == {"from": "/m/<redacted>", "to": "/t/<redacted>"}


def test_scrub_breadcrumb_drops_credential_bearing_data():
    crumb = {
        "message": "http",
        "data": {
            "url": "https://hunt.example/api/join/SECRET",
            "headers": {"Cookie": "session=abc"},
            "cookies": {"session": "abc"},
            "data": {"password": "hunter2"},
            "env": {"SECRET": "leak"},
            "query_string": "token=SECRET",
            "response": {"headers": {"Set-Cookie": "session=abc"}},
            "keep": "fine",
        },
    }

    cleaned = errors.scrub_breadcrumb(crumb)
    data = cleaned["data"]

    assert data["url"] == "https://hunt.example/api/join/<redacted>"
    for key in ("headers", "cookies", "data", "env", "query_string"):
        assert key not in data
    assert "headers" not in data["response"]
    assert data["keep"] == "fine"


def test_internal_error_is_reported_once_with_the_request_id(tmp_path):
    transport = FakeTransport()
    errors.init_error_reporting(_config(), transport=transport)

    app = create_app(
        tmp_path / "errors.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )

    @app.get("/api/boom")
    def boom() -> None:  # pragma: no cover - reached via the test client
        raise RuntimeError("explode")

    # Starlette re-raises after building the 500, which the ASGI
    # middleware captures; the client has to tolerate that raise.
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/boom")

    assert resp.status_code == 500
    request_id = resp.headers["X-Request-ID"]
    envelopes = _send(errors.sentry_sdk.get_client(), transport)
    events = [e.get_event() for e in envelopes if e.get_event().get("exception")]
    assert len(events) == 1
    assert events[0]["exception"]["values"][0]["type"] == "RuntimeError"
    assert events[0]["tags"]["request_id"] == request_id


def test_internal_error_does_not_carry_credential_locals(tmp_path):
    transport = FakeTransport()
    errors.init_error_reporting(_config(), transport=transport)

    app = create_app(
        tmp_path / "locals.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )

    @app.get("/api/boom-locals")
    def boom_locals() -> None:  # pragma: no cover - reached via the test client
        # Built at runtime so the credential is not a literal on the source
        # line Sentry shows as frame context; only the frame local holds it.
        join_code = "".join(["SUPERSECRET", "JOINCODE"])  # noqa: F841
        raise RuntimeError("explode")

    with TestClient(app, raise_server_exceptions=False) as client:
        client.get("/api/boom-locals")

    envelopes = _send(errors.sentry_sdk.get_client(), transport)
    serialized = json.dumps([e.get_event() for e in envelopes], default=str)
    # The credential is held in a frame local, and locals are not captured,
    # so it must appear nowhere in what would be sent.
    assert "SUPERSECRETJOINCODE" not in serialized
    assert "explode" in serialized


def test_scrub_event_drops_stack_frame_locals():
    event = {
        "exception": {
            "values": [
                {
                    "type": "RuntimeError",
                    "value": "explode",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "app/main.py",
                                "vars": {"invite_token": "SUPERSECRETTOKEN"},
                            }
                        ]
                    },
                }
            ]
        }
    }

    cleaned = errors.scrub_event(event)

    frame = cleaned["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert "vars" not in frame
    assert frame["filename"] == "app/main.py"


def test_create_app_is_inert_without_a_dsn(tmp_path, monkeypatch):
    monkeypatch.delenv(errors.DSN_ENV, raising=False)
    app = create_app(
        tmp_path / "inert.db",
        admin_config=("admin", hash_password("pw")),
        cookie_secure=False,
        photos_dir=tmp_path / "photos",
        static_dir=None,
    )
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
    # No DSN means no transport: nothing would leave the process.
    client = errors.sentry_sdk.get_client()
    assert not client.dsn
    assert client.transport is None


def test_runbook_documents_the_dsn():
    runbook = (
        Path(__file__).resolve().parents[2] / "deploy" / "RUNBOOK.md"
    ).read_text()
    assert "ARKHAM_ERROR_DSN" in runbook
