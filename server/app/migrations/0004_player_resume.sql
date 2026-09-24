-- 0004_player_resume.sql — a device's way back into a game it joined.
--
-- A player session ends 12 hours after it was issued (ADR 0021), and a
-- fresh join creates a new player with an empty drawer. So a phone that
-- comes back the next evening has lost its player. A resume token is the
-- device's claim on that player: it mints a new session, and only while
-- the event is open and the player is not banned (ADR 0031).
--
-- Its own table rather than a column on session: a session dies at the
-- TTL, and the resume token has to outlive it. Shaped like session, so
-- the token is kept only as its SHA-256 and a revocation is a timestamp.
-- One row per device, since a player can have more than one.

CREATE TABLE IF NOT EXISTS player_resume (
    id          TEXT PRIMARY KEY,
    token_hash  TEXT NOT NULL UNIQUE,
    player_id   TEXT NOT NULL REFERENCES player(id) ON DELETE CASCADE,
    created_at  INTEGER NOT NULL,
    revoked_at  INTEGER                 -- NULL = live
);

-- Revocation is always "every token of this player" (a moderator removal,
-- an invite switch); the lookup by token rides the unique index.
CREATE INDEX IF NOT EXISTS idx_player_resume_player
    ON player_resume(player_id);
