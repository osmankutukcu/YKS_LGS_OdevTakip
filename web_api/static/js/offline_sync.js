/**
 * YKS-LGS Koçluk Mobil - Modüler Çevrimdışı (Offline-First) Senkronizasyon Kütüphanesi
 * ====================================================================================
 * Özellikler:
 * 1. Tarayıcı yerel veri tabanı (IndexedDB) kullanarak tüm müfredat ve ödev verilerini
 *    telefon hafızasında güvenle saklar.
 * 2. Bilgisayar kapalıyken veya internet yokken ödev vermeyi ve takip yapmayı sağlar.
 * 3. Çevrimdışı yapılan tüm işlemleri güvenli bir giden kutusunda (Outbox Queue) biriktirir.
 * 4. Bilgisayar açıldığında tek bir tıkla tüm yeni ödevleri ana bilgisayara aktarır.
 */

(function (window) {
    'use strict';

    const DB_NAME = 'YKS_Offline_Store_v1';
    const DB_VERSION = 3;

    let dbInstance = null;

    function openDB() {
        return new Promise((resolve, reject) => {
            if (dbInstance) return resolve(dbInstance);

            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('snapshots')) {
                    db.createObjectStore('snapshots', { keyPath: 'key' });
                }
                if (!db.objectStoreNames.contains('outbox')) {
                    db.createObjectStore('outbox', { keyPath: 'id' });
                }
                if (!db.objectStoreNames.contains('meta')) {
                    db.createObjectStore('meta', { keyPath: 'key' });
                }
            };
            req.onsuccess = (e) => {
                dbInstance = e.target.result;
                dbInstance.onversionchange = () => { dbInstance.close(); dbInstance = null; };
                resolve(dbInstance);
            };
            req.onerror = (e) => reject(e.target.error);
            req.onblocked = () => reject(new Error('Diğer açık sekmeleri kapatıp tekrar deneyin.'));
        });
    }

    async function dbGet(storeName, key) {
        const db = await openDB();
        const value = await new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readonly');
            const req = tx.objectStore(storeName).get(key);
            tx.oncomplete = () => resolve(req.result ? req.result.value : null);
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error);
        });
        return storeName === 'snapshots' ? window.OfflineSecureStore.openRecord('snapshots', key, value) : value;
    }

    // Resolve only after transaction commit; request success alone is not durable.
    async function dbPut(storeName, key, value) {
        const safe = storeName === 'snapshots' ? await window.OfflineSecureStore.sealRecord('snapshots', key, value) : value;
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite');
            tx.objectStore(storeName).put({ key, value: safe });
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error || new Error('IndexedDB kayıt işlemi iptal edildi'));
        });
    }

    // V6: Persist only the server-authored baseline, NEVER a projection of
    // pending local edits. The outbox is durable and replayed in memory.
    // Fail closed if another tab changes the queue while the server snapshot
    // is being downloaded/decrypted/sealed.
    async function dbPutServerBaselineIfQueueStable(snapshot, pending) {
        const safe = await window.OfflineSecureStore.sealRecord('snapshots', 'current', snapshot);
        const expected = pending.map(x => `${x.id}:${x.seq}`).sort();
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(['snapshots', 'outbox'], 'readwrite');
            const check = tx.objectStore('outbox').getAll();
            let cause = null;
            check.onsuccess = () => {
                const now = (check.result || []).map(x => `${x.id}:${x.seq}`).sort();
                if (now.length !== expected.length || now.some((id, i) => id !== expected[i])) {
                    cause = new Error('İşlem kuyruğu indirme sırasında değişti; eski kayıtlar korunuyor. Yeniden deneyin.');
                    tx.abort();
                    return;
                }
                tx.objectStore('snapshots').put({key: 'current', value: safe});
            };
            tx.oncomplete = () => resolve(true);
            tx.onabort = () => reject(cause || tx.error || Error('Snapshot kaydedilemedi.'));
            tx.onerror = () => {};
        });
    }

    async function dbGetAllOutbox() {
        const db = await openDB();
        const raw = await new Promise((resolve, reject) => {
            const tx = db.transaction('outbox', 'readonly');
            const req = tx.objectStore('outbox').getAll();
            tx.oncomplete = () => resolve(req.result || []);
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error);
        });
        const commands = await window.OfflineSecureStore.openRecords('outbox',raw);
        return commands.sort((a,b) => (a.seq ?? 0)-(b.seq ?? 0) ||
            (a.created_at || '').localeCompare(b.created_at || '') || a.id.localeCompare(b.id));
    }

    async function dbCountOutbox() {
        const db=await openDB();
        return new Promise((resolve,reject)=>{
            const tx=db.transaction('outbox','readonly');
            const req=tx.objectStore('outbox').count();
            tx.oncomplete=()=>resolve(req.result||0);
            tx.onerror=()=>reject(tx.error);
            tx.onabort=()=>reject(tx.error);
        });
    }

    async function dbAddOutbox(item) {
        const encrypted = await window.OfflineSecureStore.sealRecord('outbox',item.id,item);
        const secured = await window.OfflineSecureStore.enabled();
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(['outbox', 'meta'], 'readwrite');
            const meta = tx.objectStore('meta');
            const req = meta.get('next_seq');
            req.onsuccess = () => {
                const seq = (req.result?.value || 0) + 1;
                meta.put({ key: 'next_seq', value: seq });
                const value = secured ? {id:item.id,seq,encrypted} : {...item,seq};
                // For encrypted rows, sequence is inside the sealed payload too.
                tx.objectStore('outbox').add(value);
            };
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error || new Error('Bekleyen işlem saklanamadı'));
        });
    }

    // Do not delete commands created after a request started. Only acknowledged IDs.
    async function dbDeleteAcknowledged(ids) {
        if (!ids.length) return;
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('outbox', 'readwrite');
            for (const id of ids) tx.objectStore('outbox').delete(id);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error);
        });
    }

    // Conflict resolution never overwrites desktop state silently. Only the
    // oldest independent status-change command may be replaced or discarded.
    async function resolveQueuedConflict(id, choice, freshSnapshot) {
        if (!['desktop','mobile'].includes(choice)) throw Error('Geçersiz çözüm tercihi');
        const queue = await dbGetAllOutbox();
        const old = queue.find(x => x.id === id);
        if (!old || old.type !== 'SET_HOMEWORK_STATUS') throw Error('Yalnızca ödev durum çakışmaları çözülebilir.');
        const ids = (old.payload?.homework_ids||[]).map(String);
        if (queue.some(x => x.seq > old.seq))
            throw Error('Aynı ödev için sonraki bekleyen işlemler var; sıralamayı korumak için bu çakışmayı otomatik çözemiyoruz.');
        if (queue.some(x => x.seq < old.seq))
            throw Error('Önceki işlem henüz bekliyor. Sıralı eşitleme için önce onu çözün.');
        const previous = {}, fingerprints = {};
        for (const id of ids) {
            let item, token;
            for (const curriculum of Object.values(freshSnapshot.curriculum||{})) {
                item=(curriculum.active_homeworks||[]).find(x=>String(x.id)===id);
                if (item) {token=curriculum.status_fingerprints?.[id];break;}
            }
            if (!item || !token) throw Error('Ödevin masaüstündeki güncel hâli doğrulanamadı.');
            previous[id]=isDone(item.status)?'tamam':'devam';
            fingerprints[id]=token;
        }
        const replacement = choice === 'mobile' ? {
            id:newMutationId(),type:'SET_HOMEWORK_STATUS',
            payload:{...old.payload,expected_statuses:previous,expected_fingerprints:fingerprints},
            created_at:new Date().toISOString()
        } : null;
        const sealed = replacement ? await window.OfflineSecureStore.sealRecord('outbox', replacement.id,replacement):null;
        const secured = await window.OfflineSecureStore.enabled();
        const db=await openDB();
        await new Promise((resolve,reject)=>{
            const tx=db.transaction('outbox','readwrite');
            const store=tx.objectStore('outbox');
            const check=store.getAll();
            let reason=null;
            check.onsuccess=()=>{
                const raw=check.result||[];
                const stored=raw.find(x=>x.id===id);
                if(!stored||stored.seq!==old.seq||raw.some(x=>x.seq>old.seq)) {
                    reason=Error('İşlem kuyruğu değişti. Çözüm tekrarlanmalı.');tx.abort();return;
                }
                // Compare the ciphertext envelope by identity using a read-before
                // action; no automatic retry can silently duplicate this action.
                store.delete(id);
                if (replacement) store.add(secured ? {id:replacement.id,seq:old.seq,encrypted:sealed} :
                    {...replacement,seq:old.seq});
            };
            tx.oncomplete=resolve;
            tx.onabort=()=>reject(reason||tx.error||Error('Çözüm işlemi geri alındı.'));
            tx.onerror=()=>{};
        });
        return {removed:id,replacement:replacement?.id||null};
    }

    function newMutationId() {
        const uuid = (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() :
            (window.crypto && window.crypto.getRandomValues ? (() => {
                const b = new Uint8Array(16);
                window.crypto.getRandomValues(b);
                b[6] = (b[6] & 0x0f) | 0x40;
                b[8] = (b[8] & 0x3f) | 0x80;
                const hex = Array.from(b, x => x.toString(16).padStart(2, '0')).join('');
                return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
            })() : (Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10)));
        return 'mut_' + uuid;
    }

    function isDone(v) {
        return ['tamam', 'yapildi', 'yapıldı'].includes(String(v || '').toLowerCase());
    }

    // Deterministic local projection. Server snapshot is not authoritative for
    // outstanding local changes; replay them without creating server IDs.
    function projectOutbox(snapshot, pending) {
        const copy = JSON.parse(JSON.stringify(snapshot));
        for (const item of pending) {
            const p = item.payload || {};
            if (item.type === 'SET_HOMEWORK_STATUS') {
                const changed = new Set((p.homework_ids || []).map(String));
                for (const curriculum of Object.values(copy.curriculum || {})) {
                    for (const h of curriculum.active_homeworks || []) {
                        if (changed.has(String(h.id))) h.status = p.status;
                    }
                    for (const lessonTopics of Object.values(curriculum.topics || {})) {
                        for (const topic of lessonTopics || []) {
                            for (const assigned of topic.assignments || []) {
                                if (!changed.has(String(assigned.homework_id))) continue;
                                const done = p.status === 'tamam';
                                assigned.status = done ? 'tamam' : 'devam';
                                assigned.raw_status = p.status;
                                assigned.label = done ? 'Yapıldı' : 'Devam Ediyor';
                                assigned.color = done ? 'green' : 'yellow';
                            }
                        }
                    }
                }
            } else if (item.type === 'ASSIGN_HOMEWORK') {
                const c = (copy.curriculum || {})[p.student_id];
                if (!c) continue;
                const lesson = p.lesson;
                const topicList = (c.topics || {})[lesson] || [];
                for (const name of p.topics || []) {
                    const topic = topicList.find(t => t.name === name);
                    if (!topic) continue;
                    if (!topic.assignments) topic.assignments = [];
                    // Show a pending local assignment, never fabricate a server id.
                    if (!topic.assignments.some(a => a.local_mutation_id === item.id)) {
                        topic.assignments.push({
                            homework_id: null, local_mutation_id: item.id,
                            book: p.book, status: 'devam', raw_status: 'devam',
                            label: 'Aktarım Bekliyor', color: 'yellow',
                            due_date: p.due_date || '', due_date_formatted: p.due_date || '',
                            given_date: (item.created_at || '').slice(0, 10), days: 0
                        });
                    }
                }
            }
        }
        return copy;
    }

    const OfflineSync = {
        isServerOnline: true,
        lastSnapshot: null,
        pendingCount: 0,
        lastFailures: [],
        listeners: [],

        onStatusChange(fn) {
            this.listeners.push(fn);
        },

        notify() {
            this.listeners.forEach(fn => {
                try { fn(this); } catch (e) { console.error(e); }
            });
        },

        async reloadLocal() {
            this.lastSnapshot = await dbGet('snapshots','current');
            const outbox = await dbGetAllOutbox();
            if (this.lastSnapshot && outbox.length) {
                this.lastSnapshot = projectOutbox(this.lastSnapshot,outbox);
            }
            this.pendingCount = outbox.length;
            this.notify();
            return this.lastSnapshot;
        },

        async init() {
            try {
                await this.reloadLocal();

                // Check server connection
                await this.checkConnection();

                // If server is online and no snapshot yet, auto-download in background
                if (this.isServerOnline && !this.lastSnapshot) {
                    try {
                        await this.downloadSnapshot();
                    } catch (e) {
                        console.log('[OfflineSync] initial auto-download skipped:', e);
                    }
                }

                this.notify();
            } catch (err) {
                console.warn('[OfflineSync] init error:', err);
            }
        },

        async checkConnection() {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 2000);

                const key = sessionStorage.getItem('yks_access') || '';
                const headers = { 'X-Access-Key': key };

                const res = await fetch('/api/sync/status', {
                    method: 'GET',
                    headers,
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
                if (res.ok) {
                    const status = await res.json();
                    this.serverDatabaseId = status.database_id || null;
                    this.databaseMismatch = Boolean(this.lastSnapshot?.database_id &&
                        this.serverDatabaseId && this.lastSnapshot.database_id !== this.serverDatabaseId);
                    this.isServerOnline = !this.databaseMismatch;
                } else {
                    this.isServerOnline = false;
                }
            } catch (e) {
                this.isServerOnline = false;
            }
            this.notify();
            return this.isServerOnline;
        },

        async downloadSnapshot(studentId = null, heldLock = false, guard = null) {
            if (!heldLock && window.OfflineCoordinatorV7) {
                try {
                    return await window.OfflineCoordinatorV7.runExclusive(lock => this.downloadSnapshot(studentId, true, lock));
                } catch (coordErr) {
                    console.warn('[OfflineSync] Coordinator lock fallback:', coordErr);
                    return await this.downloadSnapshot(studentId, true, null);
                }
            }
            if (this.restoring || window.OfflineSecureStore.busy) throw new Error('Güvenli yerel işlem sırasında veri indirilemez.');
            // The UI cache is a full snapshot. A filtered subset must not
            // silently erase other students when written under 'current'.
            if (studentId !== null && studentId !== undefined) {
                throw new Error('Tek öğrenci paketi tam çevrimdışı verinin üzerine yazılamaz');
            }
            // V9: read only the persisted server baseline; NEVER use the UI
            // projection with unacknowledged local outbox commands as input.
            // Legacy V8 baseline stays compatible, with V8 full-download fallback.
            let data;
            this.lastDeltaStats = null;
            try {
                const persistedBaseline = await dbGet('snapshots', 'current');
                if (persistedBaseline && window.OfflineDeltaV9) {
                    try {
                        const result = await window.OfflineDeltaV9.download({
                            api: window._originalApi, baseline: persistedBaseline,
                            expectedDatabaseId: this.lastSnapshot?.database_id || persistedBaseline.database_id,
                            assertOwned: guard ? () => guard.assertOwned() : async () => {},
                            progress: (page,total) => { this.downloadProgress={page,total};this.notify(); }
                        });
                        data = result.snapshot;
                        this.lastDeltaStats = result.stats;
                    } catch (deltaError) {
                        // V10: HTTP 404 (older server), 410 (expired page session),
                        // or 503 (temporary busy) may use a full, DB-ID-verified V8
                        // download. Auth/DB mismatch/integrity/conflict NEVER fall back.
                        if (!window.OfflineResilienceV10?.canUseFullSnapshot(deltaError) ||
                            !window.OfflinePagedV8) throw deltaError;
                        if (guard) await guard.assertOwned();
                        data = await window.OfflinePagedV8.download({
                            api: window._originalApi,
                            expectedDatabaseId: this.lastSnapshot?.database_id || persistedBaseline.database_id,
                            assertOwned: guard ? () => guard.assertOwned() : async () => {},
                            progress: (page,total) => {
                                this.downloadProgress={page,total};this.notify();
                            }
                        });
                        this.lastDeltaStats = {fallback: true, reason: 'V9 geçici olarak kullanılamadı',
                            total: data.students?.length ?? null};
                    }
                } else {
                    try {
                        data = window.OfflinePagedV8 ? await window.OfflinePagedV8.download({
                            api: window._originalApi,
                            expectedDatabaseId: this.lastSnapshot?.database_id || null,
                            assertOwned: guard ? () => guard.assertOwned() : async () => {},
                            progress: (page, total) => {
                                this.downloadProgress = {page,total}; this.notify();
                            }
                        }) : await window._originalApi('/api/sync/snapshot');
                    } catch (pagedErr) {
                        console.warn('[OfflineSync] Parçalı indirme hatası, tam anlık görüntüye geçiliyor:', pagedErr);
                        data = await window._originalApi('/api/sync/snapshot');
                    }
                }
            } finally {
                this.downloadProgress = null;
                this.notify();
            }

            if (!data || data.version !== 1 || !Array.isArray(data.students) || !data.curriculum) {
                throw new Error('Eksik veya uyumsuz çevrimdışı veri paketi');
            }
            if (guard) await guard.assertOwned();
            const pending = await dbGetAllOutbox();
            if (pending.length && this.lastSnapshot?.database_id && data.database_id !== this.lastSnapshot.database_id) {
                throw new Error('Bu telefonun kayıtları başka bir masaüstü veritabanına ait; aktarım durduruldu.');
            }
            const merged = projectOutbox(data, pending);
            if (guard) await guard.assertOwned();
            await dbPutServerBaselineIfQueueStable(data, pending);
            this.lastSnapshot = merged;
            this.snapshotRefreshNeeded = false;
            this.lastSnapshotError = null;
            await dbPut('meta', 'last_download_time', new Date().toISOString());
            if (navigator.storage?.persist) {
                try { this.storagePersistent = await navigator.storage.persist(); }
                catch (_) { this.storagePersistent = false; }
            }
            this.notify();
            return data;
        },

        async queueAssignHomework({ student_id, lesson, book, topics, due_date }) {
            if (this.restoring || window.OfflineSecureStore.busy) throw new Error('Güvenli yerel işlem sırasında yeni işlem kaydedilemez.');
            const localNow = new Date();
            const localDate = [localNow.getFullYear(), String(localNow.getMonth() + 1).padStart(2, '0'),
                String(localNow.getDate()).padStart(2, '0')].join('-');
            const mutation = {
                id: newMutationId(),
                type: 'ASSIGN_HOMEWORK',
                payload: {
                    student_id,
                    lesson,
                    book,
                    topics,
                    due_date,
                    assigned_local_date: localDate
                },
                created_at: new Date().toISOString()
            };

            await dbAddOutbox(mutation);
            this.pendingCount = await dbCountOutbox();

            // Local projections never use fabricated server-side IDs.
            if (this.lastSnapshot) {
                this.lastSnapshot = projectOutbox(this.lastSnapshot, [mutation]);
                // Local state is reconstructed from baseline + durable outbox on reload.
            }

            this.notify();
            return mutation;
        },

        async queueCompleteHomework(lineId) {
            if (this.restoring || window.OfflineSecureStore.busy) throw new Error('Güvenli yerel işlem sırasında yeni işlem kaydedilemez.');
            const mutation = {
                id: newMutationId(), type: 'COMPLETE_HOMEWORK',
                payload: { line_id: lineId }, created_at: new Date().toISOString()
            };
            await dbAddOutbox(mutation);
            this.pendingCount = await dbCountOutbox();
            this.notify();
            return mutation;
        },

        async queueSetHomeworkStatus({ homework_ids, status }) {
            if (this.restoring || window.OfflineSecureStore.busy) throw new Error('Güvenli yerel işlem sırasında yeni işlem kaydedilemez.');
            if (!Array.isArray(homework_ids) || !homework_ids.length ||
                !['tamam', 'devam'].includes(status)) throw new Error('Geçersiz durum isteği');
            const ids = [...new Set(homework_ids.map(Number))];
            const snap = this.lastSnapshot;
            if (!snap || ids.some(n => !Number.isSafeInteger(n) || n <= 0)) {
                throw new Error('Çevrimdışı durum değişikliği için kayıtlı ödevler gerekli');
            }
            const previous = {};
            const fingerprints = {};
            const queued = await dbGetAllOutbox();
            for (const id of ids) {
                let item = null;
                let fingerprint = null;
                for (const c of Object.values(snap.curriculum || {})) {
                    item = (c.active_homeworks || []).find(h => String(h.id) === String(id));
                    if (item) { fingerprint = c.status_fingerprints?.[String(id)]; break; }
                }
                if (!item) throw new Error(`Ödev #${id} kayıtlı çevrimdışı pakette bulunamadı`);
                previous[String(id)] = isDone(item.status) ? 'tamam' : 'devam';
                // If an earlier local command will change this homework first,
                // its eventual completed_at is unknown. Use expected status
                // for the dependent command instead of a stale fingerprint.
                const hasOlder = queued.some(m => m.type === 'SET_HOMEWORK_STATUS' &&
                    (m.payload?.homework_ids || []).some(n => String(n) === String(id)));
                if (!hasOlder && fingerprint) fingerprints[String(id)] = fingerprint;
            }
            const mutation = {
                id: newMutationId(), type: 'SET_HOMEWORK_STATUS',
                payload: { homework_ids: ids, status, expected_statuses: previous,
                    expected_fingerprints: fingerprints },
                created_at: new Date().toISOString()
            };
            await dbAddOutbox(mutation);
            this.pendingCount = await dbCountOutbox();
            // Keep the durable outbox as source of truth if projection fails.
            if (this.lastSnapshot) {
                this.lastSnapshot = projectOutbox(this.lastSnapshot, [mutation]);
                // Local state is reconstructed from baseline + durable outbox on reload.
            }
            this.notify();
            return mutation;
        },

        async pushSync(heldLock = false, lockGuard = null) {
            if (!heldLock && window.OfflineCoordinatorV7) {
                try {
                    return await window.OfflineCoordinatorV7.runExclusive(guard => this.pushSync(true, guard));
                } catch (coordErr) {
                    console.warn('[OfflineSync] Coordinator pushSync fallback:', coordErr);
                    return await this.pushSync(true, null);
                }
            }
            if (this.restoring || window.OfflineSecureStore.busy) throw new Error('Güvenli yerel işlem sırasında aktarım yapılamaz.');
            if (this.syncing) throw new Error('Eşitleme zaten devam ediyor');
            this.syncing = true;
            try {
                if (!(await this.checkConnection())) {
                    throw new Error(this.databaseMismatch ? 'Yanlış masaüstü veritabanı! Telefon kuyruğu korundu.' : 'Bilgisayara ulaşılamadı; kayıtlar telefonda korunuyor.');
                }
                const outbox = await dbGetAllOutbox();
                if (outbox.length && !this.lastSnapshot?.database_id) {
                    throw new Error('Masaüstü kimliği doğrulanamıyor. Bekleyen işlemler korunuyor; önce şifreli yedeği kontrol edin.');
                }
                if (!outbox.length) {
                    await this.downloadSnapshot(null, true, lockGuard);
                    return { success: true, processed_count: 0, acknowledged_count: 0, remaining: 0 };
                }
                // Limit each server batch, retaining order, so a week of edits
                // need not be transferred in a single oversize request.
                let acknowledged = 0;
                let newlyApplied = 0;
                const failures = [];
                this.lastFailures = [];
                for (let start = 0; start < outbox.length; start += 100) {
                    const batch = outbox.slice(start, start + 100);
                    const send = () => window._originalApi('/api/sync/push', 'POST', {
                        mutations: batch, database_id: this.lastSnapshot?.database_id || null
                    });
                    const result = window.OfflineCoordinatorV7
                        ? await window.OfflineCoordinatorV7.sendWithRetry(send, {
                            assertOwned: lockGuard?.assertOwned || (async () => {})
                        }) : await send();
                    if (!Array.isArray(result?.results) || result.results.length !== batch.length) {
                        throw new Error('Sunucudan eksik veya geçersiz işlem onayı geldi. Kuyruk silinmedi.');
                    }
                    const sent = new Set(batch.map(m => m.id));
                    const returned = new Set(result.results.map(r => r.id));
                    if (returned.size !== sent.size || [...returned].some(id => !sent.has(id))) {
                        throw new Error('Sunucu işlem kimlikleri uyuşmuyor. Kuyruk silinmedi.');
                    }
                    if (lockGuard) await lockGuard.assertOwned();
                    const ids = result.results.filter(r => sent.has(r.id) &&
                        (r.status === 'applied' || r.status === 'already_applied')).map(r => r.id);
                    await dbDeleteAcknowledged(ids);
                    acknowledged += ids.length;
                    newlyApplied += result.results.filter(r => sent.has(r.id) && r.status === 'applied').length;
                    failures.push(...result.results.filter(r => sent.has(r.id) &&
                        r.status !== 'applied' && r.status !== 'already_applied'));
                    this.pendingCount = await dbCountOutbox();
                    this.notify();
                    // An earlier error could make later changes logically dependent;
                    // stop here and leave them pending for review.
                    if (failures.length) break;
                }
                // Merge remaining local mutations on top of fresh server state.
                this.lastFailures = failures;
                try {
                    await this.downloadSnapshot(null, true, lockGuard);
                    this.snapshotRefreshNeeded = false;
                } catch (refreshError) {
                    // Receipts were already committed; never repopulate acknowledged
                    // mutations or describe old baseline as current.
                    this.snapshotRefreshNeeded = true;
                    this.lastSnapshotError = refreshError.message;
                    this.notify();
                }
                return { success: failures.length === 0 && !this.snapshotRefreshNeeded, processed_count: newlyApplied,
                    acknowledged_count: acknowledged, remaining: this.pendingCount, failures,
                    snapshot_refresh_needed: !!this.snapshotRefreshNeeded };
            } finally {
                this.syncing = false;
                this.notify();
            }
        },

        async reviewConflict(id) {
            if (!await this.checkConnection()) throw Error('Çözüm için masaüstü bağlantısı gerekli.');
            const failure=this.lastFailures.find(x=>x.id===id && x.status==='conflict');
            if(!failure)throw Error('Bu işlem için doğrulanmış çakışma bulunamadı.');
            const fresh=await window._originalApi('/api/sync/snapshot');
            if(!fresh?.database_id||fresh.database_id!==this.lastSnapshot?.database_id)
                throw Error('Masaüstü veritabanı uyuşmuyor.');
            const queue=await dbGetAllOutbox();
            const item=queue.find(x=>x.id===id && x.type==='SET_HOMEWORK_STATUS');
            if(!item)throw Error('Çakışma kaydı artık kuyrukta yok.');
            return {item,server:fresh};
        },

        async resolveConflict(id, choice, heldLock = false, lockGuard = null) {
            if (!heldLock && window.OfflineCoordinatorV7) {
                try {
                    return await window.OfflineCoordinatorV7.runExclusive(lock => this.resolveConflict(id, choice, true, lock));
                } catch (coordErr) {
                    console.warn('[OfflineSync] Coordinator resolveConflict fallback:', coordErr);
                    return await this.resolveConflict(id, choice, true, null);
                }
            }
            if(this.syncing || this.restoring || window.OfflineSecureStore.busy)
                throw Error('Başka bir yerel işlem devam ediyor.');
            this.restoring=true;
            try {
                const reviewed=await this.reviewConflict(id);
                const result=await resolveQueuedConflict(id,choice,reviewed.server);
                this.lastFailures=this.lastFailures.filter(x=>x.id!==id);
                this.restoring=false;
                await this.downloadSnapshot(null, true, lockGuard);
                this.pendingCount=(await dbGetAllOutbox()).length;
                this.notify();
                return result;
            } finally{this.restoring=false;}
        },

        // --- OFFLINE API INTERCEPTOR ---
        async handleOfflineApi(url, method = 'GET', body = null) {
            console.log('[OfflineSync] Intercepting offline API call:', method, url);
            const snapshot = this.lastSnapshot;

            if (!snapshot) {
                throw new Error('Çevrimdışı veri bulunamadı. Lütfen önce bilgisayar açıkken "Telefona İndir" butonuna basınız.');
            }

            // 1. Dashboard
            if (url.startsWith('/api/dashboard')) {
                const totalStudents = snapshot.students ? snapshot.students.length : 0;
                let activeTasks = 0;
                if (snapshot.curriculum) {
                    Object.values(snapshot.curriculum).forEach(c => {
                        activeTasks += (c.active_homeworks || []).filter(h => !isDone(h.status)).length;
                    });
                }
                return {
                    student_count: totalStudents,
                    pending_tasks: activeTasks,
                    success_rate: (() => { const all = Object.values(snapshot.curriculum || {}).flatMap(c => c.active_homeworks || []); return all.length ? Math.round(all.filter(h => isDone(h.status)).length / all.length * 100) : 0; })()
                };
            }

            // 2. Students list
            if (url.startsWith('/api/students')) {
                const todayStr = new Date().toISOString().slice(0, 10);
                const tmrw = new Date();
                tmrw.setDate(tmrw.getDate() + 1);
                const tmrwStr = tmrw.toISOString().slice(0, 10);
                const weekEnd = new Date();
                weekEnd.setDate(weekEnd.getDate() + 7);
                const weekEndStr = weekEnd.toISOString().slice(0, 10);

                return (snapshot.students || []).map(std => {
                    const activeHws = snapshot.curriculum?.[std.id]?.active_homeworks || [];
                    let overdue = 0, today = 0, tomorrow = 0, week = 0, pending = 0;
                    for (const h of activeHws) {
                        if (!isDone(h.status)) {
                            pending++;
                            const d = (h.due_date || '').slice(0, 10);
                            if (d && d < todayStr) overdue++;
                            else if (d === todayStr) today++;
                            else if (d === tmrwStr) tomorrow++;
                            if (d && d >= todayStr && d <= weekEndStr) week++;
                        }
                    }
                    return {
                        ...std,
                        overdue_count: overdue,
                        today_count: today,
                        tomorrow_count: tomorrow,
                        week_count: week,
                        pending_count: pending
                    };
                });
            }

            // 3. Lessons list
            if (url.startsWith('/api/lessons/list')) {
                const match = url.match(/student_id=([0-9]+)/);
                const sId = match ? match[1] : (snapshot.students[0] ? snapshot.students[0].id : null);
                if (sId && snapshot.curriculum && snapshot.curriculum[sId]) {
                    return snapshot.curriculum[sId].lessons || [];
                }
                // Fallback: collect unique lessons across curriculum
                const allL = [];
                const seen = new Set();
                Object.values(snapshot.curriculum || {}).forEach(c => {
                    (c.lessons || []).forEach(l => {
                        if (!seen.has(l.id)) { seen.add(l.id); allL.push(l); }
                    });
                });
                return allL;
            }

            // 4. Books
            if (url.startsWith('/api/student/') && url.includes('/books/')) {
                const parts = url.split('/');
                const sId = parts[3];
                const lId = decodeURIComponent(parts[5]);
                if (snapshot.curriculum && snapshot.curriculum[sId] && snapshot.curriculum[sId].books) {
                    return snapshot.curriculum[sId].books[lId] || [];
                }
                return [];
            }
            if (url.startsWith('/api/books/')) {
                const lId = decodeURIComponent(url.split('/api/books/')[1]);
                for (let sId in (snapshot.curriculum || {})) {
                    const bList = snapshot.curriculum[sId]?.books?.[lId];
                    if (bList && bList.length) return bList;
                }
                return [];
            }

            // 5. Topics list with assignments
            if (url.startsWith('/api/topics/list')) {
                const u = new URL(url, 'http://localhost');
                const lId = u.searchParams.get('lesson_id');
                const sId = u.searchParams.get('student_id');
                if (sId && lId && snapshot.curriculum && snapshot.curriculum[sId]) {
                    return snapshot.curriculum[sId].topics?.[lId] || [];
                }
                return [];
            }

            // 6. Tracking (Tab 4 Ödev Kontrol)
            if (url.startsWith('/api/student/') && url.includes('/tracking')) {
                const sId = url.split('/')[3];
                const query = new URL(url, window.location.origin).searchParams;
                const lesson = query.get('lesson');
                const filter = query.get('status');
                const dateFilter = query.get('date_filter');
                const todayStr = new Date().toISOString().slice(0, 10);
                const tmrw = new Date();
                tmrw.setDate(tmrw.getDate() + 1);
                const tmrwStr = tmrw.toISOString().slice(0, 10);
                const weekEnd = new Date();
                weekEnd.setDate(weekEnd.getDate() + 7);
                const weekEndStr = weekEnd.toISOString().slice(0, 10);

                const items = (snapshot.curriculum?.[sId]?.active_homeworks || []).filter(h => {
                    const done = isDone(h.status);
                    if (lesson && lesson !== 'Hepsi' && h.lesson !== lesson) return false;
                    if (filter === 'Yapılanlar' && !done) return false;
                    if (filter === 'Yapılmayanlar' && done) return false;
                    if (dateFilter && dateFilter !== 'all') {
                        const d = (h.due_date || '').slice(0, 10);
                        if (dateFilter === 'overdue' && (done || !d || d >= todayStr)) return false;
                        if (dateFilter === 'today' && (done || d !== todayStr)) return false;
                        if (dateFilter === 'tomorrow' && (done || d !== tmrwStr)) return false;
                        if (dateFilter === 'week' && (done || !d || d < todayStr || d > weekEndStr)) return false;
                    }
                    return true;
                });
                const doneCount = items.filter(x => isDone(x.status)).length;
                return {
                    items: items,
                    stats: {
                        total: items.length,
                        completed: doneCount,
                        percent: items.length ? Math.round((doneCount / items.length) * 100) : 0,
                        active: items.length - doneCount
                    }
                };
            }

            // 6b. WhatsApp Report (Çevrimdışı WhatsApp Raporu)
            if (url.startsWith('/api/student/') && url.includes('/whatsapp') && method === 'POST') {
                const sId = url.split('/')[3];
                const query = new URL(url, window.location.origin).searchParams;
                const lesson = query.get('lesson');
                const filter = query.get('status');
                const dateFilter = query.get('date_filter');
                const std = (snapshot.students || []).find(s => String(s.id) === String(sId));
                const studentName = std ? std.ad_soyad : 'Öğrenci';

                const todayStr = new Date().toISOString().slice(0, 10);
                const tmrw = new Date();
                tmrw.setDate(tmrw.getDate() + 1);
                const tmrwStr = tmrw.toISOString().slice(0, 10);
                const weekEnd = new Date();
                weekEnd.setDate(weekEnd.getDate() + 7);
                const weekEndStr = weekEnd.toISOString().slice(0, 10);

                let items = (snapshot.curriculum?.[sId]?.active_homeworks || []).filter(h => {
                    const done = isDone(h.status);
                    if (lesson && lesson !== 'Hepsi' && h.lesson !== lesson) return false;
                    if (filter === 'Yapılanlar' && !done) return false;
                    if (filter === 'Yapılmayanlar' && done) return false;
                    if (dateFilter && dateFilter !== 'all') {
                        const d = (h.due_date || '').slice(0, 10);
                        if (dateFilter === 'overdue' && (done || !d || d >= todayStr)) return false;
                        if (dateFilter === 'today' && (done || d !== todayStr)) return false;
                        if (dateFilter === 'tomorrow' && (done || d !== tmrwStr)) return false;
                        if (dateFilter === 'week' && (done || !d || d < todayStr || d > weekEndStr)) return false;
                    }
                    return true;
                });
                if (!items.length) {
                    return { text: "Gösterilecek ödev bulunamadı." };
                }
                const now = new Date();
                const todayFormatted = [String(now.getDate()).padStart(2, '0'), String(now.getMonth() + 1).padStart(2, '0'), now.getFullYear()].join('.');
                let lines = [];
                lines.push(`🎓 *Ödev Özeti* - ${studentName}`);
                lines.push(`📅 *Tarih:* ${todayFormatted}`);
                lines.push("");
                lines.push("```");
                let completed = 0;
                let totalMin = 0;
                for (const h of items) {
                    const done = isDone(h.status);
                    if (done) completed++;
                    const icon = done ? "✅" : "⏳";
                    let line = `${icon} ${h.lesson} / ${h.book} / ${h.topic}`;
                    const dur = Number(h.duration || 0);
                    if (dur > 0) {
                        line += ` (${dur} dk)`;
                        if (done) totalMin += dur;
                    }
                    lines.push(line);
                }
                lines.push("```");
                lines.push("");
                lines.push(`📊 *İlerleme:* ${completed}/${items.length}`);
                if (totalMin > 0) lines.push(`⏱️ *Toplam Süre:* ${totalMin} dk`);
                lines.push("🚀 _Başarılar dileriz._");
                return { text: lines.join("\n") };
            }

            // 7. Post Homework Assignment (Çevrimdışı Yeni Ödev Verme)
            if (url === '/api/homework' && method === 'POST') {
                const { student_id, lesson, book, topics, topic, due_date } = body;
                const allTopics = topics || (topic ? [topic] : []);
                await this.queueAssignHomework({
                    student_id,
                    lesson,
                    book,
                    topics: allTopics,
                    due_date
                });
                return {
                    status: 'success',
                    message: `Çevrimdışı mod: ${allTopics.length} konu telefona kaydedildi. (Bilgisayar açılınca aktarılacak)`,
                    kume_id: 0,
                    offline: true
                };
            }

            // 8. Actual desktop-style homework header toggles (including undo).
            if (url === '/api/homework/status/bulk' && method === 'POST') {
                if (!body || !Array.isArray(body.homework_ids) ||
                    !body.homework_ids.length || !['tamam', 'devam'].includes(body.status)) {
                    throw new Error('Geçersiz çevrimdışı ödev durum isteği');
                }
                await this.queueSetHomeworkStatus(body);
                return { status: 'success', updated: body.homework_ids.length, offline: true };
            }

            // 8. Post Complete Homework (Çevrimdışı Ödev Tamamlama)
            if (url.startsWith('/api/homework/') && url.endsWith('/complete') && method === 'POST') {
                const hwId = Number(url.split('/')[3]);
                if (!Number.isSafeInteger(hwId) || hwId <= 0) throw new Error('Ödev alt satırı geçersiz');
                await this.queueCompleteHomework(hwId);
                return {
                    status: 'success',
                    message: 'Çevrimdışı modda tamamlandı işaretlendi.',
                    updated: 1,
                    offline: true
                };
            }

            throw new Error(`Bu işlem için bilgisayar bağlantısı gerekiyor: ${url}`);
        }
    };

    window.OfflineSync = OfflineSync;

})(window);
