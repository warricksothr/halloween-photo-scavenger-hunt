---
schema: 3
id: TKT-01M396FF6CS39ZYQ9HFTRPCDW7
title: Shared reader connection races under concurrent requests
type: bug
status: draft
status_reason: null
priority: high
due_on: null
labels:
  - backend
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-24T07:53:29Z
updated_at: 2026-09-24T07:53:29Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

Every handler SELECT goes through one shared reader connection,
`app.state.read_db` (ADR 0013, `db.reader`). Sync dependencies and routes run
on FastAPI's threadpool, so two requests can call `execute` on that one
connection at the same moment. SQLite's statement state is per connection,
and `check_same_thread=False` only switches the guard off. The comment in
`db.connect`, which says the GIL serializes calls, does not hold for a
statement that is prepared in one call and stepped in another.

### Reproduced

This was seen locally on 2026-09-24 while verifying
TKT-01M395WVC7B97J93YTHVAXWKM6 (Give the moderator console a desktop and
tablet layout). The moderator console's first load fires three thumbnail
requests to `/api/mod/evidence/{id}/photo` in parallel. In one run:

- one answered 200;
- one answered 401 `not_authenticated`, because the session lookup in
  `current_moderator` came back empty for a valid cookie;
- one answered 500: `sqlite3.InterfaceError: bad parameter or other API
  misuse`, raised at `auth.py` `current_moderator`, in
  `conn.execute(...).fetchone()` on the reader.

It is intermittent: a second run loaded all three thumbnails. The same
exposure exists on main (the old console has queue thumbnails too), and in
any player screen that loads several photos at once, such as the drawer. On
the night, this looks like broken images and spurious sign-outs.

### Likely directions (to weigh in the plan)

- A lock around reader use, the cheapest option. It serializes reads, which
  is fine at party scale.
- A connection per thread, or a small pool of reader connections.
- A fresh reader connection per request. This costs an open per request.

Any fix needs a concurrent regression test that drives the real route
through several threads.
