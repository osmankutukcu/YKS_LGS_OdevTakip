/*
 * V7: per-origin cooperative synchronization serialization.
 * Web Locks first; an IndexedDB transactional lease on older browsers.
 * The server's idempotent receipts remain mandatory: a suspended tab may
 * resume after its fallback lease has expired, so ownership is rechecked.
 * This is coordination, not a distributed lock between different devices.
 */
(function (window) {
    'use strict';
    const DB_NAME = 'YKS_Offline_Store_v1';
    const DB_VERSION = 3;
    const LOCK_KEY = 'offline_v7_sync_lease';
    const LEASE_MS = 60000;
    const HEARTBEAT_MS = 8000;
    const failure = () => Error('Başka bir sekmede eşitleme yapılıyor veya kilit kaybedildi. İşlemler telefonda korundu.');

    function openDB() {
        return new Promise((resolve, reject) => {
            const r = indexedDB.open(DB_NAME, DB_VERSION);
            r.onupgradeneeded = () => {
                const d = r.result;
                if (!d.objectStoreNames.contains('snapshots')) d.createObjectStore('snapshots', {keyPath: 'key'});
                if (!d.objectStoreNames.contains('outbox')) d.createObjectStore('outbox', {keyPath: 'id'});
                if (!d.objectStoreNames.contains('meta')) d.createObjectStore('meta', {keyPath: 'key'});
            };
            r.onsuccess = () => resolve(r.result);
            r.onerror = () => reject(r.error);
            r.onblocked = () => reject(Error('Diğer sekmeler yerel veritabanını kilitliyor.'));
        });
    }
    async function transact(owner, kind) {
        const db = await openDB();
        try {
            return await new Promise((resolve, reject) => {
                const tx = db.transaction('meta', 'readwrite');
                const meta = tx.objectStore('meta');
                const read = meta.get(LOCK_KEY);
                let allowed = false, rejectReason = null;
                read.onsuccess = () => {
                    const now = Date.now();
                    const current = read.result?.value;
                    if (kind === 'acquire') {
                        allowed = !current || current.expires_at < now || current.owner === owner;
                        if (allowed) meta.put({key: LOCK_KEY, value: {owner, expires_at: now + LEASE_MS}});
                    } else if (kind === 'refresh') {
                        allowed = Boolean(current && current.owner === owner && current.expires_at >= now);
                        if (allowed) meta.put({key: LOCK_KEY, value: {owner, expires_at: now + LEASE_MS}});
                    } else if (kind === 'check') {
                        allowed = Boolean(current && current.owner === owner && current.expires_at >= now);
                    } else if (kind === 'release') {
                        allowed = Boolean(current && current.owner === owner);
                        if (allowed) meta.delete(LOCK_KEY);
                    }
                    if (!allowed && kind !== 'release') rejectReason = failure();
                };
                tx.oncomplete = () => rejectReason ? reject(rejectReason) : resolve(allowed);
                tx.onerror = () => reject(tx.error || Error('Yerel senkronizasyon kilidi alınamadı.'));
                tx.onabort = () => reject(tx.error || Error('Yerel senkronizasyon kilidi geri alındı.'));
            });
        } finally { db.close(); }
    }
    async function runExclusive(task) {
        if (typeof task !== 'function') throw TypeError('Eşitleme görevi eksik.');
        if (window.navigator?.locks?.request) {
            return window.navigator.locks.request('yks-offline-sync-v7',
                {mode: 'exclusive', ifAvailable: true}, async lock => {
                    if (!lock) throw failure();
                    return task({assertOwned: async () => true, method: 'web-locks'});
                });
        }
        const owner = (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() :
            (window.crypto && window.crypto.getRandomValues ? (() => {
                const b = new Uint8Array(16);
                window.crypto.getRandomValues(b);
                b[6] = (b[6] & 0x0f) | 0x40;
                b[8] = (b[8] & 0x3f) | 0x80;
                const hex = Array.from(b, x => x.toString(16).padStart(2, '0')).join('');
                return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
            })() : ('tab-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10)));
        await transact(owner, 'acquire');
        let lost = false;
        const timer = setInterval(() => {
            transact(owner, 'refresh').catch(() => { lost = true; });
        }, HEARTBEAT_MS);
        try {
            return await task({
                method: 'indexeddb-lease',
                assertOwned: async () => {
                    if (lost) throw failure();
                    await transact(owner, 'check');
                }
            });
        } finally {
            clearInterval(timer);
            try { await transact(owner, 'release'); } catch (_) { /* expiry allows recovery */ }
        }
    }
    // Retry only failures that are probably transport interruptions. Do not
    // replay 401, validation or conflict errors from the existing API caller.
    function isTransient(error) {
        const message = String(error?.message || '');
        return error?.name === 'AbortError' ||
            /Failed to fetch|NetworkError|network connection|ERR_NETWORK/i.test(message);
    }
    async function sendWithRetry(send, options = {}) {
        const delay = options.delay || (ms => new Promise(resolve => setTimeout(resolve, ms)));
        const assertOwned = options.assertOwned || (async () => {});
        const attempts = options.attempts || 3;
        for (let n = 0; n < attempts; n++) {
            await assertOwned();
            try { return await send(); }
            catch (error) {
                if (!isTransient(error) || n === attempts - 1) throw error;
                // finite bounded delay; no silent indefinite background retries
                await delay(Math.min(500 * (2 ** n), 4000));
            }
        }
    }
    window.OfflineCoordinatorV7 = Object.freeze({runExclusive, sendWithRetry, isTransient});
})(window);
