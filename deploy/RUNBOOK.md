# Pre-party runbook

One page. Run it **once, start to finish, on the real host** before the
event (build-plan.md §10: the night itself is not the time to discover
the deploy recipe missed a step). §0 and §6 set up the systemd recipe.
§1–5 apply to every recipe. Everything below assumes the checkout
is at `~/arkham` and the service is `arkham-hunt`; §6 needs an Authentik
application, which you set up once.

On a container deploy ([CONTAINER.md](CONTAINER.md)), translate as you go:

| This page says | On a container |
| --- | --- |
| `~/.config/arkham-hunt.env` | The `.env` beside your compose file |
| `systemctl --user restart arkham-hunt` | `docker compose up -d` (or `podman-compose up -d`) |
| `journalctl --user -u arkham-hunt` | `docker logs arkham-hunt` |
| `~/arkham/data` | The volume or bind mount at `/srv/arkham/data` |
| `~/arkham/deploy/backup.sh` | CONTAINER.md §4 |

[README.md](README.md) compares the recipes, [CONFIGURATION.md](CONFIGURATION.md)
lists every variable, and [OPERATIONS.md](OPERATIONS.md) covers upgrades,
restarts and credential rotation.

## 0. Deploy (first time, or after pulling changes)

The first time, set up the pieces around the checkout: the env file
(`~/.config/arkham-hunt.env`, mode 0600; see CONFIGURATION.md for what
goes in it and how to hash the password), the user unit (the install
commands are at the top of `deploy/arkham-hunt.service`), and nginx with
TLS (at the top of `deploy/nginx.conf`). Then, and after every pull:

```sh
cd ~/arkham
git pull
# Backend deps (once, or when server/requirements.lock changes). The
# lock pins the exact versions CI tests and the image ships (ADR 0012);
# a plain `-e server` would resolve whatever is newest. The test tools
# (`server[dev]`) are not needed to run it:
uv venv --clear server/.venv    # --clear: uv refuses to overwrite an existing venv
uv pip install -p server/.venv --require-hashes -r server/requirements.lock
uv pip install -p server/.venv --no-deps -e server
# Frontend build (web/dist is what uvicorn serves in production). Any
# VITE_* settings go on this line (CONFIGURATION.md):
cd web && npm ci && VITE_ERROR_RELEASE=$(git rev-parse --short HEAD) npm run build && cd ..
systemctl --user restart arkham-hunt
systemctl --user status arkham-hunt   # active (running)
curl -s https://<host>/api/health     # {"status":"ok",...}
```

Set `ARKHAM_RELEASE` in the env file to the same short commit before the
restart, so the admin console's version footer agrees with the page.
Back up before pulling a new build: it migrates the database when it
starts, and there is no way back but a restore (OPERATIONS.md).

When health is green but something feels off, log in and read the deeper
probe — it reports writer access, disk free, photo count, and live SSE
clients, all in one call:

```sh
curl -s -b admin.jar https://<host>/api/admin/readyz   # db_writable, disk, sse_subscribers, release
```

## 1. Backup, and prove the restore

A backup you have never restored is a rumor, not a backup.

Point the script at a second disk first — an archive beside the data is not a
backup. Export these in the shell that runs the script. The script does not
read `~/.config/arkham-hunt.env`: only the service does.

```sh
export ARKHAM_BACKUP_MIRROR=/mnt/usb/arkham   # another disk, not ~/arkham
export ARKHAM_BACKUP_KEEP=14                  # newest archives retained
```

```sh
~/arkham/deploy/backup.sh                      # → backups/arkham-backup-*.tar.gz, copied to the mirror
# Prove it restores. Select one archive — retention leaves several, and a
# wildcard would make tar read all but the first as member names:
systemctl --user stop arkham-hunt
mv ~/arkham/data ~/arkham/data.saved
mkdir -p ~/arkham/data
ARCHIVE=$(ls -1t ~/arkham/backups/arkham-backup-*.tar.gz | head -n 1)
tar -xzf "$ARCHIVE" -C ~/arkham/data
systemctl --user start arkham-hunt
curl -s https://<host>/api/health              # ok → the backup is real
```

