# 0020. The moderator link selects an event; OIDC supplies the identity

Date: 2026-09-23
Status: accepted; the host refusal is superseded by 0027

## Context

`docs/design.md` gives moderators in through a moderator code and a QR
link (`/m/<code>`), the same way players come in through a join code. For
players that is the whole credential story: the code is single-use, short
lived, and scoped to one event. A moderator code was treated the same way —
`POST /api/mod/join/{code}` minted a moderator row for anyone holding the
link — but a moderator is not a party guest. The link gets printed, put on a
wall, and shared with the people running the night; it outlives the event it
was made for, and whoever finds it gets the queue, the verdicts, and the
player history.

S9CT added OIDC for the host console: `require_oidc_moderator` resolves a
signed-in identity into a role (`admin` wins, else `moderator` if the account
is in the moderator group). That is the identity the moderator surface should
have used all along. Two smaller gaps sat beside it: every moderator row was
labelled `moderator`, so the queue could not tell two of them apart, and
`moderator.joined` did not record who joined.

The alternative — keep the code as the credential and bind it to a name typed
at the door — was rejected because it makes the wall's link the secret again
and cannot be revoked when someone leaves the team.

## Decision

The moderator link selects the event; it is no longer a credential. Join
requires an OIDC moderator session, checked before the rate-limit gate so a
guessing loop is still a lockout rather than an unauthenticated denial of
service:

- `POST /api/mod/join/{code}` depends on `require_oidc_moderator`. Without a
  session it is a 401 — the client starts the SSO round-trip.
- The moderator `label` and the `moderator.joined` audit details come from the
  identity (subject and name). The code is never written to the audit log.
- Migration `0002_moderator_subject.sql` adds `moderator.subject` and a
  partial unique index on `(event_id, subject)`. A rejoin the same identity
  made reuses its row and refreshes the label instead of accumulating
  moderators. The index is partial because older rows have a NULL subject and
  SQLite treats NULLs as distinct anyway; tomorrow's rows always carry one.
- The OIDC callback refuses a moderator surface with a marker rather than a
  bare JSON error, so the browser lands back on the screen with an
  explanation: `?sso=not_authorized` when the account is not a moderator,
  `?sso=not_moderator` when the host (an admin) follows a mod link. The
  screen and the marker are matched by path segment (`/m`, `/mod`, and their
  children), and `next` is clamped to a same-origin path.

## Consequences

- A leaked or printed moderator link no longer grants moderation; the worst
  it does is tell an unauthenticated visitor which event exists.
- Running a night now needs the moderators in the OIDC group before the
  event, not just the link. The RUNBOOK setup step changes from "print two
  QR codes" to "print two QR codes and add the moderation team to the group".
- `moderator` rows are identifiable and reusable, so the roster and any
  per-moderator history can be built on `subject`.
- The refusal marker is a fixed vocabulary the client switches on; a new
  reason needs both sides updated (documented in `docs/impl/api.md`).
- The `/mod` path is now a real route (the typed-code form the callback lands
  on), which also fixes a latent bug where the callback's default moderator
  target fell through to the player join screen.
