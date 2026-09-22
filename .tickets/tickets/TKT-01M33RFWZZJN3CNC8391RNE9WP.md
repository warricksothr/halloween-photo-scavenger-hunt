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
updated_at: 2026-09-22T18:45:26Z
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

## Notes

**agent:opencode/backup-restore** at 2026-09-22T18:33:54Z

### Round 1 — both findings accepted

Reviewed head `b50103bfc8aeb0dfd048d05c1e309b36289d5f7f` (review id 156), Terva
run `7f854877-6fc9-44e1-a83f-5e1a2d1e9876` for `request:backup-restore-1`,
Actions run #171 (id 8741).

- **high — the restore recipe passed a wildcard to tar.** Correct, and made
  worse by the new retention. Once more than one archive exists the shell
  expands it and tar reads all but the first as member names, so recovery
  fails. Both the RUNBOOK §1 recipe and the script header now select the newest
  archive with `ls -1t … | head -n 1` and pass one quoted path. The doc test
  asserts the recipe selects a single archive and that no `tar -xzf` line
  contains a wildcard.
- **medium — the same-second test depended on the wall clock.** Correct. The
  restricted PATH now installs a `date` stub pinned to one timestamp, so both
  runs provably share a second and only the archive suffix can separate them.
  The test asserts both names carry that stamp.

Fixed in `27ad09d`. Re-requesting review.

**agent:opencode/backup-restore** at 2026-09-22T18:39:23Z

### Round 2 — finding accepted

Reviewed head `09af2ac94c1f7ed79a960907a9c024d6d5f790a2` (review id 157), Terva
run `ef6bf85c-d785-4971-b1ac-72c31dbdd284` for `request:backup-restore-2`,
Actions run #173 (id 8745). Round-1 findings both reported resolved.

- **medium — an interrupted mirror copy stays visible as a valid backup.**
  Correct. `cp "$OUT" "$MIRROR/"` wrote the final name directly, so a short or
  cut-off copy would be counted by retention and could be the newest archive
  the restore recipe picks. The mirror now copies to
  `mktemp "$MIRROR/.arkham-backup-copy-XXXXXX"` and renames it into place only
  after `cp` succeeds; on failure the temp is removed and the run exits
  non-zero. The EXIT trap also removes the temp if the script is interrupted.

  The new test (`test_backup_publishes_no_archive_when_the_mirror_copy_fails`)
  stubs `cp` to write a short file and then fail, and asserts the mirror holds
  no `arkham-backup-*.tar.gz` and no temp. It fails against the previous script
  on exactly that archive assertion, so it proves the fix.

Fixed in `f4e3ec6`. Re-requesting review.

**agent:opencode/backup-restore** at 2026-09-22T18:42:30Z

### Round 3 — both findings disputed, with tests

Reviewed head `24d1801e84e7c798fd6c66e6689b34fbb114f886` (review id 158), Terva
run `e4e3838a-cf5d-4907-9e89-97a110785362` for `request:backup-restore-3`,
Actions run #176 (id 8750). Round-2 finding reported resolved.

Both findings rest on "the script does not use `set -e`". That premise is
incorrect: `deploy/backup.sh:32` is `set -eu`, and has been since this branch's
first commit. Under `set -e`:

- **high — unchecked `mktemp -d`/`mkdir -p`.** A failing `mktemp -d` fails the
  assignment, so `set -e` aborts before `WORK` is used; `WORK` cannot become
  empty. `mkdir -p "$DEST_DIR"` is fatal the same way.
- **medium — retention `rm` failures.** A failing `rm -f` inside `prune`
  propagates out of the `if` body, and the bare `prune "$DEST_DIR"` call is not
  in a tested context, so `set -e` aborts the script.

I added the two tests the review asked for —
`test_backup_aborts_when_the_work_directory_cannot_be_created` (stubbed
`mktemp`) and `test_backup_fails_when_retention_cannot_delete_an_archive`
(stubbed `rm`) — in `659338c`. Both pass on the current script, and both fail
when `set -eu` is reduced to `set -u` (verified), which is what makes them
evidence: the abort comes from `set -e`, not from luck. If the intent is to be
robust to `-e` being dropped, say so and I will add explicit checks; on its own
the script is already correct.

Re-requesting review.

**agent:opencode/backup-restore** at 2026-09-22T18:45:26Z

### Round 4 — finding accepted

Reviewed head `cf689931cf0fef6294e0d5d79f5251c9e1fe00e5` (review id 159), Terva
run `56a60062-2a92-45a1-9772-e91bee69669e` for `request:backup-restore-4`,
Actions run #179 (id 8754). Round-3 findings both reported resolved.

- **low — a leading-zero keep count passes validation then breaks the
  arithmetic.** Correct. `ARKHAM_BACKUP_KEEP=08` passed the digit check and
  `$((total - KEEP))` then failed, because `/bin/sh` reads a leading zero as
  octal and `8` is not an octal digit. The script now strips leading zeros
  after validation, so every digit string is decimal and `08` means eight.
  `test_backup_accepts_a_leading_zero_keep_count` runs three backups with
  `KEEP=08` and asserts all three survive, which distinguishes eight from both
  an abort and a normalisation to zero; it fails against the previous script.

Fixed in `e1fc25b`. Re-requesting review.
