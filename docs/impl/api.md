# Implementation: API contract

The endpoints the PWA and moderators actually call, defined before
increment 4 so the frontend builds against a fixed surface. Everything
here follows three rules from the spec/ADRs:

- **Snapshot on connect, deltas over SSE** (ADR 0003) — `GET /api/state`
  is the single resync point; SSE events are deltas only.
- **Conditional writes** (ADR 0002) — verdict and submission mutations
  fail explicitly on a lost race (409), never overwrite.
- **The client role is cosmetic** — every moderator/admin route checks
  its role server-side (hardening checklist).

Conventions:

- All routes are under `/api`. JSON in/out. Errors are
  `{"error": "<machine-readable-code>", "message": "<human string>"}`
  with a sensible status code.
- Auth is cookie-based: player session cookie, moderator session cookie,
  or admin session cookie. No bearer headers — the browser owns
  credentials (httpOnly cookie, token hash at rest per the schema).
- IDs and timestamps follow `docs/impl/schema.md` (TEXT ids, INTEGER
  epoch seconds).

## Roles

| Role      | How obtained                        | Cookie scope        |
| --------- | ----------------------------------- | ------------------- |
| admin     | username/password (server config)   | all events          |
| moderator | mod code for one event              | that event, mod API |
| player    | join code + display name            | that event          |

Admin and moderator are distinct: the admin creates events and acts as
host (strike reversals, event purge); moderators only work the queue.

## Endpoint inventory

### Admin (increment 2)

```
POST   /api/admin/login                 { username, password } → admin cookie
POST   /api/admin/logout
GET    /api/admin/events                → [event summary]
POST   /api/admin/events                { name, theme, leaderboard_visibility }
                                        → event + join_code + mod_code
PATCH  /api/admin/events/{id}           { name?, leaderboard_visibility? }
POST   /api/admin/events/{id}/open      lobby → open (409 unless lobby)
POST   /api/admin/events/{id}/close     open → closed; single transaction:
                                        flip status, expire pending subs,
                                        log event.closed (ADR 0002/0004)
POST   /api/admin/events/{id}/purge     delete event + photos (confirm param)
GET    /api/admin/events/{id}/riddles
POST   /api/admin/events/{id}/riddles   { text, sort_order }
PATCH  /api/admin/events/{id}/riddles/{rid}   { text?, sort_order? }
DELETE /api/admin/events/{id}/riddles/{rid}   (409 if submissions reference it)
```

Lifecycle transitions log `event.opened` / `event.closed`; riddle edits
log `riddle.edited` with before/after text in `details`.

### Player join & sessions (increment 3)

```
POST   /api/join/{join_code}            { display_name, device_label? }
                                        → 404 bad code | 409 event closed |
                                          player cookie + { event, player }
POST   /api/logout                      revoke own session (logs session.revoked)
POST   /api/me/notice-ack               acknowledge the strike-1 interstitial
                                        (clears pending_notice in the snapshot)
```

The join code never appears again after this call — the cookie is the
credential from here on.

### Player state & play (increments 4–6)

```
GET    /api/state                       → snapshot (below). THE resync point.
GET    /api/events/stream               SSE stream (below).

POST   /api/evidence                    multipart photo + optional riddle_id
                                        → 201 evidence item |
                                          413 too big | 415 not an image |
                                          429 rate limited |
                                          403 upload-restricted (strike)
                                        Logs evidence.uploaded; raises
                                        duplicate_flag.raised on cross-team
                                        phash collision.
GET    /api/evidence                    → my team's drawer (thumbnails, tags)
GET    /api/evidence/{id}/photo         derivative only; owner team or
                                        moderator, else 404 (not 403 — don't
                                        confirm existence)

POST   /api/submissions                 { riddle_id, evidence_item_id }
                                        → 201 submission (pending) |
                                          409 one already pending for this
                                          riddle (partial unique index →
                                          friendly error, spec invariant)
                                        Logs submission.created.
```

### Moderation (increment 7)

