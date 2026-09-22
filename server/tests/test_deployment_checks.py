"""Fast checks for the deployment path: backup/restore and pinned runtime."""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tomllib
from pathlib import Path

import pytest

from app import db as db_module
from app.images import MAX_BYTES

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "deploy" / "backup.sh"
REQUIREMENTS_LOCK = REPO_ROOT / "server" / "requirements.lock"
UV_LOCK = REPO_ROOT / "server" / "uv.lock"
CONTAINERFILE = REPO_ROOT / "Containerfile"
NGINX_CONF = REPO_ROOT / "deploy" / "nginx.conf"
RUNBOOK = REPO_ROOT / "deploy" / "RUNBOOK.md"
SYSTEMD_UNIT = REPO_ROOT / "deploy" / "arkham-hunt.service"


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _pinned_requirements(text: str) -> dict[str, tuple[str, str]]:
    """Parse a `--require-hashes` requirements file into name → (version, marker)."""

    pinned: dict[str, tuple[str, str]] = {}
    for raw in text.splitlines():
        # Only requirement lines start at column zero; hashes and `# via`
        # comments are indented continuations.
        if not raw or raw[0].isspace() or raw.startswith("#"):
            continue
        line = raw.rstrip("\\").strip()
        match = re.fullmatch(r"([A-Za-z0-9._-]+)==([^\s;]+)\s*(?:;\s*(.*))?", line)
        assert match, f"not a fully pinned requirement: {raw!r}"
        name, version, marker = match.groups()
        pinned[_canonical(name)] = (version, (marker or "").strip())
    return pinned


def _uv_lock_versions(text: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in tomllib.loads(text).get("package", []):
        versions[_canonical(package["name"])] = package["version"]
    return versions


def test_requirements_lock_is_fully_pinned():
    pinned = _pinned_requirements(REQUIREMENTS_LOCK.read_text())
    assert pinned, "requirements.lock is empty"
    assert len(pinned) > 10, "requirements.lock looks truncated"


def test_requirements_lock_versions_match_uv_lock():
    pinned = _pinned_requirements(REQUIREMENTS_LOCK.read_text())
    locked = _uv_lock_versions(UV_LOCK.read_text())
    assert set(pinned) <= set(locked), set(pinned) - set(locked)
    for name, (version, _) in pinned.items():
        assert version == locked[name], f"{name}: {version} != uv.lock {locked[name]}"


def test_requirements_lock_matches_fresh_uv_export():
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not on PATH; scripts/check-quality.sh enforces this in CI")
    result = subprocess.run(
        [
            uv,
            "export",
            "--project",
            "server",
            "--locked",
            "--no-dev",
            "--no-emit-project",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert _pinned_requirements(REQUIREMENTS_LOCK.read_text()) == (
        _pinned_requirements(result.stdout)
    ), "server/requirements.lock is stale; regenerate it from uv.lock"


def test_containerfile_installs_the_hash_pinned_lock():
    containerfile = CONTAINERFILE.read_text()
    assert "--require-hashes -r ./server/requirements.lock" in containerfile
    assert "pip install --no-cache-dir -e" not in containerfile


def test_nginx_upload_limit_sits_above_the_app_cap():
    match = re.search(r"client_max_body_size\s+(\d+)m;", NGINX_CONF.read_text())
    assert match, "nginx.conf has no client_max_body_size"
    proxy_bytes = int(match.group(1)) * 1024 * 1024
    assert proxy_bytes > MAX_BYTES, "nginx would cut off a body the app accepts"
    assert f"client_max_body_size {match.group(1)}m" in RUNBOOK.read_text()


def test_nginx_https_block_sends_security_headers():
    block = NGINX_CONF.read_text().split("listen 443", 1)[1]
    for header in (
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Content-Security-Policy",
    ):
        assert header in block, f"missing {header}"


def test_systemd_unit_hardens_the_data_dir():
    unit = SYSTEMD_UNIT.read_text()
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=read-only" in unit
    assert "ReadWritePaths=%h/arkham/data" in unit


def _restricted_path_without_sqlite_cli(root: Path) -> str:
    """Expose only the utilities backup.sh needs, never sqlite3."""

    bin_dir = root / "bin"
    bin_dir.mkdir()
    for name in ("cp", "date", "dirname", "gzip", "mkdir", "rm", "tar"):
        source = shutil.which(name)
        assert source is not None, f"test host lacks {name}"
        (bin_dir / name).symlink_to(source)
    return str(bin_dir)


def test_backup_archive_restores_live_database_and_photos(tmp_path):
    source = tmp_path / "live-data"
    destination = tmp_path / "backups"
    restored = tmp_path / "restored"
    source.mkdir()
    (source / "photos" / "originals").mkdir(parents=True)
    photo_bytes = b"synthetic-photo-bytes"
    (source / "photos" / "originals" / "evidence.jpg").write_bytes(photo_bytes)

    conn = db_module.connect(source / "arkham.db")
    db_module.apply_migrations(conn)
    conn.execute(
        "INSERT INTO event (id, name, join_code, mod_code, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        ("event-backup", "Restore Party", "JOINBACK", "MODBACK", 123),
    )
    conn.commit()

    env = os.environ.copy()
    env.update(
        {
            "ARKHAM_DATA_DIR": str(source),
            "PATH": _restricted_path_without_sqlite_cli(tmp_path),
        }
    )
    try:
        result = subprocess.run(
            ["/bin/sh", str(BACKUP_SCRIPT), str(destination)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    finally:
        conn.close()

    archives = list(destination.glob("arkham-backup-*.tar.gz"))
    assert len(archives) == 1
    assert str(archives[0]) in result.stdout
    assert not list(destination.glob(".backup-work-*"))

    restored.mkdir()
    with tarfile.open(archives[0], "r:gz") as archive:
        if hasattr(tarfile, "data_filter"):
            archive.extractall(restored, filter=tarfile.data_filter)
        else:  # Python 3.11 has no extraction filter argument.
            archive.extractall(restored)

    restored_conn = db_module.connect(restored / "arkham.db")
    try:
        assert (
            restored_conn.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            == 1
        )
        assert (
            restored_conn.execute(
                "SELECT name FROM event WHERE id = ?", ("event-backup",)
            ).fetchone()[0]
            == "Restore Party"
        )
        assert restored_conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            with restored_conn:
                restored_conn.execute(
                    "INSERT INTO riddle"
                    " (id, event_id, text, sort_order, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    ("orphan", "missing-event", "Nope", 1, 123),
                )
    finally:
        restored_conn.close()

    assert (
        restored / "photos" / "originals" / "evidence.jpg"
    ).read_bytes() == photo_bytes
