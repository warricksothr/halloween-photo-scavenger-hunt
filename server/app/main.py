"""Application factory and router registration.

Routers arrive increment by increment (docs/build-plan.md); this file is
where each one is registered. Increment 2 adds the admin/events router.

The factory takes everything the app needs that varies by environment —
the DB path (tests use a temp file) and the admin credentials (tests
mint a throwaway hash; production reads env vars) — so no test ever
touches real config or the real ``data/`` directory.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from app import db as db_module
from app import events, evidence, leaderboard, mod, players, sse, state, submissions

# The production frontend is the Vite build at web/dist (built with
# `npm run build`; NOT gitignored artifacts in the repo — the deploy
# recipe builds it on the host). In development this directory may not
# exist and Vite serves the app on :5173 with /api proxied here, so
# static mounting is skipped entirely when the directory is absent.
DEFAULT_STATIC_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"


def create_app(
    db_path: Path | str = db_module.DEFAULT_DB_PATH,
    admin_config: tuple[str, str] | None = None,
    cookie_secure: bool = True,
    photos_dir: Path | None = None,
    static_dir: Path | str | None = DEFAULT_STATIC_DIR,
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

    # Photos live beside the DB by default (data/photos/ — gitignored);
    # tests inject their own temp dir so no test writes real files.
    if photos_dir is None:
        photos_dir = Path(db_path).parent / "photos"

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Iterator[None]:
        conn = db_module.connect(db_path)
        db_module.apply_migrations(conn)
        app.state.db = conn
        app.state.admin_config = admin_config
        app.state.admin_sessions = set()  # in-memory; auth.py explains why
        app.state.cookie_secure = cookie_secure
        app.state.photos_dir = photos_dir
        # The broker captures the running loop: sync endpoints publish
        # from the threadpool, and asyncio queues can only be fed from
        # the loop's thread (see app/sse.py).
        app.state.sse_broker = sse.SseBroker(asyncio.get_running_loop())
        # Leaderboard-delta throttle (api.md: ≥5s apart per event). A
        # verified-verdict burst during a rush must not fan a standings
        # re-render per verdict; the snapshot stays the truth on any
        # reconnect regardless.
        app.state.leaderboard_last_sent = {}
        yield
        conn.close()

    app = FastAPI(title="Arkham Hunt", lifespan=lifespan)
    app.include_router(events.router)
    app.include_router(players.router)
    app.include_router(state.router)
    app.include_router(evidence.router)
    app.include_router(submissions.router)
    app.include_router(mod.router)
    app.include_router(leaderboard.router)
    app.include_router(sse.router)

    @app.get("/api/health")
    def health(request: Request) -> dict[str, object]:
        conn: sqlite3.Connection = request.app.state.db
        version = conn.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        return {"status": "ok", "schema_version": version}

    if static_dir is not None and Path(static_dir).is_dir():
        _mount_spa(app, Path(static_dir))

    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Serve the built PWA with an SPA fallback.

    Registered LAST so every /api route above wins. The fallback exists
    because the join and mod links live in the URL path
    (`/j/<code>`, `/m/<code>` — design.md Hosting & access): opening a
    QR link hits uvicorn directly, and the app shell parses the code
    out of the path itself.

    Caching: Vite hashes asset filenames (assets/*), so those are
    immutable forever; index.html, sw.js, and the manifest must
    revalidate every load or a deploy would strand players on a stale
    shell (and a stale service worker).
    """
    root = static_dir.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        # An unmatched /api path is a 404 in JSON, never the HTML
        # shell — a client typo should fail loudly, not parse HTML.
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={
                "error": "not_found", "message": "No such endpoint."})
        candidate = (root / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            immutable = "assets" in candidate.relative_to(root).parts
            return FileResponse(candidate, headers={"Cache-Control": (
                "public, max-age=31536000, immutable"
                if immutable else "no-cache")})
        # /j/<code>, /m/<code>, / itself: the app shell decides.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


# No module-level `app = create_app()`: constructing at import time would
# require admin credentials in every context that imports this module
# (tests, tooling). Run with uvicorn's factory mode instead:
#   uvicorn app.main:create_app --factory --reload
# with ARKHAM_ADMIN_USERNAME / ARKHAM_ADMIN_PASSWORD_HASH set.
