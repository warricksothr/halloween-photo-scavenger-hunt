---
schema: 3
id: TKT-01M33RFX3CS7WWQNY7YT6878BG
title: Correct the project-state and CI claims in AGENTS.md
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - maintenance
  - tracking
assignees: []
milestone: null
parent: TKT-01M33RFWFF6S1F67VAQ969PDFF
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/agents-md-state
  branch: t3code/agents-md-state
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-9799aac5
  commit: d73ff1f30132775b0e380875006378fad3694b48
  session: null
  claimed_at: 2026-09-22T20:06:29Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:51Z
updated_at: 2026-09-22T20:25:14Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/agents-md-state
  name: ""
extensions: {}
---

## Description

AGENTS.md still says no code exists and that CI runs the ticket-store check
with `git ticket check --strict`, but the app is fully built and no workflow
runs that check.

### Verified 2026-09-22

- `AGENTS.md:5` reads "Design phase complete; **no code exists yet**".
- `grep -rn 'git ticket' .forgejo .github` returns nothing: neither
  `quality.yml` nor `terva-review.yml` invokes the store check.
- The store *passes* `git ticket check --strict` as of `c5199a0` ("Clear the
  ticket-store warnings under check --strict"). An earlier version of this
  description said it failed on `.tickets/canvas/default.yml`; that is fixed.
  The third criterion below is therefore about keeping the check green under
  enforcement, not about repairing the store.

## Acceptance criteria

- [x] AGENTS.md describes the built state accurately.
- [x] The ticket-store check is wired into CI, or the claim that it runs is removed.
- [x] The store passes its own strict check.

## Implementation plan

### Problem

`AGENTS.md` carries three stale claims. Line 5 says "no code exists yet"
while phases 1–3 of `docs/progress.md` are complete. Line 196, inside the
tool-managed `<!-- git-ticket:begin -->` block, says "CI verifies the store
with `git ticket check --fix --dry-run --strict`", but no workflow invokes
the store check. And that same command currently fails: `check --strict`
reports two `section_heading_demoted` warnings in done tickets, so even the
local claim is false today.

### Approach

1. Rewrite the "Project state" section (lines 3–18) to describe the built
   app: phases 1–3 complete, where `server/` and `web/` live, how to run
   them, and keep the `docs/` pointers. Do not touch the tool-managed block
   for this.
2. Wire the store check into CI rather than deleting the claim, so the
   sentence becomes true. Add a step to `.forgejo/workflows/quality.yml`
   after checkout: `go install github.com/terva-sh/git-ticket@v0.23.0` (the
   version installed locally) then
   `git ticket check --fix --dry-run --strict`. The job's container is
   `golang:1.25-alpine`, so Go is already present and `$(go env GOPATH)/bin`
   is on PATH. The module is public on `proxy.golang.org`, so the runner can
   fetch it.
3. Clear the two warnings so `check --strict` passes. Both are a
   `### Acceptance criteria` sub-heading inside another section of a done
   ticket (`TKT-01M33RFWS` Summary, `TKT-01M33RFWT0` Implementation plan)
   that collides with the canonical `## Acceptance criteria` section.
   Rename each sub-heading so it no longer shadows the real section; the
   prose stays.

### Verification

- `git ticket check --fix --dry-run --strict` exits 0 with no findings.
- `bash scripts/check-quality.sh` still passes locally.
- Push the branch and watch the Quality workflow run on the PR: the new
  "Check the ticket store" step must pass. If the runner cannot reach the
  Go module proxy, fall back to rewording the AGENTS.md sentence to match
  what CI actually runs, and record why in a note.

## Notes

**agent:opencode/agents-md-state** at 2026-09-22T20:16:49Z

### CI wiring verified, and a pre-existing CI failure found

The plan named the wrong Go package: `go install github.com/terva-sh/git-ticket@v0.23.0` fails with
`module ... found, but does not contain package`. The main package lives under `cmd/`, so the workflow
now installs `github.com/terva-sh/git-ticket/cmd/git-ticket@v0.23.0`.

Verified in the exact CI container (`golang:1.25-alpine`), read-only mount of this branch:

- `go install .../cmd/git-ticket@v0.23.0` succeeds and `git-ticket` lands on `PATH`.
- `git ticket check --fix --dry-run --strict` prints "No problems found." and exits 0.

So the new steps are correct. The Quality run on this PR (`8820`, `0fffd4f`) is still red, but for a
reason that predates the branch: `deploy/backup.sh:103` uses `mktemp --suffix=.tar.gz`, a GNU-only
option that BusyBox rejects, so 8 tests in `server/tests/test_deployment_checks.py` fail under the
alpine `mktemp` and `scripts/check-server.sh` stops there. Reproduced both on the host with a BusyBox
`mktemp` symlink (8 failed, 11 passed) and in the CI container (8 failed, 221 passed). `main` has been
red since run 8763 (`49e418ef`), the merge of PR #12; the last green run is 8761 (`ee1a473b`).

Filed TKT-01M35C6QJ1AF1QW1FE30Q63TT4 (Fix GNU-only mktemp --suffix in deploy/backup.sh breaking CI)
with the reproduction and the fix. The frontend steps pass in the same container (`npm ci`, 40 tests,
`npm run build`), so the deploy tests are the only failure.

**agent:opencode/agents-md-state** at 2026-09-22T20:25:14Z

### Terva review 165 on PR #14 (head 315495c)

One high finding, accepted and fixed in this commit.

- **high: Pin the downloaded git-ticket tool by immutable commit or checksum.**
  Correct. `.terva/checklist.md:3` requires every workflow action, image and
  download to be pinned by full commit SHA, checksum or digest, and
  `go install ...@v0.23.0` pinned only a mutable tag. Fixed by installing the
  commit the Go module proxy resolved for that tag,
  `fd32d73b1301f562215f66d567bfbe5670e1bf12` (from
  `proxy.golang.org/.../@v/v0.23.0.info`'s `Origin.Hash`). Verified in the CI
  container: that SHA installs, reports `git-ticket v0.23.0`, and
  `git ticket check --fix --dry-run --strict` prints "No problems found."

The same commit corrects the earlier wrong package path: the first attempt,
`github.com/terva-sh/git-ticket@v0.23.0`, has no main package, which is what
made run 8820's new step fail.

Pre-existing, not touched here: `quality.yml:24` uses
`Actions-Mirrors/forgejo-actions-checkout@v6`, also a tag rather than a SHA,
so it has the same defect. Changing it is outside this ticket; noted for
whoever next edits the workflow.
