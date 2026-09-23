# Pre-party runbook

One page. Run it **once, start to finish, on the real host** before the
event (build-plan.md §10: the night itself is not the time to discover
the deploy recipe missed a step). Everything below assumes the checkout
is at `~/arkham` and the service is `arkham-hunt`.

## 0. Deploy (first time, or after pulling changes)

```sh
cd ~/arkham
git pull
# Backend deps (once, or when server/pyproject.toml changes):
uv venv server/.venv && uv pip install -p server/.venv -e "server[dev]"
# Frontend build (web/dist is what uvicorn serves in production):
cd web && npm install && npm run build && cd ..
systemctl --user restart arkham-hunt
systemctl --user status arkham-hunt   # active (running)
curl -s https://<host>/api/health     # {"status":"ok",...}
```

## 1. Backup, and prove the restore

A backup you have never restored is a rumor, not a backup.

Point the script at a second disk first — an archive beside the data is not a
backup. Export these (or put them in `~/.config/arkham-hunt.env`):

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

1. Open `https://<host>/` in a browser — the admin console is behind
   the login (credentials from `~/.config/arkham-hunt.env`).
2. Create the event; choose `live` or `final-reveal` standings.
3. Add the 12–15 riddles in `sort_order` order.
4. Print two QR codes — the **join link** (`https://<host>/j/<code>`)
   for players and the **mod link** (`https://<host>/m/<code>`) for
   moderators. The codes appear only in the create response.
5. Check free disk before opening: `df -h ~/arkham/data` and
   `du -sh ~/arkham/data/photos/originals`. Uploads refuse below 256 MiB
   free (`ARKHAM_MIN_FREE_BYTES` to change the floor, ADR 0023), and a
   full disk breaks SQLite writes too — so clear space now, not
   mid-round.
6. Press **open** only when players are physically present.

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

## 5. After the night

- `deploy/backup.sh` once more (the archive of the night).
- Show the recap screen on a TV / share the final standings.
- When the photos have served their purpose: purge the event from the
  admin console (`POST /api/admin/events/{id}/purge`, confirm = event
  name). Purging deletes the DB rows AND the photos — including
  quarantined originals — per the conduct rules (retained only until
  the event ends).

## Failure cheatsheet

| Symptom | Check |
| --- | --- |
| Queue/tiles don't update live | `proxy_buffering off` on the SSE location; `curl -N https://<host>/api/events/stream` should stream heartbeats |
| Players can't upload big photos | nginx `client_max_body_size 16m` sits above the app's 15 MB cap, so the app owns the 413 |
| Uploads answer 507 `storage_full` | `df -h` the data dir; free space, or set `ARKHAM_MIN_FREE_BYTES` to the floor you actually want, then restart |
| 502 after reboot | `loginctl enable-linger "$USER"`; `systemctl --user status arkham-hunt` |
| App up, site blank | `web/dist` exists and was rebuilt after the last `git pull` |
| Nothing in GlitchTip | `ARKHAM_ERROR_DSN` / `VITE_ERROR_DSN` are set and the app was restarted/rebuilt; the CSP `connect-src` includes the GlitchTip origin |

## Error reporting (GlitchTip)

Both halves of the app report to the self-hosted GlitchTip. Reporting is
opt-in: with no DSN the SDKs stay inert, so a developer checkout and the
test suite send nothing.

Put the DSNs in `~/.config/arkham-hunt.env` (the browser DSN also needs to
be in the build environment). They are ingest keys rather than hard secrets —
the browser one ships in the bundle — but anyone holding one can post events
to the project, so keep them out of the repo.

```sh
export ARKHAM_ERROR_DSN=https://<key>@glitchtip.nulloctet.com/<project>
export ARKHAM_TRACES_SAMPLE_RATE=0.1   # optional; 0 disables tracing
export ARKHAM_ENVIRONMENT=production   # optional
export ARKHAM_RELEASE=$(git -C ~/arkham rev-parse HEAD)  # optional
```

The browser DSN is compiled into the bundle, so it is a **build** input —
set it before `npm run build` (or pass it as a build arg to the container):

```sh
cd ~/arkham/web
VITE_ERROR_DSN=https://<key>@glitchtip.nulloctet.com/<project> \
VITE_TRACES_SAMPLE_RATE=0.1 npm run build
```

Check it works: open the site and watch for a request in GlitchTip's Issues. A
backend 500 — or any unhandled server error — arrives with a `request_id` tag
that matches the `X-Request-ID` header and the request log line.

