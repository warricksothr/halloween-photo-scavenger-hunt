# 0045. Moderators choose the name players see

Date: 2026-09-25
Status: accepted

## Context

Drew asked that moderators be able to choose a nickname that players see
when decisions are made, and that the moderation log keep showing the
moderator's name with the nickname in parentheses
(TKT-01M3CV2AGJ7AEX25S14DR57HPD).

Players saw no moderator name before this. A moderator's `label` is set
from their sign-in when they join (`mod.py` join: the SSO display name,
else the email, else the subject), and it is refreshed on every rejoin.
The label is a real name or an email address, so it cannot be the name
players see.

## Decision

- **A separate column.** Migration 0006 adds a nullable
  `moderator.nickname`. The moderator row is one per person per event
  (migration 0002), so a rejoin keeps the nickname, and the join's label
  refresh does not touch it.
- **Set from the console.** `PUT /api/mod/nickname {nickname}` trims it
  and caps it at 40 characters, the same cap as a codename or a team
  name. A blank value clears it to NULL. Each change is audited as
  `moderator.nickname_set` with the old and new values, and a no-op is
  not logged. The console rail has a folded form that says what players
  see with and without a nickname.
- **Players see the nickname or nothing.** Snapshot submissions carry
  `verdict_by`, the nickname of the moderator who gave the verdict, read
  at request time. The `verdict` delta carries it as `moderator`. The
  verdict banner adds the theme pack's `detail.verdictBy` line ("Analysis
  by Oracle") when one is set. Without a nickname, players see no name,
  never the label.
- **A conduct call names nobody.** For an `inappropriate` verdict,
  `verdict_by` is always null and the delta carries no moderator.
  design.md sends a player with a strike to the host, and conduct
  surfaces are plain. A name on a strike would give a player a person to
  confront over a conduct call.
- **Moderators see both.** The log's `actor_name` and `about.moderator`
  read "label (nickname)", and the console header shows the same. The
  log is where moderators need the person. The nickname is the name a
  player will use for them.

## Alternatives considered

- **Store the nickname on each verdict row.** Every verdict would keep
  the name it was given under, but that costs a column per verdict and
  splits one moderator into several names over a night. Names are
  resolved at read time elsewhere too (ADR 0044: a renamed team reads
  under its current name), so a changed nickname shows on every verdict.
- **Let players see the label when there is no nickname.** The label is
  an SSO name or an email address, and the moderator never chose to show
  it to players.
- **A default such as "A moderator" when there is no nickname.** It adds
  a line that tells the player nothing. No line is quieter and leaves
  the verdict copy as it was.
- **Replace the label with the nickname.** The label is refreshed from
  the directory on every rejoin (migration 0002), and the host and other
  moderators need to know who made a call.
- **Name the moderator on conduct calls too.** See "A conduct call names
  nobody" above.

## Consequences

- Each player snapshot joins `verdict` to `moderator` once more, which
  costs little at party size.
- The `verdict` delta and the snapshot can briefly disagree when a
  moderator renames between a verdict and the next snapshot. The client
  refetches the snapshot on every verdict delta, so it shows the
  snapshot's value.
- Tests:
  - `server/tests/test_mod_nickname.py`: setting, trimming, clearing, the
    cap, access, auditing, rejoin, what players see (and never see), the
    conduct exclusion, and the log's names.
  - `web/src/screens/mod/NicknameForm.test.jsx`: the form.
  - `web/src/screens/screens.test.jsx`: the banner line, with and without
    a nickname.
  - `web/src/screens/mod/LogPanel.test.jsx`: the `moderator.nickname_set`
    sentence.
  - `web/e2e/game-loop.spec.js`: a moderator sets a nickname and the
    player sees it on the verdict, and the log shows it in parentheses.
