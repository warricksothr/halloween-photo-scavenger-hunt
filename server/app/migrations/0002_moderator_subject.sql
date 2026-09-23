-- 0002_moderator_subject.sql — the moderator's SSO subject (S9CW).
--
-- The mod link stopped being the credential: `POST /api/mod/join/{mod_code}`
-- now requires a signed-in OIDC moderator, and the code only selects the
-- event. Recording the subject on the row ties a moderator to a person, so a
-- rejoin reuses the same row (and its label) instead of minting a fresh one
-- per visit, and the queue still names a stable moderator.
--
-- SQLite has no ADD COLUMN IF NOT EXISTS, so this file is not re-runnable the
-- way 0001 is. It does not need to be: DDL is transactional in SQLite and the
-- runner records the version in the same transaction it applies the file in.

ALTER TABLE moderator ADD COLUMN subject TEXT;

-- One row per person per event. NULL stays allowed for rows minted before
-- this migration and for any non-SSO path; SQLite unique indexes ignore NULLs,
-- so several NULL subjects do not collide.
CREATE UNIQUE INDEX IF NOT EXISTS idx_moderator_event_subject
    ON moderator(event_id, subject)
    WHERE subject IS NOT NULL;
