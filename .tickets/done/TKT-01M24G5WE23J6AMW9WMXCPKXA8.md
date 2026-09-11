---
schema: 3
id: TKT-01M24G5WE23J6AMW9WMXCPKXA8
title: Add player joining and session management
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - mvp
  - backend
  - security
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G5WDX14C8SQHVS2VFWFA9
blocks_on: none
references:
  - ref: git:d87ed15
    path: server/app/players.py
  - ref: progress:increment-3
    path: docs/progress.md
  - ref: contract:api
    path: docs/impl/api.md
claim: null
archive: null
created_at: 2026-09-10T01:51:06Z
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

Backport of Increment 3 from commit d87ed15. Added player join by event code, team-of-one creation, hashed session tokens, httpOnly SameSite cookies, throttled last-seen updates, logout, revocation, and the player authentication dependencies. The increment passed 34 tests and a live join, logout, and revoked-token smoke.

## Acceptance criteria

- [x] A valid event join creates a team-of-one, player, and session in one transaction and records `player.joined`.
- [x] The player session uses an httpOnly SameSite cookie and stores only a hash of the token at rest.
- [x] Player authentication throttles `last_seen_at` writes and supports idempotent logout and revocation with `session.revoked`.
- [x] Tests cover join, throttled activity, logout, and replay of a revoked session.

## Definition of done

- [x] The increment passes its 34 tests.
- [x] A live join, cookie round trip, logout, and revoked-token smoke pass.

## Implementation plan

Completed by extending auth.py and adding the player routes and tests after the event lifecycle was available.
