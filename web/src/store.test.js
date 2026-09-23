import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: {
    join: vi.fn(),
    logout: vi.fn(),
    modJoin: vi.fn(),
    modState: vi.fn(),
    snapshot: vi.fn(),
  },
  loadTheme: vi.fn(),
  reportError: vi.fn(),
}));

vi.mock('./api', () => ({ api: mocks.api }));
vi.mock('./theme', () => ({ loadTheme: mocks.loadTheme }));
vi.mock('./errors', () => ({
  reportError: mocks.reportError,
}));

import {
  getState,
  join,
  logout,
  modJoin,
  refresh,
  retry,
  subscribe,
  subscribeDeltas,
} from './store';

const copy = { name: 'arkham' };
const playerSnapshot = {
  event: { id: 'event-1', name: 'Photo Party', status: 'open', theme: 'arkham' },
  me: { display_name: 'Batman' },
  riddles: [],
  submissions: [],
};

class FakeEventSource {
  static instances = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  constructor(url) {
    this.url = url;
    this.closed = false;
    this.readyState = FakeEventSource.CONNECTING;
    this.listeners = new Map();
    FakeEventSource.instances.push(this);
  }

  addEventListener(name, listener) {
    const listeners = this.listeners.get(name) ?? [];
    listeners.push(listener);
    this.listeners.set(name, listeners);
  }

  emit(name, payload) {
    for (const listener of this.listeners.get(name) ?? []) {
      listener({ data: JSON.stringify(payload) });
    }
  }

  open() {
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.();
  }

  fail(readyState = FakeEventSource.CONNECTING) {
    this.readyState = readyState;
    this.onerror?.();
  }

  close() {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }
}

