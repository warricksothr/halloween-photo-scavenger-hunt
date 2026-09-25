---
schema: 3
id: TKT-01M3CN4T3VNNQ05ZCKPCZNDWPM
title: Turn the GitHub Pages site into a project page with the mocks archived
type: task
status: in-progress
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
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: null
  worktree: /tmp/bf267378-tk
  commit: b300116d6e224db1bc4ce31f3a287be5101d9311
  session: null
  claimed_at: 2026-09-25T16:07:32Z
  expires_at: null
archive: null
created_at: 2026-09-25T16:07:31Z
updated_at: 2026-09-25T16:07:32Z
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

- [ ] The Pages root is a project page with current screenshots and links to the repo and deploy/README.md
- [ ] The mocks are published under /mocks/ and labelled as a design-phase archive
- [ ] The site's source and a build script live on main, with a written publish procedure
- [ ] gh-pages is updated as a fast-forward commit, with no force-push

## Implementation plan

Source on main: docs/site/index.html (the project page, which reuses the mocks' stylesheet), scripts/build-pages.sh (copies the page, docs/screenshots and docs/impl/mocks into OUT_DIR and writes .nojekyll; refuses a non-empty OUT_DIR), docs/site/README.md (what is published from where, and the publish procedure), a banner on the mocks index, and a README link. After merge, publish by replacing gh-pages' tree with the build as one new commit on top of b93c62c, then push as a fast-forward. Rejected: a Pages workflow on GitHub Actions. The mirror runs no workflows by design, and a workflow would need a settings change to the Pages source.
