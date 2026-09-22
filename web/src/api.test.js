import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from './api';

function response({ status = 200, body = {}, json = true } = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: json
      ? vi.fn().mockResolvedValue(body)
      : vi.fn().mockRejectedValue(new Error('not JSON')),
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
});
