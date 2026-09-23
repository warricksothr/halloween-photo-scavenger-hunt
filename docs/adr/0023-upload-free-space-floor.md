# 0023. Uploads refuse below a free-space floor

Date: 2026-09-23
Status: accepted

## Context

Originals are kept for the life of the event and nothing purges them
mid-party (schema.md "Decided at design review"). Disk use is bounded
only by the per-team rate limit (30 uploads / 10 min) and the 15 MB wire
cap, so a party on a small volume can fill the disk. That is worse than a
failed upload: SQLite writes begin failing too, the admin console cannot
close the round, and nobody at the party can safely delete files under a
running game. The failure is the one uploads cannot recover from.

There was no free-space check anywhere, and the originals directory had
no documented bound — the schema note said a purge policy "can be added
later", which is a plan, not a limit.

## Decision

The upload route checks free space after reading the bounded body and
before any Pillow work. If writing the body would take the filesystem
below a floor, it answers `507 {"error":"storage_full"}` with a message
that tells the player to fetch the host. The floor is
`storage.MIN_FREE_BYTES_DEFAULT` (256 MiB), overridable with
`ARKHAM_MIN_FREE_BYTES` and read once onto `app.state.min_free_bytes` at
startup.

The check is **a guardrail, not a reservation or a quota**. Two uploads
can both see enough room and then write; the floor is a fixed byte count
shared by every team, not a per-team share. The goal is narrow and
specific: stop the disk reaching zero, which is what breaks SQLite.
Anything more (reserving the incoming bytes against concurrent writers,
partitioning space per team) needs shared state that a party of 30 does
not justify.

`507 Insufficient Storage` is the honest status: the request is valid and
the player is not at fault, so a 4xx would blame them. The SPA surfaces
the message as-is.

The floor is also the documented cap on the originals directory, and
`deploy/RUNBOOK.md` carries the pre-event `df`/`du` check — an
operational check beside the in-process guardrail, because the floor
only bounds what uploads add, not what the last event left behind.

## Consequences

- A full disk no longer turns uploads into 500s or corrupts the game
  loop; the player gets a clear 507 and the host a chance to act.
- A small host can set `ARKHAM_MIN_FREE_BYTES` low deliberately, and a
  large one can raise it; the default is safe on both.
- The guardrail does not free space. It cannot: nothing may delete
  originals mid-event. The runbook's pre-event check is what keeps the
  floor from being reached in the first place.
- The residual race (two concurrent uploads) is accepted and documented
  rather than solved with a lock, which would serialize the slow Pillow
  path for no real gain.
