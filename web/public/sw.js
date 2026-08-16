// Service worker: cache-first app shell, network-only /api.
//
// Why this split: the party runs on venue wifi that *will* hiccup, so
// the shell (HTML/JS/CSS/fonts) must load offline — but game state must
// never be served stale, so /api always goes to the network. The
// snapshot contract (ADR 0003) already handles reconnects; this only
// keeps the app itself loadable.
const SHELL_CACHE = 'arkham-shell-v1';
const SHELL_ASSETS = ['/', '/index.html', '/manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Drop caches from older versions.
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL_CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/')) {
    return; // network only — no respondWith means default fetch
  }
  if (event.request.method !== 'GET') return;
  event.respondWith(
    caches.match(event.request).then((hit) =>
      hit ||
      fetch(event.request).then((resp) => {
        // Cache successful same-origin GETs (JS/CSS bundles) as we go.
        if (resp.ok && url.origin === self.location.origin) {
          const clone = resp.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(event.request, clone));
        }
        return resp;
      })
    )
  );
});
