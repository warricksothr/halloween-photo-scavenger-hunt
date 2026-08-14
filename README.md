# Arkham Halloween Photo Scavenger Hunt

A themed, asynchronous photo scavenger hunt for parties. Players solve
riddles by photographing subjects around the venue; moderators review
submissions from a queue and issue Arkham-style verdicts — `SUBJECT
VERIFIED`, `SUBJECT OBSCURED`, `SUBJECT NOT FOUND`, `MISALIGNED` — through
a Batcomputer-flavored PWA.

Built as a themeable core: Batman: Arkham Knight/City is the first theme
pack, not a fork point.

## Status

**Design phase complete — no code yet.** The specification, build plan,
and progress tracker live in [`docs/`](docs/).

- [`docs/design.md`](docs/design.md) — the spec: game loop, verdict
  states, moderation & conduct systems, data model, flow diagrams
- [`docs/build-plan.md`](docs/build-plan.md) — repo layout and runnable
  increments
- [`docs/progress.md`](docs/progress.md) — what's done, what's next
- [`docs/reference/THEME-NOTES.md`](docs/reference/THEME-NOTES.md) —
  Arkham visual language and verdict copy bank

## Planned stack

- **Backend**: Python + FastAPI + SQLite
- **Frontend**: Preact + Vite PWA (installable, camera-first)
- **Access**: QR-scannable join codes for players, admin login for hosts,
  moderator codes for the review queue

## License

[GNU AGPL-3.0](LICENSE). Free to use, self-host, and modify — but if you
run a modified version as a service (even without distributing it), you
must offer your source. This is a hobby project that will not be
productized; the AGPL keeps it free for parties and off-limits to free
commercial rides.
