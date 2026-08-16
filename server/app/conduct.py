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

    pending_notice is always False until increment 8 lands the strike-1
    interstitial (nothing sets it before then, and the column doesn't
    exist — the snapshot field ships from day one so clients never
    guess).
    """
    rows = conn.execute(
        "SELECT level, cooldown_until FROM strike"
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
    return Restriction(level=level, cooldown_until=cooldown_until,
                       pending_notice=False)


def now() -> int:
    return int(time.time())
