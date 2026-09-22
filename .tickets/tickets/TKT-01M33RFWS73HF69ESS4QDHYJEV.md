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
updated_at: 2026-09-22T18:17:29Z
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
- Rewrite `web/public/sw.js` around a single rule: every same-origin GET is
  network-first, and the cache is the offline fallback. A navigation that
  misses falls back to `/index.html` so a deep link still opens offline.
  Successful responses refresh the cached copy.
- Leave `/api/` and cross-origin requests alone (no interception): the
  snapshot contract owns game state, and this worker does not answer for
  another origin.
- An earlier revision kept a cache-first path for hashed `assets/*` bundles.
  Review found the predicate could not tell a hashed bundle from any other
  file under `/assets/`, so that path was removed rather than pattern-matched;
  network-first is simpler and nothing can be served stale. Hashed bundles
  stay cheap via the server's `Cache-Control: immutable` plus the HTTP cache.
- Rename the cache to `arkham-shell-v2`, so this deploy's install evicts the
  stale v1 shell in `activate` and the change is observable.
- The server already sends `Cache-Control: no-cache` for `sw.js` and
  `index.html` (`server/app/main.py:156-187`), so the browser revalidates the
  worker each load; the fix is entirely on the worker side.

### Tests
- `web/src/service-worker.test.js`: load the worker source, run it against a
  fake `self`/`caches`/`fetch`, and assert install prefetch, activate eviction,
  navigation network-first (old shell cached, new build served), offline
  navigation and asset fallback, a fresh asset winning over a cached one,
  `/api/` and cross-origin bypass, and that the cache write is awaited.
- `web/e2e/service-worker.spec.js`: real browser against the built app — load,
  wait for the worker to control the page, rewrite `dist/index.html` to stand
  in for a deploy, reload, and assert the new markup is served.
- The load-bearing unit tests and the smoke fail on the pre-fix worker
  (verified), so they prove the change rather than describe it.
- `playwright.config.js` gets `workers: 1`: the specs share one served build
  and the smoke rewrites it.

### Verification
- `npm --prefix web test` (35 pass), `npm run test:e2e` (both specs pass),
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

**agent:opencode/sw-deploy-safe** at 2026-09-22T18:17:29Z

### Round 2 — one resolved, one accepted by removing the special case

Reviewed head `ab206444cfdf135e4a8095b163e8c215d80aa555` (review id 154), Terva
run `2dfb557c-f969-476f-b9c0-c74d12798da4` for `request:sw-deploy-safe-2`,
Actions run #161 (id 8727).

- **finding-2 (awaited cache writes) — resolved** by the reviewer's reading.
- **finding-1 — present, narrowed** to the `/assets/` predicate: cache-first
  still accepted any same-origin path under `/assets/`, hashed or not.
  Accepted. Rather than pattern-match Vite's filename hash, the cache-first
  path is gone entirely: every same-origin GET is network-first with the cache
  as the offline fallback. That is one rule instead of two, and no path can be
  served stale. `/api/` and cross-origin requests remain unintercepted. The
  hashed bundles stay cheap because the server marks them `immutable` and a
  worker `fetch()` reads through the HTTP cache.

The plan on this ticket has been revised to the final policy. Fixed in
`bd9ddec`; the PR description was updated to match. Re-requesting review.
