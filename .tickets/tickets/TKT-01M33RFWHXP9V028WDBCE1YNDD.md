---
schema: 3
id: TKT-01M33RFWHXP9V028WDBCE1YNDD
title: Reject malformed and oversized images with 400, not 500
type: bug
status: ready
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - evidence
  - security
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T05:19:41Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

images.process_upload only catches its own two error types; Pillow's UnidentifiedImageError, truncated-image OSError, and DecompressionBombError propagate out of evidence.upload and become a 500. Garbage bytes or a header-only decompression bomb is a cheap way to fault the server on party night.

## Acceptance criteria

- [ ] Non-image bytes, truncated images, and decompression-bomb headers return 400 with a not_an_image or too_large error body.
- [ ] The failure is counted (see the observability epic) and covered by a test.
