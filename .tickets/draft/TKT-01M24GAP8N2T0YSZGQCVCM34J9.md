---
schema: 3
id: TKT-01M24GAP8N2T0YSZGQCVCM34J9
title: Prove a second theme pack without a code fork
type: task
status: draft
status_reason: null
priority: low
due_on: null
labels:
  - theme
  - frontend
  - readiness
  - stretch
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies:
  - TKT-01M24G5WE6X3996ZZBVYNCN1KR
blocks_on: none
references:
  - ref: requirement:theme-packs
    path: docs/design.md
  - ref: implementation:theme-system
    path: web/src/theme.js
  - ref: theme:arkham
    path: web/src/themes/arkham
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

The design requires future events to select a frontend theme pack over the neutral game core. The Arkham pack is the only implemented pack today. When a second event needs a different presentation, prove the boundary with a small second pack rather than branching game logic.

## Acceptance criteria

- [ ] A second theme pack loads through the existing frontend theme contract without changing game-flow code.
- [ ] The join, lobby, riddle, drawer, submission, standings, team, and verdict views render with the second pack.
- [ ] A build and focused browser or integration smoke demonstrate that the Arkham pack still works unchanged.
- [ ] The theme contract and any newly discovered neutral-core boundary are documented.

## Definition of done

- [ ] The new pack contains no copyrighted reference images in Git.
- [ ] Any missing theme key fails clearly during development instead of silently changing game behavior.

## Implementation plan

Inventory visible player-facing copy and theme tokens, add a second theme pack using the existing loading contract, exercise the main player and moderator flows, and keep event, submission, moderation, conduct, and leaderboard behavior in the neutral core.
