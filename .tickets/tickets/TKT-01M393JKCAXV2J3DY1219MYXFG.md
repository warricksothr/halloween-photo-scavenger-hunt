---
schema: 3
id: TKT-01M393JKCAXV2J3DY1219MYXFG
title: Let the host join an event's moderator console
type: bug
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - frontend
  - moderation
  - security
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references:
  - ref: ticket:TKT-01M391CVJ10G0HGZR8ZFZB6RW4
    path: null
  - ref: adr:0020
    path: docs/adr/0020-moderator-link-selects-event-oidc-identity.md
claim:
  actor: agent:claude-code/t3code-bf267378
  branch: t3code/host-moderates
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-bf267378
  commit: a7804f68b9accfa5f52df25d5eb23fd58387de48
  session: null
  claimed_at: 2026-09-24T07:02:46Z
  expires_at: null
archive: null
created_at: 2026-09-24T07:02:45Z
updated_at: 2026-09-24T07:02:46Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Reported by Drew on 2026-09-24. Following the demo event's moderator link as the host shows "You are signed in as the host. The moderator console needs a moderator account." For the real event, the same friend will be both host (admin) and moderator, so as things stand that person cannot moderate at all.

### Cause
- `POST /api/mod/join/{mod_code}` depends on `oidc.require_oidc_moderator` (`server/app/mod.py:51`). That accepts only an SSO identity whose role is `moderator` (`server/app/oidc.py:398-413`).
- `role_for` makes an admin-group member an admin even when they are also in the moderator group (`oidc.py:352-358`). The callback then mints only an admin session, with no identity, and returns with `?sso=not_moderator` (`oidc.py:695-706`).
- This contradicts `docs/design.md:305-306`: the admin "can create events, manage riddles, and act as moderator". ADR 0020 chose the refusal.

### Decision (Drew, 2026-09-24)
Fix it on the host side: the host can join an event's moderator console through its mod link. The larger question, whether moderators should be global, stays open in TKT-01M391CVJ10G0HGZR8ZFZB6RW4 (Decide how SSO roles map to moderating events).

## Acceptance criteria

- [ ] A host signed in through Authentik (admin group) who opens an event's mod link lands in that event's moderator console, joined under their own SSO subject and name.
- [ ] A host signed in with the local break-glass password can do the same, under a fixed host identity.
- [ ] A plain SSO moderator still joins as before; anyone else, and the admin API token, is still refused.
- [ ] An ADR amends ADR 0020, and api.md and progress.md match.
- [ ] Verified on kobal: the host reaches the demo event's moderator console.

## Implementation plan

### Server
- `oidc.py` callback: an admin sign-in also mints the SSO identity cookie with role `admin`, alongside the admin session, so the join knows the person's subject and name. The `not_moderator` marker goes away, and a host who followed a mod link returns to that link.
- A new dependency, `require_moderator_identity` (it replaces `require_oidc_moderator` on the join). It accepts:
  - an SSO identity with role `moderator` or `admin`;
  - otherwise a live admin **cookie** session, as a synthetic identity: subject `local:<admin username>`, label the username. This is the break-glass host.

  The admin API token is refused: it is a script credential, and a moderator session gives a script nothing.
- Tests:
  - an OIDC admin joins as themselves;
  - the password host joins as `local:admin`;
  - a rejoin reuses the moderator row;
  - the API token and anonymous callers get 401;
  - a moderator is unchanged;
  - the callback mints both cookies for an admin, and neither for a refusal.

### Client
- `ModJoin.jsx`:
  - load the default theme, which fixes TKT-01M391CVGSJYGFHXR4ANZTDZBD (Style the moderator sign-in screen and normalise mod codes);
  - trim and upper-case both the typed code and the code from the link;
  - drop the `not_moderator` refusal.
- The revealed moderator card on the admin console gets an "Open moderator console" link, so the host has one click from the event card.

### Records
- An ADR amending 0020.
- api.md markers.
- progress.md.
