# 0025. The demo seeder lives in the app package and speaks HTTP

Date: 2026-09-23
Status: accepted

## Context

A demo, a rehearsal, or a fresh deploy needs an event with a full set of
riddles. Typing twelve riddles and their hint ladders into the console is
slow and error-prone, and the content goes through review rounds, so it
should live in version control (TKT-01M384GE6JEAN6SN72N4FGCMNA).

A seeder has three choices to make: how it writes, where it lives, and how
it authenticates.

## Decision

**It writes through the admin HTTP API, not SQL.** The admin routes own the
audit rows, the hint-ladder ordering, and the "no riddles, no open" gate. A
seeder that inserted rows would skip all three and would have to track every
schema change.

**It lives in `server/app/seed.py`, run as `python -m app.seed`, with its
fixture at `server/app/fixtures/demo-event.json`.** The container already
puts `app` on the import path, so the seeder runs inside the container
(`podman exec <container> python -m app.seed`) with no second checkout. The
server gate covers it: branch coverage and Ruff. It takes an `httpx2.Client`,
so tests hand it Starlette's `TestClient`, which is an `httpx2.Client`, and
every call runs the real route. It validates the fixture with the same
Pydantic request models the routes use, so the fixture and the server cannot
drift apart on limits.

**It authenticates with `ARKHAM_ADMIN_API_TOKEN` as a bearer token**
(TKT-01M386AR687DYXFQ7M6VBSAA6V), so it needs no cookie jar and no CSRF
pair. `podman exec` inherits the container's environment, so a container
started with the token needs nothing more.

Alternatives considered:

- *A standalone `scripts/seed-demo.py` using urllib.* It would sit outside
  the coverage gate, would not ship in the image, and would repeat the
  transport and error handling that httpx2 already gives.
- *A shell script with curl, like `smoke-container.sh`.* Nested JSON
  (riddles holding hint lists) is awkward to build in shell, and the script
  would have no unit-test story.
- *Direct SQL.* Skips the audit log and the open gate, as above.

## Consequences

- A rerun refuses to create a second event with the same name unless
  `--allow-duplicate` is passed, so a retried deploy step cannot leave
  players two identical events to join.
- The fixture is package data (`pyproject.toml`), and the image copies it
  with the rest of `server/`.
- A wrong token fails as `401 not_authenticated` on the duplicate-check
  read, or as `403 csrf_failed` on the first write when `--allow-duplicate`
  skips that read: the CSRF middleware exempts only a *matching* token, so
  it runs before auth. The seeder adds a note naming the token to either
  code, so the operator does not chase a browser problem.
- Riddle content changes are ordinary commits to the fixture, reviewed like
  code.
