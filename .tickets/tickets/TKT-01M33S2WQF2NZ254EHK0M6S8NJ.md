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
updated_at: 2026-09-22T23:09:53Z
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
