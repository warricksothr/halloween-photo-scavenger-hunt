---
schema: 3
id: TKT-01M3CJ86PQ00ZG3FA55FADD3FQ
title: Let app.security read the admin password without argv
type: task
status: draft
status_reason: null
priority: low
due_on: null
labels:
  - backend
  - security
  - operations
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-25T15:16:57Z
updated_at: 2026-09-25T15:16:57Z
created_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
updated_by:
  id: agent:claude-code/t3code-bf267378
  name: ""
extensions: {}
---

## Description

`python -m app.security 'password'` takes the password as an argument, which leaves it in shell history and visible in `ps`. The docs now work around this with a `python -c` one-liner that reads stdin (deploy/CONFIGURATION.md, "The admin password"), and the live deployment has its own helper script that does the same.

Make `python -m app.security` read the password from the terminal without echo when it gets no argument (`getpass`), ask for it twice, and read stdin when stdin is not a terminal. Keep the argument form working. The docs can then shrink to one command.

Found during TKT-01M3CHA8088PDS05GMVFVDJ8ZN (Document self-hosting).

## Acceptance criteria

- [ ] python -m app.security with no argument prompts twice without echo, or reads stdin when it is not a terminal
- [ ] deploy/CONFIGURATION.md and CONTAINER.md use the new form
