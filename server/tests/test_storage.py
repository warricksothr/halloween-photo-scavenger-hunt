"""Disk guardrail unit tests (ticket RFWPVZ)."""

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
