/** Service Worker для Petrunko's Reader — офлайн-оболонка додатку. */
const SHELL_CACHE = 'preader-shell-v2';
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

  // навігація: спершу мережа (свіжа версія), при офлайні — кеш
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).then(res => {
        const clone = res.clone();
        caches.open(SHELL_CACHE).then(c => c.put(e.request, clone));
        return res;
      }).catch(() => caches.match(e.request).then(h => h || caches.match('/index.html')))
    );
    return;
  }

  // статичні файли: кеш одразу, фоном оновлюємо
  e.respondWith(
    caches.match(e.request).then(hit => {
      const refresh = fetch(e.request).then(res => {
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(SHELL_CACHE).then(c => c.put(e.request, clone));
        }
        return res;
      }).catch(() => null);
      return hit || refresh;
    })
  );
});