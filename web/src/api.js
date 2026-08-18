// API client — the only module that talks to the backend.
//
// The contract (ADR 0003): snapshot on connect/reconnect, deltas over
// SSE later. So the only read here is GET /api/state; mutations POST
// and then hand the fresh snapshot back to the store. Errors follow
// docs/impl/api.md: {"error": code, "message": human string}.

async function request(path, options = {}) {
  // FormData bodies (photo upload) must NOT set Content-Type — the
  // browser sets it with the multipart boundary.
  const isForm = options.body instanceof FormData;
  const resp = await fetch(path, {
    headers: options.body && !isForm ? { 'Content-Type': 'application/json' } : {},
    ...options,
    body: options.body && !isForm ? JSON.stringify(options.body) : options.body,
  });
  if (resp.status === 401) {
    // Not joined (or session revoked) — the store routes to the join
    // screen; it is not an error from the player's point of view.
    return { unauthenticated: true };
  }
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    return { error: body.error ?? 'request_failed', message: body.message ?? 'Something went wrong.', status: resp.status };
  }
  return body;
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
