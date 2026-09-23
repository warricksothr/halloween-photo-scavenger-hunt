---
schema: 3
id: TKT-01M33S2WKSSFJVSM1NC79NRK1P
title: Log unhandled exceptions with request correlation
type: task
status: done
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
claim: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-23T01:04:56Z
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

- [x] An unhandled exception logs one correlated traceback and returns a JSON 500 body carrying the request id.
- [x] The handler never logs secrets, cookies, or request bodies.
- [x] Covered by a test that raises from a route.

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

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:29:36Z

Supersedes the note at head ab98776.

### high + low (review 193, run #280, request duplicate-form-fix)
Terva resolved the repeated-form finding (`finding-1` resolved: every
`parse_qsl` value is kept and the new test raises with the first duplicate).
The same review opened a high and a low.

**high: malformed bodies and request-controlled keys.** `_body_secrets` returned
`()` when JSON did not parse, so `safe_traceback` stayed false and the message
was logged even though the app may have read the raw bytes; and `_strings_in`
walked mapping values only, so a JSON key the route quoted was never scrubbed.

Accepted. `_body_secrets` now returns `None` for a body it cannot represent, and
the middleware treats `None` like truncation: the message is dropped.
`_strings_in` yields mapping keys and form field names as well as values, since
app code can quote either; a repeated form field keeps every pair rather than
folding into a dict. The message now drops in exactly two cases — the buffer was
short or the body did not parse — and every request that parses keeps it.

Tests: `test_body_secrets_reads_json_and_form_values` expects keys and names;
the malformed case asserts `None`; `test_a_json_key_quoted_by_route_code_is_scrubbed`
shows the key redacted and the message kept;
`test_a_malformed_json_body_drops_the_exception_message` reads the raw body and
asserts `message_included is False` with the secret absent.

**low: the progress note contradicted the implementation.** `docs/progress.md`
still said headers, cookies, and the body are never read, while
`_request_secrets` reads `Authorization` and `Cookie` and the middleware buffers
JSON/form bodies. Rewritten to say those are read only to seed the scrub set and
never written to the log, with the two message-dropping cases and the current
test and coverage counts. The ADR was updated to match.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 329
tests, coverage 95.47%, Ruff clean (45 files formatted). Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:39:55Z

Supersedes the note at head 559dfa55.

### high (review 195, run #284, request unparsable-body-fix)
Terva resolved both previous findings (malformed bodies and mapping keys; the
progress note). The same review opened a high.

**high: percent-encoded secrets bypassed the scrub set.** `parse_qsl`
percent-decodes and turns `+` into a space, so a form body
`password=top%2Fsecret` produced the candidate `top/secret` only. A route that
read and quoted the raw bytes still contained `top%2Fsecret`, and because the
body parsed, `safe_traceback` stayed false and the message was logged. The same
gap existed for a raw query string.

Accepted, as "scrub both representations" rather than fail closed: encoded form
and query text is ordinary, so dropping the message for it would cost real
diagnostics. `_raw_query_tokens` yields the undecoded text and each
`&`/`=`-separated piece, and both `_body_secrets` (form branch) and
`_request_secrets` (query string) add those tokens beside the decoded names and
values. A route that quotes the raw body or the raw query is now covered, and
the message survives. JSON keeps the fail-closed path: a body that does not
parse returns `None` and drops the message.

Tests: the body-secrets unit test now holds both `top/secret` and
`top%2Fsecret`; `test_a_raw_encoded_query_is_scrubbed` raises with
`request.url.query` and `test_a_raw_encoded_form_body_is_scrubbed` raises with
the raw body, both asserting the encoded and decoded forms are absent.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 331
tests, coverage 95.50%, Ruff clean (45 files formatted). Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:46:08Z

Supersedes the note at head 6c3a34e5.

### high (review 198, run #291, request raw-encoded-fix)
Terva resolved the percent-encoding finding (`finding-1` resolved: the raw query
and form text ride beside the decoded values and integration tests cover both).
The same review opened a high.

