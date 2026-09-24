---
schema: 3
id: TKT-01M3AMNFHVSMQ3DS58984S7KP0
title: Show blurhash placeholders for pending and flagged photos
type: task
status: in-progress
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
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/blurhash
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 0acf772cdc684cf920bd79f7fa1d40f2685f1110
  session: null
  claimed_at: 2026-09-24T23:15:06Z
  expires_at: null
archive: null
created_at: 2026-09-24T21:20:40Z
updated_at: 2026-09-24T23:27:38Z
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

- [x] Each new upload stores a blurhash; a migration adds the column and the schema version is bumped.
- [x] Every player-facing view of a pending photo shows its blurhash with the scanning treatment instead of the photo.
- [x] A photo flagged inappropriate appears to players only as its blurhash; the photo itself is served only to moderators and the admin.
- [x] A rejected photo shows unblurred with a distinct rejected border.
- [x] Server tests cover the payloads and access rules; unit and e2e tests cover the three states; an ADR records the design.

## Implementation plan

Server: images.process_upload encodes a 4x3 blurhash from a 32px thumbnail of the oriented image (blurhash package, pure Python), stored in evidence_item.blurhash (migration 0005, schema 5, nullable for old photos). The drawer returns blurhash and quarantined and now lists flagged photos with photo_url null; the photo and submit routes still refuse them. Client: evidenceState.js derives flagged/pending/verified/rejected/free from the drawer plus the latest snapshot submission. Blurhash.jsx decodes with Wolt's npm blurhash onto a 32x32 canvas, because the CSP blocks data: images. Drawer tiles: pending → blur + sweep + 'Scanning · Riddle n'; flagged → blur, red frame, 'Removed by a moderator'; rejected → photo in a dashed amber frame; verified → green frame. Picker: pending blurred and disabled, flagged left out, rejected framed and pickable. The SCANNING banner has the blur behind it. Moderators are unchanged. ADR 0040; tests in test_evidence, test_conduct, screens.test and e2e/blurhash.spec.js.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:08:03Z

Promoted to ready 2026-09-24 at Drew's request as batch 2, to follow batch 1.

**agent:claude-code/t3code-bf267378** at 2026-09-24T23:27:38Z

Open question from earlier, decided in ADR 0040 without asking: the 4x3 components Drew was asked about stay, because a sharper hash starts to show what is in a flagged photo. Photos uploaded before migration 0005 have no blurhash. They show as before while pending (the photo itself) and as an empty frame when flagged, never the photo; no backfill, since kobal's existing photos are test uploads.
