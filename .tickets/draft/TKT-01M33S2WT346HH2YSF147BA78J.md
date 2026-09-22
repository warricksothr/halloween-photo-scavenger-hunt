---
schema: 3
id: TKT-01M33S2WT346HH2YSF147BA78J
title: Add an operator diagnostics command and RUNBOOK queries
type: task
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - operations
  - tooling
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies:
  - TKT-01M33S2WMWE4QWMAWRXP1A1ZTR
  - TKT-01M33S2WP0F879M8AKQXVS7HRZ
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-22T05:23:13Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The operator has journalctl and sqlite3 but no single command that answers whether the system is healthy, what failed last, or who is stuck. Add a python -m app.diagnostics command with summary and errors views that reads the database directly, and document the journald and request-id queries in the RUNBOOK.

## Acceptance criteria

- [ ] python -m app.diagnostics prints a health summary (db, migrations, disk, counts, recent audit) and a recent-error view.
- [ ] The command works against the deployed data directory without starting the server.
- [ ] The RUNBOOK documents the commands and the request-id search.