**high: non-string JSON values were not in the scrub set.** `_strings_in`
collects strings, string keys, lists, and tuples only, so a body such as
`{"recovery_code": 12345678}` yielded no candidate. A route formatting the value
with an f-string logs the number, while the body parses and `safe_traceback`
stays false.

Accepted, as the fail-closed option the review offered. A number, boolean, or
null formats to text the string set cannot hold, and deciding per-value how much
redaction is too much is exactly the kind of cleverness that leaks later; the
message drops instead. `_unrepresentable` walks the decoded JSON and reports
whether any scalar is not a string; `_body_secrets` returns `None` for such a
body, so the middleware drops the message the same way it does for a body that
does not parse. The message still survives for a body of strings and containers
thereof, which is the normal API shape.

The JSON-key test's body changed from `{"topsecretkey": None}` to a string
value, because the null is now an unrepresentable body; it still proves the key
is scrubbed and the message kept.

Tests: `test_body_secrets_skips_binary_and_malformed_bodies` asserts `None` for
a top-level number and for a nested boolean;
`test_a_numeric_json_value_drops_the_exception_message` raises with the number
and asserts `message_included is False` with the digits absent.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 332
tests, coverage 95.49%, Ruff clean (45 files formatted). Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:50:15Z

Supersedes the note at head 0826a938. A commit landed after the
`json-scalar-fix` dispatch, so that run reports superseded; the fresh request is
`marker-single-pass-fix`.

### same class as PR #18's review 197
While fixing the non-string scalar finding I noticed `_scrub_secrets` on this
branch shared the rescan defect Terva found in `errors.py` (`value.replace`
in a loop, so a later secret can match the `<redacted>` marker an earlier
replacement inserted). The traceback scrub set holds body and query strings, so
a value of `redact` would survive its own redaction the same way.

Fixed here too: `_scrub_secrets` compiles one alternation of the secrets,
longest first, and runs a single `re.sub`, so replacement text is never
rescanned. `re` was already imported. `test_scrub_secrets_does_not_rescan_the_marker`
covers it.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 333
tests, coverage 95.49%, Ruff clean (45 files formatted). Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:56:49Z

Supersedes the note at head 5486e4a5.

### Review 199 (`json-scalar-fix`, head 0826a938) and review 201 (`marker-single-pass-fix`, head 5486e4a5)
Review 199 opened two highs and review 201 confirmed both still present. Review
201 also resolved nothing outstanding on the scalars (that fix held).

**high: a length floor left short request-derived secrets in the message.**
`_MIN_SECRET = 6` dropped every candidate shorter than six characters — a
four-digit PIN, a five-character code, a short cookie value — while the message
still logged them. Accepted as the review's first option: there is no floor now.
Every non-empty candidate is scrubbed, so a short value is replaced wherever it
appears, even when that touches an ordinary word. The guarantee is worth more
than a tidy message; the traceback frames still carry the diagnosis.

Removing the floor also means the JSON-key test's earlier worry about short
values is gone.

**high: a quoted cookie value bypassed literal scrubbing.** The collector split
the raw `Cookie` header and stripped whitespace, which left the quotes on, while
the framework's `SimpleCookie` parser strips them: a route reading
`request.cookies` saw `topsecret` and the scrub set held only
`"topsecret"`. Now the header is also loaded into a `SimpleCookie` (a
`CookieError` is ignored, since the framework would reject it too) and each
`morsel.value` joins the candidates. Both representations are scrubbed, matching
the raw-and-decoded approach already used for query strings and form bodies.

Tests: `test_request_secrets_collects_the_requests_own_values` now asserts a
short value is kept, with the floor comment replaced;
`test_request_secrets_unquotes_a_cookie_value`; and integration
`test_a_short_query_value_is_scrubbed` and
`test_a_quoted_cookie_value_is_scrubbed`.

