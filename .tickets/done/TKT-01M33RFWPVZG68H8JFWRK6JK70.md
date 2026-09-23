---
schema: 3
id: TKT-01M33RFWPVZG68H8JFWRK6JK70
title: Guard against disk exhaustion on uploads
type: task
status: done
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
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T13:13:42Z
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

**agent:opencode/t3code-0691bbb1** at 2026-09-23T13:03:32Z

### r1 fix note

Terva r1 raised two findings; both accepted.

- **high — the route check runs after the body may already be spooled.**
  Starlette parses the multipart form and can spool a part to a temp file
  on the same filesystem before the handler runs, so a handler-only check
  cannot promise "refuse before any work". Added
  `storage.StorageGuardMiddleware` (registered outside the body cap in
  `main.py`): it answers 507 from the declared `Content-Length` before any
  body bytes are read, and falls back to the app request cap for a chunked
  body rather than reading it. The route check stays as the second layer.
- **medium — accounting ignored the files upload writes.** The route check
  now passes `len(data) + images.MAX_DERIVATIVE_BYTES`, an upper bound on
  the re-encoded derivative, instead of `len(data)`.

Tests: middleware rejects before the downstream app reads the body; passes
an upload through when there is room; bounds a chunked upload by the cap;
ignores non-upload requests. The route happy-path test asserts a check
carrying at least `MAX_DERIVATIVE_BYTES`. ADR 0023, `docs/progress.md`
updated to the two-layer story.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T13:05:53Z

### r2 fix note

Terva r2: r1's two findings resolved; one medium — the low-disk endpoint
test no longer exercised the route guard, because the unconditional
`has_room -> False` patch now short-circuits in the middleware first.

Accepted. `test_low_disk_rejects_before_any_work` now patches `has_room`
to pass the middleware's declared-length check and fail the route's check
(which carries `MAX_DERIVATIVE_BYTES`), so the 507/no-row/no-file
assertions cover the post-parse branch. The middleware's own
reject-before-read behaviour is covered by the unit tests in
`test_storage.py`.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T13:10:01Z

### r3 fix note

Terva r3: r2's finding resolved; one high — the pre-parse guard checked
only the photos volume, but Starlette spools a multipart part to the
process temp directory (`TMPDIR`, usually `/tmp`), which need not share a
filesystem with the data volume (in the container recipe it does not).

Accepted. `StorageGuardMiddleware` now requires room on **both** the
photos volume and the spool filesystem, refusing 507 from the declared
length before any body bytes are read. New test
`test_middleware_rejects_when_only_the_spool_filesystem_is_full` proves
the spool side alone is enough to reject. ADR 0023, `docs/progress.md`,
and `deploy/RUNBOOK.md` (check `/tmp` too) updated.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T13:13:42Z

Review record (Terva, `terva-review.yml`).

- PR #32, head `463bc08b`, base `04c88a5e`; merged `e4d072007469e7681f4dcfc621495c4e5e892355`.
- r1 `harden-uploads-r1`, run `97ea1550-6089-4ab0-b6c7-ae8269b2a42f` (#448), reviewed `68b191a8`: 2 findings.
  - high: route check runs after the multipart body may already be spooled → added `StorageGuardMiddleware`, checked before parsing.
  - medium: accounting omitted the files upload writes → route now adds `MAX_DERIVATIVE_BYTES`.
- r2 `harden-uploads-r2`, run `6ff18b06-021d-4e83-92ce-52fe829ac934` (#450), reviewed `14318d77`: r1 resolved, 1 medium.
  - medium: the low-disk test only exercised the middleware branch → test now passes the middleware check and fails the route check.
- r3 `harden-uploads-r3`, run `71482f83-d3de-451b-a521-83605d0f23e3` (#452), reviewed `9176b0a4`: r2 resolved, 1 high.
  - high: the pre-parse guard checked only the photos volume, not Starlette's spool filesystem → middleware now checks `TMPDIR` too.
- r4 `harden-uploads-r4`, run `431435bc-7d44-424a-bf57-20dde1e9ad76` (#454), reviewed `463bc08b`: clean.

All findings accepted and fixed with regression tests; none disputed or
deferred.

## Summary

Uploads now refuse below a free-space floor, in two layers.
`StorageGuardMiddleware` (registered outside the body cap in `main.py`)
answers `507 storage_full` for a `POST /api/evidence` from the declared
`Content-Length` — or the request cap for a chunked body — before any
body bytes are read, checking both the photos volume and the multipart
spool filesystem. The route re-checks after the bounded read, accounting
for the original plus `images.MAX_DERIVATIVE_BYTES`, before any Pillow
work. The floor is `ARKHAM_MIN_FREE_BYTES`, default 256 MiB, read once
onto `app.state.min_free_bytes`.

It is a guardrail, not a reservation or a quota (ADR 0023); the residual
two-writer race is accepted and documented. The originals directory's
documented bound is that floor, backed by the pre-event `df`/`du` check
in `deploy/RUNBOOK.md` (now including `/tmp`).

Both acceptance criteria ticked. Merged as PR #32, merge commit
`e4d072007469e7681f4dcfc621495c4e5e892355`, after four Terva rounds
(r1 two findings, r2 one, r3 one, r4 clean). Full
`scripts/check-quality.sh` green.
