---
schema: 3
id: TKT-01M35T4X7NSYTE036FN9E159XR
title: Integrate self-hosted GlitchTip for errors and tracing
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - frontend
  - operations
  - tracking
assignees: []
milestone: null
parent: TKT-01M33S2WHFKP09V3Z7TM90Y1VQ
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/glitchtip-integration
  branch: t3code/integrate-glitchtip-error-tracing
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-0e2622bb
  commit: 794e300ea673ca01c905ba02abde408613aa4eb1
  session: null
  claimed_at: 2026-09-23T00:20:24Z
  expires_at: null
archive: null
created_at: 2026-09-23T00:20:16Z
updated_at: 2026-09-23T01:59:16Z
created_by:
  id: agent:opencode/glitchtip-integration
  name: ""
updated_by:
  id: agent:opencode/glitchtip-integration
  name: ""
extensions: {}
---

## Description

Integrate the self-hosted GlitchTip at https://glitchtip.nulloctet.com for error
and trace reporting from both surfaces. This replaces the planned Bugsink
sidecar (GlitchTip is already hosted, so no sidecar deploy is needed) and adds
tracing, which the original epic deliberately left out.

Libraries: `sentry-sdk[fastapi]` on the server and `@sentry/browser` on the web
(`@sentry/preact` does not exist on npm; the Preact app uses the browser SDK
directly). Both speak the Sentry ingest protocol, which is what GlitchTip
implements.

### Server

`server/app/errors.py`, inert unless `ARKHAM_ERROR_DSN` is set. FastAPI
integration for request transactions and spans, `send_default_pii=False`, and
`before_send` / `before_send_transaction` / `before_breadcrumb` scrubbers that
strip URL, query string, headers, cookies and bearer-code path segments. The
request id from `app/logging.py` rides as a tag. `create_app` initializes it
before the FastAPI app is constructed, and the global `Exception` handler calls
`capture_exception` — Sentry's ASGI middleware never sees an exception our
handler turns into a 500.

### Web

`web/src/errors.js` lazy-loads `@sentry/browser` only when `VITE_ERROR_DSN` is
set, so the SDK stays out of the entry bundle when unset. The same scrubbers run
in `beforeSend`/`beforeSendTransaction`/`beforeBreadcrumb`; the last
`X-Request-ID` becomes a tag. Initialized from `main.jsx`; `api.js` records the
response header.

### Deploy

`ARKHAM_ERROR_DSN` in the systemd EnvironmentFile and the compose passthrough;
`VITE_ERROR_DSN` as a Containerfile build arg and an `npm run build` env var;
the nginx CSP `connect-src` must allow the GlitchTip origin or the browser SDK's
posts are blocked.

Supersedes the Bugsink shape of TKT-01M33S2WQ, TKT-01M33S2WR and
TKT-01M33S2WV. The wider epic items (readyz, metrics, debug overlay) stay out of
this change.

## Acceptance criteria

- [ ] Server error and trace reporting is inert without ARKHAM_ERROR_DSN and active with it.
- [ ] Scrubbers keep bearer codes, query strings, cookies and headers out of errors, transactions and breadcrumbs; the request id is attached as a tag.
- [ ] The web SDK is lazy-loaded and absent from the entry bundle without VITE_ERROR_DSN, and reports errors and traces when it is set.
- [ ] nginx CSP permits the GlitchTip ingest origin and the systemd, compose and Containerfile env wiring is documented.
- [ ] Tests cover the inert path, the scrubbers and request-id tagging, and scripts/check-quality.sh passes.
- [ ] ADR, docs/progress.md and deploy/RUNBOOK.md record the decision and the operator steps.

## Implementation plan

1. Dependencies: add `sentry-sdk[fastapi]` to `server/pyproject.toml` and
   `@sentry/browser` to `web/package.json`; regenerate `server/uv.lock` and the
   hash-pinned `server/requirements.lock` together.
2. Server: `server/app/errors.py` — read `ARKHAM_ERROR_DSN`,
   `ARKHAM_TRACES_SAMPLE_RATE`, `ARKHAM_ENVIRONMENT`, `ARKHAM_RELEASE`; init a
   Sentry client with `send_default_pii=False` and the scrubbers; expose
   `capture_exception` that tags the request id. Inert (no client) without a DSN.
   Reuse the redaction rules in `app/logging.py`.
3. Wire `server/app/main.py`: initialize before `FastAPI(...)` so the
   integration patches the route handler factory, and call `capture_exception`
   from the global `_internal_error` handler.
4. Web: `web/src/errors.js` with a lazy `import('@sentry/browser')`, the mirror
   of the server scrubbers, `reportError`, and a last-request-id tag; record the
   header in `web/src/api.js`; initialize in `web/src/main.jsx`.
