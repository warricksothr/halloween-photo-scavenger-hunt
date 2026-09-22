# 0014. Back up to a mirror directory, not a remote transport

Date: 2026-09-22
Status: accepted

## Context

`deploy/backup.sh` wrote its archive into `backups/` beside the repo — the same
disk as `data/` — with no retention, and named it to the second. Two runs in
one second shared both the output path and the work directory, so one backup
silently replaced the other. A backup on the same disk protects against a
mistaken `rm`, not against losing the disk.

The ticket asks for copies off-host and a bounded count. Three transports were
on the table:

1. A **mirror directory** (`ARKHAM_BACKUP_MIRROR`) — a USB drive, an NFS mount,
   a synced folder.
2. `scp`/`rsync` to `user@host:path`.
3. A database-agnostic object store (S3-compatible), via a CLI.

Direction 3 adds a credential and a dependency to the one-command recovery path
the design treats as the whole durability story (`docs/design.md`: "the worst
realistic incident is losing the SQLite file or photos mid-party"), which is
disproportionate for a one-night party on one host. Direction 2 needs a
provisioned SSH key and a reachable host at the moment of the backup, and its
retention prune has to run as a remote command whose quoting is easy to get
wrong — a failure mode that is invisible until the night it matters.

## Decision

Copy the archive to a directory named by `ARKHAM_BACKUP_MIRROR`, and prune both
the local destination and the mirror to the newest `ARKHAM_BACKUP_KEEP`
archives (default 14). The operator points the mirror at another filesystem;
the script cannot know one exists, so an unset mirror prints a warning rather
than failing, and a mirror that is set but not a directory fails loudly —
`mkdir` there would create a directory on the root disk and shadow an unmounted
mount. When `stat` is available and the mirror shares a device with `data/`,
the script warns, because that is not off-host. `ARKHAM_BACKUP_KEEP` is
normalised to decimal before the retention sum, because a POSIX shell reads a
leading zero as octal and would abort on a value like `08`.

Archive names carry the timestamp plus a `mktemp -d` suffix, so two runs in the
same second cannot collide; pruning orders by name, which is chronological
because names are timestamp-prefixed. The mirror copy happens before either
prune: when several archives share a timestamp their names are interchangeable
to the sort, so a prune can drop the run's own archive, and the off-host copy
must not depend on it surviving locally. The copy goes to a temp name in the
mirror and is renamed into place, because a `cp` cut short by a full disk or a
dropped mount would otherwise leave a truncated file under the final name that
retention keeps and the restore recipe might select.

## Consequences

Off-host durability is a configuration the runbook sets and the pre-party drill
exercises, not a default — the script warns when it is absent, so a local-only
backup is visible rather than assumed. Retention is bounded in both
directories, so repeated mid-party runs cannot fill the disk. The systemd host
path and the container path share the same knobs; `deploy/CONTAINER.md` points
at them. The cost is that a remote host is not supported: an operator who wants
one copies the mirror directory on, which keeps the recovery command dependency
free.
