// App store — one module-scope state object plus subscribers.
//
// Deliberately not a state library: the app has exactly one server
// truth (the snapshot, ADR 0003) and this store mirrors it. Anything
// that changes server state calls api.*, then `refresh()` pulls the
// fresh snapshot — the client never maintains its own version of
// server-owned data.
import { api } from './api';
import { loadTheme } from './theme';

const state = {
  phase: 'booting', // booting | join | ready | error
  snapshot: null,   // the GET /api/state response
  copy: null,       // active theme pack's copy config
  error: null,
};

const listeners = new Set();

function set(patch) {
  Object.assign(state, patch);
  listeners.forEach((fn) => fn(state));
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getState() {
  return state;
}

// The resync point. Called on boot, after every mutation, and (in
// increment 7) on SSE reconnect / event_status deltas.
export async function refresh() {
  const result = await api.snapshot();
  if (result.unauthenticated) {
    set({ phase: 'join', snapshot: null });
    return;
  }
  if (result.error) {
    set({ phase: 'error', error: result.message });
    return;
  }
  // Theme is keyed by the event; only reload it when it changes.
  const copy =
    state.snapshot?.event?.theme === result.event.theme && state.copy
      ? state.copy
      : await loadTheme(result.event.theme);
  set({ phase: 'ready', snapshot: result, copy });
}

export async function join(joinCode, displayName, deviceLabel) {
  const result = await api.join(joinCode, displayName, deviceLabel);
  if (result.error) return result; // the join screen shows the message
  await refresh();
  return result;
}

export async function logout() {
  await api.logout();
  set({ phase: 'join', snapshot: null });
}