```
POST   /api/mod/join/{mod_code}         → moderator cookie + { event }
GET    /api/mod/queue                   → pending subs, oldest first, with
                                          photo URL, player, riddle, claim
                                          state, duplicate flags
POST   /api/mod/queue/{sub_id}/claim    soft claim (advisory; ADR 0002)
POST   /api/mod/queue/{sub_id}/verdict  { verdict, flavor_text? }
                                        conditional UPDATE WHERE status =
                                        'pending' → 409 "already resolved"
                                        on a lost race. Logs verdict.issued.
GET    /api/mod/players/{id}            per-player history: submissions,
                                        verdicts, strikes, sessions (UA,
                                        last_seen — multi-teaming heuristics)
POST   /api/mod/flags/{id}/resolve      duplicate-evidence flag resolution
                                        (logs duplicate_flag.resolved)
```

### Conduct (increment 8)

```
POST   /api/mod/queue/{sub_id}/inappropriate
                                        verdict=inappropriate + strike in one
                                        action { note?, cooldown_minutes? }
                                        Logs verdict.issued + strike.issued.
POST   /api/admin/strikes/{id}/reverse  host-only; logs strike.reversed.
                                        Derived state recomputes (ADR 0001).
```

### Leaderboard & recap (increment 9)

```
GET    /api/leaderboard                 → standings; honors visibility toggle
                                          (404 for players when final-reveal
                                          and event not closed)
GET    /api/recap                       → timeline from audit_event, themed
                                          strings; players only after close
GET    /api/mod/audit                   full forensic timeline, moderator+
```

## The state snapshot (ADR 0003)

`GET /api/state` — shape differs by role. Player version:

```json
{
  "event": {
    "id": "…", "name": "…", "status": "open",
    "leaderboard_visibility": "live", "theme": "arkham"
  },
  "me": {
    "player_id": "…", "display_name": "…", "team_id": "…",
    "restriction": {
      "level": 0,                // 0 clean, 1 warned, 2 cooldown, 3 banned
      "cooldown_until": null,    // epoch seconds when level = 2
      "pending_notice": false    // strike 1 interstitial not yet shown
    }
  },
  "riddles": [
    { "id": "…", "text": "…", "sort_order": 1,
      "state": "unsolved" }      // unsolved | pending | verified
  ],
  "submissions": [
    { "id": "…", "riddle_id": "…", "status": "obscured",
      "verdict_flavor": "…", "created_at": 1700000000 }
  ],
  "leaderboard": null            // null when hidden; else [ { team, score } ]
}
```

Design notes:

- **`restriction` is computed at request time** from non-reversed strikes
  (ADR 0001) — the snapshot is where the derived state surfaces.
- **`pending_notice`** drives the strike-1 interstitial: the client shows
  it once, then `POST /api/me/notice-ack` clears it (a mutation; logged).
- Riddle `state` collapses submission history to what the tile grid
  needs; full history is in `submissions` for the detail view.
- The moderator variant replaces `me`/`riddles` with queue depth and
  flag counts; moderators get queue detail from `/api/mod/queue`.

## SSE delta events

`GET /api/events/stream` — one stream per role-scoped session. Event
names and payloads:

| SSE event          | Sent to            | Payload                                    |
| ------------------ | ------------------ | ------------------------------------------ |
| `verdict`          | owning team        | `{ submission_id, riddle_id, status, flavor }` |
| `submission_new`   | moderators         | `{ submission_id }` (queue refetches)      |
| `queue_resolved`   | moderators         | `{ submission_id, status }` (another mod beat you) |
| `event_status`     | everyone           | `{ status }` (opened/closed → client refetches snapshot) |
| `strike`           | affected player    | `{ level, cooldown_until }`                |
| `leaderboard`      | everyone (if live) | `{ standings }` — throttled, ≥5s apart     |

Payloads are deliberately thin — ids and the changed fields only. On
`event_status: closed`, or on any reconnect, the client refetches the
full snapshot; deltas never need to be replayable (ADR 0003).

## Cross-references

- Table/column names: `docs/impl/schema.md`
- Every mutation above names its audit action; the full enum with
  payload shapes: `docs/impl/audit-actions.md`
- Why the concurrency rules look like this: ADRs 0001–0004
