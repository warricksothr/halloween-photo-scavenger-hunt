# Arkham Theme — Visual Language Notes

Distilled from reference screenshots (sourced from interfaceingame.com).
All screenshots are © Rocksteady/WB — reference only, **do not commit or
ship them**. The image files in this directory are gitignored; fetch your
own copies from the source URLs below.

## Source URLs

Full-resolution copies of each reference, as fetched at the time of
writing:

- `arkham-knight-batcomputer.jpg`
  https://interfaceingame.com/wp-content/uploads/batman-arkham-knight/batman-arkham-knight-batcomputer.jpg
- `arkham-knight-upgrade-points-earned.jpg`
  https://interfaceingame.com/wp-content/uploads/batman-arkham-knight/batman-arkham-knight-upgrade-points-earned.jpg
- `arkham-knight-main-menu.jpg`
  https://interfaceingame.com/wp-content/uploads/batman-arkham-knight/batman-arkham-knight-main-menu.jpg
- `arkham-knight-searching.jpg`
  https://interfaceingame.com/wp-content/uploads/batman-arkham-knight/batman-arkham-knight-searching.jpg
- `arkham-knight-waynetech.jpg`
  https://interfaceingame.com/wp-content/uploads/batman-arkham-knight/batman-arkham-knight-waynetech.jpg
- `arkham-city-detective-mode.jpg`
  https://interfaceingame.com/wp-content/uploads/batman-arkham-city/batman-arkham-city-detective-mode-1920x1080.jpg
- `arkham-reference-imgur-frvgmZJ.jpg` — Arkham City riddle scan HUD:
  "ENVIRONMENT ANALYSIS / Solution partially detected"
  https://i.imgur.com/frvgmZJ.jpeg
- `arkham-reference-reddit-psq9wh35xtd71.jpg` — Arkham City riddle scan
  HUD: "ENVIRONMENT ANALYSIS / Subject Out Of View"
  https://i.redd.it/psq9wh35xtd71.jpg

If a direct link has rotted, browse the per-game screenshot indexes:
https://interfaceingame.com/games/batman-arkham-knight/ and
https://interfaceingame.com/games/batman-arkham-city/ .

## References collected

| File | What it teaches us |
| ---- | ------------------ |
| `arkham-knight-batcomputer.jpg` | Menu/grid layouts, "?" unknown-state tiles, hex-pattern background, header typography |
| `arkham-knight-upgrade-points-earned.jpg` | Notification banner anatomy (icon + label + value), progress bars, cyan-on-dark popups |
| `arkham-knight-main-menu.jpg` | Overall palette and menu chrome |
| `arkham-knight-searching.jpg` | Loading/pending state: centered emblem + cyan headline + white subtext |
| `arkham-knight-waynetech.jpg` | WayneTech icon style, upgrade-tree card layout |
| `arkham-city-detective-mode.jpg` | Detective-mode palette: deep blue/black, cyan wireframes, orange threat highlights, HUD reticle corners |
| `arkham-reference-imgur-frvgmZJ.jpg` | **The actual riddle-scan feedback HUD**: "Solution partially detected" — banner anatomy (green `!` chip + uppercase headline + cyan rule + white subtext) |
| `arkham-reference-reddit-psq9wh35xtd71.jpg` | Same HUD showing "Subject Out Of View" — the game's own copy for a failed scan |

## Palette

- **Base**: near-black blues and gunmetal (`#0a0e14` → `#101820` range). UI
  panels are translucent dark with faint hex/tech patterning.
- **Primary accent — Batcomputer cyan**: pale electric cyan/ice blue
  (`~#7fd4e8` – `#a8e6f5`) for headlines, active states, icons, progress.
- **Riddler green**: bright neon green (`~#3ddc84` – `#7CFC00`) for riddle
  content, question-mark glyphs, "riddle solved" moments. Use green only for
  riddle/verdict surfaces so it reads as "the Riddler's channel."
