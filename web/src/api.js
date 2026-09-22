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
  // FormData bodies (photo upload) must NOT set Content-Type — the
  // browser sets it with the multipart boundary.
  const isForm = options.body instanceof FormData;
  const method = (options.method ?? 'GET').toUpperCase();
  const headers = options.body && !isForm ? { 'Content-Type': 'application/json' } : {};
  if (!SAFE_METHODS.has(method)) {
    const token = csrfToken();
    if (token) headers[CSRF_HEADER] = token;
  }
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    isForm ? UPLOAD_TIMEOUT_MS : REQUEST_TIMEOUT_MS,
  );
  try {
    const resp = await fetch(path, {
      headers,
      ...options,
      body: options.body && !isForm ? JSON.stringify(options.body) : options.body,
      signal: controller.signal,
    });
    if (resp.status === 401) {
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
      return { error: body.error ?? 'request_failed', message: body.message ?? 'Something went wrong.', status: resp.status };
    }
    if (bodyMalformed) {
      return { error: 'request_failed', message: 'Something went wrong.', status: resp.status };
    }
    return body;
  } catch {
    // A dropped connection or an offline phone rejects the promise, and a
    // dead one never settles until the timeout aborts it. Fold both into
    // the same error shape the rest of the client branches on, so callers
    // never see a rejection and a waiting screen cannot stay busy forever.
    return { error: 'network_error', message: 'Could not reach the server. Check your connection.', network: true };
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

export const api = {
  snapshot: () => request('/api/state'),
  join: (joinCode, displayName, deviceLabel) =>
    request(`/api/join/${encodeURIComponent(joinCode)}`, {
      method: 'POST',
      body: { display_name: displayName, device_label: deviceLabel },
    }),
  logout: () => request('/api/logout', { method: 'POST' }),
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
  modQueue: () => request('/api/mod/queue'),
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
};
