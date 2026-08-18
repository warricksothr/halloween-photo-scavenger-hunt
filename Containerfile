# Containerfile — the whole party in one image (web build + server).
#
# Multi-stage: stage 1 builds web/dist with Node, stage 2 is the
# slim Python runtime. Works identically under podman and docker
# (`podman build` and `docker build` parse the same syntax).
#
# Layout note (the why): main.py derives DEFAULT_DB_PATH and
# DEFAULT_STATIC_DIR from the package's __file__, assuming the repo
# layout — server/app beside web/dist, data/ at the repo root. The
# image keeps that layout exactly, with an editable install so `app`
# resolves to /srv/arkham/server/app. That makes the runtime's data
# directory /srv/arkham/data — the one path a volume must cover to
# persist the night's state (DB + photos).

# ── Stage 1: frontend build ──
FROM node:20-alpine AS web
WORKDIR /build/web
# Lockfile first so dependency layers cache across source-only changes.
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ── Stage 2: runtime ──
FROM python:3.12-slim AS runtime
WORKDIR /srv/arkham
COPY server/ ./server/
# Editable install: deps land in site-packages while `app` stays at
# /srv/arkham/server/app, keeping the __file__-relative data/static
# paths intact (see the layout note above).
RUN pip install --no-cache-dir -e ./server
COPY --from=web /build/web/dist ./web/dist
# Run unprivileged; the data dir must be writable by the app user.
RUN useradd --system --uid 1000 --home /srv/arkham arkham \
    && mkdir -p /srv/arkham/data \
    && chown -R arkham:arkham /srv/arkham/data
USER arkham
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
