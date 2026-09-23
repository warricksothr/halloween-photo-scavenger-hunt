---
schema: 3
id: TKT-01M38763PP35VGKNG7C9GARP5T
title: Local-only deployment-target notes directory
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - deployment
  - operations
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-23T22:46:36Z
updated_at: 2026-09-23T23:00:42Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

### What

A local-only place for deployment-target notes: one file per environment,
naming the host and the operational facts that differ from the generic deploy
docs. The notes are never committed.

`deploy/targets/README.md` states the convention (naming, what a note carries,
no secrets). `deploy/targets/.gitignore` ignores everything in the directory
except itself and the README, and the root `.gitignore` repeats the exclusion
so a target file stays untracked even if the inner file is removed.

### Why

`deploy/RUNBOOK.md` and `deploy/CONTAINER.md` are the specification of record
and assume a generic host. A real deployment diverges: kobal runs the container
path behind nginx, with its own env file, a pinned subnet for proxy headers,
and an Authentik with different group names. Those are operational facts, not
design, and they differ per host. They also name real addresses, paths, and
group names, which do not belong in the repository.

Keeping the notes beside the deploy docs but untracked lets the tracked docs
stay generic and correct while host truth travels with the checkout.

### Shape

- Directory ignored by two independent rules (root and inner `.gitignore`), so
  a mistake in one still leaves the notes uncommitted.
- The README is tracked so the convention is discoverable in a fresh clone;
  the inner `.gitignore` whitelists exactly itself and the README.
- The first note, `kobal.md`, captures the live deployment: paths, container
  commands, the systemd-vs-container translation table, debugging recipes, and
  the host's ground rules.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T23:00:42Z

Terva r1 (run 297d8071, request deploy-targets-r1): one medium — the root fallback covered only four extensions, so the README's 'stays untracked even if the inner .gitignore is removed' claim was false for extensionless/other/nested files. Fixed in 0b68c8725982861782035d9eeea0d57427d04e76 (root ignores the directory, whitelists the two tracked files). r2 clean.

## Summary

A local-only home for deployment-target notes.

deploy/targets/ takes one note per environment. The README states the
convention; the inner .gitignore ignores everything but itself and the
README; and the root .gitignore ignores the directory and whitelists the
same two files. Either rule alone keeps a note out of the repository, and
kobal.md is verified ignored by both. The host note is intentionally not
committed.

Terva r1 found the root fallback listed four extensions while the README
claimed any target file stayed untracked without the inner rule — false
for an extensionless, other-extension, or nested file. Fixed by ignoring
the directory at the root too; r2 was clean.

Merge ed895c9023d2109826a4d28c363d03357eebf4aa (PR #43).
