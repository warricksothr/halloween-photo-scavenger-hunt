// Service worker: network-first shell, cache-first hashed assets,
// everything else left alone.
//
// Why this split: the party runs on venue wifi that *will* hiccup, so
// the shell (HTML/JS/CSS) must still load offline — but a phone must
// never run an old shell against a new API after a redeploy. A
// navigation therefore goes to the network first and only falls back to
// the cache when the network is down, so a deploy takes effect without
// anyone bumping a cache name by hand. Hashed bundles
// (assets/index-<hash>.js) keep the cache-first path: the name changes
// with the content, so a cache hit is always the build that shipped it.
//
// Only those two cases are intercepted. /api always goes to the network
// (the snapshot contract, ADR 0003, owns resync and game state must
// never be served stale), and so does everything unhashed or
// cross-origin: the server already sends `Cache-Control: no-cache` for
// sw.js, index.html, and the manifest (server/app/main.py:156-187), so
// serving those from here could only make them stale.
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
  if (event.request.mode === 'navigate') {
    event.respondWith(networkFirst(event.request));
    return;
  }
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(event.request));
  }
});

// A navigation is the request whose freshness decides whether the phone
// runs the new build: fetch it, refresh the cached copy, and fall back
// to the cached shell only when the network is down. The fallback tries
// the exact URL first, then the shell, so a deep link (/j/<code>,
// /t/<token>) still opens offline.
async function networkFirst(request) {
  try {
    const resp = await fetch(request);
    if (resp.ok) {
      const cache = await caches.open(SHELL_CACHE);
      // Awaited: once this promise settles the browser may stop the
      // worker, and a cache write left in flight would be lost.
      await cache.put(request, resp.clone());
    }
    return resp;
  } catch (err) {
    const hit = (await caches.match(request)) ||
      (await caches.match('/index.html'));
    if (hit) return hit;
    throw err;
  }
}

// Hashed assets are immutable, so a cache hit is always the right build.
async function cacheFirst(request) {
  const hit = await caches.match(request);
  if (hit) return hit;
  const resp = await fetch(request);
  if (resp.ok) {
    const cache = await caches.open(SHELL_CACHE);
    await cache.put(request, resp.clone());
  }
  return resp;
}
