---
schema: 3
id: TKT-01M391CVJ10G0HGZR8ZFZB6RW4
title: Decide how SSO roles map to moderating events
type: spike
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - design
  - moderation
  - security
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies: []
blocks_on: none
references:
  - ref: ticket:TKT-01M33S9D3SV6RRDC7N5A6NWDK0
    path: null
  - ref: adr:0020
    path: docs/adr/0020-moderator-link-selects-event-oidc-identity.md
claim: null
archive: null
created_at: 2026-09-24T06:24:40Z
updated_at: 2026-09-24T06:24:40Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Raised by Drew on 2026-09-24. The moderator page "does not appear to accept Authentik or the per-event moderator code". He asks how the OIDC moderator group should relate to per-event moderators, and whether that role should instead moderate any event.

### How it works today (ADR 0020)
- **The code is not a credential.** `POST /api/mod/join/{mod_code}` requires an SSO identity whose role is `moderator` (`server/app/mod.py:47-52`, `oidc.require_oidc_moderator` at `oidc.py:398-413`). "The moderator link selects the event; it is no longer a credential" (`docs/adr/0020-moderator-link-selects-event-oidc-identity.md:31-37`). A code on its own gets a 401 and a redirect to Authentik.
- **The OIDC moderator role is global but moderates nothing by itself.** The callback creates an in-memory identity carrying the role (`oidc.py:718-733`). It is lost when the server restarts. Every `/api/mod/*` route except join needs the per-event `arkham_mod` session that the join creates (`auth.py:369-416`). A signed-in moderator therefore still needs each event's link.
- **The admin cannot moderate.** `require_oidc_moderator` rejects any role other than `moderator`. An admin who follows a mod link is refused with "You are signed in as the host. The moderator console needs a moderator account." (`ModJoin.jsx:19-20`, `oidc.py:695-706`). This contradicts `docs/design.md:305-306`: the admin "can create events, manage riddles, and act as moderator".
- **Moderators who sign in from the admin page hit a dead end.** They start from `next=/admin` (`Admin.jsx:163`), come back to `/admin`, fail the admin check, and see the login form again.
- **On kobal, Drew's Authentik login worked as admin.** The request log on 2026-09-24 shows the callback 303 followed by `GET /api/admin/events` 200, so the groups claim reaches the app. No `POST /api/mod/join` reached the server during his test.

### Options
1. **Keep ADR 0020**: an Authentik moderator plus a per-event link. Then fix the two gaps: the admin can also moderate, and the admin login sends a moderator identity to `/mod`.
2. **Global moderators**: the OIDC moderator role (and the admin) can moderate any open event, chosen from an event picker in the console. The per-event link becomes a shortcut that preselects the event. This drops the need to hand out mod links for a single-host party.
3. **Per-event grants**: the admin assigns Authentik users to events. This is the most control, and the most work, for a party-sized game.

Also decide:
- whether a bare mod code, without SSO, should work at all when OIDC is not configured (the LAN recipe)
- whether the in-memory identity must survive a restart

Record the result by amending or replacing ADR 0020, and bring design.md:305-306 into line. TKT-01M33S9D3 (Record the OIDC and role-mapping decision in an ADR) is the existing draft for that record.

## Acceptance criteria

- [ ] One option is chosen and recorded, amending or replacing ADR 0020, and design.md's admin-can-moderate line agrees with it.
- [ ] Follow-up implementation tickets are filed for the chosen option, including whether the admin can moderate and where a moderator's SSO login lands.
