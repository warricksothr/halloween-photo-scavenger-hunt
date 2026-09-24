# 0040. Players see a blurhash for a pending or flagged photo

Date: 2026-09-24
Status: accepted; amends the conduct system's quarantine (design.md)

## Context

Drew asked for a blurhash of each submitted photo (TKT-01M3AMNFH). He
settled the rules on 2026-09-24:

- **Pending:** everywhere a player sees a photo that is waiting for a
  moderator, they see its blurhash instead, under the scanning effect.
- **Inappropriate:** the blurhash is the only form of the photo players
  ever see. Only the admin and moderators see the photo itself.
- **Rejected:** the photo shows as itself, with a different border, not
  blurred.

Before this, a pending photo showed as itself, and the riddle picker
greyed it out (ADR 0035). A flagged photo was quarantined: it dropped out
of the drawer, so a team saw a gap and no reason for it.

## Decision

**Server**

- `images.process_upload` computes the blurhash of the oriented image
  (after `exif_transpose`, so the blur matches the photo as it will be
  shown). It uses 4x3 components from a 32px thumbnail, which gives the
  same string as the full image, in milliseconds. The `blurhash` package
  (pure Python, reading Pillow's pixels) does the encoding. The string is
  28 characters long.
- `evidence_item.blurhash` is a new nullable column (migration 0005,
  schema version 5). Photos uploaded before it have none.
- The drawer (`GET /api/evidence`) returns `blurhash` and `quarantined`
  for every item, and now lists flagged photos too, with `photo_url:
  null`. The photo route still 404s a flagged photo for players, and the
  submit route still refuses it. Moderators' routes are unchanged.

**Client** (`web/src/evidenceState.js`, `components/Blurhash.jsx`)

- A photo's state comes from the drawer's `quarantined` and the latest
  snapshot submission that used it: `flagged`, `pending`, `verified`,
  `rejected` (a soft rejection) or `free`.
- The blurhash is decoded by Wolt's `blurhash` npm package onto a 32x32
  `<canvas>`, which CSS stretches to the tile. It is a canvas because the
  production CSP (`img-src 'self'`) blocks `data:` images, as it did the
  QR codes (ADR 0026).
- **Pending:**
  - The Drawer tab shows the blur with the scanning sweep and "Scanning ·
    Riddle n".
  - The riddle picker shows the blur in the disabled tile (ADR 0035).
  - The SCANNING banner has the blur behind its translucent panel.
- **Flagged:** the Drawer tab shows the blur in an alert-red frame,
  labelled "Removed by a moderator". The picker leaves the photo out,
  since it cannot be submitted.
- **Rejected:** the photo itself in a dashed amber frame, labelled
  "Rejected · Riddle n". In the picker it stays selectable, since
  ADR 0035 frees it.
- A photo with no blurhash (uploaded before migration 0005) falls back
  to the photo while pending, as before, and to an empty frame when
  flagged. It never falls back to the flagged photo.

## Alternatives

- **Compute the blurhash in the browser from the photo.** The browser
  would have to load the photo to blur it, and a flagged photo must never
  reach a player's browser at all.
- **Withhold the pending photo's URL on the server as well.** It is the
  team's own photo, taken on their own phone, so hiding it from them
  protects nothing. The blur is a presentation choice, and the server
  enforces only what matters, which is flagged photos.
- **Our own encoder and decoder.** Both are short, but the reference
  decoder and a maintained encoder are safer than a hand-rolled
  base-83 codec.
- **More components** (for example 6x4). A sharper blur starts to show
  what is in the photo, which defeats the point for a flagged one.

## Consequences

- A flagged photo's rough colours and layout stay visible to its own team,
  which Drew chose over a blank gap.
- New dependencies: `blurhash` on the server (in `uv.lock` and
  `requirements.lock`) and `blurhash` on npm.
- Tests:
  - `test_evidence.py`: determinism, orientation, stored on upload.
  - `test_conduct.py`: a flagged photo is listed as a blurhash with no
    URL, and its photo route 404s.
  - `screens.test.jsx`: the drawer and picker states, and the banner.
  - `e2e/blurhash.spec.js`: a real canvas is painted for a scanning photo
    and a removed one, and the photo stays out of reach.
