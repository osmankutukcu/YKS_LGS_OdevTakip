/*
 * YKS–LGS Offline V10: version-pinned, atomic application shell.
 * No student data or authenticated API response is ever cached here.
 * The previous active cache is retained until V7 installs completely.
 * Build: 2026-10-15-v12.3-offline-resilience
 */
const CACHE_NAME = 'yks-kocluk-shell-v10';
const CACHE_PREFIX = 'yks-kocluk-shell-';
const SHELL_ASSETS = Object.freeze([
    '/',
    '/static/js/offline_secure_store_v5.js',
    '/static/js/offline_vault.js',
    '/static/js/offline_coordinator_v7.js',
    '/static/js/offline_paged_v8.js',
    '/static/js/offline_delta_v9.js',
    '/static/js/offline_resilience_v10.js',
    '/static/js/offline_folder_v8.js',
    '/static/js/offline_sync.js',
    '/static/js/offline_health_v6.js',
    '/static/manifest.json',
    '/static/tailwindcss.js',
    '/static/vue.js',
    '/static/favicon.png',
    '/static/apple-touch-icon.png',
    '/static/icon-192.png',
    '/static/icon-512.png'
]);
const SHELL_SET = new Set(SHELL_ASSETS);

async function installShell() {
    const cache = await caches.open(CACHE_NAME);
    // Cache the entire release. An incomplete shell must never activate.
    try {
        for (const path of SHELL_ASSETS) {
            const response = await fetch(path, {cache: 'reload', redirect: 'error'});
            if (!response || !response.ok || response.type === 'opaque' || response.redirected) {
                throw new Error(`Çevrimdışı dosya indirilemedi: ${path}`);
            }
            // A login page / reverse-proxy error returned for a JS file is not a JS file.
            const contentType = (response.headers?.get('content-type') || '').toLowerCase();
            if (path === '/' && contentType && !contentType.includes('text/html')) {
                throw new Error('Ana ekran geçerli HTML değil.');
            }
            if (path.endsWith('.js') && contentType &&
                !contentType.includes('javascript') && !contentType.includes('ecmascript')) {
                throw new Error(`Yanlış betik içerik türü: ${path}`);
            }
            if (path.endsWith('.json') && contentType && !contentType.includes('json')) {
                throw new Error(`Yanlış manifest içerik türü: ${path}`);
            }
            await cache.put(path, response);
        }
    } catch (e) {
        await caches.delete(CACHE_NAME);
        throw e;
    }
}

self.addEventListener('install', event => {
    if (typeof self.skipWaiting === 'function') self.skipWaiting();
    event.waitUntil(installShell());
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        const cache = await caches.open(CACHE_NAME);
        // Defensive check, not just the install promise: avoid deleting a
        // working old release if the new cache was externally evicted.
        for (const path of SHELL_ASSETS) {
            if (!await cache.match(path)) throw new Error(`Yeni çevrimdışı sürüm eksik: ${path}`);
        }
        const keys = await caches.keys();
        await Promise.all(keys.filter(n => n.startsWith(CACHE_PREFIX) && n !== CACHE_NAME)
            .map(n => caches.delete(n)));
        await self.clients.claim();
    })());
});

self.addEventListener('message', event => {
    if (event.data?.type === 'YKS_OFFLINE_VERSION' && event.ports?.[0]) {
        event.ports[0].postMessage({version: 10, cache: CACHE_NAME});
    }
});

self.addEventListener('fetch', event => {
    const request = event.request;
    if (request.method !== 'GET') return;
    const url = new URL(request.url);
    if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
    const isNavigation = request.mode === 'navigate';
    if (isNavigation && url.pathname !== '/') return;
    if (!isNavigation && !SHELL_SET.has(url.pathname)) return;
    event.respondWith((async () => {
        const cache = await caches.open(CACHE_NAME);
        if (url.search) {
            try {
                const fresh = await fetch(request);
                if (fresh && fresh.ok) {
                    await cache.put(isNavigation ? '/' : url.pathname, fresh.clone());
                    return fresh;
                }
            } catch (_) {}
        }
        const cached = await cache.match(isNavigation ? '/' : url.pathname);
        // Cache-first keeps HTML and JavaScript from the same installed release.
        // Updating a new release requires its own new Service Worker install.
        if (cached) return cached;
        // After unexpected cache eviction, online retrieval is allowed, but
        // no incomplete application shell is silently marked "offline ready".
        try { return await fetch(request, {cache: 'no-store'}); }
        catch (_) { return Response.error(); }
    })());
});
