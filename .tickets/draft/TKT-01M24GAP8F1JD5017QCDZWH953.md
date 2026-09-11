---
schema: 3
id: TKT-01M24GAP8F1JD5017QCDZWH953
title: Run the production deployment and restore drill
type: task
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - readiness
  - operations
  - deployment
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies:
  - TKT-01M24G72HQ8MYGG5QKGW3SZ252
  - TKT-01M24G8XW0YGP1Y4EHNXT7M0HF
blocks_on: none
references:
  - ref: runbook:production-smoke
    path: deploy/RUNBOOK.md
  - ref: plan:deployment-verification
    path: docs/build-plan.md
  - ref: implementation:compose
    path: compose.yml
claim: null
archive: null
created_at: 2026-09-10T01:53:44Z
updated_at: 2026-09-10T17:29:06Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The local container and compose recipes have verified smoke coverage, but the project still needs the production pre-party check described by docs/build-plan.md and deploy/RUNBOOK.md. Run the target deployment before the first event and preserve the evidence in the ticket and runbook.

## Acceptance criteria

- [ ] The target deployment reports healthy status and serves the built PWA, API, and SSE endpoint through the documented access path.
- [ ] A backup created while the app is live restores into a separate test location and contains the expected SQLite data and photo files.
- [ ] The full runbook smoke passes with two players, upload, submission, each verdict type, strike issue and reversal, round close, and final standings.
- [ ] The ticket records the verified commands, host-specific differences, and any follow-up defects without adding secrets or player photos to Git.

## Definition of done

- [ ] deploy/RUNBOOK.md contains only commands that were actually run and verified.
- [ ] A restore result and smoke result are attached as ticket notes or durable local evidence.

## Implementation plan

Deploy the verified recipe on the target host, configure credentials without committing them, execute an online backup and restore drill, then run the full smoke walkthrough through the real access path and reverse proxy.
