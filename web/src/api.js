// API client — the only module that talks to the backend.
//
// The contract (ADR 0003): snapshot on connect/reconnect, deltas over
// SSE later. So the only read here is GET /api/state; mutations POST
// and then hand the fresh snapshot back to the store. Errors follow
// docs/impl/api.md: {"error": code, "message": human string}.

// A fetch can stay pending indefinitely on a dead connection, which no
// amount of retry logic can reach. Bound the whole exchange — headers *and*
// body — so a hung connection turns into the same error shape a rejection
// does. Uploads carry a photo over a phone network, so they get a much
// longer budget than a small read.
const REQUEST_TIMEOUT_MS = 8000;
const UPLOAD_TIMEOUT_MS = 60000;

// CSRF (ADR 0015): the server plants a signed token in a readable cookie
// on any safe response. Echo it back in a header on every mutating
// request — the pair is what proves the call came from same-origin JS.
const CSRF_COOKIE = 'arkham_csrf';
const CSRF_HEADER = 'X-CSRF-Token';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

function csrfToken() {
  const prefix = `${CSRF_COOKIE}=`;
  for (const part of document.cookie.split('; ')) {
    if (part.startsWith(prefix)) return decodeURIComponent(part.slice(prefix.length));
  }
  return null;
}

async function send(path, options = {}) {
  // `reportUnauthorized` is client-only: every player route treats a 401
  // as "not joined", but the admin login form needs the body (a bad
  // password is a 401 carrying `bad_credentials` and its message).
  const { reportUnauthorized = false, ...init } = options;
  // FormData bodies (photo upload) must NOT set Content-Type — the
  // browser sets it with the multipart boundary.
  const isForm = init.body instanceof FormData;
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = init.body && !isForm ? { 'Content-Type': 'application/json' } : {};
  if (!SAFE_METHODS.has(method)) {
    const token = csrfToken();
    if (token) headers[CSRF_HEADER] = token;
  }
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    isForm ? UPLOAD_TIMEOUT_MS : REQUEST_TIMEOUT_MS,
  );
  // The id of THIS response, carried on the result so a caller reports
  // under its own request. There is no shared global to overwrite, so
  // concurrent requests cannot cross-tag.
  let responseId;
  try {
    const resp = await fetch(path, {
      headers,
      ...init,
      body: init.body && !isForm ? JSON.stringify(init.body) : init.body,
      signal: controller.signal,
    });
    // The request id is the join key to this request's server log line and
    // error report, so a browser error can name the same request (ADR 0016).
    responseId = resp.headers?.get?.('X-Request-ID') ?? null;
    if (resp.status === 401 && !reportUnauthorized) {
      // Not joined (or session revoked) — the store routes to the join
      // screen; it is not an error from the player's point of view.
      return { unauthenticated: true };
    }
    // The fetch promise settles on the headers, so the body read has to stay
    // inside this block to remain under the timeout. A body read can fail
    // three ways, and they are not the same: the timeout aborted it, the
    // connection dropped mid-stream, or the body was not JSON. Only the last
    // is a request failure, whatever the status; the other two are network
    // errors, and a body that failed to parse must not be handed back as a
    // successful empty object.
    let body = {};
    let bodyMalformed = false;
    try {
      body = await resp.json();
    } catch (err) {
      if (controller.signal.aborted) throw err;
      if (!(err instanceof SyntaxError)) throw err;
      bodyMalformed = true;
    }
    if (!resp.ok) {
      return { error: body.error ?? 'request_failed', message: body.message ?? 'Something went wrong.', status: resp.status, requestId: responseId };
    }
    if (bodyMalformed) {
      return { error: 'request_failed', message: 'Something went wrong.', status: resp.status, requestId: responseId };
    }
    return body;
  } catch {
    // A dropped connection or an offline phone rejects the promise, and a
    // dead one never settles until the timeout aborts it. Fold both into
    // the same error shape the rest of the client branches on, so callers
    // never see a rejection and a waiting screen cannot stay busy forever.
    return { error: 'network_error', message: 'Could not reach the server. Check your connection.', network: true, requestId: null };
  } finally {
    clearTimeout(timer);
  }
}