5. Deploy: allow the GlitchTip origin in the nginx CSP `connect-src` and update
   the guard test; add the DSN env to `deploy/arkham-hunt.service`, `compose.yml`
   and the `Containerfile` web build arg.
6. Tests: `server/tests/test_errors.py` and `web/src/errors.test.js` covering the
   inert path, scrubbers and request-id tagging. Write ADR 0017, update
   `docs/progress.md` and `deploy/RUNBOOK.md`.
7. Gate: `bash scripts/check-quality.sh`.

## Notes

**agent:opencode/glitchtip-integration** at 2026-09-23T00:33:20Z

Implementation changed from the plan's 'handler calls capture_exception' to 'handler calls bind_request_id (tag-only)': reporting from the handler duplicated every 500 because the two carries (generic vs starlette mechanism) are not deduped. Auto-capture by Sentry's ASGI middleware yields exactly one event, and the handler tags the scope so that event carries the request id. Function renamed capture_exception -> bind_request_id.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:04:35Z

PR #20 opened: https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/20. Head f8e946c24b50963ec2b46d1adce0c49b66982ce3, base 4a28e2f54b2a79f0cd49634bb2546a43767b8fce.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:04:51Z

Terva review requested: workflow terva-review.yml dispatched on ref main with pr=20, request-id=ready-review. Run task id 22498 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions?workflow=terva-review.yml).

**agent:opencode/glitchtip-integration** at 2026-09-23T01:11:47Z

