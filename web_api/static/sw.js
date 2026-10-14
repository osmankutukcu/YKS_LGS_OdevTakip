// Cache only this application's shell. API responses contain student data;
// they are intentionally never stored in Cache Storage.
const CACHE_NAME = 'yks-kocluk-shell-v4';
const CACHE_PREFIX = 'yks-kocluk-shell-';
const SHELL_ASSETS = ['/', '/static/js/offline_sync.js', '/static/js/offline_vault.js', '/static/manifest.json',
                      '/static/tailwindcss.js', '/static/vue.js'];

self.addEventListener('install', event => {
    event.waitUntil((async () => {
        const cache = await caches.open(CACHE_NAME);
        // All essential application-shell assets must cache successfully.
        // Activating a partially installed offline shell leaves teachers
        // unable to open the application when their computer is shut down.
        await Promise.all(SHELL_ASSETS.map(async path => {
            const response = await fetch(path, {cache: 'reload'});
            if (!response.ok) throw new Error(`Essential asset unavailable: ${path}`);
            await cache.put(path, response);
        }));
        await self.skipWaiting();
    })());
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        const names = await caches.keys();
        await Promise.all(names.filter(name => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
            .map(name => caches.delete(name)));
        await self.clients.claim();
    })());
});

self.addEventListener('fetch', event => {
    const req = event.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;
    // The application itself implements authenticated read fallback from IndexedDB.
    if (url.pathname.startsWith('/api/')) return;

    event.respondWith((async () => {
        try {
            const response = await fetch(req);
            if (response.ok && (url.pathname === '/' || url.pathname.startsWith('/static/') ||
                                url.pathname === '/manifest.json' || url.pathname === '/sw.js')) {
                const clone = response.clone();
                event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(req, clone)));
            }
            return response;
        } catch (_) {
            return (await caches.match(req)) ||
                (req.mode === 'navigate' ? await caches.match('/') : undefined) ||
                Response.error();
        }
    })());
});