describe('store', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    vi.stubGlobal('EventSource', FakeEventSource);
    FakeEventSource.instances = [];
    mocks.api.logout.mockResolvedValue({});
    mocks.loadTheme.mockResolvedValue(copy);
    await logout();
  });

  it('joins, refreshes the snapshot, and starts the player stream', async () => {
    mocks.api.join.mockResolvedValue({ ok: true });
    mocks.api.snapshot.mockResolvedValue(playerSnapshot);
    const notifications = [];
    const unsubscribe = subscribe((nextState) => notifications.push(nextState));

    await expect(join('JOINCODE', 'Robin', 'phone')).resolves.toEqual({ ok: true });

    expect(mocks.api.join).toHaveBeenCalledWith('JOINCODE', 'Robin', 'phone');
    expect(notifications.at(-1)).not.toBe(getState());
    unsubscribe();
    expect(getState()).toMatchObject({
      phase: 'ready',
      role: 'player',
      snapshot: playerSnapshot,
    });
    expect(FakeEventSource.instances[0].url).toBe('/api/events/stream');
  });

  it('does not refresh when a mod join has no SSO moderator session', async () => {
    mocks.api.modJoin.mockResolvedValue({ unauthenticated: true });

    await expect(modJoin('MODCODE1')).resolves.toEqual({ unauthenticated: true });

    expect(mocks.api.modJoin).toHaveBeenCalledWith('MODCODE1');
    // No session means no snapshot to fetch; the screen starts SSO instead.
    expect(mocks.api.snapshot).not.toHaveBeenCalled();
    expect(mocks.api.modState).not.toHaveBeenCalled();
  });

  it('routes player SSE deltas to subscribers and refreshes the snapshot', async () => {
    const updated = { ...playerSnapshot, event: { ...playerSnapshot.event, status: 'closed' } };
    mocks.api.snapshot
      .mockResolvedValueOnce(playerSnapshot)
      .mockResolvedValueOnce(updated);
    await refresh();

    const delta = vi.fn();
    const unsubscribe = subscribeDeltas(delta);
    FakeEventSource.instances[0].emit('event_status', { status: 'closed' });

    await vi.waitFor(() => expect(getState().snapshot).toEqual(updated));
    expect(delta).toHaveBeenCalledWith('event_status', { status: 'closed' });
    expect(mocks.api.snapshot).toHaveBeenCalledTimes(2);
    unsubscribe();
  });

  it('routes moderator queue deltas without refreshing the player snapshot', async () => {
    mocks.api.snapshot.mockResolvedValue({ unauthenticated: true });
    mocks.api.modState.mockResolvedValue({
      event: { id: 'event-1', name: 'Photo Party', theme: 'arkham' },
      moderator: { id: 'mod-1' },
    });
    await refresh();

    const delta = vi.fn();
    const unsubscribe = subscribeDeltas(delta);
    FakeEventSource.instances[0].emit('submission_new', { submission_id: 'sub-1' });

    expect(getState()).toMatchObject({ phase: 'ready', role: 'moderator' });
    expect(delta).toHaveBeenCalledWith('submission_new', { submission_id: 'sub-1' });
    expect(mocks.api.snapshot).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it('refetches the snapshot when a dropped stream reconnects', async () => {
    const updated = { ...playerSnapshot, event: { ...playerSnapshot.event, status: 'closed' } };
    mocks.api.snapshot
      .mockResolvedValueOnce(playerSnapshot)
      .mockResolvedValueOnce(updated);
    await refresh();

    const stream = FakeEventSource.instances[0];
    stream.open(); // the first open: the boot snapshot is already fresh
    expect(mocks.api.snapshot).toHaveBeenCalledTimes(1);

    stream.fail(); // transient drop: EventSource retries on its own
    stream.open(); // reconnect

    await vi.waitFor(() => expect(getState().snapshot).toEqual(updated));
    expect(mocks.api.snapshot).toHaveBeenCalledTimes(2);
  });

  it('rebuilds a stream the browser gave up on and refetches', async () => {
    const updated = { ...playerSnapshot, event: { ...playerSnapshot.event, status: 'closed' } };
    mocks.api.snapshot
      .mockResolvedValueOnce(playerSnapshot)
      .mockResolvedValueOnce(updated);
    await refresh();

    const first = FakeEventSource.instances[0];
    first.open();
    first.fail(FakeEventSource.CLOSED); // fatal: the browser stopped retrying
    expect(first.closed).toBe(true);

    await vi.waitFor(
      () => expect(FakeEventSource.instances).toHaveLength(2),
      { timeout: 2000 },
    );
    await vi.waitFor(() => expect(getState().snapshot).toEqual(updated), {
      timeout: 2000,
    });
  });

  it('closes the stream when a resync enters the error phase', async () => {
    vi.useFakeTimers();
    mocks.api.snapshot
      .mockResolvedValueOnce(playerSnapshot)
      .mockResolvedValue({
        error: 'network_error',
        message: 'No connection.',
        network: true,
      });
    await refresh();

    const stream = FakeEventSource.instances[0];
    stream.open();
    expect(stream.closed).toBe(false);

    // A delta-triggered resync exhausts its retries and lands on error.
    stream.emit('verdict', { submission_id: 'sub-1' });
    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(2000);

    expect(getState().phase).toBe('error');
    expect(stream.closed).toBe(true);
    vi.useRealTimers();
  });

  it('logs out, closes SSE, and removes state and delta subscriptions', async () => {
    mocks.api.snapshot.mockResolvedValue(playerSnapshot);
    await refresh();
    const stream = FakeEventSource.instances[0];
    const stateListener = vi.fn();
    const deltaListener = vi.fn();
    const unsubscribeState = subscribe(stateListener);
    const unsubscribeDelta = subscribeDeltas(deltaListener);
    unsubscribeState();
    unsubscribeDelta();

    await logout();
    expect(stream.closed).toBe(true);
    expect(getState()).toMatchObject({
      phase: 'join',
      role: null,
      snapshot: null,
      modEvent: null,
    });

    stream.emit('verdict', { submission_id: 'sub-1' });
    expect(stateListener).not.toHaveBeenCalled();
    expect(deltaListener).not.toHaveBeenCalled();
  });

  it('retries a transient failure with backoff before showing the error phase', async () => {
    vi.useFakeTimers();
    mocks.api.snapshot.mockResolvedValue({
      error: 'network_error',
      message: 'Could not reach the server. Check your connection.',
      network: true,
    });

    const done = refresh();
    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(2000);
    await done;

    expect(mocks.api.snapshot).toHaveBeenCalledTimes(4);
    expect(getState()).toMatchObject({ phase: 'error' });
    vi.useRealTimers();
  });

  it('recovers when a retried request succeeds', async () => {
    vi.useFakeTimers();
    mocks.api.snapshot
      .mockResolvedValueOnce({ error: 'network_error', network: true })
      .mockResolvedValueOnce(playerSnapshot);

    const done = refresh();
    await vi.advanceTimersByTimeAsync(500);
    await done;

    expect(mocks.api.snapshot).toHaveBeenCalledTimes(2);
    expect(getState()).toMatchObject({ phase: 'ready', role: 'player' });
    vi.useRealTimers();
  });

  it('retries a transient moderator-probe failure before giving up', async () => {
    vi.useFakeTimers();
    mocks.api.snapshot.mockResolvedValue({ unauthenticated: true });
    mocks.api.modState
      .mockResolvedValueOnce({ error: 'network_error', network: true })
      .mockResolvedValueOnce({ event: null });

    const done = refresh();
    await vi.advanceTimersByTimeAsync(500);
    await done;

    expect(mocks.api.modState).toHaveBeenCalledTimes(2);
    expect(getState()).toMatchObject({ phase: 'join' });
    vi.useRealTimers();
  });

  it('shows the error phase when the moderator probe stays down', async () => {
    vi.useFakeTimers();
    mocks.api.snapshot.mockResolvedValue({ unauthenticated: true });
    mocks.api.modState.mockResolvedValue({
      error: 'network_error',
      message: 'Could not reach the server. Check your connection.',
      network: true,
    });

    const done = refresh();
    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(2000);
    await done;

    expect(mocks.api.modState).toHaveBeenCalledTimes(4);
    expect(getState()).toMatchObject({ phase: 'error' });
    vi.useRealTimers();
  });

  it('drops a stale retry that finishes after a newer refresh', async () => {
    vi.useFakeTimers();
    mocks.api.snapshot
      .mockResolvedValueOnce({ error: 'network_error', network: true })
      .mockResolvedValueOnce(playerSnapshot)
      .mockResolvedValueOnce({ error: 'network_error', network: true })
      .mockResolvedValueOnce({ error: 'network_error', network: true })
      .mockResolvedValueOnce({ error: 'network_error', network: true });

    const slow = refresh();
    const fast = refresh();
    await fast;
    expect(getState()).toMatchObject({ phase: 'ready', role: 'player' });

    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(2000);
    await slow;

    expect(getState()).toMatchObject({ phase: 'ready', role: 'player' });
    vi.useRealTimers();
  });

  it('retry returns to booting and refreshes to ready', async () => {    mocks.api.snapshot.mockResolvedValue(playerSnapshot);

    const done = retry();
    expect(getState().phase).toBe('booting');
    await done;
    expect(getState()).toMatchObject({ phase: 'ready', role: 'player' });
  });

  it('reports a 5xx boot failure through the reporter', async () => {
    vi.useFakeTimers();
    mocks.api.snapshot.mockResolvedValue({
      error: 'request_failed',
      message: 'Something went wrong.',
      status: 500,
    });

    const done = refresh();
    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(2000);
    await done;

    expect(mocks.reportError).toHaveBeenCalledTimes(1);
    expect(mocks.reportError.mock.calls[0][1]).toMatchObject({
      where: 'refresh.snapshot',
      http_status: 500,
    });
    vi.useRealTimers();
  });

  it('does not report a 4xx the player can act on', async () => {
    mocks.api.snapshot.mockResolvedValue({
      error: 'not_joined',
      message: 'Join first.',
      status: 400,
    });

    await refresh();

    expect(mocks.reportError).not.toHaveBeenCalled();
  });

  it('reports a failed join only when the server faulted', async () => {
    mocks.api.join.mockResolvedValue({
      error: 'request_failed',
      message: 'Something went wrong.',
      status: 503,
    });

    await join('JOINCODE', 'Robin', 'phone');

    expect(mocks.reportError).toHaveBeenCalledWith(expect.any(Error), {
      where: 'join',
      error_code: 'request_failed',
      http_status: 503,
    }, null);
  });

  it('does not report a 5xx the server already reported under its own id', async () => {
    vi.useFakeTimers();
    mocks.api.snapshot.mockResolvedValue({
      error: 'request_failed',
      message: 'Something went wrong.',
      status: 500,
      requestId: 'req-own',
    });

    const done = refresh();
    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(2000);
    await done;

    expect(mocks.reportError).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('reports a dead connection under its own request id', async () => {
    vi.useFakeTimers();
    mocks.api.snapshot.mockResolvedValue({
      error: 'network_error',
      message: 'No connection.',
      network: true,
      requestId: 'req-net',
    });

    const done = refresh();
    await vi.advanceTimersByTimeAsync(500);
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(2000);
    await done;

    expect(mocks.reportError).toHaveBeenCalledTimes(1);
    expect(mocks.reportError.mock.calls[0][2]).toBe('req-net');
    vi.useRealTimers();
  });
});
