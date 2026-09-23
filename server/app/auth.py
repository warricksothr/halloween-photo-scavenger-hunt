"""Admin authentication.

Per docs/impl/schema.md ("no admin table"): the admin is one human whose
credentials live in server config, so there is no admin row in the
database and no password-set flow in the app — the argon2id hash is
generated offline (``python -m app.security '<password>'``) and passed
to ``create_app`` (production: from ``ARKHAM_ADMIN_USERNAME`` /
``ARKHAM_ADMIN_PASSWORD_HASH`` env vars).

Admin sessions are in-memory on ``app.state``: the ``session`` table
references players and a table for one row is ceremony. A restart logs
the admin out, which a party app with one admin tolerates. The set is a
``dict`` from token to expiry: a lost phone must stop working after
``SESSION_TTL_SECONDS``, not at the next restart.

Every session kind carries the same fixed TTL from when it was issued
(``created_at`` for DB rows). Fixed, not sliding on ``last_seen_at``: a
device that keeps talking would otherwise live forever, which is the
shared-device problem the TTL exists to close.

Player sessions (bottom half of this module) are the opposite: DB-backed
from day one (the ``session`` table) because moderation must be able to
list and revoke devices, and because a restart must not log out 30
players mid-party. The bearer token itself is never stored — only its
SHA-256 hash (schema.md hardening note).
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app import ids
from app.db import locked_transaction, reader

COOKIE_NAME = "arkham_admin"
PLAYER_COOKIE_NAME = "arkham_session"
MOD_COOKIE_NAME = "arkham_mod"

# How long any session stays live. Twelve hours covers one long party
# night; a device left behind stops working before the next morning.
# ARKHAM_SESSION_TTL_SECONDS overrides it (an all-day event, a rehearsal).
SESSION_TTL_SECONDS = 12 * 60 * 60

# Throttle for session.last_seen_at writes (schema invariant: max one
# write per minute per session, so the hot read path doesn't generate a
# write per request).
LAST_SEEN_THROTTLE_SECONDS = 60


def configured_session_ttl() -> int:
    """The session TTL in seconds, from ``ARKHAM_SESSION_TTL_SECONDS``.

    A malformed or non-positive value falls back to the default rather
    than refusing to start: the TTL is a hardening knob, not a
    prerequisite like the admin credential, and a party night must not
    hinge on parsing it."""
    try:
        configured = int(os.environ.get("ARKHAM_SESSION_TTL_SECONDS", ""))
    except ValueError:
        configured = 0
    return configured if configured > 0 else SESSION_TTL_SECONDS


def _expired(created_at: int, ttl: int) -> bool:
    return int(time.time()) - created_at >= ttl


def check_admin_password(config: tuple[str, str], username: str, password: str) -> bool:
    """Credential check; the argon2id verification lives in security.py
    so this module stays importable without the argon2 dependency in
    tooling contexts. Both factors are compared even when one fails so
    timing does not reveal which half was wrong."""
    from app.security import verify_password  # deferred import: argon2

    expected_user, password_hash = config
    return verify_password(password_hash, password) and secrets.compare_digest(
        username, expected_user
    )


def issue_admin_session(request: Request) -> str:
    """Mint a token and record it with its expiry. The token is the
    credential; only the token (never a hash — it never leaves the server
    except as the cookie itself, and there is no DB row to leak) is kept
    in memory."""
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + request.app.state.session_ttl
    request.app.state.admin_sessions[token] = expires_at
    return token


def revoke_admin_session(request: Request, token: str) -> None:
    request.app.state.admin_sessions.pop(token, None)


def current_admin(request: Request) -> str | None:
    """Return the admin token if the request carries a live session."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    sessions: dict[str, int] = request.app.state.admin_sessions
    expires_at = sessions.get(token)
    if expires_at is None:
        return None
    if expires_at <= int(time.time()):
        # Drop it on the way out so the dict does not accumulate dead
        # tokens for the life of the process.
        sessions.pop(token, None)
        return None
    return token


def require_admin(request: Request) -> str:
    """FastAPI dependency: 401 unless the request is an authed admin.

    Every /api/admin route lists this; the client role is cosmetic
    (hardening checklist: authorization is server-side, always).
    """
    token = current_admin(request)
    if token is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "not_authenticated", "message": "Admin login required."},
        )
    return token


# ── Player sessions ───────────────────────────────────────────────────


def _hash_token(token: str) -> str:
    """SHA-256 of the bearer token — the only form at rest (schema.md:
    plaintext never stored, so a DB leak yields no usable sessions)."""
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class PlayerContext:
    """What a player route needs: who they are and their team, resolved
    from the session cookie in one query."""

    session_id: str
    player_id: str
    team_id: str
    display_name: str
    event_id: str


def issue_player_session(
    conn: sqlite3.Connection,
    *,
    player_id: str,
    device_label: str,
    user_agent: str,
) -> str:
    """Mint a session row and return the bearer token (the cookie value).
    The token is shown to the client exactly once, as the Set-Cookie;
    the DB keeps only its hash."""
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    conn.execute(
        "INSERT INTO session (id, token_hash, player_id, device_label,"
        " user_agent, created_at, last_seen_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            ids.new_id(),
            _hash_token(token),
            player_id,
            device_label,
            user_agent,
            now,
            now,
        ),
    )
    return token