Docs: ADR 0016 drops the floor paragraph for one that states no length floor and
the two cookie representations; `docs/progress.md` #19 entry follows.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 336
tests, coverage 95.43%, Ruff clean (45 files formatted). Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T00:06:32Z

Supersedes the note at head c6b56275.

### high (review 202, run #299, request short-secret-cookie-fix)
Terva resolved both earlier highs (`finding-1`: no length floor, four-digit test;
`finding-2`: `SimpleCookie` values join the set, quoted-cookie test). The same
review opened a high.

**high: a JSON escape could survive in the message.** The JSON branch derived
candidates only from `json.loads`, so `{"password":"top\u002fsecret"}` gave
`top/secret` but not the escaped `top\u002fsecret`. A route that reads the raw
body and quotes it logs the escaped form, and the body parsed, so the message
was not dropped. The form and query branches already carried their raw text;
JSON did not.

Accepted: carry it too. A new `_raw_json_tokens` yields the whole body text and
every quoted literal with escapes intact (`re.findall(r'"((?:[^"\\]|\\.)*)"')`),
which adds the escaped value beside its decode. This is the same
decoded-versus-raw pairing the form branch uses.

Tests: `test_body_secrets_reads_json_and_form_values` now asserts the escaped
literal is a candidate; `test_a_raw_escaped_json_body_is_scrubbed` proves the
escaped body is gone and the message kept.

Docs: `docs/progress.md` #19 entry follows.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 337
tests, coverage 95.37%, Ruff clean. Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T00:16:08Z

Supersedes the note at head fe8ee1fa.

### high (review 205, run #306, request raw-json-fix)
Terva resolved the escaped-JSON finding (`finding-1` resolved at fe8ee1fa) and
opened a new high.

**high: a multipart body leaked through the exception message.** `_PARSED_MEDIA`
holds only JSON and urlencoded form, and the middleware buffered nothing else.
A multipart request left `safe_traceback` false, so a route that read a
multipart field and quoted it in a `raise` logged the value verbatim. The ADR
recorded this as a residual, which the ticket does not allow.

Accepted. The middleware now counts every `http.request` body byte in `seen`,
for every media type. On an exception:
- a media type `_body_secrets` reads keeps the existing behavior;
- any other media type with `seen > 0` marks the message unsafe, because the
  app may have read a field the scrub set never held;
- a body-less request keeps its message.

`test_a_multipart_body_drops_the_exception_message` posts a `files=` field,
raises with the field's value, and asserts `message_included is False` and the
value absent. The route closes the parsed form, so the spooled upload does not
trip pytest's unraisable check in a later test.

Docs: the ADR's multipart residual is replaced with the fail-closed rule;
`docs/progress.md` #19 entry follows.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 338
tests, coverage 95.35%, Ruff clean. Re-review requested.

## Summary

Merged as 4a28e2f on main (PR #19, merge commit; branch merged main at f3129a3 after a docs/progress.md conflict). The app's `Exception` handler logs one `arkham` line (`event="unhandled_exception"`) with the request id, method, redacted path, and scrubbed traceback, and answers a JSON 500 carrying `request_id` echoed in `X-Request-ID`. Seed values for the traceback scrub set come from `Authorization`, `Cookie`, and a buffered JSON/form body (64 KiB cap); the buffer is consumed only on the failure path and never logged. A body that overflows, does not parse, holds a non-string JSON scalar, or is a media type the scrubber does not read (multipart) fails closed: `message_included` is false and the exception message is dropped. Every candidate is replaced in one pass. Clean Terva review at code head 307eef4c (run d0ffe791, request multipart-fail-closed, actions #306); findings fixed across rounds: duplicate form values, unparsable-body fail-closed, raw percent-encoding, raw escaped JSON literals, no length floor, quoted cookie values, one-pass replacement, and multipart fail-closed. Post-merge gate: 355 tests, coverage 95.33%, `check-quality.sh` green.
