"""Fast checks for the disposable backup and restore path."""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import tarfile
from pathlib import Path

import pytest

from app import db as db_module

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "deploy" / "backup.sh"


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
