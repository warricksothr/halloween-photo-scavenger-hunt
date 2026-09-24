// App store — one module-scope state object plus subscribers.
//
// Deliberately not a state library: the app has exactly one server
// truth (the snapshot, ADR 0003) and this store mirrors it. Anything
// that changes server state calls api.*, then `refresh()` pulls the
// fresh snapshot — the client never maintains its own version of
// server-owned data.
import { api } from './api';
import { isModPath } from './paths';
import { loadTheme } from './theme';
import { reportError } from './errors';

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
  // Preact skips a state update when the same object reference comes back.
  // Publish a fresh shell so App rerenders after boot, joins, and SSE refreshes
  // while getState() remains the store's stable mutable source for callers.
  const nextState = { ...state };
  listeners.forEach((fn) => fn(nextState));
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
// the single resync point. EventSource retries a transient drop on its
// own, and the 'open' handler refreshes after a reconnect so nothing is
// missed. A drop the browser gives up on (readyState CLOSED: a 401, a
// proxy fault, a lost network) is dead, so onerror rebuilds it through
// refresh() — snapshot first, then a fresh stream (design.md "Realtime").
let eventSource = null;

// A dead stream rebuilds on the same short ladder as boot. The count
// resets on the next open so a flapping connection backs off instead of
// hammering the server.
const STREAM_RETRY_DELAYS_MS = [500, 1000, 2000, 5000];
let streamRetries = 0;
let streamTimer = null;

function scheduleStreamReconnect() {
  if (streamTimer != null) return;
  const delay =
    STREAM_RETRY_DELAYS_MS[
      Math.min(streamRetries, STREAM_RETRY_DELAYS_MS.length - 1)
    ];
  streamRetries += 1;
  streamTimer = setTimeout(() => {
    streamTimer = null;
    refresh();
  }, delay);
}

// The role the open stream serves. A browser can hold a player and a
// moderator session at once, so the stream names its role (?as=) and a
// tab whose role changed rebuilds it rather than keep the other one's.
let streamRole = null;

function startStream(role) {
  if (eventSource && streamRole === role) return;
  if (eventSource) stopStream();
  streamRole = role;
  eventSource = new EventSource(`/api/events/stream?as=${role}`);
  let opened = false;
  eventSource.onopen = () => {
    streamRetries = 0;
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
    // CONNECTING: the browser is already retrying, and its next 'open'
    // refetches. CLOSED: it has given up, so rebuild through refresh().
    if (eventSource?.readyState !== EventSource.CLOSED) return;
    stopStream();
    scheduleStreamReconnect();
  };
}

function stopStream() {
  if (streamTimer != null) {
    clearTimeout(streamTimer);
    streamTimer = null;
  }
  eventSource?.close();
  eventSource = null;
  streamRole = null;
}

export function getState() {
  return state;
}

// Boot and resync failures are usually a flaky phone connection, so a
// transient failure retries before the UI gives up. The schedule is short:
// a player on the boot screen reaches either the game or the retry
// affordance within a few seconds, and never hangs there.
const RETRY_DELAYS_MS = [500, 1000, 2000];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// A network rejection or a 5xx is worth retrying; a 4xx or a 401 is not
// (the store routes a 401 itself).
function isTransient(result) {
  return result.network === true || result.status >= 500;
}

// Both boot reads (the player snapshot and the moderator probe) go through
// this, so neither is less resilient than the other.
async function withRetry(request) {
  let result = await request();
  for (const delay of RETRY_DELAYS_MS) {
    if (!isTransient(result)) return result;
    await sleep(delay);
    result = await request();
  }
  return result;
}

// A failure the player cannot act on — a dead connection or a server fault —
// is a bug worth a report; a 4xx is the game telling the player something and
// is not. A 5xx the app answered carries a request id and the server already
// captured its own event for it, with the real stack, so the browser reports
// only the 5xx that has no id: one a proxy or a network boundary produced,
// which no server event describes. The result carries its own request id, so
// concurrent requests cannot cross-tag. Reporting is inert with no DSN
// (errors.js).
function reportFailure(result, context) {
  const serverAlreadyReported = result.status >= 500 && result.requestId != null;
  if (result.network || (result.status >= 500 && !serverAlreadyReported)) {
    reportError(
      new Error(result.message || 'request failed'),
      {
        ...context,
        error_code: result.error ?? 'unknown',
        http_status: result.status ?? null,
      },
      result.requestId ?? null,
    );
  }
}

// The resync point. Called on boot, after every mutation, and on SSE
// deltas (increment 7). Role detection: the player snapshot 401s for a
// mod-only cookie, so a 401 means "try the moderator probe" before
// concluding the visitor is unauthenticated. On a moderator path the
// order flips: the moderator session is probed first and the player
// snapshot never consulted, so a browser that also holds a player session
// (the host who plays) reaches the console or its sign-in, not the game.
//
// Refresh retries for up to a few seconds, and it is called from boot, from
// mutations, and from SSE deltas, so several can overlap. Each run takes a
// generation and drops its result if a newer run started meanwhile — an
// older run exhausting its retries must not overwrite newer good state with
// the error phase.
let refreshGeneration = 0;

