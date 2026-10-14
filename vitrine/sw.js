// Neutralise un ancien service worker PWA (quand l'app React était servie sur ce domaine).
// La vitrine est statique et n'a pas besoin de service worker : celui-ci se désinstalle,
// purge les caches et recharge les onglets pour servir la vraie vitrine.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    } catch (e) { /* noop */ }
    try { await self.registration.unregister(); } catch (e) { /* noop */ }
    const clients = await self.clients.matchAll({ type: 'window' });
    clients.forEach((c) => c.navigate(c.url));
  })());
});
