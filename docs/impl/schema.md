# Implementation: MVP schema (DDL on paper)

The `0001_init.sql` migration, designed in full before any code. This is
the concrete form of the data model in `docs/design.md` — read that for
the *why*; this file is the *what*. Every decision deferred here becomes
a rushed one in increment 1.

Conventions used throughout:

- **IDs are TEXT** (ULIDs or `lower(hex(randomblob(16)))` at insert
  time). Opaque, URL-safe, and immune to the "guess the next integer ID"
  class of mistake.
- **Timestamps are INTEGER** (Unix epoch seconds, UTC). SQLite has no
  native datetime; epoch integers compare, sort, and index correctly and
  avoid timezone bugs entirely.
- **Enums are TEXT + CHECK constraints**, not lookup tables. Lookup
  tables buy referential integrity we get from CHECK, at the cost of
  joins and seed data for values that change only with a code deploy.
- **Foreign keys + WAL** are pragmas set on every connection at open
  (`PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`) — they are
  per-connection settings, not schema, so they live in `db.py`, not here.

```sql
-- 0001_init.sql — full MVP schema. Idempotent via IF NOT EXISTS so the
-- migration runner can re-apply safely during development.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  INTEGER NOT NULL
);

-- ── Events ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS event (
    id                      TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    theme                   TEXT NOT NULL DEFAULT 'arkham',
    status                  TEXT NOT NULL DEFAULT 'lobby'
                            CHECK (status IN ('lobby', 'open', 'closed')),
    leaderboard_visibility  TEXT NOT NULL DEFAULT 'live'
                            CHECK (leaderboard_visibility IN ('live', 'final-reveal')),
    join_code               TEXT NOT NULL UNIQUE,
    mod_code                TEXT NOT NULL UNIQUE,
    created_at              INTEGER NOT NULL,
    opened_at               INTEGER,      -- set on lobby → open
    closed_at               INTEGER       -- set on open → closed
);

-- Codes are stored plaintext: they are bearer credentials meant to be
-- shown as QR codes, so hashing them adds no security (unlike session
-- tokens below, which are never displayed after issuance).

CREATE TABLE IF NOT EXISTS riddle (
    id          TEXT PRIMARY KEY,
    event_id    TEXT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    sort_order  INTEGER NOT NULL,
    created_at  INTEGER NOT NULL
);
-- No unique constraint on text: the host may legitimately want two
-- riddles with similar wording during drafting.

-- ── Players, teams, sessions ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS team (
    id          TEXT PRIMARY KEY,
    event_id    TEXT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    name        TEXT,                    -- NULL in MVP (team of one, unnamed)
    size_limit  INTEGER,                 -- NULL = event default; stretch override
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS player (
    id           TEXT PRIMARY KEY,
    team_id      TEXT NOT NULL REFERENCES team(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    created_at   INTEGER NOT NULL
);
-- No upload_restriction column: restriction is derived from non-reversed
-- strikes (ADR 0001). Store facts, compute state.

CREATE TABLE IF NOT EXISTS session (
    id           TEXT PRIMARY KEY,
    token_hash   TEXT NOT NULL UNIQUE,   -- SHA-256 of the bearer token;
                                         -- plaintext never stored (hardening list)
    player_id    TEXT NOT NULL REFERENCES player(id) ON DELETE CASCADE,
    device_label TEXT NOT NULL DEFAULT '', -- free text from the player ("Sam's phone")
    user_agent   TEXT NOT NULL DEFAULT '', -- for moderator heuristic matching
    created_at   INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,       -- throttled: max one write/minute
    revoked_at   INTEGER                 -- NULL = active
);
CREATE INDEX IF NOT EXISTS idx_session_player ON session(player_id);

-- Moderator sessions are sessions on a synthetic moderator "player" in a
-- synthetic team? No — moderators get their own table. They are not
-- players: they score nothing, appear on no leaderboard, and conflating
-- the two makes every authorization check harder to reason about.

CREATE TABLE IF NOT EXISTS moderator (
    id          TEXT PRIMARY KEY,
    event_id    TEXT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    label       TEXT NOT NULL DEFAULT 'moderator',
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS moderator_session (
    id           TEXT PRIMARY KEY,
    token_hash   TEXT NOT NULL UNIQUE,
    moderator_id TEXT NOT NULL REFERENCES moderator(id) ON DELETE CASCADE,
    created_at   INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    revoked_at   INTEGER
);

-- ── Evidence & submissions ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS evidence_item (
    id           TEXT PRIMARY KEY,
    team_id      TEXT NOT NULL REFERENCES team(id) ON DELETE CASCADE,
    uploaded_by  TEXT NOT NULL REFERENCES player(id),
    riddle_id    TEXT REFERENCES riddle(id),   -- optional aim tag
    photo_path   TEXT NOT NULL,                -- relative to data/photos/
    phash        TEXT NOT NULL,                -- hex string; compared by
                                               -- Hamming distance in code
    quarantined  INTEGER NOT NULL DEFAULT 0    -- boolean; conduct system
                                               -- (hidden from drawer/app)
                                               CHECK (quarantined IN (0, 1)),
    created_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_team ON evidence_item(team_id);
CREATE INDEX IF NOT EXISTS idx_evidence_event_phash
    ON evidence_item(phash);  -- exact re-upload short-circuit; near-match
                              -- is a full scan at party scale (spec)

CREATE TABLE IF NOT EXISTS submission (
    id               TEXT PRIMARY KEY,
    riddle_id        TEXT NOT NULL REFERENCES riddle(id),
    team_id          TEXT NOT NULL REFERENCES team(id),
    submitted_by     TEXT NOT NULL REFERENCES player(id),
    evidence_item_id TEXT NOT NULL REFERENCES evidence_item(id),
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'verified', 'obscured',
                                       'not_found', 'too_small', 'misaligned',
                                       'inappropriate', 'expired')),
    claimed_by       TEXT REFERENCES moderator(id),  -- soft claim (ADR 0002)
    claimed_at       INTEGER,
    created_at       INTEGER NOT NULL
);

-- The load-bearing invariant (spec: "one active submission per riddle
-- per team"). The database enforces it; the API translates the
-- constraint violation into a 409.
CREATE UNIQUE INDEX IF NOT EXISTS idx_submission_one_pending
    ON submission(riddle_id, team_id) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_submission_team ON submission(team_id);
CREATE INDEX IF NOT EXISTS idx_submission_queue
    ON submission(status, created_at);   -- the moderation queue query

CREATE TABLE IF NOT EXISTS verdict (
    id            TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL UNIQUE REFERENCES submission(id),
    moderator_id  TEXT NOT NULL REFERENCES moderator(id),
    verdict       TEXT NOT NULL
                  CHECK (verdict IN ('verified', 'obscured', 'not_found',
                                     'too_small', 'misaligned',
                                     'inappropriate')),
    flavor_text   TEXT NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL
);
-- UNIQUE(submission_id) is the second layer of first-verdict-wins
-- (the conditional UPDATE is the first). Immutable by design (ADR 0002):
-- no UPDATE path may exist in the codebase.

CREATE TABLE IF NOT EXISTS strike (
    id             TEXT PRIMARY KEY,
    player_id      TEXT NOT NULL REFERENCES player(id),
    event_id       TEXT NOT NULL REFERENCES event(id),
    level          INTEGER NOT NULL CHECK (level IN (1, 2, 3)),
    submission_id  TEXT NOT NULL REFERENCES submission(id),
    issued_by      TEXT NOT NULL REFERENCES moderator(id),
    note           TEXT NOT NULL DEFAULT '',
    cooldown_until INTEGER,              -- set only when level = 2
    created_at     INTEGER NOT NULL,
    reversed_by    TEXT REFERENCES moderator(id),
    reversed_at    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_strike_player ON strike(player_id)
    WHERE reversed_at IS NULL;  -- the derived-state query (ADR 0001)

-- ── Audit log (ADR 0004) ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- monotonic = replay
                                                    -- order for one event
    event_id    TEXT NOT NULL REFERENCES event(id),
    actor_type  TEXT NOT NULL
                CHECK (actor_type IN ('admin', 'moderator', 'player', 'system')),
    actor_id    TEXT,                -- NULL for 'system' (e.g. cooldown expiry)
    action      TEXT NOT NULL,       -- closed enum: docs/impl/audit-actions.md
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}',  -- JSON blob, kept small
    created_at  INTEGER NOT NULL
);
-- Deliberately no UPDATE/DELETE paths anywhere in the codebase.
-- AUTOINCREMENT is the one place we use integer IDs: replay order within
-- an event must be total and cheap.
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_event(event_id, id);

-- ── Stretch (shipped empty; written only by the teams increment) ──────

CREATE TABLE IF NOT EXISTS team_invite (
    token       TEXT PRIMARY KEY,
    team_id     TEXT NOT NULL REFERENCES team(id) ON DELETE CASCADE,
    created_by  TEXT NOT NULL REFERENCES player(id),
    expires_at  INTEGER NOT NULL,
    redeemed_by TEXT REFERENCES player(id),
    revoked_at  INTEGER,
    created_at  INTEGER NOT NULL
);
-- Ships in 0001 so the teams stretch goal is purely additive UI + routes
-- (spec: "no migrations beyond TeamInvite" — the table itself is here).
```

## Deliberate omissions

- **No `upload_restriction` on player/team** — derived (ADR 0001).
- **No score column anywhere** — score is a query over `submission.status`
  (spec: score-as-query invariant).
- **No admin table** — the creator/admin is one human with credentials in
  server config (env var), argon2id-hashed comparison in code. A table for
  one row is ceremony; if multi-admin is ever needed that's migration 0002.
- **No updated_at columns** — verdicts and strikes are immutable; riddle
  edits are recorded in the audit log with before/after in `details`.
  Mutable-state timestamps duplicate what the audit log already says better.

## Open question recorded, not decided here

- `photo_path` stores the **derivative** path only; originals are written
  to a quarantined originals dir on disk and never referenced from the DB.
  If we later want originals purge-on-verify, that's a policy decision for
  increment 5, not a schema change.
