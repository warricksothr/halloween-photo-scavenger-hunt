# Running your own hunt

Start here if you want to host the game yourself. This page says what you
are running, what it needs, and which of the three deployment recipes to
follow. The other pages in `deploy/` are the recipes and the reference.

| Page | Read it when |
| --- | --- |
| [This page](README.md) | You are deciding how to host it |
| [`CONTAINER.md`](CONTAINER.md) | You deploy with podman or docker, on a LAN or behind a TLS proxy |
| [`RUNBOOK.md`](RUNBOOK.md) | You deploy with systemd and nginx, and before every party, whichever recipe you used |
| [`CONFIGURATION.md`](CONFIGURATION.md) | You set a variable, or want to know what one does |
| [`OPERATIONS.md`](OPERATIONS.md) | You upgrade, restart, back up, rotate a credential, or read the logs |

## What you are running

One process serves everything: the API, the live-update stream, and the
built web app. There is no separate database server, cache, or worker.

- **State is one directory.** The SQLite database (`arkham.db`, in WAL
  mode, so `arkham.db-wal` and `arkham.db-shm` sit beside it) and the
  uploaded photos (`photos/originals/` and `photos/derivatives/`). Back up
  that directory and you have backed up the game. Its location is fixed:
  `data/` at the root of the checkout, or `/srv/arkham/data` in the image.
- **Live updates use Server-Sent Events** on `/api/events/stream`. A proxy
  in front must not buffer that path, or the moderation queue looks
  frozen.
- **Run exactly one process.** Admin sign-ins, rate limits and the
  live-update fan-out live in that process's memory, so two workers
  behind a load balancer would each see half the party.
- **Migrations run on start.** A new build upgrades the database the first
  time it starts, and there is no downgrade (see
  [OPERATIONS.md](OPERATIONS.md#upgrade)).

Photos are the only thing that grows. An upload is capped at 15 MB, and
the server keeps the original and a smaller copy for display. Uploads stop
with a clear error when the data volume drops below 256 MiB free
(`ARKHAM_MIN_FREE_BYTES`). After a rehearsal, `du -sh` the photos
directory to see how fast your crowd fills it.

## Who signs in, and how

| Who | Where | How they get in |
| --- | --- | --- |
| Host | `/admin` | The local admin password, or single sign-on in the admin group |
| Moderators | `/m/<code>` (the mod link) | Single sign-on in the moderator group. The host can also moderate |
| Players | `/j/<code>` (the join link or QR) | Nothing but a codename. No account, no password |

**Moderators need single sign-on.** The mod link picks the event, but it
is not a password (ADR 0020). Joining the console also takes an OIDC
identity in the moderator group, or the host's own sign-in. Without an
OIDC provider only the host can moderate, which is fine for a small party
and a bottleneck for a big one. Any OIDC provider that puts group names in
a `groups` claim works. RUNBOOK §6 walks through Authentik.

## What it needs from the network

- **HTTPS, for the full experience.** Browsers only register a service
  worker in a secure context, so on plain HTTP the game still plays in the
  browser, but it cannot be installed as an app or keep its shell
  offline. Session cookies are `Secure` by default. A plain-HTTP run has
  to turn that off (`ARKHAM_COOKIE_SECURE=false`), or every sign-in fails.
- **Phones reach the host.** Players scan a QR code that opens
  `https://<host>/j/<code>`, so `<host>` has to resolve and answer on the
  network their phones are on: the internet, or the venue's Wi-Fi.
- **Outbound, only if you use them:** your OIDC provider, for SSO, and a
  GlitchTip or Sentry server, for error reports. Neither is needed to play.
  The web app loads its fonts from Google Fonts.

## Pick a recipe

|  | LAN container | Container behind a TLS proxy | systemd and nginx |
| --- | --- | --- | --- |
| Doc | [CONTAINER.md §1–6](CONTAINER.md) | [CONTAINER.md §7](CONTAINER.md#7-behind-a-tls-reverse-proxy) | [RUNBOOK.md](RUNBOOK.md) |
| TLS, public name | No, plain HTTP | Yes, the proxy terminates it | Yes, nginx terminates it |
| Installable app | No | Yes | Yes |
| Host needs | podman or docker | podman or docker, and a proxy | Python 3.11 or newer, Node.js and npm, nginx |
| Good for | One night on a laptop at the venue, and trying it out | A standing deployment. This is how the reference deployment runs | A host without a container runtime |

If you are unsure, pick the container behind a proxy. It is the one that
has run a public deployment since September 2026, and an update is a pull
and a rebuild.

## Then, before the party

Whichever recipe you used, walk [RUNBOOK.md](RUNBOOK.md) §1–3 on the real
host before the night: prove a backup restores, set up the event, and play
the whole loop with two phones and a moderator. The night itself is the
wrong time to find a missing step.

## Host-specific notes

`deploy/targets/` holds one untracked note per real deployment: where its
files live, how it differs from these docs, and how to reach it. See
[`targets/README.md`](targets/README.md). Keep host names, addresses and
paths there, and keep these docs generic.
