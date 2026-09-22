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
updated_at: 2026-09-22T23:24:05Z
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

Keep the handler where it already is: `create_app` registers `_internal_error`
for `Exception`, and `ServerErrorMiddleware` calls it outside the request-log
middleware. Change it to build a JSON body and log one correlated traceback.

- `server/app/logging.py` gains `log_unhandled_exception(exc, ...,
  request_secrets=())`: it formats the traceback with
  `traceback.format_exception` and scrubs each request secret with
  `<redacted>`, longest first, then logs one ERROR line with
  `event="unhandled_exception"`, `exception_type`, the scrubbed `traceback`,
  `request_id`, `method`, and the redacted `path`. It does not pass `exc_info`,
  so no unscrubbed message can be emitted. `bearer_secrets(path)` and
  `_request_secrets(scope)` collect the path credential, the query values, and
  the `Authorization` and `Cookie` values; the body is never read.
- `RequestLogMiddleware` puts the id, the redacted path, and the request's
  secrets on the scope for the handler, which runs after the middleware's
  contextvars are reset.
- `server/app/main.py`: `_internal_error` passes those through, then returns
  `JSONResponse` with `{"error": "internal_error", "message": "Something went
  wrong."}` plus `request_id` when known, keeping the `X-Request-ID` header.
- Tests in `server/tests/test_logging.py`: the failing route raises with the
  path token and the `Authorization` value in its message; the body is JSON and
  carries the same id as the header; exactly one `unhandled_exception` record
  exists with the scrubbed fields; the token, the `Authorization` value, and the
  body secret are absent while the exception type and message are present. Unit
  tests cover `bearer_secrets`, `_request_secrets`, and the longest-first scrub.
- ADR 0016 records the traceback scrub and its body caveat. `docs/progress.md`
  carries the increment note.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-22T22:57:08Z

Opened PR #19 (branch t3code/unhandled-exception-handler, head c828e786af8978f749954b30a2cee297582d56e0, base 794e300ea673ca01c905ba02abde408613aa4eb1) and requested a Terva review: request-id ready-review, run https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/263. bash scripts/check-server.sh green: 313 tests, coverage 95.34%, Ruff clean.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:07:56Z

Terva review of head 45cebe45 (run #266, request ready-review) published one finding.

### high: exception messages can carry secrets
Accepted. `exc_info=exc` rendered the exception's message verbatim, and the test raised a constant `kaboom`, so a credential the app was handed could reach the log through a `raise`. Fixed by rendering the traceback in `log_unhandled_exception` and replacing the request's own secrets — the bearer path segment, the query values, the `Authorization` value, and each cookie value — with `<redacted>`, longest first. `exc_info` is no longer passed, so no unscrubbed message can be emitted. The test route now raises with the path token and the `Authorization` value in its message and asserts both are gone from the rendered record.

Boundary, recorded in ADR 0016: the body is still never read, so a value that lived only in the body and then in a `raise` message would not be scrubbed. That is a constraint on app code, not a channel this handler created — it reads nothing the module did not already handle. Values shorter than `_MIN_SECRET` (6) are left alone, because replacing a short string verbatim would mangle ordinary words.

Evidence: head 4ac8e01, `bash scripts/check-server.sh` green — 323 tests, coverage 95.36%, Ruff clean. Re-review requested after the push.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:15:31Z

Supersedes the note at head 57a0f06; the residual it documented was not accepted.

### high (review 186, run #268, request high-finding-fix): body-derived secrets
Terva accepted the path/query/header scrubbing from `4ac8e01` but kept the
finding open: a value parsed from the request body and then quoted in a
`raise` message is still logged, and the test's `hunter2` assertion was
vacuous because the route never raised with it. The reviewer offered a safe
representation that drops messages, or body-aware sanitization.

Chosen with the user: body-aware sanitization, so the traceback keeps its
message. Also note review 185 and 186 are marked "source was not executed",
so the SDK behavior claims are the reviewer's reading, not a run.

Implementation: `RequestLogMiddleware` buffers a JSON or form body up to
`_BUFFERED_BODY_BYTES`, and only for the media types `_body_secrets` reads; a
photo upload is never buffered. `_body_secrets` walks the decoded body for
string leaves (length >= `_MIN_SECRET`) and the middleware extends the same
scrub list the exception handler already reads — the handler runs after the
middleware's `finally`, so a list mutated before the re-raise is what it sees.
A request that succeeds pays nothing but the copy, and the bytes are dropped
when the request ends. The test route now raises with `payload['password']`,
and the assertions cover both that value and a body value the route never
quotes, so they can no longer pass on an unused request field.

Residual, recorded in ADR 0016: multipart parts are not parsed. The API's one
multipart route uploads a photo; binary is not mined for strings.

Evidence: head 7330985, `bash scripts/check-server.sh` green — 325 tests,
coverage 95.17%, Ruff clean (45 files formatted). New unit tests
`test_body_secrets_reads_json_and_form_values` and
`test_body_secrets_skips_binary_and_malformed_bodies`. Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:19:33Z

Supersedes the note at head e1984e7.

### high (review 188, run #272, request body-scrub-fix): a body over the buffer limit
Terva confirmed the small-body path but kept the finding open: a supported JSON
or form body larger than `_BUFFERED_BODY_BYTES` is truncated before
`_body_secrets` parses it, the truncated copy fails to parse, and the app —
which received the full body — can quote a value from it that is not in the
scrub set.

Accepted as the reviewer's "track whether the body exceeded the limit and use a
safe traceback representation when complete sanitization is impossible" remedy.
The middleware now tracks whether it dropped bytes; on the failure path it sets
`state["safe_traceback"]`, and `log_unhandled_exception` then logs the frames
and the exception type without the message (`include_message=False`, recorded
as `message_included` on the record). The message is the only place an
uninspected body value can surface, so a body too large to scrub whole loses
its message instead of risking it. The buffer stays bounded rather than growing
to the app's body cap, which is derived from the photo limit.

Tests: `test_a_truncated_body_drops_the_exception_message` shrinks
`_BUFFERED_BODY_BYTES` to 64 so a small body exercises the path; it asserts the
frame line survives, the `Traceback` header and the `RuntimeError` message do
not, and the body secret is absent.

Evidence: head 65f6f82, `bash scripts/check-server.sh` green — 326 tests,
coverage 95.19%, Ruff clean (45 files formatted). Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:24:05Z

Supersedes the note at head 65f6f82.

### high (review 190, run #275, request truncated-body-fix): repeated form fields
Terva resolved the truncated-body finding (`finding-1` resolved: the middleware
records a short copy and the logger omits the message). The same review opened a
high: `_body_secrets` folded the form pairs through `dict(parse_qsl(...))`, which
keeps only the last value of a repeated field. The app can read an earlier value
from the form's multi-value interface, so a body like
`password=firstsecret&password=secondsecret` could quote `firstsecret` in a
`raise` while the scrub set held only `secondsecret`.

Accepted. The form branch now keeps the `(name, value)` values as a list, so
every repeated value enters the scrub set; the JSON branch is unchanged and
still yields values only, never keys, which is why the field names stay out.

Tests: the unit test gains a duplicate-field case asserting both values; a new
`test_a_repeated_form_value_is_scrubbed` posts the repeated form and has the
route raise with `form.getlist('password')[0]`, asserting neither value reaches
the log.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 327
tests, coverage 95.45%, Ruff clean (45 files formatted). Re-review requested.
