/**
 * V8 read-only offline readiness audit. No mutation, personal data export,
 * network request, service-worker update, or automatic sync occurs here.
 */
(function (window) {
    'use strict';
    const CACHE = 'yks-kocluk-shell-v10';
    const ASSETS = ['/', '/static/js/offline_secure_store_v5.js',
        '/static/js/offline_vault.js', '/static/js/offline_coordinator_v7.js',
        '/static/js/offline_paged_v8.js', '/static/js/offline_delta_v9.js', '/static/js/offline_resilience_v10.js',
        '/static/js/offline_folder_v8.js', '/static/js/offline_sync.js',
        '/static/js/offline_health_v6.js', '/static/manifest.json',
        '/static/tailwindcss.js', '/static/vue.js',
        '/static/favicon.png', '/static/apple-touch-icon.png',
        '/static/icon-192.png', '/static/icon-512.png'];
    function outcome(code, ok, message, severity) {
        return {code, ok: Boolean(ok), message, severity: ok ? 'ok' : (severity || 'blocker')};
    }
    async function activeWorkerVersion(registration) {
        if (!registration?.active || !window.MessageChannel) return null;
        return new Promise(resolve => {
            const channel = new window.MessageChannel();
            let done = false;
            const finish = version => {
                if (done) return;
                done = true;
                clearTimeout(timer);
                channel.port1.close?.(); channel.port2.close?.();
                resolve(version);
            };
            const timer = setTimeout(() => finish(null), 1500);
            channel.port1.onmessage = event => finish(event.data?.version === 10 &&
                event.data?.cache === CACHE ? 10 : null);
            try { registration.active.postMessage({type:'YKS_OFFLINE_VERSION'}, [channel.port2]); }
            catch (_) { finish(null); }
        });
    }
    async function audit() {
        const results = [];
        const secure = window.isSecureContext === true && !!window.crypto?.subtle;
        results.push(outcome('secure', secure,
            secure ? 'Güvenli bağlantı ve şifreleme kullanılabilir.' :
                'Güvenli HTTPS/WebCrypto bulunamadı; çevrimdışı şifreleme kullanılamaz.'));
        results.push(outcome('indexeddb', !!window.indexedDB,
            window.indexedDB ? 'Yerel veritabanı özelliği mevcut.' :
                'IndexedDB kullanılamıyor; çevrimdışı işlemler saklanamaz.'));
        const sw = window.navigator?.serviceWorker;
        let active = false;
        try {
            const reg = await sw?.getRegistration?.('/');
            active = (await activeWorkerVersion(reg)) === 10;
        } catch (_) { /* Only indicates an incomplete readiness check. */ }
        results.push(outcome('worker', active,
            active ? 'V10 çevrimdışı uygulama çalışanı etkin.' :
                'V10 Service Worker henüz etkin değil; diğer sekmeleri kapatıp uygulamayı çevrimiçiyken yeniden açın.'));

        let missing = [...ASSETS];
        try {
            if (window.caches) {
                const cache = await window.caches.open(CACHE);
                missing = [];
                for (const asset of ASSETS) if (!await cache.match(asset)) missing.push(asset);
            }
        } catch (_) { missing = [...ASSETS]; }
        const shellReady = missing.length === 0;
        results.push(outcome('shell', shellReady,
            shellReady ? '17 temel uygulama dosyası çevrimdışı kullanılabilir.' :
                `${missing.length} temel uygulama dosyası eksik; çevrimdışı açılma güvenilir değil.`));

        // The snapshot can be locked. Don't unlock it or inspect student names.
        const sync = window.OfflineSync;
        const snapshot = sync?.lastSnapshot;
        const valid = Boolean(snapshot?.version === 1 && snapshot?.database_id &&
            Array.isArray(snapshot.students) && snapshot.curriculum &&
            typeof snapshot.curriculum === 'object');
        results.push(outcome('snapshot', valid,
            valid ? `${snapshot.students.length} öğrenci için yerel paket okunabilir.` :
                'Öğrenci paketi bulunamadı, kilitli veya geçersiz; önce giriş yapıp indirin.'));
        let configured = false;
        let sameDesktop = false;
        try {
            const dbid = await window.OfflineVault?.configuredDatabaseId?.();
            configured = !!dbid;
            sameDesktop = valid && dbid === snapshot.database_id;
        } catch (_) { /* Return a warning rather than exposing secrets. */ }
        results.push(outcome('offline-login', configured && sameDesktop,
            configured && sameDesktop ? 'Çevrimdışı giriş bu veritabanı için ayarlı.' :
                'Çevrimdışı giriş eksik veya masaüstü kimliği uyuşmuyor.'));
        let encrypted = false;
        try { encrypted = Boolean(await window.OfflineSecureStore?.enabled?.()); }
        catch (_) { /* Not ready */ }
        results.push(outcome('encrypted', encrypted,
            encrypted ? 'Yerel veriler için V5 şifrelemesi etkin.' :
                'Yerel çalışma alanı şifrelemesi etkin değil.', 'warning'));
        let usage = null, quota = null, persisted = false;
        try {
            const storage = window.navigator?.storage;
            const estimate = await storage?.estimate?.();
            usage = Number.isFinite(estimate?.usage) ? estimate.usage : null;
            quota = Number.isFinite(estimate?.quota) ? estimate.quota : null;
            persisted = Boolean(await storage?.persisted?.());
        } catch (_) { /* Browser-specific APIs may be missing. */ }
        const fraction = quota && usage !== null ? usage / quota : null;
        const enough = fraction === null || fraction < 0.8;
        results.push(outcome('headroom', enough,
            fraction === null ? 'Tarayıcı depolama kotası ölçülemedi.' :
                `Depolama kullanım oranı yaklaşık %${Math.round(fraction * 100)}.`,
            fraction === null ? 'warning' : 'blocker'));
        results.push(outcome('persistence', persisted,
            persisted ? 'Kalıcı depolama izni bildiriliyor.' :
                'Kalıcı depolama izni yok veya tarayıcı bildirmiyor; şifreli yedek alın.', 'warning'));
        const pending = Number.isSafeInteger(sync?.pendingCount) ? sync.pendingCount : null;
        return {
            version: 10, checked_at: new Date().toISOString(),
            ready: results.filter(x => x.severity === 'blocker').every(x => x.ok),
            pending, results, missing_assets: missing,
            note: 'Bu sonuç 7 günlük garanti veya gerçek telefon testi değildir. Tarayıcı saklamayı silebilir; bağımsız şifreli yedek gereklidir.'
        };
    }
    window.OfflineHealthV6 = Object.freeze({audit, requiredAssets: [...ASSETS], cacheName: CACHE});
})(window);
