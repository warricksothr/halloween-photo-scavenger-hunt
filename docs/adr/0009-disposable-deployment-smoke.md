# 0009. Keep deployment checks disposable and layered

Date: 2026-09-10
Status: accepted

## Context

The deployment recipe has two different costs. The backup and restore path can
run on every developer machine without a container runtime. The container path
needs Podman, a working image builder, host networking, and time to build the
PWA image. Combining them would either make the fast gate unavailable on a
normal Python checkout or make the container requirement implicit.

The backup script also points at the repository's live `data/` directory by
default. A regression test must use the same online SQLite backup code without
touching that directory or any event photos.

## Decision

`deploy/backup.sh` accepts the `ARKHAM_DATA_DIR` environment variable as an
isolated source-root override. Production keeps the existing `data/` default.
The fast `scripts/check-deploy.sh` command runs shell syntax checks and
`server/tests/test_deployment_checks.py`. That test creates a live temporary
SQLite database and photo tree, runs the backup with a PATH that has no
`sqlite3` executable, extracts the archive into a second directory, and checks
schema version, a representative event, foreign-key enforcement, and photo
bytes.

`scripts/smoke-container.sh` is an explicit Podman gate. It builds with
`--format docker`, runs a uniquely named image, container, and volume, tests
health, admin login, event setup, plain-HTTP player join, a synthetic photo
upload, and an SSE heartbeat, then removes the disposable resources. If the
smoke fails, it removes the runtime resources but preserves container logs,
inspect output, and the command transcript under ignored
`.deploy-smoke-results/`.

## Consequences

- `bash scripts/check-deploy.sh` stays suitable for the always-on local gate.
- `bash scripts/smoke-container.sh` remains visible and runnable, but it does
  not silently become a CI requirement for runners without Podman.
- A failed container run leaves diagnostics without leaving credentials,
  uploaded photos, containers, volumes, or smoke images behind.
- The `ARKHAM_DATA_DIR` override is test infrastructure, not a replacement for
  the production data layout.
