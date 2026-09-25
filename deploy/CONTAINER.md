# Container runbook — podman or docker

One container holds the whole app (web build + FastAPI server + SQLite).
§1–6 run it on its own over plain HTTP: the **local / LAN-party**
deployment, with no proxy and no TLS. §7 puts the same image behind a TLS
reverse proxy for a standing deployment. For the systemd path with no
container, see `deploy/RUNBOOK.md`. [`README.md`](README.md) compares
the three, and [`CONFIGURATION.md`](CONFIGURATION.md) lists every
variable.

The easy path is **compose** — one command up, one command down
(§1). The raw `podman run` recipe stays in §2 for hosts without a
compose frontend. Every command below was run and verified against the
repo `Containerfile` + `compose.yml` (podman 4.9, podman-compose). Any
of `podman-compose`, `podman compose`, or `docker compose` works — the
`Containerfile` and `compose.yml` are valid syntax for both runtimes.

## When to use this vs. the systemd path

|                        | LAN container (§1–6)               | Container behind a proxy (§7)   | systemd + nginx (RUNBOOK.md)     |
| ---------------------- | ---------------------------------- | ------------------------------- | -------------------------------- |
| TLS / public hostname  | no — plain HTTP on a LAN port      | yes — the proxy terminates TLS  | yes — nginx terminates TLS       |
| Host needs Python/Node | no — both live in the image        | no                              | yes                              |
| Best for               | party-night on a laptop/LAN, evals | a standing deployment           | a host with no container runtime |

## 1. One command: compose

```sh
# Credentials go in a gitignored .env beside compose.yml. Hash the
# password from the terminal, so it stays out of shell history
# (CONFIGURATION.md, "The admin password", has a no-Python variant):
read -rsp 'Admin password: ' PW; echo
HASH=$(printf '%s' "$PW" | server/.venv/bin/python -c \
  'import sys; from app.security import hash_password; print(hash_password(sys.stdin.read()))')
unset PW
# Single quotes, written by printf: compose expands every unquoted `$`
# in the hash, and a heredoc would expand them before compose saw them.
printf "ARKHAM_ADMIN_USERNAME=admin\nARKHAM_ADMIN_PASSWORD_HASH='%s'\n" "$HASH" > .env
chmod 600 .env

podman-compose up -d        # builds the image on first run, then starts
```

