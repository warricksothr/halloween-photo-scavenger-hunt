// Service worker: network-first for every same-origin GET, cache as the
// offline fallback.
//
// Why one rule instead of a per-path split: the party runs on venue wifi
// that *will* hiccup, so the shell and its bundles must still load
// offline — but a phone must never run an old shell against a new API
// after a redeploy. A network-first request with a cache fallback does
// both, and it keeps working when a file that was assumed immutable
// turns out not to be: whatever the URL, the network wins when it is
// reachable, so no path can be served stale.
//
// Assets are still cheap here: the server sends `Cache-Control:
// immutable` for the hashed `assets/*` bundles
// (server/app/main.py:175-184), and a service-worker `fetch()` reads
// through the HTTP cache, so a repeat load resolves without a round
// trip. The service-worker cache only matters when the network is gone.
//
// /api and cross-origin requests are left alone: the snapshot contract
// (ADR 0003) owns resync and game state must never be served stale, and
// this worker has no business answering for another origin.
const SHELL_CACHE = 'arkham-shell-v2';
const SHELL_ASSETS = ['/', '/index.html'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Drop caches from older versions — this deploy's install has already
  // refreshed the shell under the current name.
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL_CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET') return;
  if (url.pathname.startsWith('/api/')) return; // network only
  if (url.origin !== self.location.origin) return; // leave to the network
  event.respondWith(networkFirst(event.request));
});

// Fetch, refresh the cached copy, and fall back to the cache only when
// the network is down. A navigation that misses falls back to the shell,
// so a deep link (/j/<code>, /t/<token>) still opens offline.
async function networkFirst(request) {
  let resp;
  try {
    resp = await fetch(request);
  } catch (err) {
    const cached = await cachedFallback(request);
    if (cached) return cached;
    throw err;
  }

  if (resp.ok) {
    // Awaited so the write outlives the worker, but kept out of the
    // fetch's error path: a failed write (quota, unacceptable response)
    // must not cost the client the fresh copy it already has.
    try {
      const cache = await caches.open(SHELL_CACHE);
      await cache.put(request, resp.clone());
    } catch {
      // Serve the network response anyway.
    }
  }
  return resp;
}

async function cachedFallback(request) {
  const hit = await caches.match(request);
  if (hit) return hit;
  if (request.mode === 'navigate') return caches.match('/index.html');
  return undefined;
}
