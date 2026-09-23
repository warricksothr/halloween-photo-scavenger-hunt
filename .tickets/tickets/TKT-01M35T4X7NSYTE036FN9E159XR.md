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
updated_at: 2026-09-23T00:33:20Z
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
