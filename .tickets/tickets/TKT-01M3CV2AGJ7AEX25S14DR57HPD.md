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
updated_at: 2026-09-25T17:51:17Z
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

- [ ] A moderator can set, change and clear a nickname from the console; it is trimmed, capped at 32 characters, kept per event across rejoins, and each change is audited.
- [ ] Players see the nickname of the moderator who issued a game verdict on that verdict; with no nickname set they see no moderator name, and the SSO label never reaches a player.
- [ ] The INAPPROPRIATE conduct action is not attributed to a moderator on any player surface.
- [ ] The moderation log shows the moderator's name with the nickname in parentheses, for actions and for rows about a moderator.
- [ ] Server and UI tests cover it; schema.md, api.md, audit-actions.md, ui.md, progress.md and an ADR record it.

## Implementation plan

Server: migration 0006 adds a nullable `moderator.nickname`. The row is one per person per event (0002), so a rejoin keeps it; join refreshes `label` only. `PUT /api/mod/nickname {nickname}` trims, caps at 32, and treats empty as clear (NULL); audited as `moderator.nickname_set` with before/after. `GET /api/mod/state` returns it. `ModeratorContext` carries it.

Players: `/api/state` submissions gain `verdict_by`, the judging moderator's nickname, resolved at read time through verdict.moderator_id, and null for an inappropriate verdict or no nickname. The `verdict` SSE delta carries `moderator` too, so a delta is self-describing, but the client already refetches the snapshot on a verdict. RiddleDetail shows "Reviewed by NICK" under the banner. The copy stays in the theme pack, since it is a game-verdict surface.

Ledger: `_Names` formats a moderator as `label (nickname)` when one is set, for `actor_name` and `about.moderator`; LogPanel needs no change beyond the new action's sentence.

Console: a small nickname form in the rail, seeded from `state.moderator.nickname`; the header shows the nickname beside the label.

Alternatives, in the ADR: snapshot the nickname on the verdict row (stale-proof but a column per verdict and a rename would not reach old verdicts; read-time matches ADR 0044); fall back to the label for players (leaks an SSO name/email); attribute inappropriate verdicts (points players at a person over a conduct call, where design.md sends them to the host).
