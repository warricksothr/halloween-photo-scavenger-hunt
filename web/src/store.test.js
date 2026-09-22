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
}));

vi.mock('./api', () => ({ api: mocks.api }));
vi.mock('./theme', () => ({ loadTheme: mocks.loadTheme }));

import {
  getState,
  join,
  logout,
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

  constructor(url) {
    this.url = url;
    this.closed = false;
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

  close() {
    this.closed = true;
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

  it('retry returns to booting and refreshes to ready', async () => {
    mocks.api.snapshot.mockResolvedValue(playerSnapshot);

    const done = retry();
    expect(getState().phase).toBe('booting');
    await done;
    expect(getState()).toMatchObject({ phase: 'ready', role: 'player' });
  });
});
