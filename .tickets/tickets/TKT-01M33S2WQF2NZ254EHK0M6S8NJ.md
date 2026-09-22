---
schema: 3
id: TKT-01M33S2WQF2NZ254EHK0M6S8NJ
title: Add a no-op error-reporting layer with scrubbers
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - security
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
  branch: t3code/review-next-work
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0691bbb1
  commit: 794e300ea673ca01c905ba02abde408613aa4eb1
  session: null
  claimed_at: 2026-09-22T22:40:03Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:23:13Z
updated_at: 2026-09-22T23:31:29Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

Bugsink is Sentry-SDK compatible and self-hosted, so sentry-sdk can report exceptions to it. Put the SDK behind a single server/app/errors.py that is inert unless a DSN is set. Bugsink recommends send_default_pii=True for self-hosted installs, but this app must do the opposite: the PWA URL and several routes carry bearer codes in the path, and request headers carry the session cookie. Keep PII off and scrub url, query, headers, cookies, breadcrumbs, and local variables.

## Acceptance criteria

- [x] server/app/errors.py initializes reporting only when ARKHAM_ERROR_DSN is set and is inert otherwise.
- [x] before_send and before_breadcrumb strip url, query_string, headers, cookies, and known bearer-code path segments.
- [x] The request id is attached as a tag.
- [x] A test asserts the DSN secret and a join code never appear in the serialized event.

## Implementation plan

### Scope and boundaries

S2WQ owns the in-process reporting seam and its scrubbers. It does **not** deploy Bugsink or set ARKHAM_ERROR_DSN on any host (S2WV), nor wire the PWA side (S2WR). After this ticket `sentry-sdk` is a runtime dependency, but `create_app` never calls `sentry_sdk.init` in tests or local runs because no DSN is set.

### Shape

New `server/app/errors.py`:

- `Scrubber(secrets=())` with `scrub_event(event, hint=None)` and `scrub_breadcrumb(crumb, hint=None)`, both Sentry hook signatures and both returning their argument (or `None`). Constructor injects the strings to redact so tests never need the SDK.
- `init_error_reporting(dsn, *, release=None, environment=None) -> bool`: `False` and no SDK work when `dsn` is falsy; otherwise one `sentry_sdk.init(...)` with `send_default_pii=False`, `traces_sample_rate=0.0`, `before_send`/`before_breadcrumb` bound to a `Scrubber` seeded with the DSN and its key, and the request id attached as a tag. It is inert, not erroring, when the DSN is malformed.

### Redaction rules

- `request.url`: split, redact the path with `logging.redact_path`, collapse a non-empty query to `<redacted>`, drop the fragment.
- `request.query_string`: `<redacted>` when present.
- `request.headers`, `request.cookies`, `request.data`, `request.env`: removed entirely — bodies carry join codes and cookies are sessions.
- Exception `stacktrace.frames[].vars`: removed (local variables are the other PII channel).
- Every remaining string is deep-scrubbed for the DSN, its userinfo, and its public key.
- `request_id` from `logging.current_request_id()` is written to `event["tags"]`.

### Wiring

`create_app` calls `errors.init_error_reporting(os.environ.get("ARKHAM_ERROR_DSN"))` once, after `configure_logging()`. Unset is the normal case.

### Dependency

Add `sentry-sdk>=2.0` to `server/pyproject.toml` runtime deps; regenerate `server/uv.lock` and `server/requirements.lock` together (test_deployment_checks asserts they agree).

### Tests (`server/tests/test_errors.py`)

- No DSN: `init_error_reporting(None)` and `init_error_reporting("")` return `False` and do not register hooks.
- With a DSN: a join code in the URL, a bearer path, and a cookie never survive `scrub_event`; the DSN string and its key never appear anywhere in the serialized event.
- A frame-local secret is gone.
- The request id set via the logging contextvar lands as a tag.
- `scrub_breadcrumb` redacts a URL and drops headers.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-22T22:43:25Z

Implemented and verified locally. server/app/errors.py adds Scrubber (before_send/before_breadcrumb) and init_error_reporting; create_app wires ARKHAM_ERROR_DSN and stays inert when unset. sentry-sdk>=2.0 added to server/pyproject.toml with uv.lock and server/requirements.lock regenerated together. bash scripts/check-server.sh is green: 320 tests, 95.09% coverage, Ruff check and format clean. All four acceptance criteria ticked. NOT yet committed or pushed, no PR opened.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T22:52:50Z

Opened PR #18 (branch t3code/error-reporting-layer, head f7844af45b3e327a97f9c271721b8e41ba449a4b, base 794e300ea673ca01c905ba02abde408613aa4eb1) and requested a Terva review: request-id ready-review, run https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/260. Awaiting review and merge; the ticket closes with a separate store commit on main after the merge, as TKT-01M33S2WJ did.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:09:53Z

