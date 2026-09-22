---
schema: 3
id: TKT-01M35C6QJ1AF1QW1FE30Q63TT4
title: Fix GNU-only mktemp --suffix in deploy/backup.sh breaking CI
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - ci
  - deployment
  - quality
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/fix-mktemp-portability
  branch: t3code/fix-mktemp-portability
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-mktemp-fix
  commit: d73ff1f30132775b0e380875006378fad3694b48
  session: null
  claimed_at: 2026-09-22T20:36:02Z
  expires_at: null
archive: null
created_at: 2026-09-22T20:16:36Z
updated_at: 2026-09-22T20:37:01Z
created_by:
  id: agent:opencode/agents-md-state
  name: ""
updated_by:
  id: agent:opencode/fix-mktemp-portability
  name: ""
extensions: {}
---

## Description

The Quality workflow has been red on `main` and on every pull request since
PR #12 merged. The cause is `deploy/backup.sh` calling `mktemp --suffix`, a
GNU coreutils option that BusyBox does not implement.

### Evidence

- `deploy/backup.sh:103` (as of `7c9526b`):
  `OUT="$(mktemp --suffix=.tar.gz "$DEST_DIR/arkham-backup-$STAMP-XXXXXX")"`.
  `--suffix` is GNU-only. BusyBox `mktemp` rejects it:
  `mktemp: unrecognized option '--suffix=.tar.gz'`.
- Introduced by `7c9526b` ("Reserve the backup archive name with mktemp",
  PR #12). The last green Quality run is `8761` (`ee1a473b`); the first red
  is `8763` (`49e418ef`), and the runs have been red since. The CI job's
  container is `golang:1.25-alpine`, whose `mktemp` is BusyBox v1.37.0.
- `scripts/check-server.sh` runs `pytest server`, which includes
  `server/tests/test_deployment_checks.py`; `scripts/check-quality.sh` has
  `set -e`, so it stops there. The frontend steps never run.

### Reproduction

Host, with BusyBox `mktemp` first on `PATH`:

```sh
mkdir -p /tmp/bbin && ln -sf /usr/bin/busybox /tmp/bbin/mktemp
PATH=/tmp/bbin:$PATH server/.venv/bin/python -m pytest \
    server/tests/test_deployment_checks.py -q
```

Result: `8 failed, 11 passed`. The failures are the backup tests that let the
test helper symlink the real `mktemp` instead of stubbing it.

Same result inside the CI container:

```sh
podman run --rm -v "$PWD:/src:ro" \
    container.local.sothr.com/library/golang:1.25-alpine sh -c '
    cp -a /src /w && cd /w
    apk add --no-cache bash ca-certificates git nodejs npm python3 uv
    bash scripts/check-server.sh'
```

Result: `8 failed, 221 passed` (coverage 94.27%, so the 90% floor still held).
Running the same container's `npm ci`, `npm test` (40 passed) and
`npm run build` on its own passes, so these deploy tests are the only failure.

### Fix

Reserve the archive name without `--suffix`. BusyBox `mktemp` needs the `X`s
at the end of the template, so a portable option is to reserve the name
first, then append the extension, or to reserve a name and rename the staged
tarball onto it. `server/tests/test_deployment_checks.py` pins the "reserved
by mktemp, not built from the work directory" behaviour, so keep that
property and update the argument the test asserts on.

## Acceptance criteria

- [ ] `deploy/backup.sh` uses no GNU-only `mktemp` option.
- [ ] `server/tests/test_deployment_checks.py` passes with BusyBox `mktemp`
      first on `PATH` (reproduction above).
- [ ] The Quality workflow on `main` goes green again.

## Implementation plan

### Problem

`deploy/backup.sh:103` reserves the archive name with
`mktemp --suffix=.tar.gz`. `--suffix` is a GNU coreutils extension; the
BusyBox `mktemp` in the CI container (`golang:1.25-alpine`) rejects it, so 8
tests in `server/tests/test_deployment_checks.py` fail and
`scripts/check-server.sh` stops `scripts/check-quality.sh` there. The Quality
workflow has been red on `main` and on PRs since PR #12 (run 8763,
`49e418ef`), which introduced the line.

### Approach

1. Reserve the name with a template whose `X`s are at the end, which both
   GNU and BusyBox accept, and add the extension by renaming the reserved
   placeholder onto `$reserved.tar.gz` before the staged tarball is moved in.
   BusyBox needs the `X`s trailing, so a template with `.tar.gz` after them
   cannot be used. Keep `PENDING` pointing at whichever path exists, so the
   `EXIT` trap still removes the reservation if the script dies between the
   two moves.
2. Update `test_backup_reserves_the_archive_name_apart_from_the_work_directory`
   to expect the extension-less `mktemp` argument and the `.tar.gz` name
   derived from it. The test still guards the property that matters: the
   archive name comes from `mktemp`, not from the work directory.
3. Update `docs/progress.md` and `docs/adr/0014-back-up-to-a-mirror-directory.md`,
   which both name the GNU option, to describe the portable reservation.

### Verification

- `PATH=/tmp/opencode/bbin:$PATH server/.venv/bin/python -m pytest
  server/tests/test_deployment_checks.py -q` passes with a BusyBox `mktemp`
  first on `PATH` (the reproduction in the ticket).
- `bash scripts/check-quality.sh` passes.
- `git ticket check --fix --dry-run --strict` passes.
- In the CI container, `bash scripts/check-server.sh` passes.
