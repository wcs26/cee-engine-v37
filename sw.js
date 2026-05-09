/**
 * CEE Engine V37 — Service Worker (PWA)
 * Stratégie : network-first avec fallback cache pour résilience offline.
 * Les endpoints /analyse, /expert, /ai/* ne sont JAMAIS cachés (données fraîches).
 */
// V37.4.21 — Bump cache name à chaque release UI majeure pour forcer flush
const CACHE_NAME = 'cee-engine-v37-4-21';
// V37.4.21 — oracle.html RETIRÉ des assets pre-cachés : il évolue à chaque release
// et doit toujours être servi en network-first sans fallback cache initial.
const STATIC_ASSETS = [
  '/manifest.json',
  '/js/cee-pdfs.js',
];

// Endpoints qui ne doivent JAMAIS être servis depuis le cache
const NEVER_CACHE = [
  '/ai/',
  '/analyse',
  '/expert',
  '/recalcul',
  '/predictions',
  '/regulatory',
  '/siret',
  '/etablissements',
  '/cadastre',
  '/batiment',
  '/dpe',
  '/negociation',
  '/status',
  '/health',
  '/auth',
];

self.addEventListener('install', (ev) => {
  ev.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (ev) => {
  const url = new URL(ev.request.url);
  // Same-origin only
  if (url.origin !== self.location.origin) return;
  // Ne pas cacher les endpoints dynamiques
  if (NEVER_CACHE.some((p) => url.pathname.startsWith(p))) return;
  // V37.4.21 — oracle.html TOUJOURS network (pas de fallback cache) pour garantir version live
  if (url.pathname === '/oracle.html' || url.pathname === '/') {
    ev.respondWith(fetch(ev.request, {cache: 'no-store'}));
    return;
  }
  // Ne traiter que les GET
  if (ev.request.method !== 'GET') return;

  // Network-first avec fallback cache (offline)
  ev.respondWith(
    fetch(ev.request)
      .then((resp) => {
        // Cache les réponses OK
        if (resp && resp.status === 200 && resp.type === 'basic') {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(ev.request, clone)).catch(() => {});
        }
        return resp;
      })
      .catch(() => caches.match(ev.request))
  );
});
