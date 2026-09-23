"""Readiness diagnostics for the operator and the deploy smoke.

``/api/health`` answers "did the process boot?" with a constant. This
module answers the next question — "is it *ready*?" — with the facts an
operator would otherwise shell into the container to get: can the writer
still write, did migrations land, is there disk left for photos, how many
photos and SSE clients there are, and which build is running.

Everything here reads state the app already holds. Connection access goes
through ``db.reader`` and ``db.writer_is_writable`` so this module never
names the connections itself (ADR 0013).
"""

from __future__ import annotations

import os
import shutil
import time
from typing import Any

from fastapi import Request

from app import db as db_module

# Same variable the error reporter reads as its release (app/errors.py):
# one deploy sets it once and both the error report and readyz name the
# same build.
RELEASE_ENV = "ARKHAM_RELEASE"


def _schema_version(request: Request) -> int | None:
    conn = db_module.reader(request)
    return conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]


def _photo_count(request: Request) -> int:
    """Rows, not files: the row is the data truth, and the directory can
    hold an orphan between a write and its commit."""
    conn = db_module.reader(request)
    return conn.execute("SELECT COUNT(*) FROM evidence_item").fetchone()[0]


def _disk(request: Request) -> dict[str, int]:
    usage = shutil.disk_usage(request.app.state.db_path)
    return {"free_bytes": usage.free, "total_bytes": usage.total}


def _subscriber_count(request: Request) -> int | None:
    broker = getattr(request.app.state, "sse_broker", None)
    return broker.subscriber_count() if broker is not None else None


def snapshot(request: Request) -> dict[str, Any]:
    """The readiness body. Every probe is cheap and side-effect-free
    except the writability check, which rolls back."""
    started_at = getattr(request.app.state, "started_at", None)
    return {
        "status": "ok",
        "db_writable": db_module.writer_is_writable(request),
        "schema_version": _schema_version(request),
        "disk": _disk(request),
        "photo_count": _photo_count(request),
        "sse_subscribers": _subscriber_count(request),
        "release": os.environ.get(RELEASE_ENV) or "unknown",
        "uptime_seconds": (
            round(time.monotonic() - started_at, 3) if started_at is not None else None
        ),
    }
