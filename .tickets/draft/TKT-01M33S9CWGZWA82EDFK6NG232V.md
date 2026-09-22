---
schema: 3
id: TKT-01M33S9CWGZWA82EDFK6NG232V
title: Gate the moderator link behind OIDC and record identity
type: task
status: draft
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
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies:
  - TKT-01M33S9CTBFJTSEKX6QDA6N7P0
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-22T05:26:46Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/review-system-design
  name: ""
extensions: {}
---

## Description

The mod link is a bearer secret with no identity: whoever holds it is a moderator, and the moderator row's label is auto-generated (moderator-XXXX). Require an OIDC session in the moderator group before POST /api/mod/join/{mod_code} mints a moderator session, keep the mod code as the event selector, and use the OIDC name or email as the label. The ModJoin screen starts the OIDC flow and renders not-authenticated and not-a-moderator states.

## Acceptance criteria

- [ ] Joining through a mod link without an OIDC moderator session redirects to login instead of minting a moderator row.
- [ ] A signed-in user outside the moderator group gets a clear refusal, not a session.
- [ ] The moderator label comes from the OIDC identity, and the join/audit record names the subject rather than the code.
- [ ] The mod code still selects the event; no roster or event picker is added.
