# 0010. Run one locked fast gate in CI and keep long smokes explicit

Date: 2026-09-10
Status: accepted

## Context

The repository has four useful test layers. Server tests and Ruff, the isolated
backup check, frontend unit tests, and the frontend build finish quickly and
need no credentials or host services. The built-PWA browser smoke needs a
Chromium installation. The container smoke needs Podman, image builds, and
host networking. Making the latter two required in the same job would make the
pull-request gate depend on runner services that the repository cannot provide.

The local commands also need one owner. If CI spells out individual commands
while a maintainer runs a different sequence, the two quality paths can drift.

## Decision

`server/uv.lock` pins the Python application and development dependencies.
`scripts/check-quality.sh` is the shared fast command. It performs a locked
`uv sync`, runs `scripts/check-server.sh` and `scripts/check-deploy.sh`, then
runs `npm ci`, the frontend unit tests, and the production build.

`.github/workflows/quality.yml` runs that script on pull requests and pushes to
`main`. GitHub Actions caches the uv and npm dependency stores using
`server/uv.lock` and `web/package-lock.json`. The workflow uploads any browser,
deployment, or coverage diagnostics that exist when a step fails; the failed
step's test and coverage output remains in the job log.

The workflow documents the browser and Podman smokes through
`docs/impl/testing.md`, but does not run them as hidden required jobs. Maintainers
run those longer gates explicitly when their required tools are available.

## Consequences

- Pull requests and `main` pushes use the same fast command as local checks.
- Fast CI has no production credentials, uploaded photos, SQLite database, or
  repository secret dependency.
- A runner without Chromium or Podman can still enforce the application and
  build quality gate.
- Browser and deployment failures remain reproducible commands rather than
  silently absent checks, and their ignored artifact paths are named in the
  workflow and testing guide.
