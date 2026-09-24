# 0027. The host can join an event's moderator console

Date: 2026-09-24
Status: accepted

## Context

`docs/design.md` gives the admin the power to "create events, manage
riddles, and act as moderator". ADR 0020 then made the mod link a selector
and not a credential, and joining required an SSO identity with the
moderator role. `role_for` resolves someone in both groups as admin
("the host is the host"). The admin callback minted an admin session with
no identity and sent a host who had followed a mod link back with
`?sso=not_moderator`. So the host could never moderate.

That surfaced in the first kobal playtest on 2026-09-24. For the real
event one person will be both host and moderator, so as built, nobody
could have run the review queue.

## Decision

- **An admin sign-in also carries the person's identity.** The OIDC
  callback now mints the in-memory `arkham_oidc` identity for every allowed
  role, alongside the admin session for a host. A host who followed a mod
  link returns to it unmarked, and the `not_moderator` marker is retired.
- **The join admits the host.** `require_moderator_identity` replaces
  `require_oidc_moderator` on `POST /api/mod/join/{code}` and accepts:
  - an SSO identity with the moderator or admin role;
  - otherwise, a live admin **cookie** session, meaning the host on the
    local break-glass password. That login names no person, so the host
    joins under the fixed subject `local:<admin username>`, labelled with
    the username. The prefix cannot collide with a provider's subject, and
    a rejoin reuses the row.
- **The admin API token cannot join.** It is a script credential, and a
  moderator cookie gives a script nothing.
- **Nothing else changes.** Moderation still goes through the per-event
  moderator row and session, so the console, the audit (`moderator.joined`
  naming the subject) and the verdict attribution are unchanged. The host
  still needs the event's mod link, which the event card now opens
  directly (ADR 0026).

## Alternatives

- **Let `role_for` return both roles.** This is wider: every admin
  surface would have to learn about a two-role identity, to solve one
  route's check.
- **Put the host in the moderator group only for the event.** That is
  impossible, because admin wins, and it would push an app rule into
  directory administration.
- **Global moderators, where any moderator or host moderates any event.**
  Still open in TKT-01M391CVJ10G0HGZR8ZFZB6RW4 (Decide how SSO roles map to
  moderating events). This ADR is the part every option there agrees on.

## Consequences

- The host moderates under their own name, and the queue and audit say
  who issued each verdict.
- Every host sign-in now also holds an identity cookie. It grants nothing
  beyond the mod join, which already admits the host.
- A break-glass host appears as the admin username in the queue, not as a
  person's name.
