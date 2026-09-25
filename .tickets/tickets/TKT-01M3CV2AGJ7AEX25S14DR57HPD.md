---
schema: 3
id: TKT-01M3CV2AGJ7AEX25S14DR57HPD
title: Let moderators choose a nickname players see on verdicts
type: task
status: in-progress
status_reason: null
priority: normal
due_on: null
labels:
  - moderation
  - backend
  - frontend
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:claude-code/t3code-55409a8b
  branch: t3code/mod-nickname
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-55409a8b
  commit: 457f0cb2701033c046031ea358c5e749a798ad72
  session: null
  claimed_at: 2026-09-25T17:51:07Z
  expires_at: null
archive: null
created_at: 2026-09-25T17:51:01Z
updated_at: 2026-09-25T18:04:40Z
created_by:
  id: agent:claude-code/t3code-55409a8b
  name: ""
updated_by:
  id: agent:claude-code/t3code-55409a8b
  name: ""
extensions: {}
---

## Description

Drew, 2026-09-25: "Moderators should be able to choose a nickname that gets displayed to the users when decisions are made. The moderation ledger should still display the moderator name but include the nickname in parentheses."

Today players never see who judged a photo. A moderator's `label` is their SSO display name or email (mod.py join), so it must not be what players see; the nickname is a separate, moderator-chosen name, and the only moderator name a player ever receives.

## Acceptance criteria

- [x] Players see the nickname of the moderator who issued a game verdict on that verdict; with no nickname set they see no moderator name, and the SSO label never reaches a player.
- [x] The INAPPROPRIATE conduct action is not attributed to a moderator on any player surface.
- [x] The moderation log shows the moderator's name with the nickname in parentheses, for actions and for rows about a moderator.
- [x] Server and UI tests cover it; schema.md, api.md, audit-actions.md, ui.md, progress.md and an ADR record it.
- [x] A moderator can set, change and clear a nickname from the console; it is trimmed, capped at 40 characters like a codename or team name, kept per event across rejoins, and each change is audited.

## Implementation plan

Server: migration 0006 adds a nullable `moderator.nickname`. The row is one per person per event (0002), so a rejoin keeps it; join refreshes `label` only. `PUT /api/mod/nickname {nickname}` trims, caps at 40, and treats empty as clear (NULL); audited as `moderator.nickname_set` with before/after. `GET /api/mod/state` returns it. `ModeratorContext` carries it.

Players: `/api/state` submissions gain `verdict_by`, the judging moderator's nickname, resolved at read time through verdict.moderator_id, and null for an inappropriate verdict or no nickname. The `verdict` SSE delta carries `moderator` too, so a delta is self-describing, but the client already refetches the snapshot on a verdict. RiddleDetail shows "Reviewed by NICK" under the banner. The copy stays in the theme pack, since it is a game-verdict surface.

Ledger: `_Names` formats a moderator as `label (nickname)` when one is set, for `actor_name` and `about.moderator`; LogPanel needs no change beyond the new action's sentence.

Console: a small nickname form in the rail, seeded from `state.moderator.nickname`; the header shows the nickname beside the label.

Alternatives, in the ADR: snapshot the nickname on the verdict row (stale-proof but a column per verdict and a rename would not reach old verdicts; read-time matches ADR 0044); fall back to the label for players (leaks an SSO name/email); attribute inappropriate verdicts (points players at a person over a conduct call, where design.md sends them to the host).

## Notes

**agent:claude-code/t3code-55409a8b** at 2026-09-25T17:51:45Z

Cap moved from 32 to 40 characters before any code landed, to match player codenames and team names (players.py JoinBody, teams.py RenameBody): the nickname sits in the same places on screen. The criterion was re-added at the end, so the list order changed.

**agent:claude-code/t3code-55409a8b** at 2026-09-25T18:04:05Z

Built on t3code/mod-nickname: a87e0e7 (server), b08b4ec (console, banner, log, e2e), b7df7ab (ADR 0045 and docs).

Verification: `bash scripts/check-quality.sh` exits 0 (server 600 passed, 96% branch coverage, Ruff clean; web 272 vitest; build). `web/e2e/game-loop.spec.js` passes against the built app: the moderator saves "Oracle", the header reads "Browser Test Moderator (Oracle)", the player's banner reads "Analysis by Oracle", and the log row reads "... (Oracle) marked Batman's photo ...". Screenshots were checked by eye; the byline font was changed from Orbitron to the body font afterwards.

Decisions made without asking, each easy to reverse and recorded in ADR 0045: no nickname means players see no name (not "A moderator", not the label); an INAPPROPRIATE call carries no moderator for players; nicknames are read at request time, so a rename shows on past verdicts; the log sentence for moderator.nickname_set sits in the Moderation filter.

Three schema-version pins moved 5 → 6 (test_health, test_regressions, test_deployment_checks), as 0005 did. In the first gate run test_regressions::test_mod_join_after_the_event_is_purged_is_not_a_500 failed once; it passed alone and in two further full runs, so it looks like a pre-existing flake in that interleaving test. No change was made for it.

**agent:claude-code/t3code-55409a8b** at 2026-09-25T18:04:40Z

PR #71 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/pulls/71), branch t3code/mod-nickname, base main 457f0cb, head eb03699. Terva review requested as pr71-mod-nickname-1: the dispatch answered with the empty-JSON error the docs describe, and the run was created anyway as run 810 (https://git.local.sothr.com/warricksothr/arkham-halloween-photo-scavenger-hunt/actions/runs/810). Quality CI is run 809.
