"""Application factory and router registration.

Routers arrive increment by increment (docs/build-plan.md); this file is
where each one is registered. For now: the health check, which doubles
as a smoke test that the database migrated and answers a query.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from app import db as db_module


def create_app(db_path: Path | str = db_module.DEFAULT_DB_PATH) -> FastAPI:
    """Build the app around one database.

    Tests pass their own path (a temp file) so they never touch the real
    ``data/`` directory; production uses the default.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Iterator[None]:
        conn = db_module.connect(db_path)
        db_module.apply_migrations(conn)
        app.state.db = conn
        yield
        conn.close()

    app = FastAPI(title="Arkham Hunt", lifespan=lifespan)

    @app.get("/api/health")
    def health(request: Request) -> dict[str, object]:
        conn: sqlite3.Connection = request.app.state.db
        version = conn.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        return {"status": "ok", "schema_version": version}

    return app


app = create_app()
