---
schema: 3
id: TKT-01M3816ETRMEH0K7QARH78BR9Z
title: Container uvicorn ignores proxy headers behind a reverse proxy
type: bug
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - deployment
  - backend
  - security
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-23T21:01:56Z
updated_at: 2026-09-23T21:01:56Z
created_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

### The gap

The `Containerfile` starts uvicorn without `--proxy-headers`:

```dockerfile
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
```

Any deploy that runs the container behind a reverse proxy then has two faults, both
invisible until someone exercises them:

- **One shared rate-limit bucket.** uvicorn ignores `X-Forwarded-For`, so the app
  sees the proxy/docker gateway as the client for every request. `app/ratelimit.py`
  (ADR 0015) keys on that one address, so one noisy player throttles the party.
- **OIDC callback built as `http://`.** `server/app/oidc.py` derives the callback
  from `request.base_url` when `ARKHAM_OIDC_REDIRECT_URI` is unset. Without proxy
  headers that base URL is `http://<gateway>/...`, which Authentik's strict
  redirect matching rejects.

### Evidence from kobal

The kobal deploy (`scavenger.nulloctet.com`, container path) works around both in its
own `compose.yml` by overriding `command` to add
`--proxy-headers --forwarded-allow-ips=172.30.0.1`, with the docker subnet pinned so
the trust list is a fixed address. Verified there 2026-09-23: through the proxy the
app derives `https://scavenger.nulloctet.com/api/auth/oidc/callback`; a direct request
still sees `http://`.

### Options

1. Add `--proxy-headers --forwarded-allow-ips=...` to the `Containerfile` CMD. The
   trust list cannot hard-code a docker subnet for every deploy, so this needs a
   documented default (e.g. trust all proxies is wrong; a `127.0.0.1`-only default
   matches the LAN recipe but not a sidecar proxy).
2. Leave the CMD plain and document the override in `deploy/CONTAINER.md` §2 with a
   worked example, so the proxy deploy is a documented recipe rather than folklore.
3. Both: a sane default plus the documented override.

Prefer (3): the LAN path keeps working, and a proxy deploy does not have to discover
this by watching logins fail.

### Docs to correct

`deploy/CONTAINER.md` currently presents the container as "no reverse proxy" and does
not mention proxy headers at all; a proxy-fronted container is a supported-looking
case it silently gets wrong. `deploy/arkham-hunt.service` already carries the flags
for the systemd path, so the two paths have converged on the same need without the
container path stating it.
