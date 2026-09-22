---
schema: 3
id: TKT-01M33YG8MFEH48CN934V0GZPAE
title: Make /terva disposition record and surface failed review runs
type: bug
status: done
status_reason: Moved to TKT-01M33YG8AGGAW5VVVT3XY5FVS7 in the terva-action-code-review store (PR 35), which owns the review action.
priority: high
due_on: null
labels:
  - tooling
  - ci
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T06:57:54Z
updated_at: 2026-09-22T06:59:46Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

Two reliability gaps in the Terva review action, both observed on
warricksothr/arkham-halloween-photo-scavenger-hunt.

### `/terva disposition` records nothing

Posting `/terva disposition <review> <finding> deferred <reason>` as an issue
comment produces no maintained "Terva finding dispositions" comment and changes
nothing. The `issue_comment` workflow run for the command reports `success` in
about 3s (run #22, id 8433; run #26, id 8439) without running the action — a
review dispatch on the same workflow takes 30-50s, so the action is not
executing. A non-command issue comment produces a `skipped` run (#23, id 8434),
so the job gate itself is behaving. PR #2 on the same repository shows the same
shape: only the command comment, never a dispositions comment. Dispositions had
to be recorded by hand, as `docs/pr-reviews.md` allows.

### A review run can fail with no review and no status

Dispatching the review twice on one head with the same request id: one run
finishes `failure` in 46-51s with no review published and no
`terva-review/code` status; the retry publishes the review and the expected
failure-threshold status. Observed on workflow `terva-review.yml`:

- #19 (id 8427) `failure` with no review; #20 (id 8428) published review 116.
- #24 (id 8435) `failure` with no review; #25 (id 8436) published review 119.
- #10 and #12 published normally.

A silent failure is indistinguishable from a run that never happened: the gate
goes red with nothing to read and no reason to give a maintainer.

### Evidence

- Run list and detail come from `GET /repos/{owner}/{repo}/actions/runs` and
  `/actions/runs/{id}`. Forgejo 15.0.3 exposes no job-log route, so the failure
  code cannot be retrieved. `error-codes.md` says a failure after context
  capture names its code in the status description, but these runs published no
  status at all.
- Dispositions recorded by hand: arkham PR #3 comments 9355 and 9356 (review
  116 finding-1), 9362 (review 119 finding-1).

### Expected

- `/terva disposition` writes the maintained dispositions comment, or replies
  with a clear error when it cannot.
- A run that fails before publishing puts a reason in the status description or
  a comment, so an operator can act without job logs.

## Notes

**agent:opencode/review-system-design** at 2026-09-22T06:59:46Z

draft to done: Moved to TKT-01M33YG8AGGAW5VVVT3XY5FVS7 in the terva-action-code-review store (PR 35), which owns the review action.

## Summary

Moved to TKT-01M33YG8AGGAW5VVVT3XY5FVS7 in the terva-action-code-review store (PR 35), which owns the review action.
