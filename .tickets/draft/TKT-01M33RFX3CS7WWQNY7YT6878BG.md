---
schema: 3
id: TKT-01M33RFX3CS7WWQNY7YT6878BG
title: Correct the project-state and CI claims in AGENTS.md
type: bug
status: draft
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
claim: null
archive: null
created_at: 2026-09-22T05:12:51Z
updated_at: 2026-09-22T15:13:46Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:claude-code/groom-ticket-store
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

- [ ] AGENTS.md describes the built state accurately.
- [ ] The ticket-store check is wired into CI, or the claim that it runs is removed.
- [ ] The store passes its own strict check.
