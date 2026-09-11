# Testing commands

The fast checks stay separate from the browser and container smoke gates.
The shared local and CI command is:

```sh
bash scripts/check-quality.sh
```

`check-quality.sh` installs the locked Python environment with `uv sync
--locked`, installs the npm lockfile with `npm ci`, then runs the server,
deployment, frontend unit, and production-build checks. The Forgejo workflow
at `.forgejo/workflows/quality.yml` invokes this same script on pull requests
and pushes to `main`. The upstream GitHub mirror keeps
only a manual pointer workflow and does not run the quality gate.

To run only the deployment checks, use:

```sh
bash scripts/check-deploy.sh
```

`check-deploy.sh` runs shell syntax checks and an isolated backup/restore test.
The test creates a temporary SQLite database and photo tree, invokes
`deploy/backup.sh` through Python's SQLite backup API without a `sqlite3` CLI,
then restores into a separate directory and checks the schema version,
representative row, foreign-key enforcement, and photo bytes. It does not read
or write `data/`, `backups/`, production credentials, or uploaded photos.

Run the server quality gate alone with `bash scripts/check-server.sh`. Run the
frontend unit suite alone with `npm --prefix web test`.

The browser smoke builds the PWA, starts a temporary FastAPI instance with a
throwaway SQLite database and photo directory, then runs Playwright headlessly:

```sh
npm ci --prefix web
npm --prefix web exec -- playwright install chromium
npm --prefix web run test:e2e
```

`test:e2e` uses the built `web/dist` path served by uvicorn. It does not use the
Vite development server, production credentials, or repository data. The test
creates its event through the admin API and uploads a synthetic in-memory PNG.
Playwright keeps traces, screenshots, and videos for failures under
`web/.playwright-results/`; that directory is ignored and must not be committed.

Pass Playwright options after `--`, for example:

```sh
npm --prefix web run test:e2e -- --workers=1
```

Regenerate the tracked README product screenshots with the dedicated capture
spec:

```sh
npm --prefix web run screenshots
```

The spec uses the same temporary server and built PWA as the browser smoke,
seeds deterministic event data, and writes `join.png`, `riddle-board.png`,
`evidence-drawer.png`, `moderator-console.png`, and `standings.png` under
`docs/screenshots/`. Review those files as documentation assets before
committing them. Set `README_SCREENSHOT_DIR` to write a review copy elsewhere.
The fixture photo is generated in the spec and contains no player data.

The Podman deployment smoke is intentionally opt-in because it builds the full
image and needs host container networking:

```sh
bash scripts/smoke-container.sh
```

It uses unique disposable image, container, and volume names. The smoke checks
health, admin login, event and riddle setup, event open, plain-HTTP player join
with `ARKHAM_COOKIE_SECURE=false`, a synthetic photo upload, and an SSE
heartbeat. Success removes the container, volume, image, generated photos,
credentials, and temporary files. Failure removes those runtime resources but
keeps container logs, inspect output, and the command transcript under the
ignored `.deploy-smoke-results/` directory. The container gate is not part of
`check-server.sh` or `check-deploy.sh`; run it explicitly when Podman is
available.
