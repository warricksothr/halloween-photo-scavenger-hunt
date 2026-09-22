# 0013. Isolate reads on a dedicated reader connection

Date: 2026-09-22
Status: accepted

## Context

ADR 0008 and ADR 0011 serialize writes on one shared `sqlite3.Connection`
(`app.state.db`) with a reentrant `app.state.db_lock`, but reads stay unlocked
on that same connection. WAL isolates connections, not statements, so an
unlocked `SELECT` on the writer can still see another request's open,
uncommitted transaction — a dirty read. `TKT-01M33X80NSF23VQXACHMNVY3WX`
reproduced it: a writer parked inside `with conn:` after an INSERT and an
unlocked reader on the same connection both saw the uncommitted row.

Three directions were on the table:

1. Give readers their own connection so WAL snapshot isolation applies.
2. Hold the request lock for every DB handler, so reads serialize with writes.
3. Keep reads unlocked and document dirty reads as acceptable at party scale.

Direction 2 was checked against the SSE path first, as the ticket asked:
`sse.py`'s stream endpoint is `async` and holds no DB connection (asyncio
queues fed with `call_soon_threadsafe`), so a request-wide lock would not
starve the writer. It was rejected on a different ground. `hold_request_lock`
is a sync generator dependency, and FastAPI runs its `__enter__` and `__exit__`
on different threadpool threads (measured: 50 of 50 pairs). Releasing a
`threading.RLock` from a non-owning thread raises
`RuntimeError('cannot release un-acquired lock')`. A 40-request concurrent
probe through the route did not trip it, so the fragility is latent rather
than live — but building the fix on that pattern would deepen a landmine.
Direction 3 fails acceptance criterion 1 outright: the read must not see the
uncommitted row.

## Decision

Keep `app.state.db` as the single writer and add `app.state.read_db`, a second
connection opened in the lifespan (same `foreign_keys = ON` and WAL pragmas)
and closed on shutdown. Add `db.reader(request)`, which returns the reader.
The rule for every handler: a SELECT that runs outside a locked write
transaction goes through `db.reader(request)`; every write goes through
`db.locked_transaction(request)`, which yields the writer. Reads taken inside a
write transaction keep using that transaction's connection.

One shared reader is enough. Autocommit SELECTs never open a transaction, so
each one reads the last committed WAL snapshot and no reader holds a snapshot
open long enough to stall checkpointing; the GIL and the sqlite3 module
serialize calls exactly as they do on the writer today. The three
check-then-act handlers keep their full-request `hold_request_lock`, which now
also makes their read-then-write atomic across the two connections: no other
writer can commit between the reader's SELECT and the writer's transaction
while the lock is held.

A guard test asserts that no module under `app/` except `db.py` and `main.py`
names `state.db` or `state.read_db` directly, so the split stays greppable and
a new handler cannot quietly reintroduce a read on the writer.

## Consequences

An unlocked read can no longer observe another request's uncommitted rows; the
regression test parks a mutation between its INSERT and its audit row and
asserts an interleaved unlocked read does not see it. The writer keeps its
name, so existing tests that reach `client.app.state.db` for setup and
assertions are unchanged. The cost is one more open connection per process and
a discipline that only the guard test enforces — a read on the writer still
compiles and still works, it just is not isolated. The single-process
constraint from ADR 0008 is unchanged; multi-worker deployment still needs a
shared-database strategy.
