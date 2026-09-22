---
schema: 3
id: TKT-01M33S9CTBFJTSEKX6QDA6N7P0
title: Add OIDC authorization-code login for admins and moderators
type: task
status: in-progress
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - security
assignees: []
milestone: null
parent: TKT-01M33S9CSC6V3VH43J76X43ZC1
origin: null
dependencies: []
blocks_on: none
references: []
claim:
  actor: agent:opencode/oidc-login
  branch: t3code/oidc-login
  worktree: /home/sothr/.t3/worktrees/arkham-halloween-photo-scavenger-hunt/t3code-oidc-login
  commit: aba5c9fe589bc8ead0328f5957e9dc9cb5013cea
  session: null
  claimed_at: 2026-09-22T21:44:10Z
  expires_at: null
archive: null
created_at: 2026-09-22T05:26:46Z
updated_at: 2026-09-22T21:53:13Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/oidc-login
  name: ""
extensions: {}
---

## Description

Admin auth is a single offline argon2id hash (server/app/security.py) and moderator auth is an anonymous per-event mod link (server/app/mod.py:42). Add an authorization-code + PKCE flow against the Authentik issuer using authlib: a start route that redirects with state, nonce, and PKCE, and a callback that validates the id_token against JWKS (issuer, audience, expiry, nonce, signature), maps the groups claim to a role from env-configured group names, and mints the existing admin or moderator cookie session. Discard the OIDC tokens: no storage, no refresh. Keep the local password login as break-glass.

## Acceptance criteria

- [ ] GET /api/auth/oidc/login redirects to Authentik with state, nonce, and PKCE; the verifier lives in a short-lived SameSite=Lax cookie (the callback is a cross-site top-level navigation, so the existing Strict cookie would be dropped).
- [ ] The callback validates state, nonce, issuer, audience, expiry, and signature before minting any session; failures return 401 without a session cookie.
- [ ] Admin and moderator group names come from env (ARKHAM_OIDC_*), not hard-coded; a user in neither group is refused with a clear error.
- [ ] OIDC tokens, authorization codes, and the client secret never appear in logs, audit rows, or URLs after the callback.
- [ ] The argon2 password login still works when OIDC is unset, and the app starts with OIDC unconfigured.

## Implementation plan

### Scope and boundaries

S9CT owns the OIDC authorization-code + PKCE flow and the sessions it mints. It does **not** gate the mod link (S9CW), build the console (S9CX), or ship the stub-provider end-to-end suite (S9CV). The password login stays untouched as break-glass.

The moderator fork: S9CW keeps `mod_code` as the event selector and requires an OIDC moderator session *before* `POST /api/mod/join/{mod_code}` mints a moderator row. A `moderator_session` row needs an event, which the OIDC callback does not have, so S9CT mints an OIDC **identity** session instead: a new `arkham_oidc` cookie backed by an in-memory `app.state.oidc_identities` map (sub, name, email, role), exactly as `admin_sessions` is in-memory. S9CW consumes it through a `require_oidc_moderator` dependency. Admins get the existing `arkham_admin` session.

### Config

New `server/app/oidc.py`, `OidcConfig.from_env()`: `ARKHAM_OIDC_ISSUER`, `ARKHAM_OIDC_CLIENT_ID`, `ARKHAM_OIDC_CLIENT_SECRET`, optional `ARKHAM_OIDC_REDIRECT_URI`, `ARKHAM_OIDC_ADMIN_GROUP` (default `arkham-admin`), `ARKHAM_OIDC_MODERATOR_GROUP` (default `arkham-moderator`), `ARKHAM_OIDC_SCOPES` (default `openid profile email`). Enabled only when issuer + client id + client secret are all set. `create_app` gains `oidc_config` and `oidc_transport` (test injection); the default reads the env, and unset means disabled.

### Routes (`app/oidc.py`, prefix `/api/auth/oidc`)

- `GET /login`: 503 when disabled. Otherwise build the authorize URL with `state`, `nonce`, and PKCE S256; stash `state`/`nonce`/`code_verifier`/`next` in a short-lived httpOnly `SameSite=Lax` cookie `arkham_oidc_txn` (Secure per `cookie_secure`, max-age 600, HMAC-signed with `app.state.csrf_secret`) and 303. The cookie must be Lax because the callback is a cross-site top-level navigation.
- `GET /callback`: 503 when disabled. Require `code` + `state`; constant-time compare `state` against the txn cookie; exchange `code` + `code_verifier` with authlib; decode and validate the id_token against JWKS (signature, `iss`, `aud`, `exp`, `nonce`); map the `groups` claim to a role. Admin ⇒ `issue_admin_session` + `arkham_admin` cookie (Strict) + 303 to `/admin`. Moderator ⇒ identity session + `arkham_oidc` cookie (Lax) + 303 to `/mod`. Neither ⇒ 401 with a clear error. Every failure ⇒ 401 JSON, txn cookie cleared, no session cookie. Tokens, code, and secret are discarded after the call.

### Validation and hygiene

Signature/JWKS/`iss`/`aud`/`exp`/`nonce` validation uses **`joserfc`** (pulled in by authlib 1.8), not `authlib.jose` — the latter is deprecated and its import warns, which `filterwarnings = ["error"]` turns into a failure. The expected `iss` is the value published in discovery (compared to `ARKHAM_OIDC_ISSUER` with trailing slashes normalised), so a trailing-slash mismatch does not reject every login. Discovery metadata and JWKS are cached on the provider with a TTL. The callback query is already redacted by `RequestLogMiddleware` (ADR 0016), no token is placed in a redirect URL, and no audit row is written here (S9CW records identity on join), so the "never in logs/audit/URLs" criterion holds. Failure logging records only an error code/exception type, never the code or token.

### Dependencies

Add `authlib>=1.3` to `server/pyproject.toml` runtime deps (it brings `joserfc` and `cryptography`). Use **`httpx2`** as the HTTP client: authlib's `httpx_client` integration imports `httpx2` when present and falls back to the deprecated `httpx` otherwise, so the existing runtime `httpx2>=2.0,<3.0` dependency is the one authlib uses. The lockfile and `server/requirements.lock` are regenerated together.

### Tests (`server/tests/test_oidc.py`)

A stub provider built on `httpx2.MockTransport` and a generated RSA key serves discovery, JWKS, and the token endpoint; no test touches the network. Cover the admin happy path, the moderator identity path, a user in neither group, bad state, bad nonce, expired token, tampered signature, unconfigured OIDC (503, and the password login still works), and app startup with OIDC unset.
