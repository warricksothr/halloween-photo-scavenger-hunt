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
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request

COOKIE_NAME = "arkham_admin"


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
