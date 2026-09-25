# Configuration reference

Every setting the app reads, in one place. The server reads its variables
once, when the process starts, so a change takes a restart. The web app's
`VITE_*` variables are compiled into the bundle, so a change takes a
rebuild. Nothing is read from a config file of the app's own: the
environment is the whole interface.

The recipes put these in different places:

| Recipe | Where the variables go | Apply a change with |
| --- | --- | --- |
| LAN container ([CONTAINER.md](CONTAINER.md) §1) | `.env` beside `compose.yml` | `podman-compose up -d` |
| Container behind a proxy (CONTAINER.md §7) | `.env` beside your own compose file | `docker compose up -d`, or `docker compose build && docker compose up -d` for `VITE_*` |
| systemd ([RUNBOOK.md](RUNBOOK.md)) | `~/.config/arkham-hunt.env` | `systemctl --user restart arkham-hunt`, or `npm run build` first for `VITE_*` |

## Server: required

| Variable | What it is |
| --- | --- |
| `ARKHAM_ADMIN_USERNAME` | The host's username for the password sign-in. |
| `ARKHAM_ADMIN_PASSWORD_HASH` | An argon2id hash of the host's password (see [below](#the-admin-password)). The plaintext is never stored. |

Without both, the process refuses to start rather than run a party
nobody can open. The password sign-in stays available when SSO is on. It
is the way back in if your identity provider is down.

## Server: optional

| Variable | Default | What it does |
| --- | --- | --- |
| `ARKHAM_COOKIE_SECURE` | on | `false`, `0` or `no` turns off the `Secure` flag on cookies. **Only for plain HTTP** (the LAN container). Behind TLS, leave it unset: turning it off lets a session cookie travel in the clear. |
| `ARKHAM_SESSION_TTL_SECONDS` | `43200` (12 hours) | How long any session lasts: player, moderator and host. Raise it for an all-day event. A value that is not a positive whole number falls back to the default. |
| `ARKHAM_MIN_FREE_BYTES` | `268435456` (256 MiB) | Uploads answer `507 storage_full` when writing one would leave less than this free, on the data volume or on the upload spool (`/tmp`). A value that is not a positive whole number falls back to the default. |
| `ARKHAM_ADMIN_API_TOKEN` | off | A standing credential for scripts, sent as `Authorization: Bearer <token>`. The demo seeder uses it. It does not expire, so treat it like the password. Generate one with `openssl rand -hex 32`. |
| `ARKHAM_RELEASE` | `unknown` | The build's name, usually the commit it was built from. It shows in the admin console's footer and in `/api/admin/readyz`, and tags error reports. The console compares it with the page's own `VITE_ERROR_RELEASE` and warns when they differ, so an open tab from before a deploy asks to be reloaded. **Set both to the same value, or neither**: with only this one set, the warning never clears. |
| `ARKHAM_CSRF_SECRET` | random per process | The key that signs CSRF tokens. Leave it unset: a restart then just has each browser pick up a new token on its next request. It exists for a multi-process run, which this app does not support. |

### Single sign-on (OIDC)

