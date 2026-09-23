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
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# 256 MiB. Comfortably above a burst of 15 MB uploads plus WAL growth, and
# small enough to be irrelevant on any host that can run the event.
MIN_FREE_BYTES_DEFAULT = 256 * 1024 * 1024


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
