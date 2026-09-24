# 0030. Run one statement at a time on the reader connection

Date: 2026-09-24
Status: accepted; amends 0013

## Context

ADR 0013 gave handler reads their own connection, `app.state.read_db`, and
said one reader was enough because "the GIL and the sqlite3 module serialize
calls". That is wrong. Python's `sqlite3` caches prepared statements per
connection, keyed by the SQL text, so two threads running the same SQL are
handed the same `sqlite3_stmt`. The GIL is released between the `execute`
and the `fetchone`, so one thread's `execute` can reset and rebind a
statement while another thread is still stepping it.
`check_same_thread=False` only turns Python's guard off.

Every request authenticates with the same SELECT, and sync handlers and
dependencies run on the threadpool, so any burst of requests on one session
hits this. TKT-01M396FF6CS39ZYQ9HFTRPCDW7 found it through the moderator
console, whose first load fetches the queue and every thumbnail at once. One
photo answered 500 (`sqlite3.InterfaceError: bad parameter or other API
misuse`). Another answered 401 because the session row read back as missing
for a valid cookie. Players were exposed the same way on any screen that
loads several photos.

A second, quieter fault came from the same sharing. A cursor that is read
with `fetchone` and then dropped keeps its statement open until it is
garbage-collected, and an open statement holds a read transaction. So the
reader could stay pinned to an old snapshot. ADR 0013's claim that "no reader
holds a snapshot open" depended on every caller finishing its cursor.

## Decision

`db.reader(request)` returns a `SerializedReader` instead of the raw
connection. Its one method, `execute(sql, params)`, takes `app.state.read_lock`,
runs the statement, reads every row, releases the lock, and returns the rows
as `ReadRows`, a stand-in that offers only what handlers use: `fetchone`,
`fetchall` and iteration. A handler that reaches for anything else on the
reader fails loudly rather than working unsafely.

- No call site changes its logic. The fix sits where every read already goes.
- Reading all the rows under the lock means that when `execute` returns, no
  statement is left open on the reader, so no snapshot is pinned.
- Lock order: `read_lock` is always the innermost lock. Code that holds it
  runs one statement and takes no other lock. A handler holding `db_lock` may
  read through the reader, but nothing holding `read_lock` ever waits for
  `db_lock`, so the two cannot deadlock.

The writer needs no change: every use of it already runs under `db_lock`
(ADR 0008, ADR 0013).

## Alternatives

- **One reader connection per thread (thread-local).** This keeps reads
  parallel. But anyio retires idle worker threads and starts new ones, so the
  connections pile up unless something tracks thread exit, and every app in
  the test suite would add its own. That is more machinery than the load
  needs.
- **A fresh connection per request.** Every request pays an open plus the
  pragmas, and the request needs a cleanup hook to close it.
- **A small pool of reader connections.** This is the lock generalised to N,
  and it fits behind the same `reader()` without touching a call site. Keep it
  for the day contention shows up.
- **A lock at each call site.** There are 43 of them, and every new handler
  would have to remember it.

## Consequences

- Handler reads are serialised. Each is an indexed SELECT on a local file,
  so the busiest moment on the night (a console loading about twenty
  thumbnails) waits tens of milliseconds in total. The request log's
  `duration_ms` would show it if that ever stopped being true.
- `tests/test_reader_concurrency.py` holds the regression: sixteen threads
  run the same SQL on the reader, and a burst of sixty moderator requests
  goes through the real routes. Both fail on the code before this ADR.
- The one test that told the reader apart from the writer by identity with
  `app.state.read_db` checks `isinstance(conn, db.SerializedReader)` instead.
- Helpers typed `conn: sqlite3.Connection` receive either the writer or the
  reader. The annotation is loose for the reader, and only duck typing makes
  it work. The handler-level `conn: sqlite3.Connection = reader(request)`
  annotations were dropped because they were false.
