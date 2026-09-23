---
schema: 3
id: TKT-01M33RFWXA9R29N0YQXBYM43Y1
title: Fix standings loading and add mod cooldown/note controls
type: bug
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
  - moderation
  - leaderboard
assignees: []
milestone: null
parent: TKT-01M33RFWE1TGCC61P6NJX0NMG0
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T16:47:44Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

Standings can spin forever when the response is empty or an error is swallowed, and moderators have no UI to set a cooldown or leave a note even though the backend supports it.

## Acceptance criteria

- [x] Standings render an empty or error state instead of an endless spinner.
- [x] A moderator can set a cooldown and attach a note from the console.

## Implementation plan

Standings: the closed branch calls `api.recap()` and only stores the result when it has no `error`, so a failed or `unauthenticated` recap leaves `recap === null` and the "Compiling the night's intel…" line up forever. Capture the failure in its own state, render a themed error line with a Retry button that refetches, and treat a recap with no standings rows as the empty state rather than an empty panel. Guard a missing `timeline` with `?? []`.

Moderator console: the backend already accepts `{ note?, cooldown_minutes? }` (`server/app/mod.py` `InappropriateBody`, cooldown only used at strike 2, default 15) and `api.modInappropriate` already forwards both, but the console hardcodes `('', null)`. Add a note field (280 chars, matching the server) and a cooldown number field (1–1440, prefilled 15) to the conduct section, send them on the armed confirm, reset them when the open item changes or the action succeeds, and reject an out-of-range cooldown with a plain (un-themed) message before firing — conduct copy stays plain by rule.

Tests: new `web/src/screens/Standings.test.jsx` (recap error shows the error and Retry refetches; empty standings show the empty line) and `web/src/screens/ModConsole.test.jsx` (arming the strike sends the typed note and cooldown to `modInappropriate`; an out-of-range cooldown is rejected without a call).

Docs: note the two new standings copy keys and the conduct controls in `docs/impl/ui.md`; add a `docs/progress.md` entry.

## Notes

**agent:opencode/t3code-0691bbb1** at 2026-09-23T16:43:46Z

Terva review history.

PR #37, base c59e089db03acacb94c2dc42cb329a5cef886e20.

- r1: request standings-mod-controls-r1, head 3f6d1465a5f7bc79d6b298680ed568b712ff0a0a, run 4d37cd1c-df7f-4024-99fc-77966e9b491b (Actions run #505, id 9403). One medium finding: a rejected `api.recap()` promise never reaches `.then`, so the closed-standings loading line still never cleared (web/src/screens/Standings.jsx:93). Fixed in d1d1c53 by adding a rejection handler that sets the same error state under the `stale` guard, plus a test that rejects and asserts the error + Retry; the test was verified to fail on the pre-fix component.

**agent:opencode/t3code-0691bbb1** at 2026-09-23T16:47:44Z

r2: request standings-mod-controls-r2, head 0d357e1e4324b990118adeed1a0e12763833279f, run 369a0d6c-291a-44c1-bf20-58a71998f96f, clean (no findings at the failure threshold); Quality gate success 2m14s. Merged at the reviewed head.

## Summary

Merged as PR #37 (head 0d357e1e4324b990118adeed1a0e12763833279f, base c59e089db03acacb94c2dc42cb329a5cef886e20, merge aa49bd09a2692d9b8621cd08083a6e34203882f2) after a clean Terva r2 and a green quality gate.

Standings: the closed recap fetch now captures a resolved error, an unauthenticated response, and a rejected promise into an error state that renders a themed error line with a Retry button; a final board with no rows shows the empty state, and a missing timeline is guarded. Copy keys `screens.standings.error` and `.retry` were added to the arkham pack.

Moderator console: the conduct section takes a note (280 chars) and a strike-2 cooldown in minutes (1–1440, default 15), rejects an out-of-range value before firing, and resets both when the open item changes. The values reach `api.modInappropriate`, which already forwarded them; the server ignores the cooldown outside strike 2.

Tests: new `web/src/screens/Standings.test.jsx` and `web/src/screens/ModConsole.test.jsx`; web suite 134 tests. `bash scripts/check-quality.sh` passes.
