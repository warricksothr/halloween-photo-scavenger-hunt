---
schema: 3
id: TKT-01M26C6XS5X4BS67WHGR58TXDG
title: Measure Python coverage and add static checks
type: task
status: done
status_reason: null
priority: high
due_on: null
labels:
  - testing
  - tooling
  - quality
  - backend
assignees: []
milestone: null
parent: TKT-01M26C4XP6H6F83WTZGB6DXE6S
origin: null
dependencies:
  - TKT-01M26C6XRXRN4METKK3KBG1736
blocks_on: none
references:
  - ref: server:test-config
    path: server/pyproject.toml
  - ref: server:test-suite
    path: server/tests
  - ref: plan:quality-command
    path: docs/build-plan.md
claim: null
archive: null
created_at: 2026-09-10T19:20:15Z
updated_at: 2026-09-10T21:02:41Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The backend has broad API tests but no coverage report, branch measurement, linter, or formatter check. Add a maintainable local quality command that reports missing server paths and catches simple defects before review.

## Acceptance criteria

- [x] The server quality command reports line and branch coverage for app/ and names missing lines in the terminal output.
- [x] The coverage threshold is explicit, justified by the measured baseline, and enforced in the command.
- [x] Ruff checks the server package and tests for lint and formatting errors.
- [x] The command works from a fresh documented virtual environment and leaves no coverage database or generated report in Git.

## Definition of done

- [ ] The command is documented beside the existing pytest command.
- [ ] Coverage exclusions are narrow and explain generated, migration, or unreachable code instead of masking application paths.
- [ ] The first baseline report is recorded in the ticket.

## Implementation plan

Add pytest-cov or coverage for branch-aware server measurement, run it once to establish the real baseline, choose an explicit threshold from that baseline and risk, add Ruff lint and format checks, and document one command that runs them with pytest.

## Notes

**agent:terva/mieli** at 2026-09-10T21:02:22Z

Implemented the backend quality gate. `server/pyproject.toml` now includes pytest-cov and Ruff, branch-aware coverage with `show_missing = true`, a `fail_under = 90` threshold justified by the 93.29% baseline, and explicit E/F/I lint rules. `scripts/check-server.sh` runs pytest with coverage, Ruff lint, and Ruff format checks; it sends coverage data to a temporary directory and disables Ruff cache writes. The existing 32 Python files were formatted and the six pre-existing lint findings were corrected. Fresh environment verification: `133 passed`, `93.29%` coverage, Ruff checks passed, and no repository coverage or cache artifacts remained. The quality command is documented in `AGENTS.md` and `docs/progress.md`.

**agent:terva/mieli** at 2026-09-10T21:02:28Z

Task worklog for this ticket, from the session task board.

### Tasks

- [x] task-18 The server quality command reports line and branch coverage for app/ and names missing lines in the terminal output. — Added `scripts/check-server.sh`. It runs pytest-cov with `--cov-branch`, `--cov-report=term-missing`, and the app source path. The verified report lists line/branch columns and uncovered lines for each module, including `TOTAL 93%` and the named missing-line entries.
- [x] task-19 The coverage threshold is explicit, justified by the measured baseline, and enforced in the command. — Configured `fail_under = 90` in `[tool.coverage.report]`, documented that the branch-aware baseline is 93%, and passed `--cov-fail-under=90` in `scripts/check-server.sh`. The verified baseline reports `Total coverage: 93.29%`, so the 90% floor leaves three percentage points for new paths without disabling enforcement.
- [x] task-20 Ruff checks the server package and tests for lint and formatting errors. — Configured Ruff in `server/pyproject.toml` with explicit Python target and E/F/I lint rules. `scripts/check-server.sh` runs `ruff check --no-cache server/app server/tests` and `ruff format --check --no-cache server/app server/tests`; both pass across all 32 server Python files.
- [x] task-21 The command works from a fresh documented virtual environment and leaves no coverage database or generated report in Git. — Created a fresh `/tmp/arkham-quality-venv`, installed `-e 'server[dev]'`, and ran `PYTHON=... RUFF=... bash scripts/check-server.sh`: 133 tests passed, 93.29% coverage, Ruff lint/format passed. The script uses a temporary `COVERAGE_FILE`, `--no-cache`, and an EXIT trap; repository checks confirmed no `.coverage`, `.ruff_cache`, or server cache remained.
