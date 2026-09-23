---
schema: 3
id: TKT-01M33RFWPVZG68H8JFWRK6JK70
title: Guard against disk exhaustion on uploads
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - backend
  - operations
  - evidence
assignees: []
milestone: null
parent: TKT-01M33RFWDB1XFYCBPC0920QTAQ
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/harden-uploads
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 04c88a5ec2742fac89f4563d77c16fbdd4d8a9d2
  session: null
  claimed_at: 2026-09-23T12:51:30Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T12:56:29Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

Originals accumulate under data/photos and are only removed by event purge; there is no free-space check or storage cap. A full disk mid-party fails uploads and can break SQLite writes.

## Acceptance criteria

- [x] Uploads check free space and reject cleanly when low.
- [x] The originals directory has a documented cap or an operational check.

## Implementation plan

### Approach

A guardrail, not a reservation: the upload route refuses before it writes
anything when the filesystem would fall below a free-space floor.

1. New `server/app/storage.py`: `MIN_FREE_BYTES_DEFAULT` (256 MiB),
   `configured_min_free_bytes()` reading `ARKHAM_MIN_FREE_BYTES`
   (malformed/non-positive → default, mirroring
   `auth.configured_session_ttl`), and `has_room(path, extra_bytes,
   minimum)` over `shutil.disk_usage`.
2. `main.py` reads the floor once at startup onto `app.state.min_free_bytes`
   so the env var is a process setting.
3. `evidence.upload` checks, after reading the bounded body and before the
   Pillow work, that free space minus the body stays at or above the floor;
   otherwise `507 {"error":"storage_full"}` with a clean message. The check
   is before `process_upload` so a full disk costs no CPU and no file.
   Residual race (two uploads both pass, then write) is accepted: this is
   a guardrail against a full disk breaking SQLite, not a quota.
4. Tests: `configured_min_free_bytes` parsing; a low-space upload returns
   507 and leaves no row and no file; a normal upload still succeeds.
5. Docs: ADR 0023 (guardrail vs. reservation, the 507, the default);
   `docs/impl/api.md` upload errors; `docs/impl/schema.md` originals bullet
   gets the documented floor + operational check; `deploy/RUNBOOK.md` a
   pre-event disk check; `docs/progress.md`.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T12:56:29Z

### Implementation note

- `app/storage.py` — `MIN_FREE_BYTES_DEFAULT` (256 MiB),
  `configured_min_free_bytes()` (`ARKHAM_MIN_FREE_BYTES`, malformed or
  non-positive → default, mirroring `auth.configured_session_ttl`), and
  `has_room(path, extra_bytes, minimum)`. `has_room` walks to the nearest
  existing ancestor so it can probe a photos dir that does not exist yet
  without creating it.
- `main.py` — `app.state.min_free_bytes = storage.configured_min_free_bytes()`
  at startup, so the env var is a process setting.
- `evidence.upload` — after reading the bounded body and before
  `process_upload`, `has_room(photos_dir, len(data), min_free_bytes)`;
  false → `507 {"error":"storage_full"}`. Before Pillow, so a full disk
  costs no CPU, no row, and no files.
- Tests: `test_storage.py` (default, override, malformed fallback, the
  byte accounting, ancestor probe, real filesystem);
  `TestDiskGuardrail` in `test_evidence.py` (507 leaves no row and no
  files; the happy path consults the guardrail with the configured floor).
- Docs: ADR 0023 (guardrail not reservation; why 507); `docs/impl/api.md`
  upload errors; `docs/impl/schema.md` originals bullet (floor is the
  documented bound); `deploy/RUNBOOK.md` pre-event `df`/`du` step and a
  507 cheatsheet row; `deploy/CONTAINER.md` env-var note;
  `docs/progress.md`.