async function request(path, options = {}) {
  const result = await send(path, options);
  if (result.error !== 'csrf_failed') return result;
  // The token was missing or stale — a restarted server or an expired
  // cookie. Any safe GET re-plants it, so replay the call once with the
  // fresh pair rather than surfacing an error the player cannot act on.
  await fetch('/api/health', { credentials: 'same-origin' });
  return send(path, options);
}

// Single sign-on (S9CW): an unauthenticated mod screen sends the browser
// here to start the OIDC dance, carrying where to come back to. The
// server clamps `next` to a same-origin path.
export function oidcLoginUrl(next) {
  return `/api/auth/oidc/login?next=${encodeURIComponent(next)}`;
}

export const api = {
  snapshot: () => request('/api/state'),
  join: (joinCode, displayName, deviceLabel) =>
    request(`/api/join/${encodeURIComponent(joinCode)}`, {
      method: 'POST',
      body: { display_name: displayName, device_label: deviceLabel },
    }),
  logout: () => request('/api/logout', { method: 'POST' }),
  // Switch games (ADR 0033): ends the session, keeps the rejoin cookie.
  leave: () => request('/api/leave', { method: 'POST' }),
  // Rejoin (ADR 0031): the games this browser's resume cookies name, and
  // a fresh session as the same player in one of them.
  resumable: () => request('/api/resume'),
  resume: (eventId) =>
    request(`/api/resume/${encodeURIComponent(eventId)}`, { method: 'POST' }),
  noticeAck: () => request('/api/me/notice-ack', { method: 'POST' }),
  drawer: () => request('/api/evidence'),
  recap: () => request('/api/recap'),
  // ── Teams (stretch) ──
  team: () => request('/api/team'),
  renameTeam: (name) =>
    request('/api/team/rename', { method: 'POST', body: { name } }),
  createInvite: () => request('/api/team/invites', { method: 'POST' }),
  revokeInvite: (token) =>
    request(`/api/team/invites/${encodeURIComponent(token)}/revoke`,
            { method: 'POST' }),
  inviteInfo: (token) =>
    request(`/api/team/invites/${encodeURIComponent(token)}`),
  redeemInvite: (token, displayName, deviceLabel, confirmSwitch) =>
    request(`/api/team/invites/${encodeURIComponent(token)}/redeem`, {
      method: 'POST',
      body: { display_name: displayName, device_label: deviceLabel,
              confirm_switch: confirmSwitch },
    }),
  submit: (riddleId, evidenceItemId) =>
    request('/api/submissions', {
      method: 'POST',
      body: { riddle_id: riddleId, evidence_item_id: evidenceItemId },
    }),
  upload: (file, riddleId) => {
    const form = new FormData();
    form.append('photo', file);
    const query = riddleId ? `?riddle_id=${encodeURIComponent(riddleId)}` : '';
    return request(`/api/evidence${query}`, { method: 'POST', body: form });
  },
  // ── Moderator (increment 7) ──
  modJoin: (modCode) =>
    request(`/api/mod/join/${encodeURIComponent(modCode)}`, { method: 'POST' }),
  modState: () => request('/api/mod/state'),
  modLogout: () => request('/api/mod/logout', { method: 'POST' }),
  // Each claim's server-reported age becomes a time on this device's
  // clock (claimed_at_local), so claim freshness never compares the
  // server's clock with the phone's (ADR 0038).
  modQueue: () => request('/api/mod/queue').then(localiseClaims),
  modClaim: (submissionId) =>
    request(`/api/mod/queue/${submissionId}/claim`, { method: 'POST' }),
  modVerdict: (submissionId, verdict, flavorText) =>
    request(`/api/mod/queue/${submissionId}/verdict`, {
      method: 'POST',
      body: { verdict, flavor_text: flavorText },
    }),
  modResolveFlag: (evidenceId, resolution) =>
    request(`/api/mod/flags/${evidenceId}/resolve`, {
      method: 'POST',
      body: { resolution },
    }),
  modPlayerHistory: (playerId) => request(`/api/mod/players/${playerId}`),
  // ── Team management (stretch) ──
  modTeams: () => request('/api/mod/teams'),
  modRemoveMember: (teamId, playerId) =>
    request(`/api/mod/teams/${encodeURIComponent(teamId)}/remove/${encodeURIComponent(playerId)}`,
            { method: 'POST' }),
  // ── Conduct (increment 8) ──
  // Verdict + strike in one action (design.md): the moderator never
  // needs a second screen. cooldownMinutes matters only at strike 2.
  modInappropriate: (submissionId, note, cooldownMinutes) =>
    request(`/api/mod/queue/${submissionId}/inappropriate`, {
      method: 'POST',
      body: { note, cooldown_minutes: cooldownMinutes },
    }),
  // ── Admin console (S9CX) ──
  // The events list doubles as the session probe: a 401 is the "not
  // signed in" signal, a 200 list is both proof of session and the
  // console's first data.
  adminEvents: () => request('/api/admin/events'),
  adminLogin: (username, password) =>
    request('/api/admin/login', {
      method: 'POST',
      body: { username, password },
      reportUnauthorized: true,
    }),
  adminLogout: () => request('/api/admin/logout', { method: 'POST' }),
  // ── Admin event management (S9CY) ──
  // These keep the default 401 handling on purpose: they are only called
  // from behind the console, so a 401 means the admin session died and
  // the shell should fall back to login, not paint a form error.
  adminCreateEvent: (event) =>
    request('/api/admin/events', { method: 'POST', body: event }),
  // The codes on demand (ADR 0026): their own call, so the list never
  // carries them.
  adminEventCodes: (eventId) => request(`/api/admin/events/${eventId}/codes`),
  // kind is 'join' or 'mod'; answers with both codes (ADR 0039).
  adminRotateCode: (eventId, kind) =>
    request(`/api/admin/events/${eventId}/codes/${kind}/rotate`, { method: 'POST' }),
  adminOpenEvent: (eventId) =>
    request(`/api/admin/events/${eventId}/open`, { method: 'POST' }),
  adminCloseEvent: (eventId) =>
    request(`/api/admin/events/${eventId}/close`, { method: 'POST' }),
  // The server wants the event NAME re-typed as the confirmation
  // (events.py), so the caller passes it through rather than an id.
  adminPurgeEvent: (eventId, confirm) =>
    request(`/api/admin/events/${eventId}/purge`, {
      method: 'POST',
      body: { confirm },
    }),
  // ── Admin riddle management (S9CZ) ──
  // Same 401 contract as the event calls: a riddle workspace is only ever
  // reached from a live console session.
  adminRiddles: (eventId) => request(`/api/admin/events/${eventId}/riddles`),
  adminCreateRiddle: (eventId, riddle) =>
    request(`/api/admin/events/${eventId}/riddles`, {
      method: 'POST',
      body: riddle,
    }),
  adminPatchRiddle: (eventId, riddleId, patch) =>
    request(`/api/admin/events/${eventId}/riddles/${riddleId}`, {
      method: 'PATCH',
      body: patch,
    }),
  adminDeleteRiddle: (eventId, riddleId) =>
    request(`/api/admin/events/${eventId}/riddles/${riddleId}`, {
      method: 'DELETE',
    }),
  // ── Admin host actions (S9D0) ──
  // The reversal endpoint already owned the mutation (server/app/events.py);
  // this is the host's read: each player with their derived restriction and
  // strike history, so the strike to reverse can be found.
  adminPlayers: (eventId) => request(`/api/admin/events/${eventId}/players`),
  adminReverseStrike: (strikeId, reason) =>
    request(`/api/admin/strikes/${strikeId}/reverse`, {
      method: 'POST',
      body: { reason: reason ?? '' },
    }),
};

function localiseClaims(queue) {
  if (!Array.isArray(queue)) return queue;
  const received = Date.now() / 1000;
  for (const item of queue) {
    const claim = item.claimed_by;
    if (claim && typeof claim.claim_age === 'number') {
      claim.claimed_at_local = received - claim.claim_age;
    }
  }
  return queue;
}
