-- 0003_riddle_hint.sql — ordered hint levels on a riddle.
--
-- A riddle is deliberately oblique, and a stuck player stops playing. The
-- host needs a nudge lever that does not mean editing the riddle text, and
-- one hint only moves a player from stuck to stuck-with-a-clue. Hints are
-- therefore a ladder: several rows per riddle, ordered by level, each
-- spoiling a little more than the one before.
--
-- A child table rather than a column: the count is not fixed, order is a
-- property of the set, and a delete cascades. A riddle with no rows simply
-- has no hints, so no backfill is needed.

CREATE TABLE IF NOT EXISTS riddle_hint (
    id          TEXT PRIMARY KEY,
    riddle_id   TEXT NOT NULL REFERENCES riddle(id) ON DELETE CASCADE,
    level       INTEGER NOT NULL,
    text        TEXT NOT NULL,
    created_at  INTEGER NOT NULL
);

-- One hint per level per riddle: the writer replaces the whole set inside a
-- transaction, and this keeps a retry from leaving two level-1 rows.
CREATE UNIQUE INDEX IF NOT EXISTS idx_riddle_hint_level
    ON riddle_hint(riddle_id, level);

-- The reads are always "the hints of this riddle, in order"; the unique
-- index already covers that, so no separate index is needed.
