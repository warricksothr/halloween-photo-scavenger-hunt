# 0008. Lock raced mutations around the shared SQLite connection

Date: 2026-09-09
Status: accepted

## Context

The application uses one SQLite connection per FastAPI process. SQLite
transactions already protect the conditional invite and verdict writes, but
FastAPI can run synchronous handlers in different worker threads. Concurrent
handlers could interleave reads and transaction blocks on the same Python
connection before the conditional write ran. That produced connection errors in
a synchronized invite redemption race and made close-versus-verdict behavior
dependent on thread scheduling.

## Decision

Create one reentrant `app.state.db_lock` during application startup. A FastAPI
generator dependency holds that lock for the full request in the three
race-sensitive mutation handlers: invite redemption, event close, and
moderator verdict. Each handler keeps its existing transaction-level lock; the
reentrant lock makes that nested acquisition safe. The test suite coordinates
requests at an async barrier and asserts the resulting rows and audit events.

## Consequences

Those mutations serialize within the single-process deployment, so one request
cannot interleave database calls with another request on the shared connection.
The lock does not change the first-commit-wins invite or verdict rules. The
single-process architecture remains a constraint: adding multiple uvicorn
workers would require a shared database access strategy and an SSE broker that
works across processes.
