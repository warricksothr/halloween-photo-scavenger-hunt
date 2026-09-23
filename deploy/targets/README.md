# Deployment targets (local only)

This directory holds one note per deployment environment, written for agents and
people who work on a host over SSH. **The notes are not committed.** They name
real hosts, addresses, paths, and SSO group names, which do not belong in the
repository.

Everything in this directory is ignored except this file and `.gitignore`. The
same exclusion is stated in the repository root `.gitignore` under
"Deployment targets", so a target file stays untracked even if the inner
`.gitignore` is ever removed.

## Naming

One file per host or environment, named for the public host name:

```text
deploy/targets/kobal.md
deploy/targets/scavenger.nulloctet.com.md
```

## What a target note carries

- Where the deploy config, secrets, source checkout, data, and image live.
- How the app is run (container vs. systemd), and how to rebuild and restart.
- Every difference from `deploy/RUNBOOK.md` and `deploy/CONTAINER.md`, with the
  translation between the doc's commands and the host's.
- Access: SSH address and user, and the ground rules for that host.
- Where host changes are recorded (the ledger ticket, not this repository).

Do not put secrets in these files. Reference the secret's location; never its
value. A checked-in doc that names a secret's value is a leak that outlives the
rotation.

## Why a directory of ignored notes

`deploy/RUNBOOK.md` is the specification of record and assumes the systemd path
on a generic host. A real deployment diverges — a container behind nginx, a
different env file, a pinned subnet for proxy headers. Those divergences are
operational fact, not design, and they differ per host. Keeping them beside the
deploy docs but untracked lets the tracked docs stay generic and correct while
the host-specific truth travels with the checkout.
