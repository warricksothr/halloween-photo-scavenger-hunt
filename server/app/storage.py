"""Disk-space guardrail for photo uploads (ticket RFWPVZ).

Originals are kept for the life of the event and nothing purges them
mid-party (schema.md "Decided at design review"), so a full disk is the
one failure mode uploads cannot recover from: SQLite writes start failing
too, and a party mid-run has no room to intervene. The guardrail refuses
an upload before it does any work when the filesystem would fall below a
free-space floor.

It is a guardrail, not a reservation or a quota. Two uploads can both see
enough room and then write, and the floor is a fixed byte count, not a
per-team share — the point is to stop the disk reaching zero, not to
partition it. ``MIN_FREE_BYTES_DEFAULT`` leaves room for SQLite's WAL to
grow and for the host's own writes; ``ARKHAM_MIN_FREE_BYTES`` overrides it
for a small SD-card host or a big one.

Two layers enforce the floor, because the route-level check alone is too
late. ``StorageGuardMiddleware`` runs before Starlette parses the
multipart form; the route's check (evidence.upload) runs after, and
accounts for the files that upload will write, not just the body.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# 256 MiB. Comfortably above a burst of 15 MB uploads plus WAL growth, and
# small enough to be irrelevant on any host that can run the event.
MIN_FREE_BYTES_DEFAULT = 256 * 1024 * 1024

# The one endpoint that writes player-supplied bytes to disk.
UPLOAD_PATH = "/api/evidence"

STORAGE_FULL_MESSAGE = "The server is out of storage space — tell the host."


def configured_min_free_bytes() -> int:
    """The free-space floor in bytes, from ``ARKHAM_MIN_FREE_BYTES``.

    A malformed or non-positive value falls back to the default rather
    than refusing to start: like the session TTL, this is a hardening knob,
    not a prerequisite, and a party night must not hinge on parsing it."""
    try:
        configured = int(os.environ.get("ARKHAM_MIN_FREE_BYTES", ""))
    except ValueError:
        configured = 0
    return configured if configured > 0 else MIN_FREE_BYTES_DEFAULT


def has_room(path: Path, extra_bytes: int, minimum: int) -> bool:
    """True when writing ``extra_bytes`` under ``path`` keeps at least
    ``minimum`` bytes free. ``path`` may not exist yet; the check is about
    the filesystem that would hold it, so it is not created — the nearest
    existing ancestor answers for it."""
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    return free - extra_bytes >= minimum


def _any_directory_full(directories: set[Path], extra_bytes: int, minimum: int) -> bool:
    """True when any filesystem in ``directories`` would drop below
    ``minimum``. Sync so the middleware can run it in the threadpool:
    ``has_room`` stats the filesystem, and that must not block the loop."""
    return any(
        not has_room(directory, extra_bytes, minimum) for directory in directories
    )


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            return int(value)
        except ValueError:
            return None
    return None


class StorageGuardMiddleware:
    """Refuse an upload before Starlette reads or spools the body.

    A route dependency (``UploadFile``) is parsed before the handler runs,
    and Starlette spools a multipart part past its memory threshold to a
    temporary file. That temp file does not necessarily share a filesystem
    with the photos directory — in the container recipe the data volume is
    a mount while ``/tmp`` sits on the root filesystem — so this checks
    **both**: the declared length must fit on the photos volume *and* on
    the spool filesystem (``TMPDIR``, or the system temp directory). A
    full disk on either refuses before any body bytes are read.

    A chunked request declares no length, and reading the body to learn it
    would defeat the point; the app's request cap is the bound instead.

    The disk query itself is a blocking ``statvfs``, so it runs in the
    threadpool rather than on the event loop.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        photos_dir: Path,
        min_free_bytes: int,
        max_bytes: int,
        spool_dir: Path | None = None,
    ) -> None:
        self.app = app
        self.photos_dir = photos_dir
        self.min_free_bytes = min_free_bytes
        self.max_bytes = max_bytes
        self.spool_dir = spool_dir or Path(tempfile.gettempdir())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != UPLOAD_PATH
        ):
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        extra = declared if declared is not None else self.max_bytes
        directories = {self.photos_dir, self.spool_dir}
        if await run_in_threadpool(
            _any_directory_full, directories, extra, self.min_free_bytes
        ):
            response = JSONResponse(
                status_code=507,
                content={"error": "storage_full", "message": STORAGE_FULL_MESSAGE},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
