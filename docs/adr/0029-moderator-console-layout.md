# 0029. Give the moderator console a desktop and tablet layout

Date: 2026-09-24
Status: accepted

## Context

The moderator console was built inside the player's phone frame (ui.md: "the
moderator console shares the frame because moderation happens from the
floor"). On a laptop or tablet that meant a 480px column in the middle of the
screen. The queue, the photo, the verdict buttons, the player's history and
the conduct section were stacked in one scroll. The verdict buttons sat below
the photo, so every decision needed a scroll down and then a scroll back up
to the queue.

The host who moderates will run the console from a laptop or a tablet on the
night (ADR 0027), so the wide screens are the main case now, not a fallback.

## Decision

The console lays itself out by width, from one stylesheet
(`web/src/mod-console.css`):

- **Under 700px (a phone)**: one column, in the order the console always had:
  queue, review, decision.
- **700–1099px (a tablet)**: the queue sits in a rail on the left. The review
  and the decision stack in one column that scrolls beside it.
- **1100px and up (a desktop)**: three columns, queue | photo | decision.
  Each column scrolls on its own, so the verdict buttons stay in view whatever
  the queue's length.

At 700px and up the moderator frame drops the phone frame's `max-width` and
takes the full viewport height. The player screens keep the phone frame: the
moderator shell adds `mod-frame`, and every rule is scoped under it or under
`.mod-console`.

Three workflow changes ride on the layout:

- **Auto-advance.** After a verdict or an inappropriate removal, the console
  opens the oldest pending item that no other moderator is viewing
  (`nextToReview`). A claim is advisory (ADR 0002), but it is how two
  moderators avoid judging one photo twice, so auto-advance never walks into
  someone else's claim. When nothing is left, the console says so.
- **Shared-photo compare.** A queue item with a duplicate flag now carries
  `other_photo_url` and `other_team_label` (api.md). The review shows both
  photos side by side, so "same photo, two teams" is judged by looking rather
  than by trusting the hash.
- **Full-size zoom.** Clicking either photo opens it at full size in a
  dialog. Escape or a click on the backdrop closes it.

The console's sections are split into components under
`web/src/screens/mod/`, with `ModConsole.jsx` as the orchestrator that owns
the state.

The layout reads every colour, font and border from the theme pack's
variables. The theme's stylesheet is injected at runtime, after the bundled
CSS, so a modifier class that only ties with `.btn.secondary` on specificity
loses on order. The console's button modifiers are therefore written as
`.mod-console .btn.mod-btn-*`.

## Alternatives

- **Two columns at every wide width**, with the queue plus one detail column.
  This is simpler, but on a desktop the detail column has to scroll between
  the photo and the verdicts, which is the problem being solved.
- **A separate desktop route** (`/mod/desk`). This means two consoles to keep
  in step, and a host who opens the link on a tablet would need to know which
  one to use. One responsive screen avoids both.
- **Keyboard shortcuts for verdicts.** Offered, and left out of this change
  at Drew's choice. A single-key verdict is also an easy mis-key, so adding
  one later should come with a confirmation or an undo.
- **Loading the matched photo on demand** (a second request after a click).
  The compare is the reason the flag exists, so the URL rides on the queue
  item and the photo loads with the review.

## Consequences

- On a laptop the host can review, decide and move on without scrolling.
- The queue payload grows by two fields per flagged item. The matched photo
  is served through the existing moderator photo route, so no new access path
  exists.
- The phone layout is unchanged in order and content. It gains the zoom and
  the compare, and it loses nothing.
- A future theme pack restyles the console through its variables. It must
  keep `.btn` at class specificity, or the modifiers need revisiting.
