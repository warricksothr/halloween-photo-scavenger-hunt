---
schema: 3
id: TKT-01M394KVSC6GCC1EDW4NSXZRW3
title: Let a mod link reach the console in a browser with a player session
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - frontend
  - backend
  - moderation
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/mod-link-wins
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: 6b0d8688111a2cd44ba7168aef48dd91f76c17a1
  session: null
  claimed_at: 2026-09-24T07:20:56Z
  expires_at: null
archive: null
created_at: 2026-09-24T07:20:55Z
updated_at: 2026-09-24T18:46:22Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Raised by Drew on 2026-09-24. The host of the real event will also moderate, and may test as a player on the same phone. A browser that holds a player session and opens a mod link shows the game, not the moderator sign-in or the console.

### Cause
- **The client probes the player first.** `store.refresh()` (`web/src/store.js`) calls the player snapshot first and only probes `/api/mod/state` when that returns 401. With a player cookie, the moderator path is never considered. That includes the moment right after a successful mod join, whose refresh lands back on the game.
- **The shell routes on that result.** `main.jsx` shows `ModJoinScreen` only in the `join` phase, so a ready player session swallows `/m/<code>` and `/mod`.
- **The stream has the reverse bias.** `/api/events/stream` picks the moderator cookie when both are present (`server/app/sse.py:189-199`). A game tab in a browser that also holds a moderator session silently gets the moderator stream and misses its player deltas.

## Acceptance criteria

- [x] In a browser holding a player session, /m/<code> joins that event's moderator console, and /mod shows the moderator console or its sign-in, never the game.
- [x] In the same browser, the player paths still show the game, so the host can keep a game tab and a moderator tab side by side.
- [x] Each tab's live-update stream matches the role it shows, even when both cookies are present.
- [x] Reloading the console does not rejoin or write another moderator.joined row, and following a different event's mod link switches to that event.
- [ ] Verified on kobal.

## Implementation plan

### The path decides the role when both sessions exist
- A shared `web/src/paths.js` holds the path matchers: `isModPath` (from main.jsx) and `modLinkCode`.
- In `store.refresh()`, on a mod path, probe `/api/mod/state` **first**. A moderator session goes to the console. Without one, the phase is `join`, and the shell shows `ModJoinScreen`, never the game. Player paths keep today's order: player first, then moderator.
- In the `main.jsx` shell, `/m/<code>` renders `ModJoinScreen` whenever the store is ready or in `join`, so the join attempt runs even while another session exists.
- In `store.modJoin`, a successful join does `history.replaceState(null, '', '/mod')` before refreshing. A reload of the console then does not rejoin (no second `moderator.joined`), and the `/m/<code>` rule does not loop. A later `/m/<code>` for another event joins that one; the join replaces the moderator cookie.

### The stream follows the role
- The client opens `/api/events/stream?as=<role>`, using the role the store resolved.
- `sse.py` honours `as=player|moderator` and uses that session, returning 401 if the cookie for that role is missing. With no `as`, today's behaviour stays.

### Tests
- **store:** refresh ordering on mod and player paths; modJoin replaces the URL; the stream URL carries the role.
- **main shell:** `/m/<code>` with a ready player session renders ModJoin.
- **server:** `as=` selection, a 401 for a missing role, and the default unchanged.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T07:34:48Z

PR #49, https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/49. It was merged at the reviewed head b7550d8682a5131f11076ebdc17dce01a0545557, as merge commit 675faec81149a5b638449123b511f076c54186c0, onto base e7002ec624d4c0641274cf0f5cb68b523069e5d4.

### Terva reviews
- **r1** (`mod-link-wins-r1`): head efb0265, run 16cf1deb, Actions #619, review 375.
  - **high, disputed with evidence:** "a reconnect calls startStream() without a role, so the stream opens with ?as=undefined". The reconnect timer calls `refresh()`, which resolves the role and reopens the stream through the only two `startStream` calls, and both pass a role.
  - The evidence was posted on the PR (issue comment 11502), and b7550d8 adds tests pinning `?as=player` and `?as=moderator` after a fatal `onerror`.
