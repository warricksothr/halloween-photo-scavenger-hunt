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


def _pinned_requirements(text: str) -> dict[str, tuple[str, str, tuple[str, ...]]]:
    """Parse a `--require-hashes` requirements file into name → (version, marker, hashes).

    The hashes are kept, not dropped, so a drift check can compare the artifact
    digests rather than just the versions.
    """

    pinned: dict[str, tuple[str, str]] = {}
    hashes: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        # Only requirement lines start at column zero; hashes and `# via`
        # comments are indented continuations.
        if raw and raw[0].isspace():
            if current is not None:
                hashes[current].extend(re.findall(r"--hash=sha256:([0-9a-f]{64})", raw))
            continue
        if not raw or raw.startswith("#"):
            continue
        line = raw.rstrip("\\").strip()
        match = re.fullmatch(r"([A-Za-z0-9._-]+)==([^\s;]+)\s*(?:;\s*(.*))?", line)
        assert match, f"not a fully pinned requirement: {raw!r}"
        name, version, marker = match.groups()
        current = _canonical(name)
        pinned[current] = (version, (marker or "").strip())
        hashes.setdefault(current, [])
    return {
        name: (version, marker, tuple(hashes[name]))
        for name, (version, marker) in pinned.items()
    }


def _uv_lock_versions(text: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in tomllib.loads(text).get("package", []):
        versions[_canonical(package["name"])] = package["version"]
    return versions


def test_requirements_lock_is_fully_pinned():
    pinned = _pinned_requirements(REQUIREMENTS_LOCK.read_text())
    assert pinned, "requirements.lock is empty"
    assert len(pinned) > 10, "requirements.lock looks truncated"
    for name, (version, _, hashes) in pinned.items():
        assert version, f"{name} is not pinned to a version"
        assert hashes, f"{name} has no --hash entries"


def test_requirements_lock_versions_match_uv_lock():
    pinned = _pinned_requirements(REQUIREMENTS_LOCK.read_text())
    locked = _uv_lock_versions(UV_LOCK.read_text())
    assert set(pinned) <= set(locked), set(pinned) - set(locked)
    for name, (version, _, _) in pinned.items():
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


def test_containerfile_base_images_are_digest_pinned():
    images = re.findall(
        r"^FROM\s+(\S+)(?:\s+AS\s+\S+)?", CONTAINERFILE.read_text(), re.MULTILINE
    )
    assert images, "Containerfile has no FROM lines"
    for image in images:
        assert "@sha256:" in image, f"base image is a mutable tag: {image}"


def test_nginx_upload_limit_sits_above_the_app_cap():
    match = re.search(r"client_max_body_size\s+(\d+)m;", NGINX_CONF.read_text())
    assert match, "nginx.conf has no client_max_body_size"
    proxy_bytes = int(match.group(1)) * 1024 * 1024
    assert proxy_bytes > MAX_BYTES, "nginx would cut off a body the app accepts"
    assert f"client_max_body_size {match.group(1)}m" in RUNBOOK.read_text()


def _tls_server_block(text: str) -> str:
    """Return the body of the `server { … }` block that listens on 443."""

    for match in re.finditer(r"server\s*\{", text):
        depth = 1
        cursor = match.end()
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1
        block = text[match.end() : cursor - 1]
        if re.search(r"^\s*listen\s+443\b", block, re.MULTILINE):
            return block
    raise AssertionError("nginx.conf has no server block listening on 443")


def test_nginx_https_block_sends_security_headers():
    block = _tls_server_block(NGINX_CONF.read_text())
    csp = (
        "default-src 'self'; script-src 'self' 'unsafe-inline';"
        " style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;"
        " font-src 'self' https://fonts.gstatic.com; img-src 'self';"
        " connect-src 'self'; worker-src 'self'; manifest-src 'self';"
        " object-src 'none'; base-uri 'self'; form-action 'self';"
        " frame-ancestors 'none'"
    )
    for directive in (
        'add_header Strict-Transport-Security "max-age=31536000" always;',
        'add_header X-Content-Type-Options "nosniff" always;',
        'add_header X-Frame-Options "DENY" always;',
        f'add_header Content-Security-Policy "{csp}" always;',
    ):
        assert directive in block, f"missing or weakened directive: {directive}"


def test_systemd_unit_hardens_the_data_dir():
    unit = SYSTEMD_UNIT.read_text()
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=read-only" in unit
    assert "ReadWritePaths=%h/arkham/data" in unit


def _restricted_path_without_sqlite_cli(
    root: Path, *, stamp: str = "20260101-000000"
) -> str:
    """Expose only the utilities backup.sh needs, never sqlite3.

    `date` is a stub pinned to `stamp`, so a test can put two runs in the same
    second on purpose rather than relying on the wall clock.
    """

    bin_dir = root / "bin"
    bin_dir.mkdir()
    for name in ("cp", "dirname", "gzip", "mkdir", "mktemp", "rm", "stat", "tar"):
        source = shutil.which(name)
        assert source is not None, f"test host lacks {name}"
        (bin_dir / name).symlink_to(source)
    date_stub = bin_dir / "date"
    date_stub.write_text(f"#!/bin/sh\necho {stamp}\n")
    date_stub.chmod(0o755)
    return str(bin_dir)


def _live_data(root: Path) -> Path:
    """A data directory with a migrated database and one photo."""

    source = root / "live-data"
    source.mkdir()
    (source / "photos" / "originals").mkdir(parents=True)
    (source / "photos" / "originals" / "evidence.jpg").write_bytes(b"photo-bytes")
    conn = db_module.connect(source / "arkham.db")
    db_module.apply_migrations(conn)
    conn.close()
    return source


def _backup_env(source: Path, root: Path, **extra: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "ARKHAM_DATA_DIR": str(source),
            "PATH": _restricted_path_without_sqlite_cli(root),
        }
    )
    env.update(extra)
    return env


