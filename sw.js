/**
 * CEE Engine V37.4.21c — Service Worker KILL-SWITCH
 *
 * Le SW PWA causait des stale UI sur les release rapides (oracle.html
 * cache servi à la place de la version live). Décision : on désactive le
 * SW pour cette app B2B qui requiert toujours réseau pour /expert /ai/*
 * /conformite etc. — l'offline-first n'a pas de valeur métier ici.
 *
 * Au prochain fetch que le browser fait sur sw.js, ce nouveau code remplace
 * l'ancien. Au activate :
 *  1. Supprime tous les caches existants (cee-engine-v37-*).
 *  2. S'auto-désinscrit (registration.unregister()).
 *  3. Force tous les clients à recharger (skipWaiting + claim → reload).
 * Résultat : à partir du prochain refresh, plus aucun SW actif, tout va au
 * réseau directement avec les headers Cache-Control: no-store.
 */

self.addEventListener('install', (ev) => {
  self.skipWaiting();
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil((async () => {
    // 1. Supprime TOUS les caches (cee-engine-v37-*, et tout autre résiduel)
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
    // 2. Désinscrit ce SW
    await self.registration.unregister();
    // 3. Force reload tous les clients pour qu'ils repartent sans SW
    const clients = await self.clients.matchAll({type: 'window'});
    clients.forEach((client) => {
      try { client.navigate(client.url); } catch (_e) {}
    });
  })());
});

// Fallback : si le browser intercepte un fetch avant le activate, on bypass
// totalement et on laisse le réseau gérer (pas d'ev.respondWith).
self.addEventListener('fetch', (ev) => {
  // No-op : browser default fetch (réseau direct).
});
