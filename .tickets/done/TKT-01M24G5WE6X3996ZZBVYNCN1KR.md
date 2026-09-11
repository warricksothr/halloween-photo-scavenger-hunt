---
schema: 3
id: TKT-01M24G5WE6X3996ZZBVYNCN1KR
title: Build the Preact PWA frontend shell
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - mvp
  - frontend
  - theme
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G5WE23J6AMW9WMXCPKXA8
blocks_on: none
references:
  - ref: git:3ed9c5f
    path: web/src/store.js
  - ref: progress:increment-4
    path: docs/progress.md
  - ref: ui:theme-notes
    path: docs/reference/THEME-NOTES.md
  - ref: ui:contracts
    path: docs/impl/ui.md
  - ref: ui:mock-index
    path: docs/impl/mocks/index.html
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

Backport of Increment 4 from commit 3ed9c5f. Added the Vite and Preact PWA, service worker, manifest, Arkham theme pack, snapshot-backed client store, join flow, lobby, and riddle-list shell. The increment passed 37 pytest tests, a green npm build, and an end-to-end Vite proxy smoke.

## Acceptance criteria

- [x] The web package builds as a Preact and Vite PWA with a manifest, service worker, Arkham theme pack, and CSS tokens.
- [x] The client store models boot, join, ready, and error states and uses the state snapshot as its resync source.
- [x] Join, lobby, and riddle-list screens use the real backend endpoints and `/j/<code>` routing.
- [x] The frontend build and an end-to-end join-to-riddle-list smoke pass.

## Definition of done

- [x] Pytest reaches 37 passing tests after the state endpoint lands.
- [x] `npm run build` is green and the Vite proxy smoke completes.

## Implementation plan

Completed by creating the web package and connecting its first screens to the real join and state endpoints.