def _run_backup(destination: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/sh", str(BACKUP_SCRIPT), str(destination)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


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


def test_backup_restore_recipe_extracts_one_archive_into_data():
    """The header recipe must match RUNBOOK §1, or the restore is empty.

    Retention leaves several archives, so a wildcard passed to tar would make
    every file but the first a member name and the restore would fail.
    """

    header = BACKUP_SCRIPT.read_text()
    runbook = RUNBOOK.read_text()
    assert "tar -xzf" in header
    assert 'tar -xzf "$ARCHIVE" -C <repo-root>/data' in header
    assert 'tar -xzf "$ARCHIVE" -C ~/arkham/data' in runbook
    for text in (header, runbook):
        # No recipe that extracts into the repo root itself, and none that
        # lets the shell expand the archive argument.
        assert not re.search(r"-C <repo-root>(?!\S)", text)
        assert not re.search(r"tar -xzf [^\n]*\*", text)
        assert re.search(r"ARCHIVE=\$\(ls -1t [^\n]*arkham-backup-\*\.tar\.gz", text)


def test_backups_in_the_same_second_do_not_collide(tmp_path):
    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    # The stubbed date pins both runs to the same second, so only the archive
    # suffix can keep them apart.
    env = _backup_env(source, tmp_path)

    for _ in range(2):
        result = _run_backup(destination, env)
        assert result.returncode == 0, result.stderr

    archives = sorted(destination.glob("arkham-backup-*.tar.gz"))
    assert len(archives) == 2, [archive.name for archive in archives]
    assert all("20260101-000000" in archive.name for archive in archives)
    assert not list(destination.glob(".backup-work-*"))


def test_backup_mirrors_off_host_and_prunes_both_directories(tmp_path):
    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    env = _backup_env(
        source,
        tmp_path,
        ARKHAM_BACKUP_MIRROR=str(mirror),
        ARKHAM_BACKUP_KEEP="2",
    )

    for _ in range(3):
        result = _run_backup(destination, env)
        assert result.returncode == 0, result.stderr

    local = sorted(destination.glob("arkham-backup-*.tar.gz"))
    mirrored = sorted(mirror.glob("arkham-backup-*.tar.gz"))
    assert len(local) == 2, [archive.name for archive in local]
    assert len(mirrored) == 2, [archive.name for archive in mirrored]
    assert {archive.name for archive in local} == {archive.name for archive in mirrored}


def test_backup_warns_when_no_mirror_is_configured(tmp_path):
    source = _live_data(tmp_path)
    env = _backup_env(source, tmp_path)
    env.pop("ARKHAM_BACKUP_MIRROR", None)

    result = _run_backup(tmp_path / "backups", env)

    assert result.returncode == 0, result.stderr
    assert "ARKHAM_BACKUP_MIRROR is unset" in result.stderr


def test_backup_refuses_an_unmounted_mirror(tmp_path):
    source = _live_data(tmp_path)
    env = _backup_env(
        source, tmp_path, ARKHAM_BACKUP_MIRROR=str(tmp_path / "not-mounted")
    )

    result = _run_backup(tmp_path / "backups", env)

    assert result.returncode != 0
    assert "not a directory" in result.stderr
