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
    const DB_VERSION = 2;

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
                resolve(dbInstance);
            };
            req.onerror = (e) => reject(e.target.error);
        });
    }

    async function dbGet(storeName, key) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readonly');
            const req = tx.objectStore(storeName).get(key);
            req.onsuccess = () => resolve(req.result ? req.result.value : null);
            req.onerror = () => reject(req.error);
        });
    }

    // Resolve only after transaction commit; request success alone is not durable.
    async function dbPut(storeName, key, value) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(storeName, 'readwrite');
            tx.objectStore(storeName).put({ key, value });
            tx.oncomplete = () => resolve(true);
            tx.onerror = () => reject(tx.error);
            tx.onabort = () => reject(tx.error || new Error('IndexedDB kayıt işlemi iptal edildi'));
        });
    }

    async function dbGetAllOutbox() {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('outbox', 'readonly');
            const req = tx.objectStore('outbox').getAll();
            req.onsuccess = () => resolve((req.result || []).sort((a, b) =>
                (a.seq ?? 0) - (b.seq ?? 0) ||
                (a.created_at || '').localeCompare(b.created_at || '') || a.id.localeCompare(b.id)));
            req.onerror = () => reject(req.error);
        });
    }

    async function dbAddOutbox(item) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(['outbox', 'meta'], 'readwrite');
            const meta = tx.objectStore('meta');
            const req = meta.get('next_seq');
            req.onsuccess = () => {
                const seq = (req.result?.value || 0) + 1;
                meta.put({ key: 'next_seq', value: seq });
                tx.objectStore('outbox').add({ ...item, seq });
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

    function newMutationId() {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') {
            try { return 'mut_' + window.crypto.randomUUID(); } catch (_) {}
        }
        if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
            try {
                const buf = new Uint8Array(16);
                window.crypto.getRandomValues(buf);
                const hex = Array.from(buf).map(b => b.toString(16).padStart(2, '0')).join('');
                return 'mut_' + Date.now().toString(36) + '_' + hex;
            } catch (_) {}
        }
        return 'mut_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 12);
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
        listeners: [],

        onStatusChange(fn) {
            this.listeners.push(fn);
        },

        notify() {
            this.listeners.forEach(fn => {
                try { fn(this); } catch (e) { console.error(e); }
            });
        },

        async init() {
            try {
                this.lastSnapshot = await dbGet('snapshots', 'current');
                const outbox = await dbGetAllOutbox();
                // Recover a failed UI projection from the durable pending queue.
                if (this.lastSnapshot && outbox.length) {
                    this.lastSnapshot = projectOutbox(this.lastSnapshot, outbox);
                    await dbPut('snapshots', 'current', this.lastSnapshot);
                }
                this.pendingCount = outbox.length;

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

        async downloadSnapshot(studentId = null) {
            if (this.restoring) throw new Error('Yedek geri yüklenirken veri indirilemez.');
            // The UI cache is a full snapshot. A filtered subset must not
            // silently erase other students when written under 'current'.
            if (studentId !== null && studentId !== undefined) {
                throw new Error('Tek öğrenci paketi tam çevrimdışı verinin üzerine yazılamaz');
            }
            const url = studentId ? `/api/sync/snapshot?student_id=${studentId}` : '/api/sync/snapshot';
            const data = await window._originalApi(url);

            if (!data || data.version !== 1 || !Array.isArray(data.students) || !data.curriculum) {
                throw new Error('Eksik veya uyumsuz çevrimdışı veri paketi');
            }
            const pending = await dbGetAllOutbox();
            if (pending.length && this.lastSnapshot?.database_id && data.database_id !== this.lastSnapshot.database_id) {
                throw new Error('Bu telefonun kayıtları başka bir masaüstü veritabanına ait; aktarım durduruldu.');
            }
            const merged = projectOutbox(data, pending);
            await dbPut('snapshots', 'current', merged);
            this.lastSnapshot = merged;
            await dbPut('meta', 'last_download_time', new Date().toISOString());
            if (navigator.storage?.persist) {
                try { this.storagePersistent = await navigator.storage.persist(); }
                catch (_) { this.storagePersistent = false; }
            }
            this.notify();
            return data;
        },

        async queueAssignHomework({ student_id, lesson, book, topics, due_date }) {
            if (this.restoring) throw new Error('Yedek geri yüklenirken yeni işlem kaydedilemez.');
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
            this.pendingCount = (await dbGetAllOutbox()).length;

            // Local projections never use fabricated server-side IDs.
            if (this.lastSnapshot) {
                this.lastSnapshot = projectOutbox(this.lastSnapshot, [mutation]);
                await dbPut('snapshots', 'current', this.lastSnapshot);
            }

            this.notify();
            return mutation;
        },

        async queueCompleteHomework(lineId) {
            if (this.restoring) throw new Error('Yedek geri yüklenirken yeni işlem kaydedilemez.');
            const mutation = {
                id: newMutationId(), type: 'COMPLETE_HOMEWORK',
                payload: { line_id: lineId }, created_at: new Date().toISOString()
            };
            await dbAddOutbox(mutation);
            this.pendingCount = (await dbGetAllOutbox()).length;
            this.notify();
            return mutation;
        },

        async queueSetHomeworkStatus({ homework_ids, status }) {
            if (this.restoring) throw new Error('Yedek geri yüklenirken yeni işlem kaydedilemez.');
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
            this.pendingCount = (await dbGetAllOutbox()).length;
            // Keep the durable outbox as source of truth if projection fails.
            if (this.lastSnapshot) {
                this.lastSnapshot = projectOutbox(this.lastSnapshot, [mutation]);
                await dbPut('snapshots', 'current', this.lastSnapshot);
            }
            this.notify();
            return mutation;
        },

        async pushSync() {
            if (this.restoring) throw new Error('Yedek geri yüklenirken aktarım yapılamaz.');
            if (this.syncing) throw new Error('Eşitleme zaten devam ediyor');
            this.syncing = true;
            try {
                if (!(await this.checkConnection())) {
                    throw new Error(this.databaseMismatch ? 'Yanlış masaüstü veritabanı! Telefon kuyruğu korundu.' : 'Bilgisayara ulaşılamadı; kayıtlar telefonda korunuyor.');
                }
                const outbox = await dbGetAllOutbox();
                if (!outbox.length) {
                    await this.downloadSnapshot();
                    return { success: true, processed_count: 0, acknowledged_count: 0, remaining: 0 };
                }
                // Limit each server batch, retaining order, so a week of edits
                // need not be transferred in a single oversize request.
                let acknowledged = 0;
                let newlyApplied = 0;
                const failures = [];
                for (let start = 0; start < outbox.length; start += 100) {
                    const batch = outbox.slice(start, start + 100);
                    const result = await window._originalApi('/api/sync/push', 'POST', { mutations: batch, database_id: this.lastSnapshot?.database_id || null });
                    if (!Array.isArray(result.results)) {
                        throw new Error('Sunucu güvenli işlem bazlı onay vermedi; kuyruk silinmedi.');
                    }
                    const sent = new Set(batch.map(m => m.id));
                    const ids = result.results.filter(r => sent.has(r.id) &&
                        (r.status === 'applied' || r.status === 'already_applied')).map(r => r.id);
                    await dbDeleteAcknowledged(ids);
                    acknowledged += ids.length;
                    newlyApplied += result.results.filter(r => sent.has(r.id) && r.status === 'applied').length;
                    failures.push(...result.results.filter(r => sent.has(r.id) &&
                        r.status !== 'applied' && r.status !== 'already_applied'));
                    this.pendingCount = (await dbGetAllOutbox()).length;
                    this.notify();
                    // An earlier error could make later changes logically dependent;
                    // stop here and leave them pending for review.
                    if (failures.length) break;
                }
                // Merge remaining local mutations on top of fresh server state.
                await this.downloadSnapshot();
                return { success: failures.length === 0, processed_count: newlyApplied,
                    acknowledged_count: acknowledged, remaining: this.pendingCount, failures };
            } finally {
                this.syncing = false;
                this.notify();
            }
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
