---
schema: 3
id: TKT-01M33RFWHXP9V028WDBCE1YNDD
title: Reject malformed and oversized images with 400, not 500
type: bug
status: in-progress
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
references:
  - ref: TKT-01M33S2WP0F879M8AKQXVS7HRZ
    path: .tickets/draft/TKT-01M33S2WP0F879M8AKQXVS7HRZ.md
claim:
  actor: agent:opencode/review-system-design
  branch: t3code/image-validation-errors
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-e28f1e35
  commit: 8047061eae36a3f2ceb95022b2654905bda4db4f
  session: null
  claimed_at: 2026-09-22T14:42:25Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T14:56:22Z
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

- [x] Non-image bytes, truncated images, and decompression-bomb headers return 400 with a not_an_image or too_large error body.
- [ ] The failure is counted (see the observability epic) and covered by a test.

## Implementation plan

### Approach

Translate Pillow's failures inside `images.process_upload` so the module keeps
its two-error contract and the route answers 4xx instead of faulting.

- Wrap the open/load/re-encode block.
- `Image.DecompressionBombError` and `Image.DecompressionBombWarning` become
  `TooManyPixelsError` (413 `too_large`). The warning only matters because
  pytest runs `filterwarnings = ["error"]`; in production the explicit
  `MAX_PIXELS` check covers the 50M–89M band Pillow ignores.
- `Image.UnidentifiedImageError` and the truncated-file `OSError` become
  `NotAnImageError` (415 `not_an_image`).
- Do not touch `Image.MAX_IMAGE_PIXELS`; our own cap stays the authority.

Tests in `server/tests/test_evidence.py`: four pipeline-unit cases and two
endpoint cases, all proven to fail on pre-fix `images.py`.

### Status codes

`docs/impl/api.md` is the specification of record and names 413/415, and the
existing tests assert them, so keep those and read the ticket title's "400" as
"a 4xx, not a 500". Flagged to the user in the PR body.

### Counting (AC2)

No metrics or log seam exists in the server; the counting half belongs to
TKT-01M33S2WP0F879M8AKQXVS7HRZ (observability epic, still a draft). Cover the
failure with tests here and leave the counting half unticked, linked to that
ticket rather than growing this one.

## Notes

**agent:opencode/review-system-design** at 2026-09-22T14:52:02Z

### Terva review 136 (head 5b1f1b2) — all three findings accepted and fixed

Published on PR #6, run `cd11cbba-aaf2-4f3e-bdeb-a6f7aefbbf9b`, Actions run #99 (id
8563), request `tkt-01m33rfwhx-1`. All fixed in commit `0c80198`.

- **finding-1 (medium) — the broad `OSError` handler blamed derivative faults on
  the upload.** Accepted. The `try` now wraps only `Image.open` / `img.load`
  (plus our `MAX_PIXELS` check); EXIF transpose, hashing, resize, conversion,
  and `img.save` run outside it, so a server-side fault stays a 500 instead of
  becoming a 415. Locked in by
  `test_derivative_failure_is_not_blamed_on_the_upload`, which monkeypatches
  `average_hash` to raise `OSError` and asserts it is not re-labelled
  `NotAnImageError`.
- **finding-2 (low) — the `DecompressionBombWarning` branch had no test.**
  Accepted. Added `test_decompression_bomb_warning_is_too_many_pixels` with a
  10000×10000 header (100M pixels, between Pillow's 89M warning and 179M error
  ceilings), so the warning-as-error path is exercised.
- **finding-3 (low) — the ticket-store change was missing from the diff.**
  Accepted. This note, the plan, the reference, and the claim land on the branch
  in the same PR.

### Acceptance criteria

- AC1 satisfied: garbage-after-magic and truncated bytes now answer 415
  `not_an_image`; bomb headers answer 413 `too_large`. Status codes follow
  `docs/impl/api.md` (413/415), not the title's literal "400" — see the PR body.
- AC2 half satisfied: the failure is covered by tests. The counting half is left
  unticked — there is no metrics or log seam in the server, and "Uploads
  accepted/rejected by reason" is owned by TKT-01M33S2WP0F879M8AKQXVS7HRZ
  (observability epic, still a draft), which this ticket now references.

**agent:opencode/review-system-design** at 2026-09-22T14:56:22Z

### Terva review 137 (head 4fcbab6) — one low, fixed; round 3 clean

Review 137 (run `614933d1-a4d8-450d-8931-cd034854cd51`, Actions run #103 id 8573,
request `tkt-01m33rfwhx-2`) confirmed all three findings from review 136
resolved and raised one new `low`: the `process_upload` docstring still promised
"exactly two failure modes and nothing else" while the narrowing deliberately
lets post-decode faults propagate. Accepted and fixed in `620fada` — the
docstring now says decode failures are normalized and post-decode faults
propagate unchanged.

Round 3 on head `620fada` came back **clean**: run
`da12dc83-8da9-4ce1-adf2-acaba9003759`, Actions run #107 (id 8577), request
`tkt-01m33rfwhx-3`, zero findings, review 137's `finding-1` resolved. A clean run
creates no review object; it posts a "Terva review status" comment (PR #6 comment
9520). "Stored clean runs: 1/32".

Dispositions: review 136 findings 1–3 accepted (fixed `0c80198` / `4fcbab6`);
review 137 finding-1 accepted (fixed `620fada`). Recorded as `/terva disposition`
comments 9514 and 9518 plus hand-written records 9515 and 9519, because
`/terva disposition` is still a no-op (TKT-01M33YG8AGGAW5VVVT3XY5FVS7).

Gate on head `620fada`: `bash scripts/check-server.sh` — 150 passed, 94.80%
coverage, Ruff clean. PR #6 open, awaiting merge authorization.
