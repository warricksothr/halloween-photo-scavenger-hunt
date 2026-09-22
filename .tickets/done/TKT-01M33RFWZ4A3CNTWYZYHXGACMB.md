---
schema: 3
id: TKT-01M33RFWZ4A3CNTWYZYHXGACMB
title: Pin the container runtime to uv.lock
type: task
status: done
status_reason: null
priority: high
due_on: null
labels:
  - deployment
  - quality
assignees: []
milestone: null
parent: TKT-01M33RFWERCGE04CK7F44NP313
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T15:47:11Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/harden-runtime-security
  name: ""
extensions: {}
---

## Description

The Containerfile installs the server with pip install -e, which resolves the lower-bound ranges in pyproject.toml and ignores uv.lock. The artifact that runs the party is the only one not pinned, and Pillow behavior is load-bearing.

## Acceptance criteria

- [x] The image installs from the locked dependency set (uv sync --locked or an exported pinned requirements file).
- [x] The built image and CI resolve identical versions.

## Implementation plan

### Approach

1. Commit `server/requirements.lock`, generated with
   `uv export --project server --locked --no-dev --no-emit-project`. Every
   runtime dependency is pinned to one version with a sha256 per artifact.
2. Containerfile: install from that file with
   `pip install --no-cache-dir --require-hashes -r ./server/requirements.lock`,
   then drop the editable install for `ENV PYTHONPATH=/srv/arkham/server`.
   `app` still resolves to `/srv/arkham/server/app`, so the `__file__`-relative
   data/static paths are unchanged, and the image no longer runs pip's build
   isolation (an unpinned setuptools download) to make the package importable.
3. Update the Containerfile layout comment and the matching paragraph in
   `deploy/CONTAINER.md` that call the editable install load-bearing.
4. Guard in `server/tests/test_deployment_checks.py`: the lock is fully pinned
   (`name==version`, no ranges), and when `uv` is on PATH it equals a fresh
   export of `uv.lock`. CI runs `scripts/check-quality.sh`, which has uv, so
   drift fails.

Ticket TKT-01M33RFWJ (CSRF) is not touched.

## Notes

**agent:opencode/harden-runtime-security** at 2026-09-22T15:43:19Z

### Implementation

- Added `server/requirements.lock` (export of `uv.lock`: 34 resolved, 19
  runtime pins, each with sha256 hashes).
- `Containerfile` installs `pip install --no-cache-dir --require-hashes -r
  ./server/requirements.lock` and drops the editable install for
  `ENV PYTHONPATH=/srv/arkham/server`. `app` resolves to the same path, so the
  `__file__`-relative data/static layout is unchanged, and no build-isolation
  setuptools download remains. `deploy/CONTAINER.md` updated to match.
- ADR 0012 records the decision.
- Guard tests in `server/tests/test_deployment_checks.py`: lock is fully
  pinned; versions match `uv.lock`; a fresh `uv export` equals the committed
  file (skipped only where uv is absent — CI has it); Containerfile uses the
  lock and no editable install.

### Evidence

- `podman build --format docker -t arkham-hunt:test .` succeeded; the run logs
  show the 19 pins installed and no setuptools/build step.
- The built image served `{"status":"ok","schema_version":1}` from
  `/api/health`.
- `bash scripts/check-quality.sh` passes (157 server tests, 94.80% coverage,
  ruff clean).

**agent:opencode/harden-runtime-security** at 2026-09-22T15:47:11Z

### Review round 1

PR #8, head `e33b1f0`, base `8a0d600` (`main`). Requested a Terva review with
`request-id=ready-review`; the dispatch returned the documented empty-JSON
error but created
[Actions run #8588](https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/8588)
(id 21891), running at the time of writing. Outcome recorded in a later note.

## Summary

`server/requirements.lock` is the committed hash-pinned export of `uv.lock`,
and `Containerfile` installs from it with `--require-hashes`; `app` rides on
`PYTHONPATH` instead of an editable install, so no unpinned build-isolation
download remains. ADR 0012 records it. Guard tests fail CI on lock drift.
Verified by a podman build that served `/api/health`. Branch:
`t3code/harden-runtime-and-security`.