`compose.yml` pins the whole recipe: build from the Containerfile,
`ARKHAM_COOKIE_SECURE=false`, loopback port 8080, and the `arkham-data`
named volume. It refuses to start without `ARKHAM_ADMIN_PASSWORD_HASH`
(a `:?` interpolation guard) so you never get a running container with
no admin path. Teardown is `podman-compose down` (add `-v` to also drop
the volume — only when the night's data is done). For a LAN party, edit
the port to `"8080:8000"` to publish on all interfaces.

## 2. Raw podman/docker (no compose frontend)

Build the image:

```sh
# --format docker keeps the HEALTHCHECK: podman's default OCI format
# silently drops it, and docker-built images carry it natively.
podman build --format docker -t arkham-hunt:local .
podman image inspect arkham-hunt:local \
  --format '{{.Config.Healthcheck.Test}}'   # must print a CMD-SHELL line
```

The build is multi-stage: stage 1 runs `npm ci && npm run build` in
`node:20-alpine`, stage 2 is `python:3.12-slim` with `web/dist` copied
in. Runtime dependencies install from `server/requirements.lock`, the
hash-pinned export of `server/uv.lock`, so the image resolves exactly
the versions CI tests. `app` is not installed as a distribution:
`PYTHONPATH=/srv/arkham/server` puts it on the import path from the
source tree. That is load-bearing — `main.py` derives the DB and static
paths from the package's `__file__`, so the image keeps the repo layout
and the runtime data dir lands at `/srv/arkham/data` — the one path a
volume must cover.

Then run it:

```sh
# Hash the admin password into $HASH first (CONFIGURATION.md, "The admin
# password"; the image itself can do it). "$HASH" passes it through
# whole: the shell does not re-expand the `$`s inside a variable's value.
podman volume create arkham-data
podman run -d --name arkham-hunt \
  -p 127.0.0.1:8080:8000 \
  -e ARKHAM_ADMIN_USERNAME=admin \
  -e ARKHAM_ADMIN_PASSWORD_HASH="$HASH" \
  -e ARKHAM_COOKIE_SECURE=false \
  -v arkham-data:/srv/arkham/data \
  arkham-hunt:local
```

The environment variables, and why:

- `ARKHAM_ADMIN_USERNAME` / `ARKHAM_ADMIN_PASSWORD_HASH` — required;
  the app refuses to start without them.
- `ARKHAM_COOKIE_SECURE=false` — **required for this recipe.** The app
  sets `Secure` cookies by default; browsers refuse to send those over
  plain HTTP, and without the toggle every login silently 401s. Do not
  set this on the TLS path — production keeps the default.
- `ARKHAM_MIN_FREE_BYTES` — optional. The free-space floor below which
  uploads answer 507 `storage_full`; defaults to 256 MiB. Set it on a
  small volume, and size the `arkham-data` volume above it (ADR 0023).
- `ARKHAM_OIDC_ISSUER` / `ARKHAM_OIDC_CLIENT_ID` /
  `ARKHAM_OIDC_CLIENT_SECRET` — optional, all three together. Turn on
  Authentik single sign-on for hosts and moderators; with any one missing
  the app starts with SSO off. On this plain-HTTP path the callback URI is
  `http://<host>:8080/api/auth/oidc/callback` — register exactly that in
  Authentik, or set `ARKHAM_OIDC_REDIRECT_URI`. If your groups scope
  mapping has its own scope name, list it too, e.g.
  `ARKHAM_OIDC_SCOPES="openid profile email groups"` — an unrequested
  scope emits no claim. `deploy/RUNBOOK.md` §6 covers the Authentik side
  and troubleshooting.
- `ARKHAM_ADMIN_API_TOKEN` — optional. A standing credential for a script
  with no browser: send it as `Authorization: Bearer <token>` and skip the
  cookie jar and CSRF pair. Unset means off. Unlike a session it does not
  expire on restart, so rotate it by editing the env and recreating the
  container.

`-p 127.0.0.1:8080:8000` binds loopback only. For a LAN party (players
on phones on the same network), publish on all interfaces and give the
room the host's LAN address: `-p 8080:8000`.

There is no reverse proxy on this path, so uvicorn sees each player's
real address directly and the rate limiter (`app/ratelimit.py`, ADR
0015) keys on it with no extra flags. The nginx path is the one that
needs `X-Forwarded-For` plus `--proxy-headers` (`deploy/nginx.conf`,
`deploy/arkham-hunt.service`).

## 3. Prove it works (30 seconds)

```sh
curl -s http://127.0.0.1:8080/api/health        # {"status":"ok",...}
curl -s http://127.0.0.1:8080/ | head -c 60     # the SPA's index.html
curl -s http://127.0.0.1:8080/t/ANYTOKEN | head -c 60
                                                # also index.html — invite
                                                # links resolve client-side
podman inspect arkham-hunt --format '{{.State.Health.Status}}'
                                                # healthy
```

Then in a browser: `http://<host>:8080/` → log in as admin → create the
night's event → open it → join from a phone. A join that works (the
game board appears instead of bouncing back to the join screen) proves
the cookie toggle; a join that silently returns to the join screen
means `ARKHAM_COOKIE_SECURE=false` is missing.

After logging in, `GET /api/admin/readyz` reports writer access, disk free,
photo count, and live SSE clients in one call — the probe to read when
health is green but the app feels wrong:

```sh
curl -s -b admin.jar http://127.0.0.1:8080/api/admin/readyz
```

For a disposable local gate that exercises the same raw recipe, run
`bash scripts/smoke-container.sh` from the repository root. The script builds
with `--format docker`, checks health, admin login, the authed readyz probe,
event setup, plain-HTTP player join, a synthetic photo upload, and an SSE
heartbeat. It removes its
container, volume, image, temporary credentials, and generated photos on both
success and failure. A failed run keeps container logs and inspect output under
ignored `.deploy-smoke-results/`.

