import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from './api';

function response({ status = 200, body = {}, json = true } = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: json
      ? vi.fn().mockResolvedValue(body)
      : vi.fn().mockRejectedValue(new SyntaxError('not JSON')),
  };
}

describe('api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
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
    });
  });

  it('folds a rejected fetch into the network error shape', async () => {
    globalThis.fetch.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(api.snapshot()).resolves.toEqual({
      error: 'network_error',
      message: 'Could not reach the server. Check your connection.',
      network: true,
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
    });
  });
});
