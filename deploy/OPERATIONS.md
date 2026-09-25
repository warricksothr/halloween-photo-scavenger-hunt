# Operating a deployment

Day-two work for a running deployment, whichever recipe it uses:
upgrading, restarting, reading the logs, backing up, and replacing
credentials. For setting one up, see [README.md](README.md). For the
night itself, see [RUNBOOK.md](RUNBOOK.md).

Commands are shown for a container deploy with docker compose. The
equivalents:

| Container (docker or podman) | systemd |
| --- | --- |
| `docker compose up -d` | `systemctl --user restart arkham-hunt` |
| `docker compose build && docker compose up -d` | `cd web && npm ci && npm run build`, then restart |
| `docker logs arkham-hunt` | `journalctl --user -u arkham-hunt` |
| `docker compose ps` | `systemctl --user status arkham-hunt` |

## What is running, and is it well

Three places say which build is live and whether it is healthy.

- **`/api/health`**, open to anyone: `{"status":"ok","schema_version":N}`.
  The container's health check calls it. `schema_version` is the newest
  migration applied to the database.
- **`/api/admin/readyz`**, host only. It adds whether the database takes
  writes (`db_writable`), free and total disk (`disk`), `photo_count`,
  live stream clients (`sse_subscribers`), lock, upload and verdict counters
  (`metrics`), `release`, and `uptime_seconds`. Read it when health is
  green and the game still feels wrong. From a script, use the API token:

  ```sh
  curl -s -H "Authorization: Bearer $ARKHAM_ADMIN_API_TOKEN" \
    https://<host>/api/admin/readyz
  ```

- **The admin console's footer** shows the page's build, the server's
  build and the schema version. When the server is newer than the open
  page, it says so and offers a reload. Players see the page's build on
  the join and team screens, and moderators in the console's side rail,
  which helps when someone reports a problem from a phone.

`release` comes from `ARKHAM_RELEASE`, and the page's build from
`VITE_ERROR_RELEASE`. They read `unknown` and `dev` unless you set them on each deploy
([CONFIGURATION.md](CONFIGURATION.md)).

## Logs

The server writes one JSON line per request to standard output:

```json
{"ts": "2026-09-25T15:03:54+0000", "level": "INFO", "logger": "arkham.request", "event": "request", "request_id": "e8177f1a2a2b07db", "method": "GET", "path": "/api/state", "status": 200, "duration_ms": 2.72}
```

- **Codes never reach the log.** Join, moderator and invite codes in a
  path are replaced with `<redacted>` before the line is written
  (ADR 0016), so logs are safe to share.
- **`request_id` is the join key.** Every response carries it in the
  `X-Request-ID` header, an unhandled error logs its traceback under the
  same id, and the error report in GlitchTip is tagged with it. Given the
  id from any one of them, find the rest:

  ```sh
  docker logs arkham-hunt 2>&1 | grep e8177f1a2a2b07db
  ```

- Nothing is written to files, and the app does not rotate anything.
  Docker and journald keep and rotate stdout under their own settings.

## What a restart does

A restart takes a few seconds. Checked by restarting a running container
with a signed-in host and a joined player:

- **The host is signed out.** Host sign-ins, by password or SSO, live in
  the process's memory, and the admin console asks for a sign-in again.
- **Players and moderators carry on.** Their sessions are in the
  database. Their phones' live connection drops, reconnects by itself, and
  refetches the whole game state.
- **Anything in flight fails once.** An upload or verdict sent during the
  restart gets an error, and sending it again works.
- **Rate-limit counters reset,** and each browser picks up a new CSRF
  token on its next request without anyone noticing.

So a restart is safe during a round, but avoid one if you can: the host
has to sign in again, and a moderator mid-verdict has to press the button
twice.

## Upgrade

A new build can add migrations. The server applies them when it starts,
each in one transaction (ADR 0022), and there is no downgrade: an older
build cannot use a database a newer one has migrated. So every upgrade
starts with a backup, and happens outside a round if you can manage it.

1. **See what is coming.** New migrations are the part you cannot undo:

   ```sh
   git -C <checkout> fetch
   git -C <checkout> diff --stat HEAD origin/main -- server/app/migrations
   ```