## 4. Backup / restore

The state lives entirely in the named volume (`/srv/arkham/data`: the
SQLite DB — WAL mode, so expect `arkham.db-wal` alongside — and
`photos/`). The DB snapshot must use SQLite's online backup, not a raw
file copy of a live WAL database:

```sh
# Snapshot while running:
podman exec arkham-hunt python -c "
import sqlite3
src = sqlite3.connect('/srv/arkham/data/arkham.db')
dst = sqlite3.connect('/srv/arkham/data/arkham-backup.db')
src.backup(dst); dst.close(); src.close()"
podman cp arkham-hunt:/srv/arkham/data/arkham-backup.db ./

# Or with the container stopped, archive the whole volume (photos too):
podman run --rm -v arkham-data:/data:ro -v "$PWD:/out" alpine \
  tar -czf /out/arkham-data-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
```

Restore: stop the container, replace the volume contents, start. Prove
the restore once before the night — a backup never restored is a rumor.

Copy each archive to a second disk and keep only a bounded number of them
(the host deploy's `deploy/backup.sh` does both via `ARKHAM_BACKUP_MIRROR`
and `ARKHAM_BACKUP_KEEP`); an archive left beside the volume is on the same
disk as the data it protects.

### With a bind mount: `deploy/backup.sh`

When the data is a host directory rather than a named volume (§7 uses
one), run the same script the systemd path uses, from a checkout, with
`ARKHAM_DATA_DIR` pointing at it. It takes the online snapshot while the
game runs, archives the photos with it, and mirrors and prunes as
`CONFIGURATION.md` describes.

The files belong to the container's user (uid 1000), and SQLite needs to
write beside a WAL database even to read it, so run the script as that
owner. As yourself it fails with `attempt to write a readonly database`.

```sh
# Rootless podman: `podman unshare` runs it as the owner of the mapped files.
podman unshare env ARKHAM_DATA_DIR=/path/to/data \
  sh deploy/backup.sh /path/to/backups
# Rootful docker: the files are uid 1000 on the host too.
sudo env ARKHAM_DATA_DIR=/path/to/data sh deploy/backup.sh /path/to/backups
```

Restore into a bind mount: stop the container, move the old directory
aside, extract the archive into a fresh one, give it back to uid 1000,
and start. The archive holds `arkham.db` and `photos/` at its root, so
extract into the data directory itself:

```sh
podman stop arkham-hunt
podman unshare mv /path/to/data /path/to/data.saved
mkdir -p /path/to/data
ARCHIVE=$(ls -1t /path/to/backups/arkham-backup-*.tar.gz | head -n 1)
podman unshare tar -xzf "$ARCHIVE" -C /path/to/data
podman unshare chown -R 1000:1000 /path/to/data
podman start arkham-hunt
curl -s http://127.0.0.1:8080/api/health    # ok, and the same schema_version
```

With rootful docker, drop `podman unshare` and run those lines with
`sudo`. Skip the `chown` and the app cannot write its own database.

## 5. Update to a new build

Back up first (§4): a new build migrates the database when it starts,
and an older build cannot use the migrated file. `OPERATIONS.md` covers
upgrades and rolling back.

```sh
git pull
podman-compose up -d --build   # rebuilds the image, swaps the container
# (raw path: podman build --format docker -t arkham-hunt:local . &&
#  podman stop arkham-hunt && podman rm arkham-hunt, then §2's run)
```

## 6. Teardown

```sh
podman-compose down           # stop + remove the container
podman-compose down -v        # …and the volume — only when the night's
                              # data is done
podman rmi arkham-hunt:local  # image too, if reclaiming space
# (raw path: podman rm -f arkham-hunt && podman volume rm arkham-data)
```

## 7. Behind a TLS reverse proxy

The standing deployment: the same image, published on loopback only, with
nginx (or any reverse proxy) in front terminating TLS on the public name.
This is how the reference deployment has run since 2026-09-23, under
docker compose. The files below are its own, with the host's names taken
out.

