"""Disk guardrail unit tests (ticket RFWPVZ)."""

import asyncio
from collections import namedtuple

import pytest

from app import storage

Usage = namedtuple("Usage", "total used free")


@pytest.mark.parametrize("value", ["", "nope", "0", "-5"])
def test_malformed_or_non_positive_falls_back_to_default(monkeypatch, value):
    monkeypatch.setenv("ARKHAM_MIN_FREE_BYTES", value)
    assert storage.configured_min_free_bytes() == storage.MIN_FREE_BYTES_DEFAULT


def test_unset_uses_default(monkeypatch):
    monkeypatch.delenv("ARKHAM_MIN_FREE_BYTES", raising=False)
    assert storage.configured_min_free_bytes() == storage.MIN_FREE_BYTES_DEFAULT


def test_override_is_read(monkeypatch):
    monkeypatch.setenv("ARKHAM_MIN_FREE_BYTES", "1024")
    assert storage.configured_min_free_bytes() == 1024


def test_has_room_accounts_for_the_incoming_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda p: Usage(0, 0, 1000))
    assert storage.has_room(tmp_path, 100, 900) is True
    assert storage.has_room(tmp_path, 101, 900) is False


def test_has_room_probes_an_ancestor_without_creating_the_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda p: Usage(0, 0, 1000))
    missing = tmp_path / "data" / "photos"
    assert storage.has_room(missing, 100, 900) is True
    assert not missing.exists()


def test_has_room_against_the_real_filesystem(tmp_path):
    # The unpatched path: a real statvfs result, generous floor.
    assert storage.has_room(tmp_path, 1, 0) is True
    free = storage.shutil.disk_usage(tmp_path).free
    assert storage.has_room(tmp_path, 0, free + 1) is False


class _Downstream:
    """A stand-in app that reads one body message and answers 200."""

    def __init__(self) -> None:
        self.called = False
        self.body_reads = 0

    async def __call__(self, scope, receive, send):
        self.called = True
        await receive()
        self.body_reads += 1
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def _call_middleware(middleware, scope, messages):
    incoming = list(messages)

    async def receive():
        return incoming.pop(0)

    sent = []

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))
    return sent


def _scope(method="POST", path=storage.UPLOAD_PATH, content_length=None):
    headers = []
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))
    return {"type": "http", "method": method, "path": path, "headers": headers}


def test_middleware_rejects_before_the_body_is_read(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "has_room", lambda *a, **k: False)
    downstream = _Downstream()
    middleware = storage.StorageGuardMiddleware(
        downstream, photos_dir=tmp_path, min_free_bytes=1, max_bytes=100
    )

    sent = _call_middleware(
        middleware,
        _scope(content_length=10),
        [{"type": "http.request", "body": b"0123456789", "more_body": False}],
    )

    assert sent[0]["status"] == 507
    assert b"storage_full" in sent[1]["body"]
    # The whole point: the body was never touched, so nothing spooled.
    assert downstream.called is False
    assert downstream.body_reads == 0


def test_middleware_passes_an_upload_through_when_there_is_room(tmp_path):
    downstream = _Downstream()
    middleware = storage.StorageGuardMiddleware(
        downstream, photos_dir=tmp_path, min_free_bytes=0, max_bytes=100
    )

    sent = _call_middleware(
        middleware,
        _scope(content_length=10),
        [{"type": "http.request", "body": b"0123456789", "more_body": False}],
    )

    assert sent[0]["status"] == 200
    assert downstream.called is True


def test_middleware_bounds_a_chunked_upload_by_the_request_cap(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(
        storage,
        "has_room",
        lambda path, extra, minimum: seen.append(extra) or True,
    )
    middleware = storage.StorageGuardMiddleware(
        _Downstream(), photos_dir=tmp_path, min_free_bytes=0, max_bytes=777
    )

    # No content-length: the declared size is unknown, so the cap stands in.
    _call_middleware(
        middleware,
        _scope(),
        [{"type": "http.request", "body": b"x", "more_body": False}],
    )
    # Checked against both the photos volume and the spool filesystem.
    assert seen == [777, 777]


def test_middleware_rejects_when_only_the_spool_filesystem_is_full(
    tmp_path, monkeypatch
):
    spool = tmp_path / "tmp"
    spool.mkdir()
    monkeypatch.setattr(
        storage,
        "has_room",
        lambda path, extra, minimum: path != spool,
    )
    downstream = _Downstream()
    middleware = storage.StorageGuardMiddleware(
        downstream,
        photos_dir=tmp_path,
        min_free_bytes=0,
        max_bytes=100,
        spool_dir=spool,
    )

    sent = _call_middleware(
        middleware,
        _scope(content_length=10),
        [{"type": "http.request", "body": b"0123456789", "more_body": False}],
    )
    assert sent[0]["status"] == 507
    assert downstream.called is False


def test_middleware_ignores_other_requests(tmp_path, monkeypatch):
    monkeypatch.setattr(
        storage, "has_room", lambda *a, **k: pytest.fail("consulted off the path")
    )
    downstream = _Downstream()
    middleware = storage.StorageGuardMiddleware(
        downstream, photos_dir=tmp_path, min_free_bytes=0, max_bytes=100
    )

    _call_middleware(
        middleware,
        _scope(method="GET", path="/api/state"),
        [{"type": "http.request", "body": b"", "more_body": False}],
    )
    assert downstream.called is True
