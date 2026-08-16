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
  role: null,       // 'player' | 'moderator' (set once ready)
  snapshot: null,   // the GET /api/state response (players)
  modEvent: null,   // the GET /api/mod/state response (moderators)
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

// Screen-level delta listeners (the mod console refetches its queue on
// submission_new / queue_resolved). Distinct from state subscribers:
// these fire per SSE event, not per store patch.
const deltaListeners = new Set();

export function subscribeDeltas(fn) {
  deltaListeners.add(fn);
  return () => deltaListeners.delete(fn);
}

function emitDelta(name, payload) {
  deltaListeners.forEach((fn) => fn(name, payload));
}

// ── SSE (ADR 0003: snapshot on connect/reconnect, deltas after) ─────
//
// One EventSource for the life of a session. Payloads are thin by
// design, so every delta routes back to refresh() — the snapshot stays
// the single resync point. EventSource reconnects itself on drop; the
// 'open' handler refreshes after a reconnect so nothing is missed.
let eventSource = null;

function startStream() {
  if (eventSource) return;
  eventSource = new EventSource('/api/events/stream');
  let opened = false;
  eventSource.onopen = () => {
    if (opened) refresh(); // reconnect: refetch the snapshot
    opened = true;
  };
  for (const name of ['verdict', 'event_status', 'strike', 'leaderboard',
                      'submission_new', 'queue_resolved']) {
    eventSource.addEventListener(name, (e) => {
      const payload = JSON.parse(e.data);
      emitDelta(name, payload);
      // Player-facing deltas change the snapshot; moderator deltas
      // (submission_new, queue_resolved) only change the queue, which
      // the console refetches via emitDelta — no snapshot churn.
      if (state.role === 'player' &&
          ['verdict', 'event_status', 'strike', 'leaderboard'].includes(name)) {
        refresh();
      }
    });
  }
  eventSource.onerror = () => {
    // EventSource retries on its own; nothing to do but not crash.
  };
}

function stopStream() {
  eventSource?.close();
  eventSource = null;
}

export function getState() {
  return state;
}

// The resync point. Called on boot, after every mutation, and on SSE
// deltas (increment 7). Role detection: the player snapshot 401s for a
// mod-only cookie, so a 401 means "try the moderator probe" before
// concluding the visitor is unauthenticated.
export async function refresh() {
  const result = await api.snapshot();
  if (result.unauthenticated) {
    const mod = await api.modState();
    if (mod.event) {
      const copy =
        state.copy && state.themeName === mod.event.theme
          ? state.copy
          : await loadTheme(mod.event.theme);
      set({ phase: 'ready', role: 'moderator', modEvent: mod.event,
            moderator: mod.moderator, copy, themeName: mod.event.theme,
            snapshot: null });
      startStream();
      return;
    }
    set({ phase: 'join', role: null, snapshot: null, modEvent: null });
    stopStream();
    return;
  }
  if (result.error) {
    set({ phase: 'error', error: result.message });
    return;
  }
  // Theme is keyed by the event; only reload it when it changes.
  const copy =
    state.themeName === result.event.theme && state.copy
      ? state.copy
      : await loadTheme(result.event.theme);
  set({ phase: 'ready', role: 'player', snapshot: result, copy,
        themeName: result.event.theme, modEvent: null });
  startStream();
}

export async function modJoin(modCode) {
  const result = await api.modJoin(modCode);
  if (result.error) return result; // the mod join screen shows the message
  await refresh();
  return result;
}

export async function join(joinCode, displayName, deviceLabel) {
  const result = await api.join(joinCode, displayName, deviceLabel);
  if (result.error) return result; // the join screen shows the message
  await refresh();
  return result;
}

export async function logout() {
  await api.logout();
  stopStream();
  set({ phase: 'join', role: null, snapshot: null, modEvent: null });
}
