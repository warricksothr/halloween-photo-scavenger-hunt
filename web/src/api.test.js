import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from './api';

function response({ status = 200, body = {}, json = true, requestId } = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: {
      get: vi.fn((name) =>
        name === 'X-Request-ID' ? requestId ?? null : null,
      ),
    },
    json: json
      ? vi.fn().mockResolvedValue(body)
      : vi.fn().mockRejectedValue(new SyntaxError('not JSON')),
  };
}

describe('api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    document.cookie = 'arkham_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
  });

  it('returns JSON and sends JSON request bodies', async () => {
    const fetchMock = globalThis.fetch;
    fetchMock.mockResolvedValue(response({ body: { id: 'player-1' } }));

    await expect(api.join('JOIN/1', 'Robin', 'phone')).resolves.toEqual({
      id: 'player-1',
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/join/JOIN%2F1', {
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
      body: JSON.stringify({ display_name: 'Robin', device_label: 'phone' }),
      signal: expect.any(AbortSignal),
    });
  });

  it('returns a stable request error when the response is not JSON', async () => {
    globalThis.fetch.mockResolvedValue(response({ status: 502, json: false }));

    await expect(api.snapshot()).resolves.toEqual({
      error: 'request_failed',
      message: 'Something went wrong.',
      status: 502,
      requestId: null,
    });
  });

  it('decodes an API error from a non-2xx JSON response', async () => {
    globalThis.fetch.mockResolvedValue(
      response({
        status: 409,
        body: { error: 'submission_pending', message: 'Already scanning.' },
      }),
    );

    await expect(api.snapshot()).resolves.toEqual({
      error: 'submission_pending',
      message: 'Already scanning.',
      status: 409,
      requestId: null,
    });
  });

  it('keeps the 401 body for admin login while player calls stay unauthenticated', async () => {
    const fetchMock = globalThis.fetch;
    fetchMock.mockResolvedValueOnce(
      response({
        status: 401,
        body: {
          error: 'bad_credentials',
          message: 'Wrong username or password.',
        },
      }),
    );
    await expect(api.adminLogin('admin', 'nope')).resolves.toEqual({
      error: 'bad_credentials',
      message: 'Wrong username or password.',
      status: 401,
      requestId: null,
    });

    fetchMock.mockResolvedValueOnce(response({ status: 401, body: {} }));
    await expect(api.snapshot()).resolves.toEqual({ unauthenticated: true });
  });

  it("puts each queue claim's age on this device's clock (ADR 0038)", async () => {
    globalThis.fetch.mockResolvedValue(response({
      body: [
        { id: 'a', claimed_by: { id: 'm', label: 'Oracle', claimed_at: 1, claim_age: 120 } },
        { id: 'b', claimed_by: null },
      ],
    }));
    const before = Date.now() / 1000;
    const queue = await api.modQueue();
    const local = queue[0].claimed_by.claimed_at_local;
    // Two minutes before receipt by this clock, whatever the server's says.
    expect(local).toBeGreaterThanOrEqual(before - 120 - 1);
    expect(local).toBeLessThanOrEqual(Date.now() / 1000 - 120 + 1);
    expect(queue[1].claimed_by).toBeNull();
  });

  it('folds a rejected fetch into the network error shape', async () => {
    globalThis.fetch.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(api.snapshot()).resolves.toEqual({
      error: 'network_error',
      message: 'Could not reach the server. Check your connection.',
      network: true,
      requestId: null,
    });
  });

  it('aborts a fetch that never settles', async () => {
    vi.useFakeTimers();
    globalThis.fetch.mockImplementation(
      (_url, opts) =>
        new Promise((_resolve, reject) => {
          opts.signal.addEventListener('abort', () => reject(new Error('aborted')));
        }),
    );

    const pending = api.snapshot();
    await vi.advanceTimersByTimeAsync(8000);

    await expect(pending).resolves.toEqual({
      error: 'network_error',
      message: 'Could not reach the server. Check your connection.',
      network: true,
      requestId: null,
    });
    vi.useRealTimers();
  });

  it('aborts a response body that never settles', async () => {
    vi.useFakeTimers();
    globalThis.fetch.mockImplementation((_url, opts) =>
      Promise.resolve({
        status: 200,
        ok: true,
        json: () =>
          new Promise((_resolve, reject) => {
            opts.signal.addEventListener('abort', () => reject(new Error('aborted')));
          }),
      }),
    );

    const pending = api.snapshot();
    await vi.advanceTimersByTimeAsync(8000);

    await expect(pending).resolves.toEqual({
      error: 'network_error',
      message: 'Could not reach the server. Check your connection.',
      network: true,
      requestId: null,
    });
    vi.useRealTimers();
  });

  it('classifies a dropped response body as a network error', async () => {
    globalThis.fetch.mockResolvedValue({
      status: 200,
      ok: true,
      json: () => Promise.reject(new TypeError('terminated')),
    });

    await expect(api.snapshot()).resolves.toEqual({
      error: 'network_error',
      message: 'Could not reach the server. Check your connection.',
      network: true,
      requestId: null,
    });
  });

  it('classifies a dropped body on an error response as a network error', async () => {
    globalThis.fetch.mockResolvedValue({
      status: 503,
      ok: false,
      json: () => Promise.reject(new TypeError('terminated')),
    });

    await expect(api.snapshot()).resolves.toEqual({
      error: 'network_error',
      message: 'Could not reach the server. Check your connection.',
      network: true,
      requestId: null,
    });
  });

  it('echoes the CSRF cookie in the header on a mutating request', async () => {
    document.cookie = 'arkham_csrf=nonce.signature';
    const fetchMock = globalThis.fetch;
    fetchMock.mockResolvedValue(response({ body: {} }));

    await api.logout();

    expect(fetchMock).toHaveBeenCalledWith('/api/logout', {
      headers: { 'X-CSRF-Token': 'nonce.signature' },
      method: 'POST',
      body: undefined,
      signal: expect.any(AbortSignal),
    });
  });

  it('leaves the CSRF header off a safe read', async () => {
    document.cookie = 'arkham_csrf=nonce.signature';
    const fetchMock = globalThis.fetch;
    fetchMock.mockResolvedValue(response({ body: {} }));

    await api.snapshot();

    expect(fetchMock).toHaveBeenCalledWith('/api/state', {
      headers: {},
      body: undefined,
      signal: expect.any(AbortSignal),
    });
  });

  it('re-plants the token and retries once after csrf_failed', async () => {
    const fetchMock = globalThis.fetch;
    fetchMock
      .mockResolvedValueOnce(
        response({ status: 403, body: { error: 'csrf_failed', message: 'stale' } }),
      )
      .mockResolvedValueOnce(response({ body: {} }))
      .mockResolvedValueOnce(response({ body: { id: 'player-1' } }));

    await expect(api.join('J', 'Robin', 'phone')).resolves.toEqual({ id: 'player-1' });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/health',
      { credentials: 'same-origin' },
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/join/J',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('carries the response X-Request-ID on an error result', async () => {
    // The error result owns the id; the store hands it to reportError, so
    // a browser error correlates without any shared module state.
    globalThis.fetch.mockResolvedValue(
      response({
        status: 502,
        body: { error: 'upstream', message: 'Bad gateway.' },
        requestId: 'req-123',
      }),
    );

    await expect(api.snapshot()).resolves.toMatchObject({
      status: 502,
      requestId: 'req-123',
    });
  });

  it('reports a network failure with a null request id', async () => {
    globalThis.fetch.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(api.snapshot()).resolves.toMatchObject({
      network: true,
      requestId: null,
    });
  });

  it('returns the second csrf_failed rather than retrying forever', async () => {
    const fetchMock = globalThis.fetch;
    fetchMock.mockResolvedValue(
      response({ status: 403, body: { error: 'csrf_failed', message: 'stale' } }),
    );

    await expect(api.join('J', 'Robin', 'phone')).resolves.toEqual({
      error: 'csrf_failed',
      message: 'stale',
      status: 403,
      requestId: null,
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
