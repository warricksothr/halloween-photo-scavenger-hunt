---
schema: 3
id: TKT-01M3CN4T3VNNQ05ZCKPCZNDWPM
title: Turn the GitHub Pages site into a project page with the mocks archived
type: task
status: done
status_reason: null
priority: low
due_on: null
labels:
  - maintenance
  - tooling
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-25T16:07:31Z
updated_at: 2026-09-25T17:13:28Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Drew (2026-09-25) asked to review the `gh-pages` branch on the public GitHub mirror and consider updating it.

### Found
- The site at https://warricksothr.github.io/halloween-photo-scavenger-hunt/ is legacy Pages, built from `gh-pages` at `/`. It holds only the 14 static UI mocks from `docs/impl/mocks`, published 2026-08-14 in three commits (b93c62c is the tip). Apart from `.nojekyll`, it is byte-identical to `docs/impl/mocks` on main. The built app has moved well past those mocks.
- No source on main produced the branch, and no procedure for publishing it was written down.

### Decision (Drew, 2026-09-25)
Of the three options offered, Drew chose "Project page + mocks": a project page with the current screenshots and links to the repo and the self-hosting docs, with the mocks moved to `/mocks/` and labelled as the design-phase archive. The rejected options were to add a banner to the mocks only, or to leave the site as it is.

## Acceptance criteria

- [x] The Pages root is a project page with current screenshots and links to the repo and deploy/README.md
- [x] The mocks are published under /mocks/ and labelled as a design-phase archive
- [x] The site's source and a build script live on main, with a written publish procedure
- [x] gh-pages is updated as a fast-forward commit, with no force-push

## Implementation plan

Source on main: docs/site/index.html (the project page, which reuses the mocks' stylesheet), scripts/build-pages.sh (copies the page, docs/screenshots and docs/impl/mocks into OUT_DIR and writes .nojekyll; refuses a non-empty OUT_DIR), docs/site/README.md (what is published from where, and the publish procedure), a banner on the mocks index, and a README link. After merge, publish by replacing gh-pages' tree with the build as one new commit on top of b93c62c, then push as a fast-forward. Rejected: a Pages workflow on GitHub Actions. The mirror runs no workflows by design, and a workflow would need a settings change to the Pages source.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-25T16:16:34Z

PR #70: https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/70 (branch t3code/pages-site).

- pages-site-70-r1, run 802, head c19fa6c: failure.
- pages-site-70-r2, run 803, head 60b3b51, base e295ae2: failure on the declined medium only. Quality gate green on 60b3b51.

Disposition of `pages-site-70-r1` / `-r2`:

- **medium "advertises unsupported team invitations": declined.** "The MVP is a team of one" in AGENTS.md describes the MVP's schema. The project state at the top of the same file, and `docs/progress.md` "Phase 3 — Stretch", record team invites, rosters and multi-member drawers as shipped:
  - `server/app/teams.py` issues `/t/<token>` invite URLs, and `web/src/screens/TeamJoin.jsx` redeems them.
  - ADR 0006 covers moderator team removal.
  - `team_invite.*` rows are in `docs/impl/audit-actions.md`.
  The bullet describes the shipped game.
- **low "builder only syntax-checked": accepted**, fixed in 60b3b51. r2 marks it resolved.
- **low ".tickets not in the PR": declined.** By project practice the ticket store is committed straight to main. TKT-01M3CN4T3VNNQ05ZCKPCZNDWPM is there.

The publish procedure was dry-run against the real gh-pages branch (tip b93c62c) with the push left out. It produced one commit on top of b93c62c, a fast-forward. Not merged and not published: waiting for Drew.

## Summary

Merged as PR #70 (a0143f7) at the reviewed head 60b3b51, on Drew's go-ahead. GitHub main was fast-forwarded to a0143f7. Published by the docs/site/README.md procedure: gh-pages e8a7e2b, one commit on top of b93c62c, pushed as a fast-forward with no force. The Pages build for e8a7e2b reports built. The live site answers 200 for /, /mocks/, a screenshot and the mocks stylesheet, and /mocks/ carries the archive banner. The Terva medium about team invites was declined with evidence (phase 3 shipped invites), as recorded in the PR comment. The app is unchanged, so kobal needed no redeploy. To republish after changing the screenshots, the page or the mocks, rerun the procedure.