The script copies the archive to `ARKHAM_BACKUP_MIRROR` and prunes both
directories to the newest `ARKHAM_BACKUP_KEEP`. It warns if the mirror is
unset or lands on the same device as `data/`, and fails if the mirror is not a
directory (an unmounted mount point).

## 2. Set up the night's event

1. Open `https://<host>/admin` in a browser — the admin console is behind
   the login: SSO if §6 is configured, or the local break-glass password
   you chose when generating `ARKHAM_ADMIN_PASSWORD_HASH` (the file holds
   only the hash).
2. Create the event; choose `live` or `final-reveal` standings.
3. Add the 12–15 riddles in `sort_order` order.
4. Print two QR codes — the **join link** (`https://<host>/j/<code>`)
   for players and the **mod link** (`https://<host>/m/<code>`) for
   moderators. The event's **Links & QR** shows them at any time; its
   **Print** button prints a one-page join sheet, and **SVG**/**PNG**
   save the join QR. The mod link stays hidden until you reveal it.
   The mod link picks the event but lets no one in by itself: each
   moderator also signs in through SSO with an account in the moderator
   group (§6). Without SSO, only you can moderate, signed in as host.
   Have each moderator follow the link and sign in once before the
   night, so a group-membership mistake turns up now.
5. Check free disk before opening: `df -h ~/arkham/data /tmp` and
   `du -sh ~/arkham/data/photos/originals`. Uploads refuse below 256 MiB
   free on the data volume **and** on the multipart spool filesystem
   (`ARKHAM_MIN_FREE_BYTES` to change the floor, ADR 0023), and a full
   disk breaks SQLite writes too — so clear space now, not mid-round.
6. Press **open** only when players are physically present.

### A demo event, from the bundled fixture

For a demo or a rehearsal, the seeder creates the Riddler demo event
(twelve riddles, three hint levels each) through the admin API, opens it,
and prints the join and mod codes. It needs `ARKHAM_ADMIN_API_TOKEN` set on
the running server (§6, "Scripted access"). `podman exec` inherits the
container's environment, so nothing else is passed:

```sh
podman exec arkham-hunt python -m app.seed
```

- `--no-open` leaves the event in the lobby, so you can review the riddles
  in the console first.
- A second run refuses to create another event with the same name, and
  names the one that exists. Pass `--allow-duplicate` to create it anyway.
- If a run fails after creating the event, the error names that event.
  Its codes were never printed, so no player can join it. Rerun with
  `--allow-duplicate`.
- From outside the container, use the server venv and point it at the
  app: `server/.venv/bin/python -m app.seed --base-url http://127.0.0.1:8000`.
- `answered 403 (csrf_failed ...)` or `401 not_authenticated` means the
  token did not match the server's. Check both sides.

The riddle text is in `server/app/fixtures/demo-event.json`. Edit it there.

## 3. Full smoke walkthrough (do this with a second phone)

Two players, one moderator — the whole game loop against the real
deploy:

1. **Join as two players** (scan the join QR on both phones, or type
   the code) and join the mod console on a third device (or a desktop
   tab).
2. Player A: take a photo → it appears in the drawer → submit it for a
   riddle → the tile shows SCANNING.
3. Moderator: the submission appears in the queue **without refreshing**
   (if it doesn't, SSE is broken — check `proxy_buffering off` in
   nginx). Open it; issue **VERIFIED** → player A's tile flips to
   RIDDLE SOLVED and standings update.
4. Player B: submit a blurry/dark photo; moderator issues **OBSCURED** →
   player B sees the rejection copy and resubmits.
5. Player B: submit an off-topic photo; moderator issues **SUBJECT NOT
   FOUND**.
6. Moderator: flag a submission **INAPPROPRIATE** → that player sees
   the plain strike interstitial; the photo vanishes from their drawer;
   the queue item is gone.
7. Host (admin console): **reverse** the strike → the player's
   restriction clears on their next snapshot.
8. **Close** the round → every pending submission expires, final
   standings appear (instantly, under final-reveal), and the recap
   timeline shows the night's first solves and lead changes.

If all eight pass, the night is ready.

## 4. During the night

- Re-run `~/arkham/deploy/backup.sh` at a natural break (it is an
  online backup — safe while the game is live). Each run mirrors off-host and
  prunes, so no manual cleanup is needed.
- If a phone shows stale state: reload the page. The snapshot is the
  resync point; SSE reconnects refetch everything.
- To see who did what, open the moderator console's **Log**: every
  verdict, strike, removal and flag, newest first, with the photo behind
  each. **Everything** adds joins, uploads and settings changes.
- If a join QR ends up somewhere public, or a mod link reaches the wrong
  person, open the event's **Links & QR** and press **New join code** or
  **New moderator code**, then hand out the new one. Players and moderators already in stay in (ADR 0039).
- A strike given in error is reversed from the admin console. The
  player's restriction lifts on their next refresh.
- If the round was closed too early, **Reopen the round** from the event
  card puts it back in play. Scans that the close expired stay expired,
  and players can submit those photos again (ADR 0042).
- Avoid restarting the server mid-round. Players and moderators stay
  signed in and their phones reconnect by themselves, but the host has to
  sign in again (OPERATIONS.md, "What a restart does").

## 5. After the night

- `deploy/backup.sh` once more (the archive of the night).
- Show the recap screen on a TV / share the final standings.
- When the photos have served their purpose: purge the event from the
  admin console (`POST /api/admin/events/{id}/purge`, confirm = event
  name). Purging deletes the DB rows AND the photos — including
  quarantined originals — per the conduct rules (retained only until
  the event ends).

## 6. Single sign-on (OIDC via Authentik)

Hosts and moderators sign in through Authentik; players never do. The app
reads the issuer and client from the environment only, and the local
admin password (§2) stays as break-glass so an Authentik outage cannot
lock you out of your own party.

### Authentik side

Create these once in the Authentik admin UI:

1. **Groups → Create.** Two groups whose names match the app's
   defaults: `arkham-admin` and `arkham-moderator`. Put your host account
   in the first and any moderator accounts in the second. The host can
   also moderate: opening an event's mod link while signed in as host
   joins its queue under the host's own name (ADR 0027).
2. **Property Mappings → Create → OAuth2 Provider scope mapping**
   (type: Scope mapping) that emits the caller's group names. Give it the
   scope name **`groups`** (the app reads the `groups` claim, so the
   mapping's expression must be):

   ```python
   return {"groups": [group.name for group in request.user.ak_groups.all()]}
   ```

   Verify the claim name is exactly `groups`: without it every sign-in is
   refused as `not_authorized`, because no role can be read from the
   token.
3. **Applications → Create with Provider → OAuth2/OpenID Provider.**
   - Client type: **Confidential**.
   - Redirect URI (exact): `https://<host>/api/auth/oidc/callback`.
   - **Advanced protocol settings → Scopes:** the three defaults
     (`openid`, `profile`, `email`) **plus the `groups` mapping** you
     created. Authentik emits a scope mapping only when its scope name is
     in the requested scopes, so the app must ask for `groups` too (next
     section) — otherwise the token carries no `groups` claim and every
     login is refused as `not_authorized`.
4. Copy the provider's **Client ID** and **Client secret**, and note the
   issuer URL — the application's `OpenID Configuration Issuer`, of the
   form `https://<authentik-host>/application/o/<slug>/` (keep the
   trailing slash).

Raise the signing key's rotation period if Authentik warns: the app
caches JWKS for five minutes, so a rotation is picked up within that
window.

### App side

Put these in `~/.config/arkham-hunt.env` (mode 0600, never committed —
repo policy), then `systemctl --user restart arkham-hunt`. The file is a
systemd `EnvironmentFile`, not a shell script: use **bare assignments, no
`export`** — systemd silently skips a line it cannot read as
`NAME=value`, and an exported line leaves SSO off with no error.

```sh
ARKHAM_OIDC_ISSUER=https://<authentik-host>/application/o/<slug>/
ARKHAM_OIDC_CLIENT_ID=<client id>
ARKHAM_OIDC_CLIENT_SECRET=<client secret>
# Required when the groups mapping has its own scope name:
ARKHAM_OIDC_SCOPES=openid profile email groups
# Optional — these are the defaults:
# ARKHAM_OIDC_ADMIN_GROUP=arkham-admin
# ARKHAM_OIDC_MODERATOR_GROUP=arkham-moderator
# Only if the callback URL cannot be derived from the request:
# ARKHAM_OIDC_REDIRECT_URI=https://<host>/api/auth/oidc/callback
# Optional — standing token for scripted admin access (see below):
# ARKHAM_ADMIN_API_TOKEN=<random secret>
```

`ARKHAM_OIDC_SCOPES` must list every scope the provider emits, including
the `groups` mapping from the Authentik step — the app's default
(`openid profile email`) does not include it, and a scope the app does
not request is a claim it never receives.

`ARKHAM_OIDC_REDIRECT_URI` is usually unnecessary: behind nginx,
uvicorn's `--proxy-headers` makes `request.base_url` the public URL, and
the app derives `https://<host>/api/auth/oidc/callback` from it. Set the
variable only when the derived URL differs from the one registered in
Authentik — they must match exactly, or the token exchange fails.

All three of issuer, client id, and client secret must be present or SSO
is off (`create_app` treats half-configured SSO as none). The app
starts with SSO off, so a missing or typo'd variable never stops the
party — it just disables the SSO button.

### Sign in, and break glass

- Admin console: open `https://<host>/admin` → **Sign in with SSO**
  (or start at `https://<host>/api/auth/oidc/login`). A host account
  lands on `/admin`; a moderator account following the `/m/<code>` mod
  link lands on the moderator console.
- The password form still works: it is the break-glass path and stays
  independent of Authentik. `~/.config/arkham-hunt.env` stores only the
  hash (`ARKHAM_ADMIN_PASSWORD_HASH`), so the plaintext is the one you
  typed when the hash was generated — keep it in a password manager, not
  on the host. Use the form if Authentik is unreachable.

### Scripted access: the admin API token

For a script that has no browser — a smoke test, a seeding script, a CI
check — set `ARKHAM_ADMIN_API_TOKEN` to a random secret and send it as
`Authorization: Bearer <token>`. The request then needs no cookie jar and
no CSRF pair, because a header credential is not the ambient cookie CSRF
protects against. Unset it and nothing changes; the password and SSO
paths are untouched.

Generate one with `openssl rand -hex 32`. Treat it like the password
hash: env only, never committed, and **not** a session — the token does
not expire when the process restarts and cannot be revoked from the UI.
To rotate it, edit the file and `systemctl --user restart arkham-hunt`.
Keep it out of shell history and off the host where you can.

```sh
curl -s -H "Authorization: Bearer $ARKHAM_ADMIN_API_TOKEN" \
  https://<host>/api/admin/events
```

### Troubleshooting OIDC

| Symptom | Check |
| --- | --- |
| **Sign in with Authentik** answers `503 oidc_disabled` | Issuer, client id, and secret are all set in `~/.config/arkham-hunt.env`, and the service was restarted after editing it |
| `401 not_authorized` after a successful Authentik login | The account is in `arkham-admin` / `arkham-moderator`, and the `groups` scope mapping is attached to the provider and emits a `groups` claim |
| `401 oidc_bad_token` in the redirect | Redirect URI in Authentik does not exactly match `https://<host>/api/auth/oidc/callback`; client secret is current; the issuer has its trailing slash |
| `502 oidc_unavailable` | The app cannot reach Authentik's discovery or token endpoint — check DNS and TLS from the host: `curl -s $ARKHAM_OIDC_ISSUER.well-known/openid-configuration` |
| `401 oidc_bad_state` | The five-minute sign-in window expired, or the transaction cookie was dropped — retry, and confirm cookies are not blocked |
| Login loops between the app and Authentik | Cookie `SameSite`/`Secure` mismatch — the TLS path keeps the secure default; a plain-HTTP test needs `ARKHAM_COOKIE_SECURE=false` |

## Failure cheatsheet

| Symptom | Check |
| --- | --- |
| Queue/tiles don't update live | `proxy_buffering off` on the SSE location; `curl -N https://<host>/api/events/stream` should stream heartbeats |
| Players can't upload big photos | nginx `client_max_body_size 16m` sits above the app's 15 MB cap, so the app owns the 413 |
| Uploads answer 507 `storage_full` | `df -h` the data dir; free space, or set `ARKHAM_MIN_FREE_BYTES` to the floor you actually want, then restart |
| 502 after reboot | `loginctl enable-linger "$USER"`; `systemctl --user status arkham-hunt` |
| App up, site blank | `web/dist` exists and was rebuilt after the last `git pull` |
| Nothing in GlitchTip | `ARKHAM_ERROR_DSN` / `VITE_ERROR_DSN` are set and the app was restarted/rebuilt; the CSP `connect-src` includes the GlitchTip origin |
| SSO sign-in answers `503 oidc_disabled` | See §6 — the issuer/client/secret trio is incomplete or the service was not restarted |
| One busy player gets everyone rate-limited, or SSO sends an `http://` callback | The app is not trusting the proxy's headers: `--proxy-headers` with the proxy's address in `--forwarded-allow-ips` (the unit file carries both; a container needs CONTAINER.md §7) |
| A moderator's sign-in comes back `not_authorized` | Their account is not in the moderator group, or the group name in the env differs from the `groups` claim (case and spaces count) |
| The admin footer keeps saying the page is out of date | `ARKHAM_RELEASE` and the build's `VITE_ERROR_RELEASE` differ, or only one is set |
| Script's `Authorization: Bearer` gets 401 | `ARKHAM_ADMIN_API_TOKEN` is set and the service was restarted after editing the env file; the header is exactly `Bearer <token>` |

## Error reporting (GlitchTip)

Both halves of the app report to the self-hosted GlitchTip. Reporting is
opt-in: with no DSN the SDKs stay inert, so a developer checkout and the
test suite send nothing.

Put the DSNs in `~/.config/arkham-hunt.env` (the browser DSN also needs to
be in the build environment). They are ingest keys rather than hard secrets —
the browser one ships in the bundle — but anyone holding one can post events
to the project, so keep them out of the repo.

The env file takes bare `NAME=value` lines, never `export` (§6), and does
not run commands, so write the release out rather than a `$(git …)`:

```sh
ARKHAM_ERROR_DSN=https://<key>@<glitchtip-host>/<project>
# Optional; 0 disables tracing:
ARKHAM_TRACES_SAMPLE_RATE=0.1
ARKHAM_ENVIRONMENT=production
# The short commit you deployed (§0):
ARKHAM_RELEASE=<commit>
```

The browser DSN is compiled into the bundle, so it is a **build** input —
set it before `npm run build` (or pass it as a build arg to the container):

```sh
cd ~/arkham/web
VITE_ERROR_DSN=https://<key>@<glitchtip-host>/<project> \
VITE_TRACES_SAMPLE_RATE=0.1 \
VITE_ERROR_RELEASE=$(git rev-parse --short HEAD) npm run build
```

Allow `https://<glitchtip-host>` in the CSP's `connect-src` in
`deploy/nginx.conf`, or the browser blocks its own reports.

Check it works: open the site and watch for a request in GlitchTip's Issues. A
backend 500 — or any unhandled server error — arrives with a `request_id` tag
that matches the `X-Request-ID` header and the request log line.

