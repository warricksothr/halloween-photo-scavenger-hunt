---
schema: 3
id: TKT-01M33V6A940RKS2XGCV8RXCS0B
title: Install the Terva PR review process
type: chore
status: draft
status_reason: null
priority: normal
due_on: null
labels: []
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T06:00:02Z
updated_at: 2026-09-22T06:05:57Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

Install the Terva PR review process in this repository, delivered as two PRs
because the action reads its configuration at the PR base commit.

### What landed

- PR #1 `Add the project review config and PR review guide` (base `main`,
  head `t3code/install-terva-review-config`): `.terva/review.yml`,
  `.terva/checklist.md`, `.terva/conventions.md`, `docs/pr-reviews.md`, and
  `AGENTS.md` updates. Quality gate green.
- PR #2 `Add the Terva review workflow` (base `t3code/install-terva-review-config`,
  head `t3code/install-terva-review-workflow`): `.forgejo/workflows/terva-review.yml`
  with the pinned action, checksum-pinned Terva, digest-pinned runner image, and
  `config-file: .terva/review.yml`. Stacked on PR #1; retarget to `main` after
  PR #1 merges.

### Review evidence

Self-review dispatched from the workflow branch.

- Head `6d03980`, base `3b14a37`, request `install-review`, run #10
  (`a8945c79-632f-4ce7-b4c6-be7a66196378`), review 113.
  - `finding-1` high, pin the runner container and packages. Accepted: image is
    digest-pinned; the Alpine package set is a documented exception.
- Head `b2c7b05`, base `bd6a08e`, request `install-review-2`, run #12
  (`5bd92003-db91-44b9-a02f-4f4216589cc1`), review 115.
  - `finding-1` medium, a bare `/terva` comment does not trigger the job.
    Declined: every documented command is `/terva <subcommand> ...`; a bare
    `/terva` has no defined behavior. Recorded in PR #2 comment 9332.

`terva-review/code` is red on head `b2c7b05` because the declined medium finding
meets `fail-severity`. That is the configured gate, not a run failure.

### Known limitations

- The `/terva` comment commands cannot fire until the workflow is on the default
  branch; manual dispatch from a branch works and is how PR #2 was reviewed.
- PR #2 receives no Quality gate until it is retargeted to `main`, because
  `quality.yml` triggers on PRs to `main` only.

## Notes

**agent:opencode/review-system-design** at 2026-09-22T06:05:57Z

Both PRs merged to main: #1 as 655e467, #2 as 48226a0. The workflow now lives on the default branch, so the /terva comment commands are live and future PRs get the Quality gate. Both feature branches deleted. Still in draft; promote and close to track it.
