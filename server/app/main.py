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
import secrets
import threading
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx2
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from app import (
    auth,
    cache,
    csrf,
    diagnostics,
    errors,
    events,
    evidence,
    leaderboard,
    limits,
    metrics,
    mod,
    oidc,
    players,
    ratelimit,
    sse,
    state,
    storage,
    submissions,
    teams,
)
from app import db as db_module
from app.logging import (
    REQUEST_ID_HEADER,
    RequestLogMiddleware,
    configure_logging,
    log_unhandled_exception,
)

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
    oidc_config: oidc.OidcConfig | None = None,
    oidc_transport: httpx2.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Build the app around one database and one admin credential pair.

    ``admin_config`` is (username, argon2id password hash). In production
    it comes from ``ARKHAM_ADMIN_USERNAME`` / ``ARKHAM_ADMIN_PASSWORD_HASH``;
    if neither the argument nor the env vars provide it, the app refuses
    to start — silently running with no admin path is how a party app
    ends up unopenable on the night.

    ``oidc_config`` is the SSO issuer/client; unlike the admin credential
    it is optional. Unset (and unset in the env) means the SSO routes
    answer 503 and the password login is the only way in — the app must
    start either way.
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
    # ARKHAM_COOKIE_SECURE=false exists for plain-HTTP runs (the local
    # container recipe, LAN party hosts with no TLS). Browsers refuse to
    # send Secure cookies over http, which is correct in production (the
    # VPS terminates TLS) and a silent 401 factory everywhere else —
    # without this toggle a local container could never log in. Tests
    # keep passing the argument; the env var only fills the default.
    if cookie_secure and os.environ.get("ARKHAM_COOKIE_SECURE", "").lower() in {
        "0",
        "false",
        "no",
    }:
        cookie_secure = False

    # Photos live beside the DB by default (data/photos/ — gitignored);
    # tests inject their own temp dir so no test writes real files.
    if photos_dir is None:
        photos_dir = Path(db_path).parent / "photos"

    # Uploads refuse below this free-space floor (app/storage.py). Read
    # once here so the env var is a process setting, like the TTL — and so
    # the middleware below can be built with it.
    min_free_bytes = storage.configured_min_free_bytes()

    # SSO is optional, so an unset config is the normal local case rather
    # than the startup error a missing admin credential is.
    if oidc_config is None:
        oidc_config = oidc.OidcConfig.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Iterator[None]:
        conn = db_module.connect(db_path)
        db_module.apply_migrations(conn)
        # A second connection for reads (ADR 0013): WAL isolates
        # connections, not statements, so an unlocked SELECT on the writer
        # could still observe another request's open transaction.
        read_conn = db_module.connect(db_path)
        app.state.db = conn
        app.state.read_db = read_conn
        # One statement at a time on the reader: concurrent threads on one
        # sqlite3 connection corrupt each other's statements (ADR 0030).
        app.state.read_lock = threading.Lock()
        # Kept for the readiness probe: disk_usage needs the path, and
        # uptime is measured from boot (app/diagnostics.py).
        app.state.db_path = Path(db_path)
        app.state.started_at = time.monotonic()
        # In-process counters (app/metrics.py). The writer lock is wrapped
        # so its contention is observable; every ``with app.state.db_lock``
        # site is measured without changing those sites.
        app.state.metrics = app_metrics
        # Sync endpoints share one writer. Race-sensitive mutation
        # handlers hold this reentrant lock for the full request, then
        # acquire it again around their transaction blocks.
        app.state.db_lock = metrics.MeteredLock(threading.RLock(), app.state.metrics)
        app.state.admin_config = admin_config
        app.state.admin_sessions = {}  # in-memory; auth.py explains why
        # Optional standing token for scripted admin access (auth.py).
        # Read once here so it is a process setting; unset means off.
        app.state.admin_api_token = auth.configured_api_token()
        # Session lifetime for every kind of session (auth.py). Read once
        # here so the env var is a process setting, not a per-request one.
        app.state.session_ttl = auth.configured_session_ttl()
        app.state.cookie_secure = cookie_secure
        # SSO: the provider caches discovery and JWKS; identities are the
        # in-memory counterpart of admin_sessions (app/oidc.py).
        app.state.oidc = (
            oidc.OidcProvider(oidc_config, transport=oidc_transport)
            if oidc_config is not None
            else None
        )
        app.state.oidc_identities = {}
        # CSRF signing key. Minted per process; a restart invalidates
        # outstanding tokens, which the SPA re-earns on its next safe
        # request. ARKHAM_CSRF_SECRET pins it for a multi-worker run
        # (this deployment is one uvicorn process, so the default is
        # enough — see ADR 0015).
        app.state.csrf_secret = os.environ.get("ARKHAM_CSRF_SECRET", "").encode() or (
            secrets.token_bytes(32)
        )
        # Per-process failure counters for the unauthenticated entry
        # points (app/ratelimit.py, ADR 0015). In-memory on purpose: the
        # deployment is one worker and a restart may as well clear them.
        app.state.rate_limiter = ratelimit.RateLimiter()
        app.state.photos_dir = photos_dir
        # Uploads refuse below this free-space floor (app/storage.py).
        app.state.min_free_bytes = min_free_bytes
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
        read_conn.close()
        conn.close()

    # One structured line per request, with bearer codes redacted and
    # uvicorn's own raw-path access line dropped (app/logging.py).
    configure_logging()

    # Install the error/trace reporter before the app and its routes are
    # built: the FastAPI integration patches the route handler factory, so
    # it only sees routes created afterwards. Inert unless
    # ARKHAM_ERROR_DSN is set, so local runs and tests never send an event
    # (app/errors.py). The env is read here, not at import, so a deploy can
    # set it per process.
    errors.init_error_reporting()

    # Counters live here, not in the lifespan, because the body-limit
    # middleware is built before the lifespan runs and an oversized upload
    # is refused there — the route's own 413 is never reached, so the
    # refuser needs the same counter the route writes to (S2WP review).
    app_metrics = metrics.Metrics()

    app = FastAPI(title="Arkham Hunt", lifespan=lifespan)

    # An unhandled exception is turned into a 500 by ServerErrorMiddleware,
    # which wraps this app's middleware stack — so that response never
    # passes the request log's ``send`` wrapper and would lose the request
    # id. The log middleware puts the id on the scope for this handler.
    def _internal_error(request: Request, exc: Exception) -> JSONResponse:
        log_unhandled_exception(
            exc,
            request_id=getattr(request.state, "request_id", None),
            method=request.method,
            path=getattr(request.state, "redacted_path", None),
            request_secrets=getattr(request.state, "request_secrets", ()),
            include_message=not getattr(request.state, "safe_traceback", False),
        )
        request_id = getattr(request.state, "request_id", None)
        # Tag the scope rather than report here: ServerErrorMiddleware
        # re-raises after this handler returns, and Sentry's ASGI
        # middleware captures exactly one event from that re-raise.
        errors.bind_request_id(request_id)
        body: dict[str, str] = {
            "error": "internal_error",
            "message": "Something went wrong.",
        }
        if request_id:
            body["request_id"] = request_id
        response = JSONResponse(body, status_code=500)
        # ServerErrorMiddleware builds this response outside the user
        # middleware stack, so NoStoreMiddleware never sees it (ADR 0021).
        # Stamp it here for the same reason the layer exists at all: an
        # error body is still per-session and must not be cached.
        if cache.is_api_path(request.url.path):
            response.headers["Cache-Control"] = "no-store"
        if request_id:
            response.headers[REQUEST_ID_HEADER] = request_id
        return response

    app.add_exception_handler(Exception, _internal_error)

    # Middleware is added inner-to-outer: the last one added wraps the
    # rest. The body cap goes on first so an oversized request is refused
    # before CSRF or any route touches it; CSRF sits just inside it. The
    # storage guard sits outside the body cap so a full disk refuses an
    # upload before even the cap reads the body (ADR 0023). The request log
    # goes on last so it wraps both, logs the requests they reject, and
    # measures the whole request.
    app.add_middleware(csrf.CsrfMiddleware)
    app.add_middleware(
        limits.BodyLimitMiddleware,
        on_reject=lambda scope: (
            app_metrics.record_upload("too_large_bytes")
            if scope.get("path") == "/api/evidence"
            else None
        ),
    )
    app.add_middleware(
        storage.StorageGuardMiddleware,
        photos_dir=photos_dir,
        min_free_bytes=min_free_bytes,
        max_bytes=limits.MAX_REQUEST_BYTES,
    )
    app.add_middleware(cache.NoStoreMiddleware)
    app.add_middleware(RequestLogMiddleware)
    app.include_router(events.router)
    app.include_router(oidc.router)
    app.include_router(players.router)
    app.include_router(state.router)
    app.include_router(evidence.router)
    app.include_router(submissions.router)
    app.include_router(mod.router)
    app.include_router(leaderboard.router)
    app.include_router(teams.router)
    app.include_router(sse.router)

    @app.get("/api/health")
    def health(request: Request) -> dict[str, object]:
        conn = db_module.reader(request)
        version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[
            0
        ]
        return {"status": "ok", "schema_version": version}

    # Readiness lives under /api/admin so it is not a public fingerprint:
    # it names the build and counts photos and live clients, which is for
    # the operator, not a stranger. The deploy smoke logs in first.
    @app.get("/api/admin/readyz")
    def readyz(
        request: Request, _: str = Depends(auth.require_admin)
    ) -> dict[str, object]:
        return diagnostics.snapshot(request)

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
            return JSONResponse(
                status_code=404,
                content={"error": "not_found", "message": "No such endpoint."},
            )
        candidate = (root / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            immutable = "assets" in candidate.relative_to(root).parts
            return FileResponse(
                candidate,
                headers={
                    "Cache-Control": (
                        "public, max-age=31536000, immutable"
                        if immutable
                        else "no-cache"
                    )
                },
            )
        # /j/<code>, /m/<code>, / itself: the app shell decides.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


# No module-level `app = create_app()`: constructing at import time would
# require admin credentials in every context that imports this module
# (tests, tooling). Run with uvicorn's factory mode instead:
#   uvicorn app.main:create_app --factory --reload
# with ARKHAM_ADMIN_USERNAME / ARKHAM_ADMIN_PASSWORD_HASH set.
