# 0007. Run browser smoke tests against the built PWA

Date: 2026-09-09
Status: accepted

## Context

The curl smoke checks exercise HTTP endpoints, and Vitest covers frontend
modules, but neither check proves that the built PWA routes a player and a
moderator through the same browser session. A test against the Vite development
server would also miss uvicorn's static asset and SPA fallback behavior.

The smoke must not touch the event database, credentials, or photos used by a
local or production run. A failure needs browser artifacts without adding those
artifacts to the repository.

## Decision

Use Playwright with a separate `npm run test:e2e` command. The command builds
`web/dist`, starts uvicorn with a temporary SQLite database and photo directory,
and drives the built shell through player join, evidence upload, submission,
moderator verdict, and standings. The test server generates an ephemeral admin
password hash and removes its temporary directory when it exits.

## Consequences

The browser dependency and Chromium installation add a deliberate longer gate
beside the fast unit suite. The test catches static serving, cookies, theme
loading, screen transitions, SSE verdict delivery, and moderator/player role
routing. Playwright's failure artifacts stay under an ignored output directory,
so maintainers must inspect them locally or in CI rather than commit them.
