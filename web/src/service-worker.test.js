// The service worker is a static file, so it is loaded here as source
// and run against a fake ServiceWorkerGlobalScope. This is the only
// place the shell-caching policy is exercised: it is what decides
// whether a phone runs the build that shipped after a redeploy.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';

// Vitest runs with the web/ package as its root, so the static worker
// is reachable from the working directory.
const SOURCE = readFileSync(resolve(process.cwd(), 'public/sw.js'), 'utf8');
const ORIGIN = 'https://hunt.test';

function response(body, { ok = true } = {}) {
  return { body, ok, clone: () => response(body, { ok }) };
}

function keyOf(request) {
  const url = typeof request === 'string' ? request : request.url;
  return new URL(url, ORIGIN).href;
}

function loadWorker() {
  const handlers = {};
  const entries = new Map();
  const deleted = [];

  const cache = {
    addAll: vi.fn(async (urls) => {
      urls.forEach((url) => entries.set(keyOf(url), response(`cached:${url}`)));
    }),
    put: vi.fn(async (request, resp) => {
      entries.set(keyOf(request), resp);
    }),
  };

  const caches = {
    open: vi.fn(async () => cache),
    match: vi.fn(async (request) => entries.get(keyOf(request))),
    keys: vi.fn(async () => ['arkham-shell-v1', 'arkham-shell-v2']),
    delete: vi.fn(async (name) => {
      deleted.push(name);
      return true;
    }),
  };

  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type, handler) => {
      handlers[type] = handler;
    },
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn() },
  };

  const fetch = vi.fn();

  new Function('self', 'caches', 'fetch', SOURCE)(self, caches, fetch);

  function waitFor(type) {
    let pending;
    handlers[type]({ waitUntil: (p) => { pending = p; } });
    return pending;
  }

  function request(url, mode = 'cors') {
    let responded;
    handlers.fetch({
      request: { url: new URL(url, ORIGIN).href, method: 'GET', mode },
      respondWith: (p) => { responded = p; },
    });
    return responded;
  }

  return { entries, deleted, caches, cache, self, fetch, waitFor, request };
}

describe('service worker shell policy', () => {
  it('prefetches the shell on install', async () => {
    const worker = loadWorker();
    await worker.waitFor('install');

    expect([...worker.entries.keys()].sort()).toEqual([
      `${ORIGIN}/`,
      `${ORIGIN}/index.html`,
    ]);
  });

  it('drops caches from an older version on activate', async () => {
    const worker = loadWorker();
    await worker.waitFor('activate');

    expect(worker.deleted).toEqual(['arkham-shell-v1']);
  });

  it('serves a new build on a navigation even when an old shell is cached', async () => {
    const worker = loadWorker();
    worker.entries.set(`${ORIGIN}/index.html`, response('old shell'));
    worker.fetch.mockResolvedValue(response('new shell'));

    const resp = await worker.request('/index.html', 'navigate');

    expect(resp.body).toBe('new shell');
    expect(worker.entries.get(`${ORIGIN}/index.html`).body).toBe('new shell');
  });

  it('falls back to the cached shell when a navigation is offline', async () => {
    const worker = loadWorker();
    worker.entries.set(`${ORIGIN}/index.html`, response('cached shell'));
    worker.fetch.mockRejectedValue(new Error('offline'));

    const resp = await worker.request('/j/ABC123', 'navigate');

    expect(resp.body).toBe('cached shell');
  });

  it('never intercepts /api', () => {
    const worker = loadWorker();

    expect(worker.request('/api/state')).toBeUndefined();
    expect(worker.fetch).not.toHaveBeenCalled();
  });

  it('leaves unhashed and cross-origin requests to the network', () => {
    const worker = loadWorker();

    expect(worker.request('/manifest.webmanifest')).toBeUndefined();
    expect(worker.request('https://fonts.googleapis.com/css?family=Spectral'))
      .toBeUndefined();
  });

  it('commits the refreshed shell before the navigation response settles', async () => {
    const worker = loadWorker();
    let release;
    worker.cache.put.mockReturnValue(
      new Promise((resolve) => { release = resolve; }),
    );
    worker.fetch.mockResolvedValue(response('new shell'));

    let settled = false;
    const pending = worker.request('/index.html', 'navigate')
      .then((resp) => { settled = true; return resp; });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(settled).toBe(false);

    release();
    expect((await pending).body).toBe('new shell');
  });

  it('serves hashed assets from the cache without a network read', async () => {
    const worker = loadWorker();
    const asset = `${ORIGIN}/assets/index-abc123.js`;
    worker.entries.set(asset, response('cached bundle'));

    const resp = await worker.request('/assets/index-abc123.js');

    expect(resp.body).toBe('cached bundle');
    expect(worker.fetch).not.toHaveBeenCalled();
  });
});
