---
schema: 3
id: TKT-01M391CVK8TGZZM4WRZ4BFS1Y1
title: Link the admin, moderator and player views to each other
type: task
status: draft
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
updated_at: 2026-09-24T07:19:46Z
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

- [ ] The admin console links to the moderator view and the player view, and the moderator console links back to the host console for an admin.
- [ ] Links that need an event (a mod link) are available per event row.

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T07:19:46Z

2026-09-24: no longer waits on TKT-01M391CVJ10G0HGZR8ZFZB6RW4 (Decide how SSO roles map to moderating events), which was retired with per-event moderation kept. So a 'Moderate' link has to be per event. The revealed mod card's 'Open moderator console' (PR #48) already covers the admin→moderator direction for each event. What remains is moderator→host console and admin→player view.
