"""Admin authentication.

Per docs/impl/schema.md ("no admin table"): the admin is one human whose
credentials live in server config, so there is no admin row in the
database and no password-set flow in the app — the argon2id hash is
generated offline (``python -m app.security '<password>'``) and passed
to ``create_app`` (production: from ``ARKHAM_ADMIN_USERNAME`` /
``ARKHAM_ADMIN_PASSWORD_HASH`` env vars).

Admin sessions are in-memory on ``app.state``: the ``session`` table
references players and a table for one row is ceremony. A restart logs
the admin out, which a party app with one admin tolerates.

Player sessions (bottom half of this module) are the opposite: DB-backed
from day one (the ``session`` table) because moderation must be able to
list and revoke devices, and because a restart must not log out 30
players mid-party. The bearer token itself is never stored — only its
SHA-256 hash (schema.md hardening note).
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from app import ids

COOKIE_NAME = "arkham_admin"
PLAYER_COOKIE_NAME = "arkham_session"

# Throttle for session.last_seen_at writes (schema invariant: max one
# write per minute per session, so the hot read path doesn't generate a
# write per request).
LAST_SEEN_THROTTLE_SECONDS = 60


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
    """Mint a token and record it. The token is the credential; only the
    token (never a hash — it never leaves the server except as the
    cookie itself, and there is no DB row to leak) is kept in memory."""
    token = secrets.token_urlsafe(32)
    request.app.state.admin_sessions.add(token)
    return token


def revoke_admin_session(request: Request, token: str) -> None:
    request.app.state.admin_sessions.discard(token)


def current_admin(request: Request) -> str | None:
    """Return the admin token if the request carries a live session."""
    token = request.cookies.get(COOKIE_NAME)
    if token and token in request.app.state.admin_sessions:
        return token
    return None


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
        (ids.new_id(), _hash_token(token), player_id, device_label,
         user_agent, now, now),
    )
    return token


def current_player(request: Request) -> PlayerContext | None:
    """Resolve the session cookie to a live player context.

    Also maintains ``last_seen_at`` — throttled to one write per minute
    (schema invariant) so every authenticated request doesn't generate
    a write. A revoked or unknown token resolves to None, never an
    error page — the client routes to the join screen."""
    token = request.cookies.get(PLAYER_COOKIE_NAME)
    if not token:
        return None
    conn: sqlite3.Connection = request.app.state.db
    row = conn.execute(
        "SELECT s.id AS session_id, s.last_seen_at, s.revoked_at,"
        "       p.id AS player_id, p.display_name, p.team_id, t.event_id"
        " FROM session s"
        " JOIN player p ON p.id = s.player_id"
        " JOIN team t ON t.id = p.team_id"
        " WHERE s.token_hash = ?",
        (_hash_token(token),),
    ).fetchone()
    if row is None or row["revoked_at"] is not None:
        return None
    now = int(time.time())
    if now - row["last_seen_at"] >= LAST_SEEN_THROTTLE_SECONDS:
        conn.execute("UPDATE session SET last_seen_at = ? WHERE id = ?",
                     (now, row["session_id"]))
        conn.commit()
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


def revoke_player_session(
    conn: sqlite3.Connection, session_id: str
) -> None:
    """Stamp revoked_at. Idempotent — re-revoking is a no-op because the
    moderator 'clear devices' flow (stretch) may batch-revoke."""
    conn.execute(
        "UPDATE session SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
        (int(time.time()), session_id),
    )
