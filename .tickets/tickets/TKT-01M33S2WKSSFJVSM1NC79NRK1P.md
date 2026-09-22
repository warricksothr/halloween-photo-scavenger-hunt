---
schema: 3
id: TKT-01M33S2WKSSFJVSM1NC79NRK1P
title: Log unhandled exceptions with request correlation
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - operations
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies:
  - TKT-01M33S2WJJCKSDJ9T12S5AGFSJ
blocks_on: none
references: []
claim:
  actor: agent:opencode/t3code-0691bbb1
  branch: t3code/unhandled-exception-handler
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 794e300ea673ca01c905ba02abde408613aa4eb1
  session: null
  claimed_at: 2026-09-22T22:53:10Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-22T22:53:54Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

An unhandled exception surfaces only as a bare 500; nothing ties it to a request, actor, or the screen the player was on. Add an exception handler that logs the traceback with the request id and structured context and returns a stable JSON error body.

## Acceptance criteria

- [ ] An unhandled exception logs one correlated traceback and returns a JSON 500 body carrying the request id.
- [ ] The handler never logs secrets, cookies, or request bodies.
- [ ] Covered by a test that raises from a route.

## Implementation plan

### Approach

Keep the handler where it already is: `create_app` registers
`_internal_error` for `Exception`, and `ServerErrorMiddleware` calls it
outside the request-log middleware. Change it to build a JSON body and log
one correlated traceback.

- `server/app/logging.py` gains `log_unhandled_exception(exc)`: one ERROR
  line on the `arkham` logger with `event="unhandled_exception"`,
  `request_id` and `path` read from the existing contextvars, and
  `exc_info=exc` so the JSON formatter emits `exc_info`. It reads no
  headers, cookies, or body and never touches the query string.
- `server/app/main.py`: `_internal_error` calls the helper, then returns
  `JSONResponse` with `{"error": "internal_error", "message": "Something
  went wrong."}` plus `request_id` when known, keeping the `X-Request-ID`
  header. Drop `PlainTextResponse` if it becomes unused.
- Tests in `server/tests/test_logging.py`: the body is JSON and carries the
  same id as the header; exactly one `unhandled_exception` record exists per
  failure with `request_id`, `method`, and the redacted `path`; a
  `Cookie`/`Authorization` header and a body secret sent with the failing
  request never appear in the rendered record, while the exception's own
  message does.
- `docs/progress.md`: add the increment note.