def _live_session_guard(table: str, session_id: str, ttl: int):
    """Return a check that re-reads ``session_id`` on the writer.

    ``current_player``/``current_moderator`` read on the reader, which
    serves the last committed snapshot. A revocation that commits after
    that read but before a handler's write would otherwise go unseen, so
    ``db.locked_transaction`` re-runs this on the writer first. The TTL is
    deterministic from ``created_at``, so it is checked here too for the
    same reason: a handler must not write for a session that has expired
    since the reader read."""

    def guard(conn: sqlite3.Connection) -> None:
        row = conn.execute(
            f"SELECT revoked_at, created_at FROM {table} WHERE id = ?", (session_id,)
        ).fetchone()
        if (
            row is None
            or row["revoked_at"] is not None
            or _expired(row["created_at"], ttl)
        ):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "not_authenticated",
                    "message": "Your session was revoked; join again.",
                },
            )

    return guard


def current_player(request: Request) -> PlayerContext | None:
    """Resolve the session cookie to a live player context.

    Also maintains ``last_seen_at`` — throttled to one write per minute
    (schema invariant) so every authenticated request doesn't generate
    a write. A revoked, expired, or unknown token resolves to None, never
    an error page — the client routes to the join screen."""
    token = request.cookies.get(PLAYER_COOKIE_NAME)
    if not token:
        return None
    conn = reader(request)
    ttl = request.app.state.session_ttl
    row = conn.execute(
        "SELECT s.id AS session_id, s.created_at, s.last_seen_at, s.revoked_at,"
        "       p.id AS player_id, p.display_name, p.team_id, t.event_id"
        " FROM session s"
        " JOIN player p ON p.id = s.player_id"
        " JOIN team t ON t.id = p.team_id"
        " WHERE s.token_hash = ?",
        (_hash_token(token),),
    ).fetchone()
    if row is None or row["revoked_at"] is not None or _expired(row["created_at"], ttl):
        return None
    # Writes must re-check this on the writer: the reader read above is a
    # committed snapshot, so a revocation can commit before the handler
    # writes (ADR 0013).
    request.state.session_guard = _live_session_guard("session", row["session_id"], ttl)
    now = int(time.time())
    if now - row["last_seen_at"] >= LAST_SEEN_THROTTLE_SECONDS:
        # Locked: this write must never commit another request's open
        # transaction (ADR 0004 atomicity — see locked_transaction).
        with locked_transaction(request) as writer:
            writer.execute(
                "UPDATE session SET last_seen_at = ? WHERE id = ?",
                (now, row["session_id"]),
            )
    return PlayerContext(
        session_id=row["session_id"],
        player_id=row["player_id"],
        team_id=row["team_id"],
        display_name=row["display_name"],
        event_id=row["event_id"],
    )


def require_player(request: Request) -> PlayerContext:
    """FastAPI dependency: 401 unless the request is an authed player."""
    ctx = current_player(request)
    if ctx is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "not_authenticated", "message": "Join the event first."},
        )
    return ctx


def revoke_player_session(conn: sqlite3.Connection, session_id: str) -> None:
    """Stamp revoked_at. Idempotent — re-revoking is a no-op because the
    moderator 'clear devices' flow (stretch) may batch-revoke."""
    conn.execute(
        "UPDATE session SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
        (int(time.time()), session_id),
    )


# ── Moderator sessions ────────────────────────────────────────────────


@dataclass
class ModeratorContext:
    """What a moderator route needs: who they are and which event's
    queue they're working, resolved from the session cookie."""

    session_id: str
    moderator_id: str
    event_id: str
    label: str


def issue_moderator_session(
    conn: sqlite3.Connection,
    *,
    moderator_id: str,
) -> str:
    """Mint a moderator_session row and return the bearer token. Same
    at-rest rule as player sessions: only the SHA-256 hash is stored
    (moderator_session table, schema.md)."""
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    conn.execute(
        "INSERT INTO moderator_session (id, token_hash, moderator_id,"
        " created_at, last_seen_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (ids.new_id(), _hash_token(token), moderator_id, now, now),
    )
    return token


def current_moderator(request: Request) -> ModeratorContext | None:
    """Resolve the mod cookie to a live moderator context, with the
    same throttled last_seen_at write and TTL as player sessions."""
    token = request.cookies.get(MOD_COOKIE_NAME)
    if not token:
        return None
    conn = reader(request)
    ttl = request.app.state.session_ttl
    row = conn.execute(
        "SELECT s.id AS session_id, s.created_at, s.last_seen_at, s.revoked_at,"
        "       m.id AS moderator_id, m.event_id, m.label"
        " FROM moderator_session s"
        " JOIN moderator m ON m.id = s.moderator_id"
        " WHERE s.token_hash = ?",
        (_hash_token(token),),
    ).fetchone()
    if row is None or row["revoked_at"] is not None or _expired(row["created_at"], ttl):
        return None
    # Same writer-side re-check as current_player (ADR 0013).
    request.state.session_guard = _live_session_guard(
        "moderator_session", row["session_id"], ttl
    )
    now = int(time.time())
    if now - row["last_seen_at"] >= LAST_SEEN_THROTTLE_SECONDS:
        # Same lock rule as current_player: never commit a peer's
        # in-flight mutation (ADR 0004).
        with locked_transaction(request) as writer:
            writer.execute(
                "UPDATE moderator_session SET last_seen_at = ? WHERE id = ?",
                (now, row["session_id"]),
            )
    return ModeratorContext(
        session_id=row["session_id"],
        moderator_id=row["moderator_id"],
        event_id=row["event_id"],
        label=row["label"],
    )


def require_moderator(request: Request) -> ModeratorContext:
    """FastAPI dependency: 401 unless the request is an authed
    moderator. Every /api/mod route lists this."""
    ctx = current_moderator(request)
    if ctx is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "not_authenticated",
                "message": "Moderator login required.",
            },
        )
    return ctx
