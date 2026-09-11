---
schema: 3
id: TKT-01M26C6XRXRN4METKK3KBG1736
title: Remove test-suite deprecation warnings
type: chore
status: done
status_reason: null
priority: high
due_on: null
labels:
  - testing
  - maintenance
  - quality
assignees: []
milestone: null
parent: TKT-01M26C4XP6H6F83WTZGB6DXE6S
origin: null
dependencies: []
blocks_on: none
references:
  - ref: server:dependencies
    path: server/pyproject.toml
  - ref: server:test-fixtures
    path: server/tests/conftest.py
  - ref: implementation:image-hash
    path: server/app/images.py
claim: null
archive: null
created_at: 2026-09-10T19:20:15Z
updated_at: 2026-09-10T20:49:16Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The current 133-test suite passes but emits 89 warnings. Starlette reports a TestClient/httpx compatibility deprecation, and Pillow reports that Image.getdata will change before Pillow 14. Warning output currently hides new regressions and weakens the signal from CI.

## Acceptance criteria

- [x] The normal server test command completes without the current Starlette/httpx and Pillow deprecation warnings.
- [x] The supported dependency versions and any compatibility constraint are recorded in server/pyproject.toml or the maintainer documentation.
- [x] A warning introduced by application or test code fails the quality command instead of being silently filtered.
- [x] All existing server tests still pass.

## Definition of done

- [ ] The warning-free command is the command used by later coverage and CI tickets.
- [ ] No warning filter hides the two existing warnings or all warnings globally.
- [ ] The change records why the chosen dependency versions are supported.

## Implementation plan

Identify the supported FastAPI, Starlette, httpx, and Pillow combinations, update code or dependency pins deliberately, replace deprecated Pillow calls, and make the normal test command fail on unexpected warnings without blanket suppression.

## Notes

**agent:terva/mieli** at 2026-09-10T20:48:50Z

Implemented warning cleanup. `server/app/images.py` now reads the mode-L hash pixels with `tobytes()`, which works with the Pillow >=10 baseline without the Pillow 12 `getdata()` deprecation. `server/pyproject.toml` now installs `httpx2>=2.0,<3.0` for Starlette 1.x TestClient, caps AnyIO at `<4.15` for Starlette 1.6's deprecated portal import, and sets pytest `filterwarnings = ["error"]` so new warnings fail instead of being filtered. Fresh installs and the local constrained environment pass `server/.venv/bin/python -m pytest server -q`: 133 passed. `-W default` also reports no warnings; Pillow 10.0's evidence tests pass 11/11.

**agent:terva/mieli** at 2026-09-10T20:49:09Z

Task worklog for this ticket, from the session task board.

### Tasks

- [x] task-14 The normal server test command completes without the current Starlette/httpx and Pillow deprecation warnings. — Replaced Pillow's deprecated `Image.getdata()` with the compatible `Image.tobytes()` path in `server/app/images.py`. A fresh `server[dev]` environment ran `python -m pytest server -q -W default` with 133 passed and no warnings.
- [x] task-15 The supported dependency versions and any compatibility constraint are recorded in server/pyproject.toml or the maintainer documentation. — Recorded the compatibility contract in `server/pyproject.toml`: `httpx2>=2.0,<3.0` for Starlette 1.x TestClient and `anyio>=4.0,<4.15` because Starlette 1.6 accesses the deprecated AnyIO portal alias at 4.15. A fresh install resolved FastAPI 0.141.1, Starlette 1.6.0, httpx2 2.12.0, AnyIO 4.14.2, and Pillow 12.3.0.
- [x] task-16 A warning introduced by application or test code fails the quality command instead of being silently filtered. — Added `filterwarnings = ["error"]` to `[tool.pytest.ini_options]` in `server/pyproject.toml`. The fresh-environment normal command passed only after the dependency and Pillow fixes, so future warnings fail pytest rather than being filtered or ignored.
- [x] task-17 All existing server tests still pass. — Updated the local test environment to the declared AnyIO constraint and ran `server/.venv/bin/python -m pytest server -q`: 133 passed. Collection remains 133 tests, and `git diff --check` passes.
