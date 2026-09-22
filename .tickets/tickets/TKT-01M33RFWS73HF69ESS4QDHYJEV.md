---
schema: 3
id: TKT-01M33RFWS73HF69ESS4QDHYJEV
title: Make the service worker deploy-safe
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - deployment
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/sw-deploy-safe
  branch: t3code/sw-deploy-safe
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-9799aac5
  commit: 7c04c4912631c3fc477f3d75c259c02eb53e69b5
  session: sw-deploy-safe
  claimed_at: 2026-09-22T18:03:55Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-22T18:13:42Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/sw-deploy-safe
  name: ""
extensions: {}
---

## Description

The service worker caches navigation responses and uses a manually bumped cache name, so after a redeploy a phone can run an old shell against a new API with no invalidation.

## Acceptance criteria

- [ ] A deploy invalidates the old shell; navigation is network-first or the cache is build-stamped.
- [ ] A test or smoke proves the new build is served after a version change.

## Implementation plan

### Problem
`web/public/sw.js` is copied verbatim into the build, so a deploy that does
not touch the worker never reinstalls it. Its fetch handler is cache-first for
everything but `/api/`, so every navigation is answered from
`arkham-shell-v1` — a phone keeps running the old `index.html` and its old
hashed bundles against the new API. Bumping the cache name by hand is the only
way to release it, and nothing enforces that.

### Approach
- Rewrite `web/public/sw.js` around a per-request-type policy:
  - navigations (`request.mode === 'navigate'`) — network-first, cache the
    successful response, fall back to the exact cached URL then `/index.html`
    when offline;
  - same-origin GET assets (hashed `assets/*`) — cache-first, since the
    filename changes with the content;
  - `/api/` — untouched (network only).
- Rename the cache to `arkham-shell-v2`, so this deploy's install evicts the
  stale v1 shell in `activate` and the change is observable.
- The server already sends `Cache-Control: no-cache` for `sw.js` and
  `index.html` (`server/app/main.py:156-187`), so the browser revalidates the
  worker each load; the fix is entirely on the worker side.

### Tests
- `web/src/service-worker.test.js`: load the worker source, run it against a
  fake `self`/`caches`/`fetch`, and assert install prefetch, activate eviction,
  navigation network-first (old shell cached, new build served), offline
  fallback, `/api/` bypass, and cache-first hashed assets.
- `web/e2e/service-worker.spec.js`: real browser against the built app — load,
  wait for the worker to control the page, rewrite `dist/index.html` to stand
  in for a deploy, reload, and assert the new markup is served.
- Both fail on the pre-fix worker (verified), so they prove the change rather
  than describe it.
- `playwright.config.js` gets `workers: 1`: the specs share one served build
  and the smoke rewrites it.

### Verification
- `npm --prefix web test` (32 pass), `npm run test:e2e` (both specs pass),
  `bash scripts/check-quality.sh` exit 0.

## Notes

**agent:opencode/sw-deploy-safe** at 2026-09-22T18:13:42Z

### Round 1 — both findings accepted

Reviewed head `5fccc52006a22fa0d2087c962a67c193b61fca17` (review id 153), Terva
run `2da0d6ef-edd2-41e7-bde1-cd89da648752` for `request:sw-deploy-safe-1`,
Actions run #158 (id 8724).

- **medium — cache-first applied to unhashed and cross-origin requests.**
  Accepted. The handler now routes only same-origin `/assets/` GETs to
  `cacheFirst`; `/api/`, cross-origin requests, and unhashed same-origin
  resources are left to the network, and the manifest is no longer
  prefetched into the shell cache. New tests assert that
  `/manifest.webmanifest` and a `fonts.googleapis.com` request are not
  intercepted.
- **medium — navigation cache refresh can be abandoned before it completes.**
  Accepted. Both `cache.put` calls are now awaited. A new test holds the
  `put` promise open and asserts the navigation response does not settle
  until it resolves; it fails on the previous head, so the fake can detect
  the worker-lifetime failure the finding described.

Fixed in `1c1989f`. Re-requesting review.
