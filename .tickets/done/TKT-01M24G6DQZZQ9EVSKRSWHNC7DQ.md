---
schema: 3
id: TKT-01M24G6DQZZQ9EVSKRSWHNC7DQ
title: Build the evidence upload pipeline
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - mvp
  - backend
  - frontend
  - evidence
  - security
assignees: []
milestone: null
parent: null
origin: null
dependencies:
  - TKT-01M24G5WE6X3996ZZBVYNCN1KR
blocks_on: none
references:
  - ref: git:2790f50
    path: server/app/images.py
  - ref: progress:increment-5
    path: docs/progress.md
  - ref: design:trust-abuse
    path: docs/design.md
  - ref: contract:schema
    path: docs/impl/schema.md
  - ref: contract:api
    path: docs/impl/api.md
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

Backport of Increment 5 from commit 2790f50. Added magic-byte validation, Pillow re-encoding, EXIF orientation and removal, dimension and decompression limits, perceptual hashing, rolling team rate limits, authenticated derivative serving, the evidence drawer, and camera capture. The increment passed 48 pytest tests and a live upload round trip with the derivative and audit row verified.

## Acceptance criteria

- [x] Uploads accept only supported image formats, apply EXIF orientation before stripping metadata, enforce wire, dimension, and decompressed-size limits, and re-encode clean JPEG derivatives.
- [x] Every upload stores a 64-bit perceptual hash, applies the team rate limit, and runs blocking Pillow work off the event loop.
- [x] Only the owning team and moderators can serve stripped derivatives; originals remain quarantined on disk.
- [x] The player drawer supports camera capture and upload, and tests cover valid, invalid, oversized, rotated, and access-controlled images.

## Definition of done

- [x] The increment passes 48 pytest tests.
- [x] A live upload returns the derivative and its `evidence.uploaded` audit row.

## Implementation plan

Completed by adding the image pipeline and evidence routes, running Pillow work in a thread pool, and wiring the drawer into the PWA.
