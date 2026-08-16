// API client — the only module that talks to the backend.
//
// The contract (ADR 0003): snapshot on connect/reconnect, deltas over
// SSE later. So the only read here is GET /api/state; mutations POST
// and then hand the fresh snapshot back to the store. Errors follow
// docs/impl/api.md: {"error": code, "message": human string}.

async function request(path, options = {}) {
  const resp = await fetch(path, {
    headers: options.body ? { 'Content-Type': 'application/json' } : {},
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
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
};