2. **Back up**, and keep that archive until the new build has been used
   for real: CONTAINER.md §4 (container) or RUNBOOK.md §1 (systemd).
3. **Pull, rebuild and restart**, with the release set to the new commit:
   CONTAINER.md §7 or RUNBOOK.md §0.
4. **Check it.** `/api/health` answers, with the new `schema_version` if
   the build added a migration, and the admin footer names the new
   release for both web and server once you reload.

Phones pick up the new web build the next time they load a page: the
service worker fetches from the network first and only falls back to its
cache when the network is gone. A page left open keeps its old code until
it is reloaded. The admin console flags that for the host, and for
everyone else the next navigation fixes it.

## Roll back

Because migrations only go forward, rolling back is a restore:

1. Stop the app.
2. Restore the archive you took before the upgrade (CONTAINER.md §4 or
   RUNBOOK.md §1). Anything that happened since the upgrade is lost.
3. Check out the commit you were on before (`git -C <checkout> checkout
   <commit>`), rebuild, and start.
4. Check `/api/health` shows the old `schema_version`.

When the new build added no migration, the database needs no restore:
check out the old commit, rebuild, and start. Remember to move the
checkout back to `main` before the next upgrade, or `git pull` has
nothing to pull onto.

## Back up

`deploy/backup.sh` takes an online snapshot of the database and copies
the photos. It is safe to run during a round. It writes a timestamped
archive, copies it to `ARKHAM_BACKUP_MIRROR` on another disk, and keeps
the newest `ARKHAM_BACKUP_KEEP` in each place. Where to run it from, and
as whom, depends on the recipe: RUNBOOK.md §1 for systemd, CONTAINER.md §4
for containers.

Nothing schedules it. At the least, take one before each upgrade, one at
a break in the party, and one when it ends. A backup you have never
restored is a rumor, so restore one into a scratch location before the
night that matters (RUNBOOK.md §1).

## Rotate a credential or a code

| What | How | What happens to people already in |
| --- | --- | --- |
| Host password | New hash into the env file ([CONFIGURATION.md](CONFIGURATION.md#the-admin-password)), then restart | Every host is signed out by the restart |
| Admin API token | New value in the env file, then restart | The old token stops working at once |
| SSO client secret | Rotate it at the identity provider, put the new one in the env file, then restart | Hosts sign in again. Moderators already in the console stay |
| Error-reporting DSN | Server: env file and restart. Browser: build again | None |
| An event's join code | Admin console, the event's **Links & QR**, **New join code** | Players already in stay. The old QR stops working, so print the new one |
| An event's moderator code | The same, **New moderator code** | Moderators already in stay |
| One player on a team | Moderator console, the player's team, remove them | Every session they hold is revoked, and they are parked on an empty team of their own (ADR 0006). Their photos stay with the team they left |

A code replacement is immediate and needs no restart (ADR 0039).
Removing a player does not stop them joining again with the join code. To
keep someone out, remove them and then replace the join code.

## Events over time

- **Close** ends the round: waiting scans expire, final standings appear,
  and the recap opens. **Reopen the round** undoes a close you did not
  mean (ADR 0042). Neither deletes anything.
- **Purge** deletes an event's rows and every photo it holds, quarantined
  originals included. It cannot be undone. The admin console asks you to
  type the event's name to confirm. Back up first if you want to keep an
  archive of the night.
- **Purged photos live on in backups** taken before the purge, until
  retention prunes those archives. If a photo has to be gone for good,
  delete the archives that hold it, on the mirror too.
- **Disk:** photos are what grows. Watch `disk` in the readiness probe.
  Uploads refuse with `507 storage_full` below `ARKHAM_MIN_FREE_BYTES`,
  so the server never fills the disk its database needs.

## What the server keeps about people

Players have no accounts: a codename and team name, the device label
their browser reports, their photos, their submissions and verdicts, and
any strikes. Moderators are stored with the name and subject their
identity provider sent. Hosts are not stored at all. Every action lands
in an append-only audit log (ADR 0004), which is what the moderator
console's **Log** reads. Purging an event removes all of it for that
event, the audit log included.