SSO is on only when the first three are all set. With any one missing the
app starts with SSO off. The admin sign-in page still shows its **Sign in
with Authentik** button, which then answers `503 oidc_disabled`, and the
password form below it works as before.
[RUNBOOK.md §6](RUNBOOK.md#6-single-sign-on-oidc-via-authentik) covers
setting up the provider.

| Variable | Default | What it does |
| --- | --- | --- |
| `ARKHAM_OIDC_ISSUER` | | The provider's issuer URL, exactly as its discovery document states it, trailing slash included. |
| `ARKHAM_OIDC_CLIENT_ID` | | The client ID. |
| `ARKHAM_OIDC_CLIENT_SECRET` | | The client secret. A secret. |
| `ARKHAM_OIDC_SCOPES` | `openid profile email` | The scopes to request. Add the scope that carries the `groups` claim. On Authentik that is `groups`, and without it every sign-in is refused as `not_authorized`. |
| `ARKHAM_OIDC_ADMIN_GROUP` | `arkham-admin` | The group whose members are hosts. It must match a name in the `groups` claim exactly, including case and spaces. |
| `ARKHAM_OIDC_MODERATOR_GROUP` | `arkham-moderator` | The group whose members may moderate. Same matching rule. |
| `ARKHAM_OIDC_REDIRECT_URI` | derived | The callback URL. Normally the app derives `https://<host>/api/auth/oidc/callback` from the request. Behind a proxy that only works if the proxy headers are trusted (CONTAINER.md §7). Set this if the derived URL is wrong. |

### Error reporting (GlitchTip or Sentry)

With no DSN, error reporting is off and nothing leaves the host.

| Variable | Default | What it does |
| --- | --- | --- |
| `ARKHAM_ERROR_DSN` | off | The server project's DSN. An ingest key rather than a password, but anyone holding it can post to your project, so keep it out of the repository. |
| `ARKHAM_TRACES_SAMPLE_RATE` | `0.1` | The share of requests traced, from 0 to 1. `0` turns tracing off. A value outside that range falls back to the default. |
| `ARKHAM_ENVIRONMENT` | none | A tag on every report, such as `production`. |

`ARKHAM_RELEASE` (above) also tags each report.

## Web build: compiled in

Vite inlines these when it builds `web/dist`, so they are build inputs: a
build argument on the container recipes, and an environment variable for
`npm run build` on the systemd recipe. Changing one without rebuilding
changes nothing. Every one is optional.

| Variable | Default | What it does |
| --- | --- | --- |
| `VITE_ERROR_DSN` | off | The browser project's DSN. It ships inside the JavaScript, so it is public by design. Allow its origin in the CSP's `connect-src` (`deploy/nginx.conf`), or the browser blocks the reports. |
| `VITE_TRACES_SAMPLE_RATE` | `0.1` | As on the server. |
| `VITE_ERROR_ENVIRONMENT` | none | As `ARKHAM_ENVIRONMENT`. |
| `VITE_ERROR_RELEASE` | `dev` in the app | The build tag the app shows on its join, team and moderator screens, and sends with reports. Set it to the same value as `ARKHAM_RELEASE`. |

## Backup script

`deploy/backup.sh` reads these. The app itself does not.

| Variable | Default | What it does |
| --- | --- | --- |
| `ARKHAM_DATA_DIR` | `data/` in the checkout | The data directory to back up. Set it when the data is somewhere else, such as a container's bind mount. |
| `ARKHAM_BACKUP_MIRROR` | none | A directory on another disk. Each archive is copied there too. The script warns when it is unset or on the same disk as the data, and fails when it is not a directory (an unmounted mount point). |
| `ARKHAM_BACKUP_KEEP` | `14` | How many archives to keep in each directory. |

## The admin password

The server stores only an argon2id hash. Generate one on the host, and
keep the password itself in a password manager.

`python -m app.security 'password'` also prints a hash. It takes the
password as an argument, though, which leaves it in your shell history and
visible in `ps`. Read it from the terminal instead:

```sh
# From a checkout with the server environment installed:
read -rsp 'Admin password: ' PW; echo
HASH=$(printf '%s' "$PW" | server/.venv/bin/python -c \
  'import sys; from app.security import hash_password; print(hash_password(sys.stdin.read()))')
unset PW

# Or with the image, so the host needs no Python:
read -rsp 'Admin password: ' PW; echo
HASH=$(printf '%s' "$PW" | podman run --rm -i --entrypoint python arkham-hunt:local -c \
  'import sys; from app.security import hash_password; print(hash_password(sys.stdin.read()))')
unset PW
```

`printf '%s'` sends the password without a trailing newline, which
would otherwise become part of it. The hash begins `$argon2id$`, and
every `$` in it matters, so writing it to a file needs care, which the
next section covers.

To change the password later, generate a new hash, replace the line, and
restart. The restart signs out every host, since host sign-ins live in the
process's memory. Players and moderators stay signed in.

## Env file formats

The recipes read two different formats, and the hash breaks each one in a
different way.

**Compose `.env`** (both container recipes). Compose expands `$NAME` in
unquoted and double-quoted values, so an unquoted hash arrives mangled
and every sign-in fails. **Single-quote the hash.** Writing the line with
`printf`, rather than a heredoc or `echo`, keeps your shell from expanding
it first:

```sh
printf "ARKHAM_ADMIN_PASSWORD_HASH='%s'\n" "$HASH" >> .env
chmod 600 .env
```

`docker compose config` displays each `$` as `$$`. That is how it prints
them, not the stored value. To see what the container got, run
`docker exec arkham-hunt printenv ARKHAM_ADMIN_PASSWORD_HASH`. Values with
spaces, such as a group named `Hunt Moderators`, need single quotes too.

**systemd `EnvironmentFile`** (`~/.config/arkham-hunt.env`). systemd
does not expand `$`, so the hash goes in bare. Write every line as
`NAME=value`. A line starting with `export` is skipped without an error,
which is how SSO ends up off with nothing in the logs. Keep the file
`chmod 600`.

## Which values are secrets

Keep these out of the repository, out of tickets, and out of chat:
`ARKHAM_ADMIN_PASSWORD_HASH`, `ARKHAM_ADMIN_API_TOKEN`,
`ARKHAM_OIDC_CLIENT_SECRET`, and `ARKHAM_CSRF_SECRET` if you set it. The
DSNs are ingest keys and the browser one is public, but the server one
still belongs in the env file. The event's join and moderator codes live
in the database rather than the environment. [OPERATIONS.md](OPERATIONS.md#rotate-a-credential-or-a-code)
covers replacing each one.
