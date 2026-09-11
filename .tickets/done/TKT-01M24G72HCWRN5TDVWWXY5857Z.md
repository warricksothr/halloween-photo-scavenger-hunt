---
schema: 3
id: TKT-01M24G72HCWRN5TDVWWXY5857Z
title: Add moderator team management
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - stretch
  - backend
  - frontend
  - teams
  - moderation
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G72H6Q21JS87DD59KVE4X
blocks_on: none
references:
  - ref: git:7a25f23
    path: docs/adr/0006-member-removal-parks-on-fresh-team.md
  - ref: progress:moderator-team-management
    path: docs/progress.md
  - ref: design:moderator-teams
    path: docs/design.md
  - ref: contract:api
    path: docs/impl/api.md
  - ref: ui:moderator-mock
    path: docs/impl/mocks/moderator.html
claim: null
archive: null
created_at: 2026-09-10T01:51:45Z
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

Backport of moderator team management from commit 7a25f23. Added the moderator roster view, member removal route, audited removal action, fresh-team parking for removed players, revoked sessions, empty-team standings behavior, and the confirmed removal UI. The increment added six tests and the progress record reports 133 full-suite tests plus a live roster, removal, revoked-session, and audit smoke.

## Acceptance criteria

- [x] Moderators can inspect event-wide team rosters, member activity, open invites, and effective size limits.
- [x] Removing a member writes the audited action, revokes all sessions, and parks the player on a fresh empty team-of-one without orphaning `player.team_id`.
- [x] Existing evidence and submissions remain attached to the old team, and empty old teams remain queryable in standings.
- [x] The console uses a confirmed Remove action and reports the documented not-found and unauthorized cases.

## Definition of done

- [x] Six focused tests plus the full 133-test suite pass.
- [x] Live roster, removal, revoked-session, and audit-row checks pass.

## Implementation plan

Completed by keeping player.team_id non-null and moving a removed player to a fresh empty team while leaving old evidence and submissions attached to the old team.
