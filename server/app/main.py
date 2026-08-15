"""Application factory and router registration.

Routers arrive increment by increment (docs/build-plan.md); this file is
where each one is registered. Increment 2 adds the admin/events router.

The factory takes everything the app needs that varies by environment —
the DB path (tests use a temp file) and the admin credentials (tests
mint a throwaway hash; production reads env vars) — so no test ever
touches real config or the real ``data/`` directory.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from app import db as db_module
from app import events


def create_app(
    db_path: Path | str = db_module.DEFAULT_DB_PATH,
    admin_config: tuple[str, str] | None = None,
    cookie_secure: bool = True,
) -> FastAPI:
    """Build the app around one database and one admin credential pair.

    ``admin_config`` is (username, argon2id password hash). In production
    it comes from ``ARKHAM_ADMIN_USERNAME`` / ``ARKHAM_ADMIN_PASSWORD_HASH``;
    if neither the argument nor the env vars provide it, the app refuses
    to start — silently running with no admin path is how a party app
    ends up unopenable on the night.
    """
    if admin_config is None:
        username = os.environ.get("ARKHAM_ADMIN_USERNAME")
        password_hash = os.environ.get("ARKHAM_ADMIN_PASSWORD_HASH")
        if username and password_hash:
            admin_config = (username, password_hash)
    if admin_config is None:
        raise RuntimeError(
            "Admin credentials not configured: set ARKHAM_ADMIN_USERNAME "
            "and ARKHAM_ADMIN_PASSWORD_HASH (generate the hash with "
            "`python -m app.security '<password>'`), or pass admin_config "
            "to create_app()."
        )
    # cookie_secure=False exists for tests and plain-HTTP local dev only —
    # browsers refuse to send Secure cookies over http, which is correct
    # behavior in production (the VPS terminates TLS) and a silent 401
    # factory everywhere else.

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Iterator[None]:
        conn = db_module.connect(db_path)
        db_module.apply_migrations(conn)
        app.state.db = conn
        app.state.admin_config = admin_config
        app.state.admin_sessions = set()  # in-memory; auth.py explains why
        app.state.cookie_secure = cookie_secure
        yield
        conn.close()

    app = FastAPI(title="Arkham Hunt", lifespan=lifespan)
    app.include_router(events.router)

    @app.get("/api/health")
    def health(request: Request) -> dict[str, object]:
        conn: sqlite3.Connection = request.app.state.db
        version = conn.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        return {"status": "ok", "schema_version": version}

    return app


# No module-level `app = create_app()`: constructing at import time would
# require admin credentials in every context that imports this module
# (tests, tooling). Run with uvicorn's factory mode instead:
#   uvicorn app.main:create_app --factory --reload
# with ARKHAM_ADMIN_USERNAME / ARKHAM_ADMIN_PASSWORD_HASH set.
