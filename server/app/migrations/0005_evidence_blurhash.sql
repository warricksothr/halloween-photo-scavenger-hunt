-- 0005_evidence_blurhash.sql — a blurred stand-in for a photo (ADR 0040).
--
-- While a photo waits for a moderator, players see its blurhash under the
-- scanning effect rather than the photo, and a photo flagged inappropriate
-- is only ever shown to players as its blurhash. The hash is a short
-- string computed once at upload from the oriented image.
--
-- Nullable: photos uploaded before this migration have none, and the
-- client falls back to the plain scanning panel for them.
ALTER TABLE evidence_item ADD COLUMN blurhash TEXT;
