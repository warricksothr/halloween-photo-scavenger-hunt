---
schema: 3
id: TKT-01M3B0EWQAPS240GZX1TJF348G
title: Show the running build in the frontend
type: task
status: in-progress
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
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/version-info
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 4c6ff5eabff2a1f9532ad1e25e529f7cf366e59b
  session: null
  claimed_at: 2026-09-25T00:46:58Z
  expires_at: null
archive: null
created_at: 2026-09-25T00:46:47Z
updated_at: 2026-09-25T00:47:08Z
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

- [ ] Players and moderators see the web build id in a small, unobtrusive line: the join screen, the player's Case screen and the moderator console. A local build with no release reads 'dev'.
- [ ] The host console shows the web build, the server release and the schema version (from readyz), and warns when the page's build differs from the server's.
- [ ] No new public endpoint exposes the server release.
- [ ] No host or compose change is needed on kobal.
- [ ] Tests cover the build label and the mismatch warning, and an ADR records the decision.

## Implementation plan

Client: web/src/version.js exports WEB_BUILD from import.meta.env.VITE_ERROR_RELEASE, falling back to 'dev'. The variable is reused because kobal's compose already passes it as a build arg from ARKHAM_RELEASE; a new variable would need a compose change. components/BuildTag.jsx renders 'Build <id>' in dim small text at the foot of Join, Team (the player's Case screen) and ModConsole. Host console: a footer, shown while signed in, calls GET /api/admin/readyz (already admin-only) and shows Web, Server and Schema. When release differs from WEB_BUILD it warns that the page is older than the server and offers a reload. If readyz fails, only the web build shows. Server: no change; /api/health keeps schema_version only. ADR 0041 records why the server release stays admin-only. Tests: vitest for BuildTag, the fallback, and admin version/mismatch/failure.
