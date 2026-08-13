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

### Data model (MVP)

Team-scoped from day one: the MVP is a "team of one" with no grouping
functionality. Every player gets a team on join; submissions, evidence,
and scoring reference teams. This makes the teams stretch goal purely
additive (invites, roster UI, multi-member drawers) with no migration.

- `Event` (id, join_code, mod_code, theme, status: lobby/open/closed,
  leaderboard_visibility: live/final-reveal)
- `Riddle` (id, event_id, text, sort order)
- `Team` (id, event_id, size_limit) — MVP creates one per player, unnamed
- `Player` (id, team_id, display_name)
- `Session` (token, player_id, device_label, created_at, last_seen_at,
  revoked_at) — first-class from the start so moderation can revoke devices
- `EvidenceItem` (id, team_id, uploaded_by, riddle_id optional tag,
  photo_path, created_at) — MVP uploads go straight here; "submit" picks
  from the drawer even for a team of one
- `Submission` (id, riddle_id, team_id, submitted_by player_id,
  evidence_item_id, status, created_at)
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

## Stretch goal: teams & shared evidence drawer

Post-MVP. The MVP schema is already team-scoped (team of one, one
session, drawer-based submission), so this goal adds *grouping
functionality* on a stable foundation: invites, multi-member teams, and
the moderation tooling around them.

### Team formation

- On joining an event, a player gets a unique session (secure cookie /
  bearer token). The session id never appears in the URL — URLs stay
  shareable-safe.
- To form a team, a player opens their **team invite**: a QR code shown on
  their own screen, encoding a **single-use invite token** (not their
  session). A teammate scans it, gets their own fresh session, and lands on
  the inviting player's team.
- **Why invite tokens instead of sharing the session**: a shared session
  means impersonation and painful revocation. A single-use token redeems
  into an independent session bound to the team — clean identity, clean
  revocation.
- **Share limits without fingerprinting**: enforcing "max N members" on
  token *redemption* (one token = one join, team size cap checked at
  redeem time) removes the need for device fingerprinting entirely.
  Fingerprinting on the open web is fragile (Safari/ITP, private modes)
  and privacy-unfriendly for a party app; tokens sidestep it. This is the
  recommended design. The abuse vector that remains (a player minting many
  sequential tokens to build an over-cap team) is closed by the team-size
  cap itself and, if desired, per-team invite rate limits.
- Invite tokens expire (e.g. 10 minutes) and can be revoked by their
  creator or a moderator.

### Moderation / administration additions

- Team roster view: members, their sessions (with device label + last-seen
  time), pending invites.
- **Clear registered devices** for a player or whole team (revoke sessions)
  — handles lost phones, accidental joins, or freeing a slot for a new
  member.
- **Adjust per-team size limit** (event default + per-team override) when
  the host wants to allow a bigger group.

### Shared evidence drawer

- Each team has a **drawer**: a pool of uploaded photos shared by all
  members. Anyone on the team uploads candidate shots to the drawer
  (optionally tagged with the riddle they were aiming for).
- Submitting a riddle = picking a photo **from the drawer** (or shooting a
  new one, which goes through the drawer anyway). The submission records
  which evidence item was used and which member submitted it.
- Drawer photos are visible to the whole team as thumbnails; one active
  submission per riddle per team still applies.
- Scoring and verdicts become team-scoped: a `VERIFIED` solves the riddle
  for the team; verdict notifications go to all members. Leaderboard (live
  or final-reveal) ranks teams. Solo players are unaffected in practice —
  their team of one behaves like today's individual flow.

### Data model deltas (stretch)

Only one new table; everything else shipped with the MVP schema.

- `TeamInvite` (token, team_id, created_by, expires_at, redeemed_by,
  revoked_at) — single-use
- `Team`: add optional `name` and per-team `size_limit` override
- New UI only: invite QR screen, team roster, drawer thumbnails for
  multi-member teams, moderator team-management screens
