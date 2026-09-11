---
schema: 3
id: TKT-01M24G6DRKXP1FKDBEFF1M1VRD
title: Add conduct enforcement and strike controls
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - mvp
  - backend
  - frontend
  - moderation
  - conduct
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G6DRE6AEN9482NVXAW5EB
blocks_on: none
references:
  - ref: git:71ee84e
    path: server/app/conduct.py
  - ref: progress:increment-8
    path: docs/progress.md
  - ref: decision:derived-strikes
    path: docs/adr/0001-derived-strike-state.md
  - ref: decision:audit-log
    path: docs/adr/0004-append-only-audit-log.md
  - ref: design:conduct
    path: docs/design.md
claim: null
archive: null
created_at: 2026-09-10T01:51:24Z
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

Backport of Increment 8 from commit 71ee84e. Added the one-tap INAPPROPRIATE verdict, quarantine, derived strike ladder, cooldown and upload-ban restrictions, notice acknowledgement, host reversal, player-routed strike SSE, moderator confirmation UI, strike history, and the player interstitial. The increment passed 94 pytest tests and a live strike, acknowledgement, reversal, and audit-order smoke.

## Acceptance criteria

- [x] An INAPPROPRIATE action atomically issues the verdict, quarantines evidence, issues the derived strike, and writes the required audit rows.
- [x] The strike ladder derives warning, cooldown, and upload-ban restrictions from non-reversed strikes, and notice acknowledgement is audit-backed and idempotent.
- [x] Hosts can reverse a strike conditionally without un-quarantining evidence.
- [x] Players receive strike SSE and an interstitial, while moderators have a confirmed danger action and strike history.

## Definition of done

- [x] The increment passes 94 pytest tests.
- [x] Live strike, notice acknowledgement, reversal, restriction, and audit-order checks pass.

## Implementation plan

Completed by extending the moderation transaction, deriving restrictions from non-reversed strikes, and adding the conduct UI without placing themed copy on conduct surfaces.