- **Alert/warning**: red-orange (`~#ff4d3a`) for rejections and warnings
  (detective mode's "threat" orange is the tonal reference).
- **Text**: white for body, cyan for headings/links, desaturated grey for
  secondary text.

## Typography

- Condensed, geometric, uppercase sans-serif for headings and labels
  (free approximations: **Rajdhani**, **Saira Condensed**, **Electrolize**,
  **Orbitron** for numerals/badges).
- Sentence-case light sans for body/flavor text.
- Headline + subtext pattern (see `searching.jpg`): cyan headline,
  smaller white subtext beneath, centered — this is exactly our
  `SCANNING...` pending screen.

## UI anatomy to borrow

1. **Verdict banner** (from the two riddle-scan HUD shots): bright green
   square chip with a white `!` glyph on the left, uppercase headline
   ("ENVIRONMENT ANALYSIS") beside it, a thin cyan horizontal rule
   extending right from the headline, and smaller white subtext beneath
   ("Solution partially detected"). This is the game's *literal* riddle
   verdict UI — it is the primary template for our verdict notifications.
   Map states onto it: headline stays "ENVIRONMENT ANALYSIS" (or
   "SUBJECT ANALYSIS"), subtext carries the verdict; chip color shifts
   with severity (green = info/solved, amber = soft rejection, red =
   not found).
2. **Notification banner** (from `upgrade-points-earned.jpg`): dark rounded
   panel, hexagonal icon chip on the left, bold uppercase title, thin cyan
   rule, smaller subtext. → Our verdict notifications: `SUBJECT VERIFIED` /
   `SUBJECT OBSCURED` / `SUBJECT NOT FOUND`, icon chip = bat emblem / green `?`.
2. **Tile grid** (from `batcomputer.jpg`): uniform square tiles with thin
   borders; unknown entries shown as a large `?` glyph; unlocked entries show
   imagery; small orange "new" tab in the corner. → Our riddle list: unsolved
   riddles are `?` tiles, verified ones reveal the player's photo.
3. **HUD reticle corners** (from `detective-mode.jpg`): thin cyan bracket
   corners around the focused subject. → Frame the photo preview / camera
   viewfinder with these brackets; animate them closing in on submit
   ("scanning" moment).
4. **Progress strip**: thin bar with segment ticks (progress screen) →
   player's solved-count strip across the riddle list.
5. **Icon chips**: hexagonal or beveled-square chips containing a single
   glyph — use for verdict icons and moderator action buttons.

## Motion/flavor ideas (cheap in CSS)

- Verdict reveal: text "types" in like a terminal, or glitch-flickers once.
- `SCANNING...` pending state: pulsing reticle brackets over the submitted
  photo with an animated sweep line (detective-mode scan sweep).
- Rejected (`NOT FOUND`): brief red flash on the tile.
- Soft rejections (`OBSCURED` / `TOO_SMALL` / `MISALIGNED`): amber/yellow
  flash instead of red — "try again" should feel warmer than "wrong."
- Solved: tile flips from `?` to the photo with a green `?`-glyph stamp.

## Verdict copy bank (draft)

- `PENDING` → "SCANNING SUBJECT…" / "Cross-referencing with Batcomputer
  database…"
- `VERIFIED` → "SUBJECT VERIFIED. Riddle solved." / "Riddle solved. The
  Riddler underestimates you, detective."
- `OBSCURED` → "SUBJECT OBSCURED. Detective vision cannot resolve the
  subject — adjust your angle." / "Partial match only. Get a clearer shot."
- `TOO_SMALL` → "SUBJECT TOO SMALL. Move closer, detective." / "The
  Batcomputer cannot resolve a subject at this range."
- `MISALIGNED` → "MISALIGNED. Adjust your perspective." / "Scan incomplete —
  reframe the subject and try again." / **"Solution partially detected"**
  (verbatim from the game's scan HUD — the most authentic soft-rejection
  copy we have)
- `NOT_FOUND` → "SUBJECT NOT FOUND." / **"Subject Out Of View"** (verbatim
  from the game) / "That is not the answer. The Riddler expected better."
- `EXPIRED` → "INTEL EXPIRED. This window has closed."

## Sources for more reference later

- interfaceingame.com/games/batman-arkham-knight (and Arkham City) —
  organized per-screen UI shots.
- gameuidatabase.com (game id 187) — filterable by UI category (HUD, menu,
  popup).
- YouTube "Arkham Knight riddle scan" clips for the actual
  subject-not-found / misaligned scan messages in motion.
