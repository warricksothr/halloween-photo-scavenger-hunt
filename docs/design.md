# Design: Themed Photo Scavenger Hunt (working title)

## Event shape

- **Players**: 10–30 friends/acquaintances at a house party.
- **Duration**: one night, one scoring round.
- **Content**: 12–15 riddles pointing at photo subjects around the house and yard.
- **Scoring**: one point per verified riddle. Win conditions: first to solve all, or most solved at end of round. No speed bonuses, no tiers.
- **Anti-cheat**: minimal by design — subjects are on-site, so stock photos don't help. No proof-of-presence tokens, no EXIF checks.

## Experience

Standalone **progressive web app** — installable to home screen, but the only device capability we really need is the camera/photo picker. No accounts with passwords; players join an event with a short code and pick a display name.

First theme: **Batman: Arkham Knight/City**. The software must be theme-agnostic: theme = frontend skin (colors, fonts, copy strings, verdict messages) over a neutral core. Future events get a new theme pack, not a fork.

## Game loop

1. Player opens a riddle, takes/uploads a photo of the subject, submits.
2. Submission enters state `PENDING` (Arkham skin: `SCANNING...`).
3. A moderator reviews from a queue and issues a verdict:
   - `VERIFIED` → point awarded, riddle marked solved for that player.
   - `SUBJECT OBSCURED` → right idea, unusable photo (blocked, blurry, too dark, cropped). Free resubmission.
   - `SUBJECT NOT FOUND` → wrong subject. Free resubmission.
   - `SUBJECT TOO SMALL` → subject too distant or cropped to verify. Free resubmission.
   - `MISALIGNED` → right area, wrong framing or angle. Free resubmission.
4. Player sees verdict + moderator flavor text, resubmits if rejected.

Verdicts are the core flavor surface. The Arkham theme ships canned Batcomputer/Riddler-style lines per verdict type; moderators pick one or write custom text.

### Verdict states (core, theme-neutral)

| Core state   | Arkham skin        | Meaning                              |
| ------------ | ------------------ | ------------------------------------ |
| `PENDING`    | `SCANNING...`      | Awaiting moderator review            |
| `VERIFIED`   | `SUBJECT VERIFIED` | Accepted, point awarded              |
| `OBSCURED`   | `SUBJECT OBSCURED` | Right subject, bad photo (blocked/blurry); resubmit |
| `NOT_FOUND`  | `SUBJECT NOT FOUND`| Wrong subject; resubmit              |
| `TOO_SMALL`  | `SUBJECT TOO SMALL`| Subject too distant/cropped to verify; resubmit |
| `MISALIGNED` | `MISALIGNED`       | Right area, wrong framing/angle; resubmit |
| `EXPIRED`    | `INTEL EXPIRED`    | Round ended before review (optional) |

`TOO_SMALL` and `MISALIGNED` are taken from the game's actual riddle-scan
feedback. Like `OBSCURED`, they are soft rejections with free resubmission —
they give moderators precise, in-fiction language for the two most common
"try again" cases: the subject is there but unresolvable at that distance,
and the player photographed the right area from the wrong position.

## Moderator experience

- **Queue view**: pending submissions, oldest first (or grouped by riddle).
  Photo, player name, and riddle text side by side.
- **One-tap verdicts** with optional flavor-text picker/override.
- **Per-player history** so moderators stay consistent.
- Moderator role assigned at event setup (host creates event, gets a mod link/code).
- Multiple moderators can work the queue simultaneously; a submission is
  claimed/locked while a mod has it open (or simply: first verdict wins).

## Architecture

- **Backend**: Python + **FastAPI**, SQLite store (one file, trivially
  self-hosted; plenty for 30 concurrent users). Owns events, riddles,
  players, submissions, verdicts, and serves uploaded photos.
- **Frontend**: **Preact** PWA (Vite build, service worker, manifest,
  offline-tolerant shell). Preact is enough: a handful of screens, one
  camera input, polling/SSE updates. Camera capture via
  `<input type="file" accept="image/*" capture>`.
- **Realtime**: Server-Sent Events for player verdict notifications and
  moderator queue updates. One-night event, ~30 users — SSE from FastAPI
  handles this without extra infrastructure.
- **Theming**: theme pack = config (name, verdict copy, flavor lines) + CSS
  variables/assets. Core UI reads copy from the active theme.

## Hosting & access

- Small public VPS, single deployment.
- **Creator/admin role**: authenticated login (real credentials), can create
  events, manage riddles, and act as moderator.
- **Player access**: no accounts. Each event gets a **join code**: random,
  effectively unguessable, short enough that a full join URL fits
  comfortably in a QR code that phones scan to open the PWA.
  - Sizing: 8–10 characters from an unambiguous alphabet (no `0/O`, `1/I/L`)
    gives ~40–50 bits — unguessable at party scale, and a join URL like
    `https://host.example/j/8XK3Q2MN7P` is trivial QR content. A QR code at
    moderate error correction holds ~100+ alphanumeric chars comfortably, so
    we have ample headroom.
  - The join code *is* the player's credential: opening the link establishes
    a session (cookie/token) tied to that event. Moderator access uses a
    separate moderator code/link, generated alongside the join code.

## Game parameters (decided)

- **Riddles are standalone**: players see the full riddle list when the
  round opens and may submit in any order. No unlock chains, no
  dependencies, no per-riddle hints.
- **Leaderboard visibility**: intentionally left open as a build option —
  implement as an event-level toggle (`live` / `final-reveal`) rather than
  deciding now.

### Data model (draft)

- `Event` (id, join_code, mod_code, theme, status: lobby/open/closed)
- `Riddle` (id, event_id, text, optional hint, sort order)
- `Player` (id, event_id, display_name)
- `Submission` (id, riddle_id, player_id, photo_path, status, created_at)
- `Verdict` (id, submission_id, moderator, verdict, flavor_text, created_at)

## Build approach

This project is partly a teaching vehicle: a maintainer who knows Python but
is new to full-stack web services should be able to follow every layer.
Consequences:

- Prefer boring, well-documented choices over clever ones (FastAPI + SQLite
  + Preact is already that).
- Keep the architecture document current as we build; add short ADRs
  (architecture decision records) in `docs/adr/` for anything non-obvious.
- Build in small, runnable increments, each leaving the app working.
- Comment the *why*, not the what; the docs carry the design, the code
  carries the mechanism.