Don't reuse the repository's `compose.yml` for this. It is the LAN recipe
and gets three things wrong behind a proxy:

1. **Proxy headers are off.** The image starts uvicorn without
   `--proxy-headers`, so behind a proxy every request seems to come from
   the proxy's address. Every player then shares one rate-limit bucket
   (ADR 0015), so one noisy phone throttles the party. And the app
   builds its SSO callback as `http://`, which a strict identity
   provider rejects. The compose file below overrides the command to trust
   `X-Forwarded-*` from the proxy, and only from the proxy
   (TKT-01M3816ETRMEH0K7QARH78BR9Z tracks fixing the image).
2. **It turns secure cookies off.** Right on plain HTTP, and wrong behind
   TLS, where it would let a session cookie travel in the clear. Leave
   `ARKHAM_COOKIE_SECURE` unset here.
3. **It keeps the data in a named volume.** A bind mount puts the data
   where your host's backups can see it.

### The compose file

Keep it in a directory of its own with its `.env`, outside the checkout,
so a `git pull` never touches it. `<checkout>` is a clone of this
repository, and `<data>` is the data directory. Create `<data>` owned by
uid 1000 before the first start, since the container runs as that user:
`sudo install -d -o 1000 -g 1000 -m 750 <data>`.

```yaml
services:
  arkham:
    build:
      context: <checkout>
      dockerfile: Containerfile
      args:
        # Compiled into the web app: change these, then build again.
        VITE_ERROR_DSN: ${VITE_ERROR_DSN:-}
        VITE_TRACES_SAMPLE_RATE: ${VITE_TRACES_SAMPLE_RATE:-0.1}
        VITE_ERROR_ENVIRONMENT: ${ARKHAM_ENVIRONMENT:-production}
        VITE_ERROR_RELEASE: ${ARKHAM_RELEASE:-}
    image: localhost/arkham-hunt:prod
    container_name: arkham-hunt
    restart: unless-stopped
    ports:
      # Loopback only. Docker's port publishing bypasses a host firewall
      # such as ufw, so "8456:8000" would be public whatever ufw says.
      - "127.0.0.1:8456:8000"
    # The image's command plus --proxy-headers, trusting X-Forwarded-* only
    # from the network's gateway: the address every request from the host's
    # proxy arrives from. The subnet is pinned below so it cannot drift.
    command:
      - python
      - -m
      - uvicorn
      - app.main:create_app
      - --factory
      - --host
      - 0.0.0.0
      - --port
      - "8000"
      - --proxy-headers
      - --forwarded-allow-ips=172.30.0.1
    environment:
      ARKHAM_ADMIN_USERNAME: ${ARKHAM_ADMIN_USERNAME:-admin}
      ARKHAM_ADMIN_PASSWORD_HASH: ${ARKHAM_ADMIN_PASSWORD_HASH:?set in .env, single-quoted}
      ARKHAM_ADMIN_API_TOKEN: ${ARKHAM_ADMIN_API_TOKEN:-}
      ARKHAM_OIDC_ISSUER: ${ARKHAM_OIDC_ISSUER:-}
      ARKHAM_OIDC_CLIENT_ID: ${ARKHAM_OIDC_CLIENT_ID:-}
      ARKHAM_OIDC_CLIENT_SECRET: ${ARKHAM_OIDC_CLIENT_SECRET:-}
      ARKHAM_OIDC_SCOPES: ${ARKHAM_OIDC_SCOPES:-openid profile email groups}
      ARKHAM_OIDC_ADMIN_GROUP: ${ARKHAM_OIDC_ADMIN_GROUP:-arkham-admin}
      ARKHAM_OIDC_MODERATOR_GROUP: ${ARKHAM_OIDC_MODERATOR_GROUP:-arkham-moderator}
      ARKHAM_ERROR_DSN: ${ARKHAM_ERROR_DSN:-}
      ARKHAM_TRACES_SAMPLE_RATE: ${ARKHAM_TRACES_SAMPLE_RATE:-0.1}
      ARKHAM_ENVIRONMENT: ${ARKHAM_ENVIRONMENT:-production}
      ARKHAM_RELEASE: ${ARKHAM_RELEASE:-}
    volumes:
      - <data>:/srv/arkham/data
    networks:
      - hunt

networks:
  hunt:
    ipam:
      config:
        - subnet: 172.30.0.0/24
          gateway: 172.30.0.1
```

