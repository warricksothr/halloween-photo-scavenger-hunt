# Container runbook — local podman or docker

One page. This is the **local / LAN-party** deployment: one container
holds the whole app (web build + FastAPI server + SQLite), with no
nginx and no TLS. For the TLS-terminated VPS path, see
`deploy/RUNBOOK.md` (systemd + nginx) instead.

Every command below was run and verified against the image built from
the repo `Containerfile` (podman 4.9). `docker` is a drop-in
replacement — swap the word `podman` for `docker` throughout; the
`Containerfile` is valid syntax for both.

## When to use this vs. the systemd path

|                        | Container (this doc)              | systemd + nginx (RUNBOOK.md)        |
| ---------------------- | --------------------------------- | ----------------------------------- |
| TLS / public hostname  | no — plain HTTP on a LAN port     | yes — nginx terminates TLS          |
| Host needs Python/Node | no — both live in the image       | yes                                 |
| Best for               | party-night on a laptop/LAN, evals | the standing VPS deployment         |

## 0. Build the image

```sh
# --format docker keeps the HEALTHCHECK: podman's default OCI format
# silently drops it, and docker-built images carry it natively.
podman build --format docker -t arkham-hunt:local .
podman image inspect arkham-hunt:local \
  --format '{{.Config.Healthcheck.Test}}'   # must print a CMD-SHELL line
```

The build is multi-stage: stage 1 runs `npm ci && npm run build` in
`node:20-alpine`, stage 2 is `python:3.12-slim` with the server
installed editable and `web/dist` copied in. The editable install is
load-bearing: `main.py` derives the DB and static paths from the
package's `__file__`, so the image keeps the repo layout and the
runtime data dir lands at `/srv/arkham/data` — the one path a volume
must cover.

## 1. First run

```sh
# Generate the admin password hash once (any checkout with the server
# venv works; or `podman run --rm --entrypoint python arkham-hunt:local
# -m app.security 'your-password'`):
server/.venv/bin/python -m app.security 'your-password'

podman volume create arkham-data
podman run -d --name arkham-hunt \
  -p 127.0.0.1:8080:8000 \
  -e ARKHAM_ADMIN_USERNAME=admin \
  -e ARKHAM_ADMIN_PASSWORD_HASH='<hash from above>' \
  -e ARKHAM_COOKIE_SECURE=false \
  -v arkham-data:/srv/arkham/data \
  arkham-hunt:local
```

The three environment variables, and why:

- `ARKHAM_ADMIN_USERNAME` / `ARKHAM_ADMIN_PASSWORD_HASH` — required;
  the app refuses to start without them.
- `ARKHAM_COOKIE_SECURE=false` — **required for this recipe.** The app
  sets `Secure` cookies by default; browsers refuse to send those over
  plain HTTP, and without the toggle every login silently 401s. Do not
  set this on the TLS path — production keeps the default.

`-p 127.0.0.1:8080:8000` binds loopback only. For a LAN party (players
on phones on the same network), publish on all interfaces and give the
room the host's LAN address: `-p 8080:8000`.

## 2. Prove it works (30 seconds)

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

## 3. Backup / restore

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

## 4. Update to a new build

```sh
git pull
podman build --format docker -t arkham-hunt:local .
podman stop arkham-hunt && podman rm arkham-hunt
# same run command as §1 — the volume carries the state forward
```

## 5. Teardown

```sh
podman rm -f arkham-hunt
podman volume rm arkham-data      # only when the night's data is done
podman rmi arkham-hunt:local
```

## Gotchas verified on the first pass

- **Port already in use**: if `podman run` fails with
  `rootlessport ... bind: address already in use`, another service owns
  the port (dev servers love 8000/8080) — pick another host port.
- **Healthcheck missing**: you built without `--format docker`. The app
  runs fine; you just lose `podman inspect`'s health status.
- **Logins bounce**: missing `ARKHAM_COOKIE_SECURE=false` (see §1).
- **SELinux hosts** (Fedora/RHEL rootless podman) with a *bind mount*
  instead of a named volume: append `:Z` (`-v /path/data:/srv/arkham/data:Z`).
  Named volumes need no label.
