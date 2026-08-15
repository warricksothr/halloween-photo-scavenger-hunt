"""Append-only audit log (ADR 0004).

One row per state mutation, written **in the same transaction** as the
mutation itself — callers get a connection that is already inside a
transaction (``with conn:`` block or an explicit BEGIN) and call
``log_action`` alongside their writes. The enum is closed: every value
is documented in ``docs/impl/audit-actions.md``, and a test parses that
file to prove the two lists cannot drift.

Reads and advisory actions (claims, SSE connects, snapshot fetches) are
deliberately never logged — see "What is deliberately not an action" in
the enum doc.
"""

from __future__ import annotations

import json
import sqlite3
import time
from enum import StrEnum


class Action(StrEnum):
    # Events (increment 2; event.purged lands in increment 10)
    EVENT_CREATED = "event.created"
    EVENT_OPENED = "event.opened"
    EVENT_CLOSED = "event.closed"
    EVENT_PURGED = "event.purged"
    # Riddles (increment 2)
    RIDDLE_CREATED = "riddle.created"
    RIDDLE_EDITED = "riddle.edited"
    RIDDLE_DELETED = "riddle.deleted"
    # Players & sessions (increment 3)
    PLAYER_JOINED = "player.joined"
    SESSION_REVOKED = "session.revoked"
    # Evidence (increments 5, 8)
    EVIDENCE_UPLOADED = "evidence.uploaded"
    EVIDENCE_QUARANTINED = "evidence.quarantined"
    # Submissions & moderation (increments 6–7)
    SUBMISSION_CREATED = "submission.created"
    VERDICT_ISSUED = "verdict.issued"
    DUPLICATE_FLAG_RAISED = "duplicate_flag.raised"
    DUPLICATE_FLAG_RESOLVED = "duplicate_flag.resolved"
    # Conduct (increment 8)
    STRIKE_ISSUED = "strike.issued"
    STRIKE_REVERSED = "strike.reversed"
    NOTICE_ACKNOWLEDGED = "notice.acknowledged"
    # Stretch: teams
    TEAM_INVITE_CREATED = "team_invite.created"
    TEAM_INVITE_REDEEMED = "team_invite.redeemed"
    TEAM_INVITE_REVOKED = "team_invite.revoked"
    TEAM_RENAMED = "team.renamed"
    TEAM_MEMBER_REMOVED = "team.member_removed"


class ActorType(StrEnum):
    # Mirrors the CHECK constraint on audit_event.actor_type.
    ADMIN = "admin"
    MODERATOR = "moderator"
    PLAYER = "player"
    SYSTEM = "system"


def log_action(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    actor_type: ActorType,
    actor_id: str | None,
    action: Action,
    entity_type: str,
    entity_id: str,
    details: dict | None = None,
) -> None:
    """Append one audit row on ``conn``'s open transaction.

    ``details`` must stay small: before/after values, ids, counts —
    never photo content, tokens, or join/mod codes (enum doc rules).
    """
    conn.execute(
        "INSERT INTO audit_event (event_id, actor_type, actor_id, action,"
        " entity_type, entity_id, details, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id,
            str(actor_type),
            actor_id,
            str(action),
            entity_type,
            entity_id,
            json.dumps(details or {}),
            int(time.time()),
        ),
    )
