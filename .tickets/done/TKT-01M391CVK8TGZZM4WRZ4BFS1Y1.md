---
schema: 3
id: TKT-01M391CVK8TGZZM4WRZ4BFS1Y1
title: Link the admin, moderator and player views to each other
type: task
status: done
status_reason: null
priority: normal
due_on: null
labels:
  - frontend
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies:
  - TKT-01M391CVFHW62D1KF3E5Y3KACC
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-24T06:24:40Z
updated_at: 2026-09-24T23:52:49Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Reported by Drew on 2026-09-24: the admin console has no link to the moderator console or back to the game, and the moderator console has none either.

### What the code does
- **Admin console.** The header in `web/src/screens/Admin.jsx:110-122` holds only the title, a literal `/admin` label and Sign out. The only links are the OIDC login and the redirect after sign-out.
- **One-time codes panel.** `AdminEvents.jsx:259-260` builds the `/j/<code>` and `/m/<code>` URLs only inside the panel shown once at creation, as QR codes, text and copy buttons, not as links.
- **No links elsewhere.** `ModConsole.jsx` and `components/Header.jsx` contain no `href`. The only cross-link is "Go to the host console" on the moderator refusal screen (`ModJoin.jsx:87-91`).
- **Not specified.** `docs/impl/ui.md:36-41` does not cover navigation between the three views.

### Likely fix
- The admin header gains "Moderate" and "Player view" links, and each event row gets per-event links once the codes can be shown again.
- The moderator console header gains a "Host console" link, shown when the session is also an admin.
- The exact targets depend on the moderator-role decision: with global moderators, "Moderate" is simply `/mod`.

## Acceptance criteria

- [x] The admin console links to the moderator view and the player view, and the moderator console links back to the host console for an admin.
- [x] Links that need an event (a mod link) are available per event row.

## Implementation plan

Admin → moderator: the event card's revealed mod card already has 'Open moderator console' (PR #48), which covers AC2. The admin header adds a 'Moderator console' link to /mod (the console this browser last joined) and a 'Player view' link to / (the landing page, whose Open Cases lists this browser's games). Moderator → host: /api/mod/state's moderator object gains host = auth.current_admin(request) is not None; the console header shows a 'Host console' link to /admin beside Leave console when it is true. It is a hint only; /api/admin checks every call. Tests: test_mod (host flag true for a password host, false for an SSO moderator, false after admin logout), Admin.test and main.test for the links, and an admin-phone e2e that follows the links at 390px with no overflow.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T07:19:46Z

2026-09-24: no longer waits on TKT-01M391CVJ10G0HGZR8ZFZB6RW4 (Decide how SSO roles map to moderating events), which was retired with per-event moderation kept. So a 'Moderate' link has to be per event. The revealed mod card's 'Open moderator console' (PR #48) already covers the admin→moderator direction for each event. What remains is moderator→host console and admin→player view.

**agent:claude-code/t3code-bf267378** at 2026-09-24T22:08:03Z

Promoted to ready 2026-09-24 at Drew's request as batch 2, to follow batch 1.

**agent:claude-code/t3code-bf267378** at 2026-09-24T23:14:28Z

PR #62 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/62), branch t3code/view-links, stacked on #61.

Terva reviews:
- pr62-view-links-1, run 727, head bff0aae. Two findings:
  - medium: no .tickets change in the PR. Declined, because ticket changes are committed to main.
  - low: the SSO moderator case is untested. Declined with evidence: the test's plain moderator comes from test_mod._mod, which signs in through support.sign_in_moderator, the planted SSO identity. 805afad adds a comment saying so. An SSO host case was tried and dropped: the stub plants only the identity cookie, while a real SSO admin sign-in also creates the host session, and that session is all the flag reads.
- pr62-view-links-2, run 728 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/728), head 805afad4de442ea084f1da100452651135755e4b: only the declined .tickets item remains, and the reviewer marked the SSO item unassessable from the diff (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/62#issuecomment-12676).

Local gate passes; npm run test:e2e 11/11. Awaiting Drew's merge authorization.

## Summary

Merged in PR #62 (merge ca1de54). The host console links to the moderator console and player view, and the moderator console links back when this browser holds a host sign-in. Deployed to scavenger.nulloctet.com at 37486df on 2026-09-24.
