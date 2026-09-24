# 0028. The path decides the role when a browser holds two sessions

Date: 2026-09-24
Status: accepted

## Context

A browser can hold a player session (`arkham_session`) and a moderator
session (`arkham_mod`) at once. Since ADR 0027 that is the expected case for
a host who moderates and also plays on the same phone. The two halves of the
app disagreed about which session wins:

- **The client** probed the player snapshot first and only looked for a
  moderator when that returned 401. A mod link, and even the refresh right
  after a successful mod join, therefore showed the game.
- **The SSE route** preferred the moderator cookie, so a game tab in such a
  browser silently received the moderator stream and missed its player
  deltas.

## Decision

Each tab shows one role, and its path says which:

- **Moderator paths.** On `/m`, `/m/<code>`, `/mod` and `/mod/*`, the store
  probes the moderator session first and never consults the player snapshot.
  Without a moderator session the shell shows the moderator sign-in, never
  the game.
- **`/m/<code>` always joins.** It renders the join whatever the browser
  holds, including a moderator session for another event. After a
  successful join the URL is replaced with `/mod`. That stops the rule from
  looping, and a reload of the console does not rejoin or write another
  `moderator.joined`.
- **Player paths** keep the old order: the player first, then the moderator.
- **The stream follows the tab.** The client opens
  `/api/events/stream?as=<role>`, using the role it resolved, and rebuilds the
  stream if that role changes. The server uses the named session, or returns
  401 if the browser does not hold it. Without `as` it keeps its old
  preference for the moderator cookie.

## Alternatives

- **One session per browser**, where joining one role drops the other. This
  is simpler, but it is the opposite of what a host who plays needs.
- **A role switcher in the UI.** It adds a control, and a tab still needs to
  know its role on reload. The path already carries that information.

## Consequences

- The host can keep a game tab and a moderator tab open side by side, each
  with the right stream.
- A mod link is always a join. Following a second event's link switches
  that browser's moderator session to that event, because the join replaces
  the cookie.
