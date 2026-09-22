---
schema: 3
id: TKT-01M33S2WJJCKSDJ9T12S5AGFSJ
title: Add request-ID structured logging with secret redaction
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - operations
  - security
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/request-id-logging
  branch: t3code/request-id-logging
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-request-id-logging
  commit: d14ff957630888d5b9a4c2b294f4c93ee1fb81c7
  session: null
  claimed_at: 2026-09-22T21:07:21Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-22T21:17:36Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/request-id-logging
  name: ""
extensions: {}
---

## Description

server/app has no logging or middleware, and no request id ties a log line to an actor or request. Uvicorn's access log writes the raw path, so the join, moderator, and invite codes in /api/join/{join_code}, /api/mod/join/{mod_code}, and /api/team/invites/{token} land in journald. Add middleware that assigns and propagates a request id and emits one structured line per request, with path segments, query strings, cookies, and Authorization redacted, and filter uvicorn's own access log.

## Acceptance criteria

- [x] Every request logs one structured line with request_id, method, redacted path, status, and duration_ms.
- [x] Bearer codes (join, mod, invite) never appear in logs or downstream error reports.
- [x] The server quality gate passes and a test asserts a join code is absent from captured logs.

## Implementation plan

### Approach

1. New `server/app/logging.py` holding the whole feature: a `JsonFormatter`,
   `redact_path()`, the request-id contextvars, `configure_logging()`, and
   `RequestLogMiddleware`. A module named `logging.py` inside the package is
   safe under absolute imports (stdlib still wins for `import logging`), and
   it is the name a reader will look for.

2. `redact_path(path)` replaces the bearer segment of every code-carrying
   route with `<redacted>`: `/api/join/<code>`, `/api/mod/join/<code>`,
   `/api/team/invites/<token>` plus its `/revoke` and `/redeem` suffixes, and
   the SPA links `/j/<code>` and `/m/<code>` (a QR link hits uvicorn directly,
   so those leak too). Anything else passes through unchanged. The middleware
   logs the path without its query string and adds `query: "<redacted>"` when
   one was present, so a query value can never leak either. Cookies and
   `Authorization` are simply never read.

3. `RequestLogMiddleware` is pure ASGI, like `csrf.CsrfMiddleware`, so it
   cannot disturb the SSE stream. It mints a request id (an inbound
   `X-Request-ID` only when it matches `[A-Za-z0-9._-]{1,64}`, else
   `secrets.token_hex(8)`), stores the id and redacted path in contextvars for
   the rest of the request (S2WK reuses them for exception logs), wraps
   `send` to capture the status and echo `X-Request-ID` back, and emits
   exactly one line in `finally` with `request_id`, `method`, `path`, `status`
   and `duration_ms`. An unhandled exception logs status 500 and re-raises.
   One caveat to record: an SSE line lands when the stream ends, so its
   `duration_ms` is the connection's lifetime.

4. `configure_logging()` is idempotent and called from `create_app`. It puts
   the JSON handler on the `arkham` logger and leaves `propagate` on so
   pytest's `caplog` still sees records. It attaches a dropping filter to
   `uvicorn.access`: that line writes the raw path (the leak), and the
   middleware already logs the request with a redacted one, so dropping keeps
   exactly one line per request.

5. Wire it in `main.py`: call `configure_logging()`, and add
   `RequestLogMiddleware` last so it wraps the body cap and CSRF gate and sees
   their rejections too.

6. Docs: new `docs/adr/0016-request-logging-and-redaction.md` (log shape, why
   path segments are redacted by route, why the uvicorn access log is dropped,
   the SSE duration caveat); update `docs/progress.md`. RUNBOOK query changes
   belong to S2WT, not here.

### Tests

New `server/tests/test_logging.py`:

- `redact_path` for each bearer route, the invite suffixes, `/j/<code>` and
  `/m/<code>`, and an untouched ordinary path.
- One line per request with the five fields, and `X-Request-ID` echoed.
- The acceptance test: a real POST to `/api/join/<code>` against a seeded
  event, then assert the code appears in no formatted record while the
  redacted path does. Format records with the app's `JsonFormatter`, since
  `caplog.text` uses pytest's own formatter.
- Inbound id propagation, and that an unsafe inbound id is replaced.
- The `uvicorn.access` filter drops a record.

### Verification

- `server/.venv/bin/python -m pytest server -q` passes.
- `bash scripts/check-server.sh` passes (90% coverage floor, Ruff, format).
- Dev-server smoke: `curl /api/join/<code>` and read one redacted line in the
  uvicorn output.

## Notes

**agent:opencode/request-id-logging** at 2026-09-22T21:16:57Z

Implementation landed on t3code/request-id-logging: server/app/logging.py (JsonFormatter, redact_path, request-id contextvars, idempotent configure_logging, pure-ASGI RequestLogMiddleware), wired in main.py last so it wraps the body cap and CSRF gate, tests in server/tests/test_logging.py. Discrimination checked: neutering redact_path and the uvicorn.access filter fails 9 of the 16 tests. Live uvicorn smoke: POST /api/join/SECRETJOIN42 logged path /api/join/<redacted> at status 403 and ?secret=hunter2 logged "query": "<redacted>"; grep for either secret in the server output found nothing, and no uvicorn access line was emitted. check-server.sh: 246 passed, 94.31% coverage, Ruff clean. check-quality.sh exit 0.

**agent:opencode/request-id-logging** at 2026-09-22T21:17:36Z

Review request: PR #16 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/16), head 60ec3d6, base d14ff95. Request id s2wj-request-logging-v1, run https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/223 (terva-review.yml); PR quality run https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/222.
