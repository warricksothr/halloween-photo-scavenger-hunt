---
schema: 3
id: TKT-01M393JKCAXV2J3DY1219MYXFG
title: Let the host join an event's moderator console
type: bug
status: done
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
claim: null
archive: null
created_at: 2026-09-24T07:02:45Z
updated_at: 2026-09-24T07:36:49Z
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

- [x] A host signed in through Authentik (admin group) who opens an event's mod link lands in that event's moderator console, joined under their own SSO subject and name.
- [x] A host signed in with the local break-glass password can do the same, under a fixed host identity.
- [x] A plain SSO moderator still joins as before; anyone else, and the admin API token, is still refused.
- [x] An ADR amends ADR 0020, and api.md and progress.md match.
- [x] Verified on kobal: the host reaches the demo event's moderator console.

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

## Notes

**agent:claude-code/t3code-bf267378** at 2026-09-24T07:17:15Z

PR #48, https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/48. It was merged at the reviewed head c0e2eedd8af7b7c2ce60cd60fcb02e116023f158, as merge commit 7d94385f546ab68748090515ff145f00d60b7a94, onto base 35f006a608ead1d50ecd1d83cb2e70630773831a.

### Terva reviews
- **r1** (`host-moderates-r1`): head ad27291, run 88dd0134, Actions #611, review 369.
  - **medium, accepted:** a provider subject starting with `local:` could share the password host's moderator row. The callback now refuses subjects in that reserved namespace, with a test that fails without the fix.
  - **medium, accepted:** a failed theme-chunk load left the mod sign-in blank forever. The screen now shows unstyled on rejection, with a test that fails without the fix.
  - **low, declined:** no .tickets/ change in the PR. In this repo ticket commits go straight to main, as on PR #47.
- **r2** (`host-moderates-r2`): head c0e2eed, run b2dfc1b7, Actions #613, review 371, status success. Both mediums are resolved; only the declined low remains.
- The CI quality gate passed on c0e2eed.

### Deploy on kobal (2026-09-24)
- The checkout and `ARKHAM_RELEASE` are at 7d94385, and I ran `docker compose build && up -d`. The container is healthy with schema 3.
- In the running container, `app.oidc.require_moderator_identity` exists and `require_oidc_moderator` does not.
- The live bundle contains "Open moderator console" and no longer contains the host refusal copy.

### Local end-to-end check (headless Chromium, built app)
- `/mod` signed out renders with the Arkham theme.
- The password host logged in, opened Links & QR, revealed the mod link, followed "Open moderator console", and landed in the demo event's queue. The join returned 201.

**AC5 is not ticked.** The host path on kobal goes through Drew's Authentik login, which I cannot perform. The restart also cleared every in-memory session, so Drew signs in again first.

**agent:claude-code/t3code-bf267378** at 2026-09-24T07:17:15Z

AC1 (the SSO host joins as themselves) and AC2 (the password host joins under local:<username>) are ticked on the strength of server tests that go through the real routes, plus the local browser run for AC2. AC5, the live check on kobal, is still open for Drew.

**agent:claude-code/t3code-bf267378** at 2026-09-24T07:36:49Z

AC5 verified on kobal on 2026-09-24 from Drew's screenshot of the live demo event's moderator console. The header reads 'The Riddler's Halloween — Demo Event — Moderator'. The queue shows 2 pending submissions (Robin and Toad on riddle #8, with Toad's flagged 'Shared?'), and both rows read 'DREW SHORT IS VIEWING', which is the claim label taken from Drew's Authentik display name. So the Authentik host joined the event's queue under their own identity, as ADR 0027 intends. The screenshot was not stored, because it contains player photos.

## Summary

Shipped in PR #48 (merge 7d94385), live on kobal on 2026-09-24. The host can join any event's moderator console through its mod link. An Authentik admin sign-in now also carries the person's identity, and the host joins under it. A host on the local password joins as local:<admin username>. The admin API token cannot join, and provider subjects in the reserved local: namespace are refused. ADR 0027 amends ADR 0020. Verified on kobal: Drew's Authentik host session moderated the demo event's queue as 'Drew Short'.
