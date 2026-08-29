/** Service Worker для Petrunko's Reader — офлайн-оболонка додатку. */
const SHELL_CACHE = 'preader-shell-v1';
const SHELL = ['/', '/index.html', '/manifest.json', '/sw.js', '/icon.svg'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(SHELL_CACHE)
      .then(c => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== SHELL_CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/')) return;
  e.respondWith(
    caches.match(e.request).then(hit => hit || fetch(e.request))
  );
});