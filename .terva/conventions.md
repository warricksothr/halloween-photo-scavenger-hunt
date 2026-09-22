Comments explain why, not what. This project is a teaching vehicle and the extra commentary is deliberate; do not rate it as noise.
Files under .tickets/ are bookkeeping written by git ticket. Do not rate their wording or structure as a code defect.
web/dist/, data/ and docs/reference/ images are generated, runtime or copyrighted and are gitignored. Do not expect them in the diff or flag them missing.
The MVP is a team of one by design; do not flag the absence of team grouping, invites or rosters.
server/app/db.py holds one shared SQLite connection guarded by app.state.db_lock by design (ADR 0008). Do not propose a connection pool or a per-request connection.
The built-PWA browser smoke and the container smoke are explicit manual gates by design (ADR 0010); do not flag them as missing from CI.
