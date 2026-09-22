---
schema: 3
id: TKT-01M33RFWZZJN3CNC8391RNE9WP
title: Fix the backup restore path and make backups survivable
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - deployment
  - operations
assignees: []
milestone: null
parent: TKT-01M33RFWERCGE04CK7F44NP313
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/backup-restore
  branch: t3code/backup-restore
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-9799aac5
  commit: a44be870116d672380c5deac6a28f69a380065e5
  session: null
  claimed_at: 2026-09-22T18:23:09Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T18:24:48Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/backup-restore
  name: ""
extensions: {}
---

## Description

backup.sh's header restores into <repo-root>, but the app reads <repo-root>/data, so following the comment yields a silently empty database. Backups also live on the same disk with no retention and collide within one second.

## Acceptance criteria

- [ ] The restore instructions match RUNBOOK section 1 and restore into data/.
- [ ] Backups are copied off-host and pruned to a bounded count.
- [ ] Archive names cannot collide within one second.

## Implementation plan

### Problem
Two defects in `deploy/backup.sh`:

1. Its header restore recipe extracts the archive into `<repo-root>`, so
   `arkham.db` lands at `<repo-root>/arkham.db`. The app reads
   `<repo-root>/data/arkham.db` (`server/app/main.py` / `ARKHAM_DATA_DIR`), so
   following the comment yields a silently empty database. The RUNBOOK §1
   recipe is correct; the header contradicts it.
2. Every archive lands in `backups/` beside the repo — the same disk as
   `data/` — with no retention, and the name is second-granular. Two backups in
   one second share `$OUT` and `$WORK`, so one overwrites the other.

### Approach
- **Restore recipe (AC1):** change the header to extract into
  `<repo-root>/data`, matching RUNBOOK §1, and point at the RUNBOOK as the
  source of truth.
- **Unique names (AC3):** create the work directory with `mktemp -d` (atomic)
  and derive the archive's suffix from it, so two runs in the same second
  cannot share either name. `mktemp` joins the test's restricted PATH.
- **Off-host + retention (AC2):** new optional `ARKHAM_BACKUP_MIRROR`
  directory — a different disk, NFS mount, or USB drive. After the local
  archive is written, copy it to the mirror, then prune both the local
  destination and the mirror to the newest `ARKHAM_BACKUP_KEEP` archives
  (default 14). A POSIX-sh `prune` helper counts matches and deletes the oldest
  `total - keep` by glob order, which is chronological because names are
  timestamp-prefixed.
- **Guards:** if the mirror is unset, warn on stderr that backups are
  local-only; if it is set but not a directory, fail rather than `mkdir` a
  mount point (which would shadow an unmounted mirror); warn if the mirror
  resolves to the same device as the data directory, since that is not
  off-host.
- **Docs:** RUNBOOK §1/§4 and `deploy/CONTAINER.md` §4 document the mirror and
  keep count.
- **ADR 0014** records the mirror-directory choice over `scp`/`rsync` (no new
  host dependency, testable, no ssh key to provision), prune-by-name, and the
  keep default.

### Tests
`server/tests/test_deployment_checks.py` (run by `scripts/check-deploy.sh`):
- The existing restore test still passes; extend its restricted PATH with
  `mktemp`.
- Two backups in the same second produce two archives (AC3).
- With `ARKHAM_BACKUP_MIRROR` set and `ARKHAM_BACKUP_KEEP=2`, three backups
  leave the two newest in both the local dir and the mirror, and the third is
  gone (AC2).
- The header's restore line extracts into `data` and agrees with RUNBOOK §1
  (AC1).
- An unset mirror warns; a mirror that is not a directory fails.
