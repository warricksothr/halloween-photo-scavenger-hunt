"""Conduct system primitives (increment 6: the shared pieces).

The full conduct system is increment 8 (strikes, quarantine,
interstitials). This module holds the one piece increments 6+ already
need: the **derived restriction** — a pure function of non-reversed
strikes (ADR 0001). There is deliberately no stored column to keep in
sync; state.py, evidence.py, and submissions.py all compute from this
same query so the rule lives in exactly one place.

Levels (design.md strike ladder):
- 0 — clean
- 1 — warned (interstitial pending until acknowledged; no play effect)
- 2 — cooldown: uploads blocked until cooldown_until
- 3 — banned: uploads and submissions blocked for the rest of the event
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass


@dataclass
class Restriction:
    level: int                      # 0 clean, 1 warned, 2 cooldown, 3 banned
    cooldown_until: int | None      # epoch seconds when level == 2
    pending_notice: bool            # strike-1 interstitial not yet shown
    pending_notice_strike_id: str | None  # the strike the ack endpoint clears

    def as_dict(self) -> dict:
        # The snapshot shape (docs/impl/api.md).
        return {"level": self.level, "cooldown_until": self.cooldown_until,
                "pending_notice": self.pending_notice}

    def blocks_uploads(self, now: int) -> bool:
        if self.level == 3:
            return True
        return (
            self.level == 2
            and self.cooldown_until is not None
            and self.cooldown_until > now
        )

    def blocks_submissions(self, now: int) -> bool:
        # Strike 3 bans submissions; strike 2's cooldown gates uploads
        # but a player may still submit an existing drawer photo.
        return self.level == 3


def derive_restriction(conn: sqlite3.Connection, player_id: str) -> Restriction:
    """Compute the restriction from non-reversed strikes.

    The ladder is "count the non-reversed strikes" (design.md), but the
    rows themselves tell the level: with moderator confirmation between
    rungs there is exactly one strike per level, so MAX(level) is the
    count. The pending interstitial is the earliest non-reversed strike
    with no ``notice.acknowledged`` row naming it in the audit log —
    ack state is audit data (ADR 0004), not a stored flag that can go
    stale when a strike is reversed.
    """
    rows = conn.execute(
        "SELECT id, level, cooldown_until FROM strike"
        " WHERE player_id = ? AND reversed_at IS NULL"
        " ORDER BY level DESC",
        (player_id,),
    ).fetchall()
    level = rows[0]["level"] if rows else 0
    cooldown_until = next(
        (r["cooldown_until"] for r in rows
         if r["level"] == 2 and r["cooldown_until"] is not None),
        None,
    )
    pending_notice_strike_id = _unacknowledged_strike(conn, player_id)
    return Restriction(
        level=level, cooldown_until=cooldown_until,
        pending_notice=pending_notice_strike_id is not None,
        pending_notice_strike_id=pending_notice_strike_id)


def _unacknowledged_strike(conn: sqlite3.Connection,
                           player_id: str) -> str | None:
    """The earliest non-reversed strike with no matching
    ``notice.acknowledged`` audit row, or None."""
    row = conn.execute(
        "SELECT s.id FROM strike s"
        " WHERE s.player_id = ? AND s.reversed_at IS NULL"
        " AND NOT EXISTS ("
        "     SELECT 1 FROM audit_event a"
        "     WHERE a.action = 'notice.acknowledged'"
        "       AND a.entity_type = 'strike'"
        "       AND a.entity_id = s.id)"
        " ORDER BY s.created_at ASC LIMIT 1",
        (player_id,),
    ).fetchone()
    return row["id"] if row else None


def now() -> int:
    return int(time.time())
