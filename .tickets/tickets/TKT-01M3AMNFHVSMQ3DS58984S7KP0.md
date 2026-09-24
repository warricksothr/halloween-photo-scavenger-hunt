---
schema: 3
id: TKT-01M3AMNFHVSMQ3DS58984S7KP0
title: Show blurhash placeholders for pending and flagged photos
type: task
status: ready
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
updated_at: 2026-09-24T22:08:03Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Drew's idea (2026-09-24): compute a blurhash of every submitted photo. While a photo waits for a moderator, show the player the blurhash under the SCANNING treatment, so they see a blurred impression of what they sent.

### Drew's rules (2026-09-24, clarified)
- **Pending: blurhash everywhere.** Anywhere a player-facing view shows a photo whose submission is still pending, it shows the blurhash, not the photo: the riddle detail's SCANNING banner (`web/src/screens/RiddleDetail.jsx`, `.scan-sweep` in `theme.css`), the Drawer, and anywhere else a pending photo appears to the team.
- **Inappropriate: the blurhash is the only form players see.** Only an admin or a moderator can see the photo itself. Today a flagged photo is quarantined: it drops out of the drawer (`server/app/evidence.py:348`) and its file 404s for players (`evidence.py:366-368`). That access rule stays. The change is that players see the blurhash where the photo was, not a gap.
- **Rejected: no blur.** A rejected photo shows as itself, with a distinct border (a rejected-state frame), not blurred.
- Moderators and the admin always see the real photo, since they have to judge it.

### Notes from the code
- `xyz.amorgan.blurhash` is a JVM library. This stack would use the Python `blurhash` package, or a small encoder on Pillow (already a dependency), on the server, and the npm `blurhash` decoder drawing to a canvas in the PWA.
- Encode in `server/app/images.py`, where the upload is decoded, orientation-fixed and `average_hash`ed before the JPEG derivative is written. The string (about 20-30 chars at 4x3 components) is a new column on the evidence item, so it needs a migration and a schema-version bump (5). Photos uploaded before the migration have no blurhash; decide whether to backfill from the stored derivatives or fall back to the plain scan panel.
- The snapshot and drawer payloads need the blurhash, and must *not* carry a `photo_url` for a quarantined item. The blurhash of an inappropriate photo is deliberately coarse, but confirm with Drew that 4x3 is blurry enough for anything a moderator would flag.

## Acceptance criteria

- [ ] Each new upload stores a blurhash; a migration adds the column and the schema version is bumped.
- [ ] Every player-facing view of a pending photo shows its blurhash with the scanning treatment instead of the photo.
- [ ] A photo flagged inappropriate appears to players only as its blurhash; the photo itself is served only to moderators and the admin.
- [ ] A rejected photo shows unblurred with a distinct rejected border.
- [ ] Server tests cover the payloads and access rules; unit and e2e tests cover the three states; an ADR records the design.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:08:03Z

Promoted to ready 2026-09-24 at Drew's request as batch 2, to follow batch 1.
