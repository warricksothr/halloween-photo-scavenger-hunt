---
schema: 3
id: TKT-01M3AMNFHVSMQ3DS58984S7KP0
title: Show a blurhash of the pending photo behind the SCANNING banner
type: task
status: draft
status_reason: null
priority: low
due_on: null
labels:
  - frontend
  - evidence
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-24T21:20:40Z
updated_at: 2026-09-24T21:20:40Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Drew's idea (2026-09-24): while a submitted photo waits for a moderator, the player sees the SCANNING banner with its cyan sweep (`web/src/screens/RiddleDetail.jsx`, `.scan-sweep` in `theme.css`). Compute a blurhash of each photo and use it as the banner's background while the verdict is pending, so the player sees a blurred impression of what they sent under the scan.

Drew's message was cut off after this point ("...while we wait for a decision from a moderator. I"), so the rest of the idea still needs asking before this is planned.

### Notes from the code
- `xyz.amorgan.blurhash` is a JVM library. This stack would use the Python `blurhash` package (or a small encoder on Pillow, already a dependency) on the server and the npm `blurhash` decoder in the PWA.
- The natural place to encode is `server/app/images.py`, where the upload is decoded, orientation-fixed and hashed (`average_hash`) before the JPEG derivative is written. A blurhash string (about 20-30 chars at 4x3 components) would be a new column on the evidence item and a field in the snapshot's submission rows, so it needs a migration and a schema-version bump.
- Open questions: should the blurhash also stand in on the Drawer and the moderator queue while the full image loads; and should a rejected or inappropriate photo keep showing its blurhash (probably not for inappropriate ones).