Pick a free loopback port and a subnet no other network on the host uses,
and change `--forwarded-allow-ips` to match the gateway. `.env` holds
the variables ([CONFIGURATION.md](CONFIGURATION.md)). Single-quote the
password hash and any group name with a space in it.

Build and start, and set `ARKHAM_RELEASE` to the commit on each deploy,
so the admin console, the readiness probe and error reports name the
build:

```sh
sed -i "s/^ARKHAM_RELEASE=.*/ARKHAM_RELEASE=$(git -C <checkout> rev-parse --short HEAD)/" .env
docker compose build && docker compose up -d
docker compose ps                        # Up … (healthy)
curl -s http://127.0.0.1:8456/api/health # {"status":"ok","schema_version":N}
```

The `sed` edits an existing `ARKHAM_RELEASE=` line, so add one to `.env`
the first time.

### The proxy

Start from `deploy/nginx.conf`, pointed at `127.0.0.1:8456`. What
matters, and why:

- **`proxy_buffering off` on `/api/events/stream`**, with a read timeout
  above the app's 15-second heartbeat. Without it the queue and the
  players' tiles stop updating live.
- **`X-Forwarded-Proto https`**, so the app builds `https://` links and
  its SSO callback.
- **`X-Forwarded-For`**, for the rate limiter. The reference deployment
  sets it to `$remote_addr` rather than appending, because nginx is the
  edge and nothing a client sends in that header should reach the app.
- **`client_max_body_size 16m`**, above the app's 15 MB cap, so an
  oversized photo gets the app's own error instead of nginx's HTML page.
- **The security headers and CSP.** The app sends none of its own. Put
  your GlitchTip origin in `connect-src` if you report browser errors.

Check what the app derives, through the proxy's headers, without a
browser. The `redirect_uri` in the answer must match the one registered
with your identity provider exactly:

```sh
curl -s -o /dev/null -w '%{redirect_url}\n' -H 'Host: <your host>' \
  -H 'X-Forwarded-Proto: https' http://127.0.0.1:8456/api/auth/oidc/login
```

A request that skips the proxy still gets an `http://` callback, which is
the trust list doing its job.

### Running it

| Task | Command |
| --- | --- |
| Apply a changed `.env` | `docker compose up -d` |
| Apply a changed `VITE_*`, or a new commit | `docker compose build && docker compose up -d` |
| State and health | `docker compose ps` |
| Logs | `docker logs -f --since 10m arkham-hunt` |
| What the container really got | `docker exec arkham-hunt printenv NAME` |
| A shell inside it | `docker exec -it arkham-hunt sh` |
| Back up and restore | §4, "With a bind mount" |

[OPERATIONS.md](OPERATIONS.md) covers upgrades, restarts and credential
rotation for every recipe.

## Gotchas verified on the first pass

- **Port already in use**: if `podman run` fails with
  `rootlessport ... bind: address already in use`, another service owns
  the port (dev servers love 8000/8080) — pick another host port.
- **`podman restart` fails to bind its own port** (podman 5 with the
  `pasta` network): `Failed to bind port ... (Address already in use)`,
  and the container stays down. `podman stop arkham-hunt && podman start
  arkham-hunt` works.
- **Healthcheck missing**: you built without `--format docker`. The app
  runs fine; you just lose `podman inspect`'s health status.
- **Logins bounce**: missing `ARKHAM_COOKIE_SECURE=false` (see §1).
- **SELinux hosts** (Fedora/RHEL rootless podman) with a *bind mount*
  instead of a named volume: append `:Z` (`-v /path/data:/srv/arkham/data:Z`).
  Named volumes need no label.
- **Compose override files don't replace ports**: the classic
  list-merge semantics APPEND a ports mapping from an override file
  instead of replacing the base one — the container then still tries
  the base file's port. Change the port by editing `compose.yml`,
  never by override.
