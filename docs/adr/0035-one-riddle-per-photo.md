# 0035. One riddle per photo

Date: 2026-09-24
Status: accepted

## Context

design.md kept one pending submission per riddle per team, and said
nothing about one photo used for several riddles. The riddle page offered
every drawer photo, and the server checked only that the photo belonged to
the team and was not quarantined. Drew found that a photo pending on one
riddle could be submitted to a second (TKT-01M390Y0TE). A photo already
accepted for one riddle could also be submitted to another and score
twice.

Drew decided the rule on 2026-09-24. Within a team, a photo that is
pending or verified on one riddle cannot go to another. Once its
submission ends in any other verdict, the photo is free again. In the
picker, a photo in use stays visible but greyed out, labelled with its
riddle.

## Decision

- **`POST /api/submissions`** refuses a photo that has a `pending` or
  `verified` submission on another riddle, with 409 `evidence_in_use`.
  The body also carries `riddle_id` and `status` for the submission
  holding the photo. The check runs on the writer inside the submit
  transaction, under the shared write lock, like the route's other
  checks. So two riddles racing for one photo cannot both pass.
- A second pending submission of the same photo to the **same** riddle
  is a double tap. It still reaches the partial unique index and gets
  `submission_pending`, so the player keeps hearing "already scanning".
- The check runs after the strike-3 ban. A banned player hears that
  submissions are off, which is the more basic answer.
- The snapshot's `submissions` rows gain `evidence_item_id`. The picker
  on the riddle page marks each photo held by a pending or verified
  submission. The photo is disabled, dimmed and labelled "Scanning ·
  Riddle n" (pulsing) or "Solved · Riddle n". Its accessible name carries
  the same words. If a teammate takes the photo after the picker loaded,
  the 409 is explained with the riddle's number, and the refresh greys it
  out.

## Alternatives

- **A partial unique index on `submission(evidence_item_id)` where the
  status is pending or verified.** It would put the invariant in the
  database, as ADR 0002 prefers. But kobal's database may already hold a
  photo used twice, because Drew tested exactly that, and the migration
  would fail on it. Cleaning live rows in a migration would mean choosing
  which of two verified submissions to demote, which changes a score. The
  write lock already makes the check atomic.
- **Block only while pending.** Drew's first expectation allowed either
  way. But a verified photo reused on a second riddle scores twice, which
  the leaderboard would count.
- **Hide photos in use.** This is cleaner, but a player whose photo
  vanished from the picker cannot tell where it went.

## Consequences

- Rows that already break the rule stay as they are. The rule applies to
  new submissions only.
- A team needs a photo per riddle. That was always the intent of the
  game, and the drawer holds as many as they take.
- The Drawer tab itself does not yet show which photos are in use.
  TKT-01M3AMNFH (blurhash placeholders) brings the pending state there.
- Tests: `test_submissions.py` (pending and verified reuse, freed by a
  rejection, across teammates, the double tap), `screens.test.jsx` (the
  picker and the 409 message), and `e2e/photo-one-riddle.spec.js`.