Terva reviews posted for head f8e946c24b50963ec2b46d1adce0c49b66982ce3 (base 0bc6c11b1ff5611825299b1ef1be461c7fd4f19a was the config commit; PR base moved to 4a28e2f54b2a79f0cd49634bb2546a43767b8fce after PR #19 merged).

- Review 209, run 707377c5-707b-49a4-b705-029b103ffff0, Actions run #319 (id 9038), request ready-review: high scrub_text absolute-URL leak (web/src/errors.js:59); medium main.jsx:27 init not awaited before refresh; medium reportError has no production call site (errors.js:160).
- Review 210, run 4d1266f3-c751-4b58-8f4a-0d5a97f47739, Actions run #320 (id 9041), request ready-review-2: high no browserTracingIntegration (errors.js:145); medium browser DROPPED_REQUEST_KEYS omits env (errors.js:20).

The failed run #314 was infra (reviews had not posted); retry produced 209/210.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:15:29Z

Addressed both reviews on head f8e946c. All five findings accepted:
- scrub_text absolute-URL leak (high, both reviews' #1 style): server/app/errors.py _scrub now routes absolute-URL tokens through scrub_url via _ABSOLUTE_URL regex; web/src/errors.js scrubText now routes ABSOLUTE_URL tokens through scrubUrl. Tests: test_scrub_text_redacts_path_like_tokens absolute cases, test_scrub_transaction_scrubs_spans absolute span description, web transaction + breadcrumb absolute-URL tests.
- browser tracing (high): web/src/errors.js Sentry.init now installs browserTracingIntegration(); test asserts it and that config.integrations contains it.
- env dropped (medium): added 'env' to web DROPPED_REQUEST_KEYS (and asserted data too) to match the server.
- async init race (medium): web/src/main.jsx now chains refresh on initErrorReporting().finally(refresh) so Sentry's handlers are installed before the first request.
- reportError orphan (medium): web/src/store.js adds reportFailure() and calls it at all four caught-error paths (refresh snapshot, refresh modState, join, modJoin), reporting only 5xx/network (never a 4xx the player can act on). store.test.js asserts report on 500/503 and no report on 400.

Quality gate: bash scripts/check-quality.sh exit 0 — 330 server tests @ 95.05%, 20 deploy checks, 57 frontend tests, production build. Bundle re-verified: no DSN → no Sentry chunk (56.09 kB entry); DSN → separate 447.71 kB lazy chunk, entry free of sentry references.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:15:41Z

Re-requested Terva review after the fixes: request review-fixes-1, PR 20 head f047122 (base f8e946c parent; PR base still 4a28e2f on main). Dispatch HTTP 204. Polling for the Actions run and the posted review.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:18:31Z

Second Terva review (211, head f047122, run c30e3edc-96d6-435d-abd6-0cc5ee5147b4, Actions run #323/id 9048, request review-fixes-1): both prior findings resolved. Two new findings, both accepted:
- high exception-message leak: scrub_event now scrubs exception.values[*].value/type/module and logentry.message via scrub_text on server, and the browser mirror; tests place a credential in an exception message and a logentry on both surfaces.
- medium stale request id: errors.js adds beginRequest() (clears id) and recordRequestId now clears on falsy; api.js calls beginRequest() before every fetch, so a request that never got headers reports with no id. HTTP failures still carry the response id (recorded before returning the error result). api.test.js asserts the stale id is cleared on a rejected fetch and on a header-less response.
Quality gate re-run: exit 0 — 331 server tests @ 95.00%, 20 deploy checks, 60 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:23:51Z

Third Terva review (213, head de6cc5b, run 90a6c3c8-7112-4eee-adbb-99c9d84948f4, Actions run #328/id 9053, request review-fixes-2): both findings from 211 resolved; two new medium findings, both accepted and fixed:
- medium SDK-import latch: initErrorReporting now imports the chunk in a try/catch, sets started only after the SDK is in hand, and swallows the failure so a later call retries and no rejection escapes; main.jsx wraps the chain as initErrorReporting().then(refresh, refresh) so a reporter-boot failure cannot block boot or surface as an unhandled rejection. Test: a first import that throws, then a second that succeeds, reporting goes live.
- medium request-id race: the response X-Request-ID is now carried on each failure result (requestId) and reportFailure passes it explicitly to reportError (new third arg); the module-global remains only for the SDK's own auto-capture, which cannot receive a per-call id. Tests: api.test.js asserts the result carries null on network/headerless failures and the explicit id on error results; store.test.js asserts the failing result's own id reaches reportError, not the global.
Quality gate re-run: exit 0 — 331 server tests @ 95.00%, 20 deploy checks, 63 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:26:27Z

Fourth Terva review (216, head 9bb18eb, run 45db22db-0d74-4780-8aba-ae385604c885, Actions run #334/id 9064, request review-fixes-3): both findings from 213 resolved; one new high finding, accepted and fixed:
- high top-level message leak: scrub_event now scrubs string-valued event['message'] (server) and cleaned.message (browser); tests on both surfaces place a credential in a top-level message and assert redaction.
Quality gate re-run: exit 0 — 332 server tests @ 95.00%, 20 deploy checks, 64 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:30:10Z

Fifth Terva review (218, head d9072d3, run 40306654-c7c3-49c1-88e4-d455311d3b87, Actions run #336/id 9076, request review-fixes-4): the top-level message finding resolved; one new high finding, accepted and fixed:
- high free-text redaction missed quoted/prefixed/multiline paths: scrub_text (server) and scrubText (browser) no longer split on whitespace and test each token's start. Both scan arbitrary text for a URL/path run (new _URL_IN_TEXT / URL_IN_TEXT regex), redact it in place, and peel back trailing sentence punctuation before restoring it. So 'request to `/api/join/SECRET` failed', url=/api/join/SECRET, and GET\n/api/join/SECRET\nfailed all redact the bearer and keep their surrounding text intact. Tests added on both surfaces for quoted, key-prefixed, and newline-separated paths.
Quality gate re-run: exit 0 — 333 server tests @ 95.00%, 20 deploy checks, 65 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:35:11Z

Sixth Terva review (219, head c1647f8, run 2dcf0a66-f14f-4769-ad2c-9f701c07268c, Actions run #338/id 9079, request review-fixes-5): the free-text redaction finding resolved; two new findings, both accepted and fixed:
- high frame locals: init now sets include_local_variables=False, and scrub_event defensively drops exception.values[*].stacktrace.frames[*].vars through a new _drop_frame_vars helper. Tests: a transport-level test holds a credential in a runtime-built local and asserts it is absent from the serialized envelope; a unit test feeds a frame carrying vars and asserts they are dropped. (Note: with this SDK, frame vars do not appear in the envelope either way, so the unit test is the deterministic guard and the option is the documented one.)
- medium setContext shape: reportError now passes the scalar fields as one named object via scope.setContext('app', fields) instead of a primitive per key; the errors test asserts the 'app' object shape.
Quality gate re-run: exit 0 — 335 server tests @ 95.03%, 20 deploy checks, 65 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:38:53Z

Seventh Terva review (220, head 3f8f61e, run 2d77a102-eda1-4550-91ef-8377a4dce9d1, Actions run #340/id 9118, request review-fixes-6): both prior findings resolved; one new high finding, accepted and fixed:
- high bare-path query/fragment: scrub_text's _replace sent a bare-path match straight to redact_path, which redacts only designated bearer segments and keeps any query string or fragment, so '/api/state?token=SECRET' survived. Both surfaces now route every match — bare path and absolute URL alike — through scrub_url/scrubUrl, which was already able to drop query and fragment for a schemeless path. Tests added on both surfaces for a query and a fragment on an ordinary (non-bearer) path.
Quality gate re-run: exit 0 — 336 server tests @ 95.02%, 20 deploy checks, 66 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:41:46Z

Eighth Terva review (221, head 2c0b242, run f086a9f3-b7d5-435c-a2ba-2d90edb0bed2, Actions run #342/id 9128, request review-fixes-7): the bare-path query/fragment finding resolved; one new high finding, accepted and fixed:
- high span-data query/fragment: both span scrubbers only used scrub_url for an allowlisted URL key, and sent any other '/' -starting value through redact_path, which keeps a query or fragment. Both now run every string span-data value through scrub_url/scrubUrl, which redacts a bearer segment and drops query and fragment for a bare path, an absolute URL, or plain text alike; the now-redundant URL-key allowlist was removed on both surfaces. Tests added on both surfaces for a query and fragment under a non-URL key such as path.
Quality gate re-run: exit 0 — 337 server tests @ 95.11%, 20 deploy checks, 67 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:45:41Z

Ninth Terva review (222, head e6bd5fe, run df483f79-46e1-3b4d-8318-8f7d0dc913e1 -> run df483f79, Actions run #344/id 9132, request review-fixes-8): the span-data query/fragment finding resolved; one new high finding, accepted and fixed:
- high breadcrumb data: scrub_breadcrumb/scrubBreadcrumb kept every breadcrumb data key except the three URL fields, so headers, cookies, body data, env and query_string rode along — against the ADR/PR promise that before_breadcrumb drops them. Both now call a new recursive drop helper (_drop_sensitive_keys / dropSensitiveKeys) that removes the sensitive keys at any depth, so a nested request/response shape is covered. The request drop-list constant was unified into _SENSITIVE_KEYS. ADR 0017 wording updated to say the drop is recursive and covers breadcrumb/span data. Tests added on both surfaces for headers, cookies, body data, env, query_string, and a nested response.headers.
Quality gate re-run: exit 0 — 338 server tests @ 95.06%, 20 deploy checks, 68 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:49:29Z

Tenth Terva review (223, head abed8b3, run 1513c4a7-7f3c-4874-801e-67487bd6b0f7, Actions run #346/id 9137, request review-fixes-9): the breadcrumb-data finding resolved; one new high finding, accepted and fixed — same class in span data:
- high nested span data: _scrub_span/scrubSpan scrubbed only top-level string values and never recursed, so a nested response.headers, request.cookies/env, or query_string survived, against ADR 0017's recursive-drop wording. Both now route span data through a recursive scrubber (_scrub_span_data / scrubData) that drops sensitive keys at any depth and scrub_url/scrubUrl's every string; the web scrubData is shared with scrubBreadcrumb, replacing the per-key url/from/to list. The span data drop and the string scrub now happen in one recursive pass (previously the server scrubbed strings first, then dropped keys, leaving nested strings unscrubbed). Tests added on both surfaces for nested headers, cookies, env, query_string, and a query string on a nested url.
Quality gate re-run: exit 0 — 339 server tests @ 94.90%, 20 deploy checks, 69 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:54:34Z

Eleventh Terva review (224, head f55a22a, run 954921ff-a6c4-4e6d-9e31-9fad81164da6, Actions run #348/id 9162, request review-fixes-10): the nested-span-data finding resolved; one new high finding, accepted and fixed:
- high prose in span/breadcrumb data: the recursive data scrubbers sent every string through scrub_url/scrubUrl, which only redacts when the whole value starts with a bearer path or a URL, so a diagnostic field like note='request to /api/join/SECRET failed' kept its code. Both surfaces now send data strings through scrub_text/scrubText, which finds an embedded path and drops any query/fragment with it. On the server, _drop_sensitive_keys was folded into one recursive _scrub_data that both drops sensitive keys and scrubs every string, used by scrub_breadcrumb and _scrub_span (breadcrumb data previously dropped keys but did not scrub strings). Tests added on both surfaces for an embedded bearer path in span data and breadcrumb data.
Quality gate re-run: exit 0 — 340 server tests @ 95.08%, 20 deploy checks, 70 frontend tests, build.

**agent:opencode/glitchtip-integration** at 2026-09-23T01:59:16Z

Twelfth Terva review (225, head a070252, run 35a58e74-7599-4bf6-a4cd-876508d50860, Actions run #350/id 9176, request review-fixes-11): the prose-in-data finding resolved; one new medium finding, accepted and fixed:
- medium uncorrelated errors re-correlated at beforeSend: reportError(error, context, null) means 'do not correlate', but scrubEvent's fallback re-added the module-global lastRequestId whenever the event had no request_id tag, so a concurrent request finishing between capture and beforeSend could attach the wrong id. reportError now marks an explicit null with scope.setContext('arkham_uncorrelated', {value: true}); scrubEvent reads and deletes that marker and skips the global fallback. Test: explicit-null report, then the global moves, then scrubEvent — no tag attached and the marker removed. Server unchanged: it has no global fallback, bind_request_id is tag-only and auto-capture is the single path.
Quality gate re-run: exit 0 — 340 server tests @ 95.08%, 20 deploy checks, 71 frontend tests, build.
