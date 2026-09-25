# 0041. Show the running build, and keep the server's release for the host

Date: 2026-09-24
Status: accepted

## Context

Drew asked for version information in the frontend
(TKT-01M3B0EWQAPS240GZX1TJF348G). Two questions come up during a party:
"which build is this phone on?", after a deploy, and "is the page I have
open the build the server is running?". The PWA keeps a page open for a
long time, and a service worker cannot swap code under a running page, so
a page opened before a deploy keeps its old bundle until it reloads.

Two facts already existed:

- The web bundle inlines `VITE_ERROR_RELEASE` at build time, for error
  reports (ADR 0018). kobal's compose passes it from `ARKHAM_RELEASE`, so
  the client's build id is already readable by anyone who loads the
  JavaScript.
- The server's release is deliberately not public. `GET /api/health`
  answers only liveness and the schema version. `release` lives in
  `GET /api/admin/readyz`, which requires the admin (ADR 0023), so that
  the running build is not a fingerprint for a stranger to match against
  known bugs.

## Decision

- `web/src/version.js` exports `WEB_BUILD`: `VITE_ERROR_RELEASE`, or
  `dev` for a local build without it. It reuses the error reporter's
  variable instead of adding a new one, so no host needs a new build
  argument.
- Players and moderators see `Build <id>` in small print at the foot of
  the join screen, the player's Case screen and the moderator console's
  queue rail (`components/BuildTag.jsx`). It is the client's id only.
- The signed-in host console has a footer with the web build, the server
  release and the schema version, read from `readyz`. When the server
  names a release and it differs from the page's, the footer says the
  page is an older build and offers Reload. If `readyz` fails, the footer
  shows only the web build.
- The server does not change. No public endpoint gains the release.

## Alternatives considered

- **A public `/api/version`**, compared on every client. It would let a
  player's phone warn about a stale page too. It lost because it
  publishes the server's release, which ADR 0023 keeps behind sign-in. A
  network-first service worker makes a stale page rare for players
  anyway: any reload fetches the new bundle.
- **A dedicated `VITE_APP_VERSION` build argument**, or one computed with
  `git rev-parse` in `vite.config.js`. The container build context
  excludes `.git`, and a new argument would need kobal's compose changed.
  The release the error reporter already carries is the same value.
- **Showing the build on every player screen.** Considered and rejected
  as clutter. The Case screen is where a player goes for their own
  details, and the join screen is where someone lands before they have a
  game.

## Consequences

- A build made without `VITE_ERROR_RELEASE` reads `dev`. The host footer
  then warns only if the server names a real release, which is the case
  where the page really is not the deployed bundle.
- The build id shown to players is a short commit hash. It is the value
  already in the bundle, so showing it reveals nothing new.
- Tests: `components/BuildTag.test.jsx` covers the label and fallback.
  `screens/Admin.test.jsx` covers the footer's match, mismatch, `unknown`
  and failure cases.