- **r2** (`mod-link-wins-r2`): head b7550d8, run 27911e84, Actions #622, clean-status comment 11504, status success. It marks the finding resolved, and its text agrees the reconnect path goes through refresh().
- The CI quality gate passed on b7550d8.

### Local end-to-end check (headless Chromium, one browser context, built app)
1. A player joined, and the tab showed the game.
2. The password host signed in, and the mod link opened in a new tab moved to `/mod` with the console.
3. A reload of the console stayed on the console, and the server logged one `mod/join` in total.
4. A reload of the game tab stayed on the game.
- The stream requests were `?as=player`, `?as=moderator`, `?as=moderator`, `?as=player`.

### Deploy on kobal (2026-09-24)
- The checkout and `ARKHAM_RELEASE` are at 675faec, and I ran `docker compose build && up -d`. The container is healthy with schema 3.
- Publicly, the stream answers 401 with no session for no `as`, `?as=player` and `?as=moderator`, and 422 for `?as=admin`.
- The live bundle requests `events/stream?as=`.

**AC5 is not ticked.** The live check needs a real player session and Drew's host sign-in in one browser. I did not add a test player to the live demo event.

**agent:claude-code/t3code-bf267378** at 2026-09-24T18:35:13Z

### Live check on kobal (Drew, iPhone, 2026-09-24): AC5 not met

Drew reports:
- The moderator link could not be clicked.
- A copied, pasted link showed an error.
- Visiting the page and typing the code joined and connected.

The kobal container log (codes redacted) matches:
- 18:31:53: `GET /m/<code>`, then `/api/mod/state` 401, then `POST /api/mod/join/<code>` **404** (bad_mod_code). This came after a fresh OIDC round-trip (login 303 at 18:30:55, callback 303 at 18:31:36).
- 18:32:30: `GET /m/` (typed-code form), `/api/mod/state` 401, `POST /api/mod/join/<code>` **201**, `/api/mod/state` 200.

So the server did not recognise the code the link carried, but the typed code matched. The code alphabet (`ids._CODE_ALPHABET`) fits the client's `modLinkCode` regex, and `ModJoin` upper-cases both paths, so neither explains the difference.

Unverified:
- Which surface the link came from. The URL text in `CodeCard` is a `<code>` element, not an anchor. The post-create CodesPanel has no open button, and the Links & QR card has "Open moderator console" with `target=_blank`.
- Whether that link belonged to another event.

Next: ask Drew which screen the link was on and where it was pasted. Then reproduce with a link copied from that surface.

**agent:claude-code/t3code-bf267378** at 2026-09-24T18:38:47Z

Drew confirmed the likely cause: the moderator link was not clickable or right-clickable, so he copied the URL text by hand and got a bad copy. Fix on branch t3code/mod-link-anchor: CodeCard renders the URL as an anchor (target=_blank) on both the post-create panel and Links & QR, so a phone can tap it or long-press for Copy Link. A join link still asks for a name before joining, so tapping it never creates a player. AdminEvents.test.jsx pins the href and target on both panels. The quality gate passes.

**agent:claude-code/t3code-bf267378** at 2026-09-24T18:39:56Z

PR #52, https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/52: head 34aa6487d4c3fa56f5ae17391cb1024038af0834, base 60a89f0f4b75769d8ec3e4a9b7560bc4a0213633. Terva r1 (mod-link-anchor-r1), run ad1b78e0, Actions #653, clean-status comment 12282: clean, no findings. Not merged yet: waiting for Drew's go-ahead. After the deploy, AC5 needs Drew to tap or long-press the mod link on the phone.

**agent:claude-code/t3code-bf267378** at 2026-09-24T18:46:22Z

Drew authorized the merge. PR #52 merged at the reviewed head 34aa648 as 7062d34 (CI quality gate success, Terva r1 clean). Deployed to kobal: container healthy, schema 3. The live bundle renders the card URL as <a class=admin-code-url href target=_blank>. AC5 still needs Drew to tap or long-press the mod link on the phone.
