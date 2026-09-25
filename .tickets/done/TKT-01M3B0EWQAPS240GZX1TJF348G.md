---
schema: 3
id: TKT-01M3B0EWQAPS240GZX1TJF348G
title: Show the running build in the frontend
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels: []
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-25T00:46:47Z
updated_at: 2026-09-25T02:09:29Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Drew asked (2026-09-24) to expose version information in the frontend, so anyone can tell which build a phone is running, and the host can tell whether that build matches the server after a deploy.

### Constraint

`/api/admin/readyz` sits behind admin auth on purpose: main.py says the build name "is not a public fingerprint". The web bundle already inlines `VITE_ERROR_RELEASE`, which kobal's compose sets from `ARKHAM_RELEASE`, so the client's own build id is already public. The server's release is not.

## Acceptance criteria

- [x] Players and moderators see the web build id in a small, unobtrusive line: the join screen, the player's Case screen and the moderator console. A local build with no release reads 'dev'.
- [x] The host console shows the web build, the server release and the schema version (from readyz), and warns when the page's build differs from the server's.
- [x] No new public endpoint exposes the server release.
- [x] No host or compose change is needed on kobal.
- [x] Tests cover the build label and the mismatch warning, and an ADR records the decision.

## Implementation plan

Client: web/src/version.js exports WEB_BUILD from import.meta.env.VITE_ERROR_RELEASE, falling back to 'dev'. The variable is reused because kobal's compose already passes it as a build arg from ARKHAM_RELEASE; a new variable would need a compose change. components/BuildTag.jsx renders 'Build <id>' in dim small text at the foot of Join, Team (the player's Case screen) and ModConsole. Host console: a footer, shown while signed in, calls GET /api/admin/readyz (already admin-only) and shows Web, Server and Schema. When release differs from WEB_BUILD it warns that the page is older than the server and offers a reload. If readyz fails, only the web build shows. Server: no change; /api/health keeps schema_version only. ADR 0041 records why the server release stays admin-only. Tests: vitest for BuildTag, the fallback, and admin version/mismatch/failure.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-25T00:57:15Z

PR #65 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/65), branch t3code/version-info, base main.
- pr65-version-info-1 (run 748, head 5f2b38f): two low findings. (1) No .tickets change in the PR: declined as on every PR, because ticket commits go to main. (2) The dev-fallback test never unset the variable: accepted. 793a93a stubs VITE_ERROR_RELEASE and imports a fresh module for both the set and unset cases.
- pr65-version-info-2 (run 750, head 793a93a, https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/65#issuecomment-12826): passed, with (2) resolved and only (1) remaining. CI quality gate passed. Awaiting Drew's merge.

## Summary

Merged in PR #65 (merge a7bbd21). The join, Case and moderator screens show 'Build <id>' from VITE_ERROR_RELEASE. The host console's footer compares the web build with readyz's release and schema and offers Reload when they differ. The server's release stays admin-only (ADR 0041). Deployed to scavenger.nulloctet.com at ef654d9 on 2026-09-24.