export async function refresh() {
  const generation = ++refreshGeneration;
  const stale = () => generation !== refreshGeneration;

  if (isModPath(window.location.pathname)) {
    const mod = await withRetry(api.modState);
    if (stale()) return;
    await settleModerator(mod, stale);
    return;
  }

  const result = await withRetry(api.snapshot);
  if (stale()) return;
  if (result.unauthenticated) {
    const mod = await withRetry(api.modState);
    if (stale()) return;
    await settleModerator(mod, stale);
    return;
  }
  if (result.error) {
    reportFailure(result, { where: 'refresh.snapshot' });
    stopStream();
    set({ phase: 'error', error: result.message });
    return;
  }
  // Theme is keyed by the event; only reload it when it changes.
  const copy =
    state.themeName === result.event.theme && state.copy
      ? state.copy
      : await loadTheme(result.event.theme);
  if (stale()) return;
  set({ phase: 'ready', role: 'player', snapshot: result, copy,
        themeName: result.event.theme, modEvent: null });
  startStream('player');
}

// The moderator probe's outcome: the console, the join screen, or the
// connection-error screen.
async function settleModerator(mod, stale) {
  if (mod.error) {
    // The probe failed, so this is a connection problem, not an
    // unauthenticated visitor — do not drop them on the join screen.
    reportFailure(mod, { where: 'refresh.modState' });
    stopStream();
    set({ phase: 'error', error: mod.message });
    return;
  }
  if (mod.event) {
    const copy =
      state.copy && state.themeName === mod.event.theme
        ? state.copy
        : await loadTheme(mod.event.theme);
    if (stale()) return;
    set({ phase: 'ready', role: 'moderator', modEvent: mod.event,
          moderator: mod.moderator, copy, themeName: mod.event.theme,
          snapshot: null });
    startStream('moderator');
    return;
  }
  set({ phase: 'join', role: null, snapshot: null, modEvent: null });
  stopStream();
}

// The retry affordance on the connection-error screen: back to booting so
// the retry shows progress, then the full refresh (with its backoff).
export function retry() {
  set({ phase: 'booting', error: null });
  return refresh();
}

export async function modJoin(modCode) {
  const result = await api.modJoin(modCode);
  if (result.unauthenticated) {
    // No OIDC moderator session (S9CW): the screen sends the browser to
    // sign in. Refreshing would only re-probe and land back on join.
    return result;
  }
  if (result.error) {
    reportFailure(result, { where: 'modJoin' });
    return result; // the mod join screen shows the message
  }
  // Leave the link for the console's own path: the shell renders the join
  // screen for any /m/<code>, so staying there would loop, and a reload
  // of the console must not rejoin (and write another moderator.joined).
  window.history.replaceState(null, '', '/mod');
  await refresh();
  return result;
}

export async function join(joinCode, displayName, deviceLabel) {
  const result = await api.join(joinCode, displayName, deviceLabel);
  if (result.error) {
    reportFailure(result, { where: 'join' });
    return result; // the join screen shows the message
  }
  await refresh();
  return result;
}

// The games this browser can rejoin, for the join screen. A failure is
// an empty list: the join form below it still works.
export async function resumableGames() {
  const result = await api.resumable();
  if (result.error) {
    reportFailure(result, { where: 'resumableGames' });
    return [];
  }
  return result.games ?? [];
}

// Rejoin as the same player (ADR 0031). A refusal (the game closed, the
// player was banned) comes back for the join screen to show.
export async function resume(eventId) {
  const result = await api.resume(eventId);
  if (result.error) {
    reportFailure(result, { where: 'resume' });
    return result;
  }
  await refresh();
  return result;
}

// Leave the moderator console on this browser (ADR 0032). The server
// ends the moderator session; the player session, if any, is untouched.
// The URL moves to / so that the refresh lands on the game, or on the join
// screen with its rejoin list, and Back does not reopen a dead console. A
// 401 means the session had already ended, which is the same outcome.
export async function leaveModerator() {
  const result = await api.modLogout();
  if (result.error) {
    reportFailure(result, { where: 'leaveModerator' });
    return result;
  }
  stopStream();
  window.history.replaceState(null, '', '/');
  await refresh();
  return result;
}

// Switch games (ADR 0033): end this session but keep the game in Open
// Cases, then show the join screen. It goes straight to the join phase
// rather than refreshing, since a refresh at / would fall through to a
// moderator session if the browser holds one.
export async function switchGame() {
  const result = await api.leave();
  if (result.error) {
    reportFailure(result, { where: 'switchGame' });
    return result;
  }
  toJoinScreen();
  return result;
}

// Sign out on this phone: logout also forgets the game (ADR 0031), so it
// is for a phone changing hands, not for switching.
export async function logout() {
  await api.logout();
  toJoinScreen();
}

function toJoinScreen() {
  stopStream();
  // A /j/<code> or /t/<token> path would otherwise reopen that link.
  window.history.replaceState(null, '', '/');
  set({ phase: 'join', role: null, snapshot: null, modEvent: null });
}