Terva review of head 8a21fd09 (run #265, request ready-review) published one finding.

### medium: malformed DSN can abort application startup
Accepted. `init_error_reporting` passed every non-empty value straight to `sentry_sdk.init`, and the SDK raises `sentry_sdk.utils.BadDsn` on a malformed DSN — confirmed against the pinned 2.70.0, where `not a dsn`, `https://`, and `ftp://...` all raise. A typo in `ARKHAM_ERROR_DSN` would therefore propagate through `create_app` and stop the server, contradicting the contract that a malformed DSN leaves reporting inert. Fixed by catching `BadDsn`, logging one `error_reporting_disabled` warning that names the reason but never the DSN (a DSN carries a key), and returning `False`.

Tests: `test_init_is_inert_with_a_malformed_dsn` (unit; asserts the warning and that the DSN text never appears) and `test_malformed_dsn_does_not_stop_the_app` (sets `ARKHAM_ERROR_DSN=not a dsn`, builds the app, and serves `/api/health`).

Evidence: head c1d38cb, `bash scripts/check-server.sh` green — 323 tests, coverage 95.18%, Ruff clean. Re-review requested after the push.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:16:59Z

Supersedes the note at head 439cadf.

### medium (review 187, run #270, request medium-finding-fix): the guard was too narrow
Terva confirmed the `BadDsn` case but kept the finding open: `Scrubber.for_dsn`
runs inside the same block and parses the DSN with `urlsplit`, which raises a
plain `ValueError` on an unmatched IPv6 bracket (`https://[`). Verified in the
pinned 2.70.0: `BadDsn.__mro__` is `(BadDsn, ValueError, ...)`, and
`urlsplit("https://[")` raises `ValueError: Invalid IPv6 URL`. The catch is now
`except ValueError`, and the comment says both failure modes are the same
"malformed configuration" case. The warning still names no DSN value.

Tests: the parametrized malformed-DSN test gained `https://[` (the case the SDK
never sees), and `test_malformed_dsn_does_not_stop_the_app` is now parametrized
over `not a dsn` and `https://[`, so both `create_app` paths are exercised.

Evidence: head 1f0b50d, `bash scripts/check-server.sh` green — 325 tests,
coverage 95.17%, Ruff clean (47 files formatted). Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:21:04Z

Supersedes the note at head 29fa7fd.

### medium resolved, new high (review 189, run #274, request parser-failure-fix)
Terva confirms the malformed-DSN medium is resolved: `except ValueError` covers
both the SDK's `BadDsn` and the `urlsplit` parser failure, and both are tested
through direct init and `create_app`. `finding-1` is resolved.

The same review opened a high: `_scrub_breadcrumb` dropped `headers` from a
breadcrumb and its `data` but never `cookies`, so an HTTP breadcrumb carrying a
session cookie was sent unchanged. The ticket's acceptance criterion says
`before_breadcrumb` strips cookies.

Accepted. Both pops now run over `_DROPPED_BREADCRUMB_KEYS = ("headers",
"cookies")` in both locations, matching the request scrub's cookie removal.
`test_breadcrumb_url_and_headers_are_scrubbed` became
`test_breadcrumb_url_headers_and_cookies_are_scrubbed` and now carries cookies
in the crumb and in `data` with a session value that is in no scrub set, so only
the drop removes it.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 325
tests, coverage 95.19%, Ruff clean (47 files formatted). Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:25:36Z

Supersedes the note at head 46fa8f3.

### medium (review 191, run #278, request breadcrumb-cookie-fix): secrets in mapping keys
Terva resolved the breadcrumb-cookie finding (`finding-1` resolved: headers and
cookies both dropped from the crumb and its `data`, with the test carrying
session cookies in both). The same review opened a medium: `_scrub_strings`
scrubbed mapping values but copied keys unchanged, and keys serialize. A DSN,
userinfo, or public key used as an `extra` key was therefore sent intact, which
the ticket's "the DSN never appears in the serialized event" criterion forbids.

Accepted. The dict branch now scrubs string keys through the same replacement as
values. Two keys that collapse onto `<redacted>` collide, and the first wins —
an event may lose a field, never send a secret.

Tests: `test_secrets_in_mapping_keys_never_serialize` puts the DSN and the public
key in nested mapping keys, serializes the event, and asserts neither leaks
while the surviving redacted key keeps its value. The pre-existing assertions
that the DSN and key stay out of the blob still hold.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 326
tests, coverage 95.20%, Ruff clean (47 files formatted). Re-review requested.

**agent:opencode/t3code-0691bbb1** at 2026-09-22T23:31:29Z

Supersedes the note at head dadd75b1.

### medium (review 194, run #282, request mapping-key-fix)
Terva resolved the mapping-key finding (`finding-1` resolved: `_scrub_strings`
now scrubs keys as well as values, first-wins on collision). The same review
opened a medium.

**medium: the breadcrumb's own URL and query keys bypass the scrubber.**
`_scrub_breadcrumb` applied `_scrub_mapping` only to the nested `data` mapping,
so a navigation breadcrumb carrying `url`, `to`, `from`, `query`, or
`query_string` at the top level kept its bearer path segment and query values.

Accepted. `_scrub_breadcrumb` now calls `_scrub_mapping(crumb)` before it
touches `data`, so both levels lose the credential and the query. The URL and
query keys can sit on either level, and one scrub per level covers both.

Test: `test_breadcrumb_url_headers_and_cookies_are_scrubbed` now carries a
top-level `url` and `query_string` beside the nested pair and asserts the join
code and query value are gone from the JSON, that the crumb's own `url` is
`https://hunt.example/m/<redacted>?<redacted>`, and that `query_string` is
`<redacted>`. The header and cookie drop assertions stay.

Evidence: head after this commit, `bash scripts/check-server.sh` green — 326
tests, coverage 95.21%, Ruff clean (47 files formatted). Re-review requested.
