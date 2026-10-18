/**
 * V4 optional offline re-entry + encrypted recovery bundles.
 * Keeps the existing desktop authentication and SQLite schema unchanged.
 * WARNING: the existing IndexedDB snapshot/outbox remain plaintext at rest.
 * This local passphrase only wraps the server access key and the backup file.
 */
(function (window) {
    'use strict';
    const NAME = 'YKS_Offline_Store_v1';
    const VERSION = 3;
    const KDF_ITERATIONS = 310000;
    const MAX_FILE_BYTES = 40 * 1024 * 1024;
    const BACKUP_KIND = 'YKS_LGS_OFFLINE_ENCRYPTED_BACKUP';
    const AAD = new TextEncoder().encode('YKS-LGS|V4|encrypted-backup');

    function requireCrypto() {
        if (!window.crypto?.subtle || !window.crypto.getRandomValues) {
            throw new Error('Şifreleme bu bağlantıda kullanılamıyor. Güvenilir HTTPS bağlantısı gerekli.');
        }
    }
    function validatePassword(password) {
        if (typeof password !== 'string' || password.length < 12 || password.length > 256) {
            throw new Error('En az 12 karakterlik güçlü bir parola girin (en fazla 256).');
        }
    }
    function b64(bytes) {
        let str = '';
        for (let i = 0; i < bytes.length; i += 16384) {
            str += String.fromCharCode(...bytes.subarray(i, i + 16384));
        }
        return btoa(str);
    }
    function unb64(s) {
        if (typeof s !== 'string' || s.length > MAX_FILE_BYTES * 2 || !/^[A-Za-z0-9+/]*={0,2}$/.test(s)) {
            throw new Error('Şifreli veri biçimi geçersiz.');
        }
        const raw = atob(s);
        const buf = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
        return buf;
    }
    async function keyFromPassword(password, salt, iterations) {
        const material = await crypto.subtle.importKey('raw', new TextEncoder().encode(password),
            'PBKDF2', false, ['deriveKey']);
        return crypto.subtle.deriveKey({name: 'PBKDF2', salt, iterations, hash: 'SHA-256'}, material,
            {name: 'AES-GCM', length: 256}, false, ['encrypt', 'decrypt']);
    }
    async function seal(content, password, tag) {
        requireCrypto();
        validatePassword(password);
        const salt = crypto.getRandomValues(new Uint8Array(16));
        const iv = crypto.getRandomValues(new Uint8Array(12));
        const key = await keyFromPassword(password, salt, KDF_ITERATIONS);
        const plaintext = new TextEncoder().encode(JSON.stringify(content));
        const encrypted = await crypto.subtle.encrypt({name: 'AES-GCM', iv,
            additionalData: tag}, key, plaintext);
        return {kdf: 'PBKDF2-SHA256', rounds: KDF_ITERATIONS, cipher: 'AES-256-GCM',
            salt: b64(salt), iv: b64(iv), ciphertext: b64(new Uint8Array(encrypted))};
    }
    async function unseal(data, password, tag) {
        requireCrypto();
        if (!data || data.kdf !== 'PBKDF2-SHA256' || data.cipher !== 'AES-256-GCM' ||
            !Number.isSafeInteger(data.rounds) || data.rounds < KDF_ITERATIONS || data.rounds > 2000000) {
            throw new Error('Desteklenmeyen veya güvensiz şifreleme biçimi.');
        }
        const salt = unb64(data.salt);
        const iv = unb64(data.iv);
        if (salt.length !== 16 || iv.length !== 12) throw new Error('Şifreli veri başlığı geçersiz.');
        const key = await keyFromPassword(password, salt, data.rounds);
        try {
            const clear = await crypto.subtle.decrypt({name: 'AES-GCM', iv, additionalData: tag}, key, unb64(data.ciphertext));
            return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(clear));
        } catch (_) {
            throw new Error('Parola yanlış veya şifreli dosya değiştirilmiş/bozulmuş.');
        }
    }
    function openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(NAME, VERSION);
            request.onupgradeneeded = () => {
                const db = request.result;
                if (!db.objectStoreNames.contains('snapshots')) db.createObjectStore('snapshots', {keyPath: 'key'});
                if (!db.objectStoreNames.contains('outbox')) db.createObjectStore('outbox', {keyPath: 'id'});
                if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', {keyPath: 'key'});
            };
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
            request.onblocked = () => reject(new Error('Başka sekme veritabanını kilitledi; diğer sekmeyi kapatın.'));
        });
    }
    async function getMeta(key) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('meta', 'readonly');
            const req = tx.objectStore('meta').get(key);
            tx.oncomplete = () => {db.close(); resolve(req.result?.value || null);};
            tx.onerror = () => {db.close(); reject(tx.error);};
        });
    }
    async function putMeta(key, value) {
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('meta', 'readwrite');
            tx.objectStore('meta').put({key, value});
            tx.oncomplete = () => {db.close(); resolve(true);};
            tx.onerror = () => {db.close(); reject(tx.error);};
            tx.onabort = () => {db.close(); reject(tx.error);};
        });
    }
    // V5 encrypted records are read outside an IndexedDB transaction because
    // WebCrypto promises cannot safely be awaited inside an active IDB tx.
    async function readBundle() {
        const db = await openDB();
        const raw = await new Promise((resolve, reject) => {
            const tx = db.transaction(['snapshots','outbox','meta'], 'readonly');
            const sn = tx.objectStore('snapshots').get('current');
            const queue = tx.objectStore('outbox').getAll();
            const lock = tx.objectStore('meta').get('offline_access_v4');
            tx.oncomplete = () => {db.close();resolve({snapshot:sn.result?.value || null,
                outbox:queue.result || [],offline_access:lock.result?.value || null});};
            tx.onerror = () => {db.close();reject(tx.error);};
            tx.onabort = () => {db.close();reject(tx.error);};
        });
        const secure = window.OfflineSecureStore;
        if (secure && await secure.enabled()) {
            raw.snapshot = await secure.openRecord('snapshots','current',raw.snapshot);
            raw.outbox=await secure.openRecords('outbox',raw.outbox);
        }
        return raw;
    }
    function comparableMutation(m) {
        return JSON.stringify([m.id, m.type, m.payload, m.created_at]);
    }
    function validateBundle(bundle) {
        if (!bundle || bundle.kind !== BACKUP_KIND || bundle.version !== 1 ||
            !bundle.snapshot || bundle.snapshot.version !== 1 ||
            !bundle.snapshot.database_id || !Array.isArray(bundle.snapshot.students) ||
            !bundle.snapshot.curriculum || !Array.isArray(bundle.outbox) || bundle.outbox.length > 100000) {
            throw new Error('Yedek geçerli bir tam çevrimdışı veri paketi değil.');
        }
        if (bundle.database_id !== bundle.snapshot.database_id) throw new Error('Yedekte masaüstü kimliği uyuşmuyor.');
        const used = new Set();
        for (const mutation of bundle.outbox) {
            if (!mutation || typeof mutation.id !== 'string' || mutation.id.length < 8 ||
                mutation.id.length > 128 || used.has(mutation.id) ||
                !['ASSIGN_HOMEWORK','SET_HOMEWORK_STATUS','COMPLETE_HOMEWORK'].includes(mutation.type) ||
                !mutation.payload || typeof mutation.payload !== 'object') {
                throw new Error('Yedekte bozuk/çift işlem bulundu.');
            }
            used.add(mutation.id);
        }
        if (bundle.offline_access && (bundle.offline_access.database_id !== bundle.database_id ||
            bundle.offline_access.version !== 1)) throw new Error('Yedekte offline giriş kimliği farklı.');
    }
    // Restore is all-or-nothing. The *existing* outbox remains and imported
    // commands are appended in order, with duplicate mutation IDs checked.
    async function commitRestoreEncrypted(bundle) {
        const secure=window.OfflineSecureStore;
        if (!secure?.unlocked) throw Error('Önce şifreli çalışma alanını açın.');
        const databaseId=await secure.databaseId();
        if (databaseId!==bundle.database_id) throw Error('Bu yedek farklı bir masaüstüne ait.');
        const db=await openDB();
        const original=await new Promise((resolve,reject)=>{
            const t=db.transaction(['snapshots','outbox','meta'],'readonly');
            const sn=t.objectStore('snapshots').get('current');
            const q=t.objectStore('outbox').getAll();
            const seq=t.objectStore('meta').get('next_seq');
            const lock=t.objectStore('meta').get('offline_access_v4');
            t.oncomplete=()=>resolve({snapshot:sn.result || null,queue:q.result || [],
                seq:seq.result || null,lock:lock.result||null});
            t.onerror=()=>reject(t.error);
            t.onabort=()=>reject(t.error);
        });
        db.close();
        const existing=original.snapshot ? await secure.openRecord('snapshots','current',original.snapshot.value):null;
        const saved=await secure.openRecords('outbox',original.queue);
        if ((existing && existing.database_id!==databaseId) ||
            (original.lock?.value && original.lock.value.database_id!==databaseId))
            throw Error('Başka masaüstü veritabanına ait kayıt var; geri yükleme durduruldu.');
        const ids=new Map(saved.map(x=>[x.id,x]));
        let next=Number(original.seq?.value||0),imported=0;
        for(const row of saved)next=Math.max(next,Number(row.seq||0));
        const sealed=[];
        for(const item of bundle.outbox) {
            if(ids.has(item.id)) {
                if(comparableMutation(ids.get(item.id))!==comparableMutation(item))
                    throw Error('Aynı işlem kimliğinde farklı kayıt var; geri yükleme durduruldu.');
                continue;
            }
            const seq=++next;
            sealed.push({id:item.id,seq,encrypted:await secure.sealRecord('outbox',item.id,item)});
            ids.set(item.id,item); imported++;
        }
        let snapshotRow=null;
        if(!existing || String(bundle.snapshot.generated_at||'')>String(existing.generated_at||''))
            snapshotRow={key:'current',value:await secure.sealRecord('snapshots','current',bundle.snapshot)};
        const writable=await openDB();
        try {
            await new Promise((resolve,reject)=>{
                const tx=writable.transaction(['snapshots','outbox','meta'],'readwrite');
                const sn=tx.objectStore('snapshots').get('current');
                const q=tx.objectStore('outbox').getAll();
                const seq=tx.objectStore('meta').get('next_seq');
                const lock=tx.objectStore('meta').get('offline_access_v4');
                let ready=0,cause=null;
                function readyCheck(){
                    if(++ready!==4)return;
                    if(JSON.stringify(sn.result||null)!==JSON.stringify(original.snapshot) ||
                        JSON.stringify(q.result||[])!==JSON.stringify(original.queue) ||
                        JSON.stringify(seq.result||null)!==JSON.stringify(original.seq) ||
                        JSON.stringify(lock.result||null)!==JSON.stringify(original.lock)){
                        cause=Error('Geri yükleme sırasında kayıtlar değişti; işlem güvenle iptal edildi.');tx.abort();return;
                    }
                    const dest=tx.objectStore('outbox');
                    for(const row of sealed)dest.add(row);
                    if(snapshotRow)tx.objectStore('snapshots').put(snapshotRow);
                    tx.objectStore('meta').put({key:'next_seq',value:next});
                    if(!lock.result && bundle.offline_access)
                        tx.objectStore('meta').put({key:'offline_access_v4',value:bundle.offline_access});
                }
                sn.onsuccess=readyCheck;q.onsuccess=readyCheck;seq.onsuccess=readyCheck;lock.onsuccess=readyCheck;
                tx.oncomplete=resolve;
                tx.onabort=()=>reject(cause || tx.error || Error('Geri yükleme geri alındı.'));
                tx.onerror=()=>{};
            });
        } finally {writable.close();}
        return {imported,total:bundle.outbox.length};
    }
    async function commitRestore(bundle) {
        if (window.OfflineSecureStore && await window.OfflineSecureStore.enabled())
            return commitRestoreEncrypted(bundle);
        const db = await openDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(['snapshots','outbox','meta'], 'readwrite');
            const sn = tx.objectStore('snapshots').get('current');
            const outgoing = tx.objectStore('outbox').getAll();
            const seqReq = tx.objectStore('meta').get('next_seq');
            const lockReq = tx.objectStore('meta').get('offline_access_v4');
            let importedCount = 0;
            let errorMessage = null;
            let settled = 0;
            function finishRead() {
                settled++;
                if (settled !== 4) return;
                const existing = sn.result?.value || null;
                const saved = outgoing.result || [];
                const lock = lockReq.result?.value || null;
                const existingId = existing?.database_id || lock?.database_id;
                if (existingId && existingId !== bundle.database_id) {
                    errorMessage = 'Bu telefonda başka masaüstü veritabanına ait kayıt var; geri yükleme durduruldu.';
                    tx.abort(); return;
                }
                if (lock && lock.database_id !== bundle.database_id) {
                    errorMessage = 'Çevrimdışı erişim anahtarı farklı veritabanına ait.';
                    tx.abort(); return;
                }
                if (!existingId && saved.length) {
                    errorMessage = 'Telefonda kaynağı belirlenemeyen bekleyen işlemler var; otomatik birleştirme engellendi.';
                    tx.abort(); return;
                }
                const ids = new Map(saved.map(m => [m.id, m]));
                let next = Number(seqReq.result?.value || 0);
                for (const m of saved) next = Math.max(next, Number(m.seq || 0));
                for (const item of bundle.outbox) {
                    if (ids.has(item.id)) {
                        if (comparableMutation(ids.get(item.id)) !== comparableMutation(item)) {
                            errorMessage = 'Aynı işlem kimliği iki farklı içerikte; hiçbir kayıt değiştirilmedi.';
                            tx.abort(); return;
                        }
                        continue;
                    }
                    const safe = {...item, seq: ++next};
                    tx.objectStore('outbox').add(safe);
                    ids.set(item.id, safe);
                    importedCount++;
                }
                tx.objectStore('meta').put({key: 'next_seq', value: next});
                if (!lock && bundle.offline_access) {
                    tx.objectStore('meta').put({key:'offline_access_v4', value:bundle.offline_access});
                }
                // If both snapshots exist for the same DB, prefer the fresher
                // server baseline; queued commands are never removed.
                if (!existing || String(bundle.snapshot.generated_at || '') > String(existing.generated_at || '')) {
                    tx.objectStore('snapshots').put({key:'current', value:bundle.snapshot});
                }
            }
            sn.onsuccess = finishRead;
            outgoing.onsuccess = finishRead;
            seqReq.onsuccess = finishRead;
            lockReq.onsuccess = finishRead;
            tx.oncomplete = () => {db.close(); resolve({imported: importedCount, total: bundle.outbox.length});};
            tx.onabort = () => {db.close(); reject(new Error(errorMessage || 'Geri yükleme atomik olarak iptal edildi.'));};
            tx.onerror = () => {db.close(); reject(tx.error);};
        });
    }

    const OfflineVault = {
        busy: false,
        async isConfigured() { return !!(await getMeta('offline_access_v4')); },
        async configuredDatabaseId() { return (await getMeta('offline_access_v4'))?.database_id || null; },
        async configureOfflineAccess(accessKey, password, databaseId) {
            if (!accessKey || accessKey.length < 32 || !databaseId) throw new Error('Önce çevrimiçi giriş ve tam veri indirme gerekli.');
            if (window.OfflineSecureStore && await window.OfflineSecureStore.enabled())
                throw Error('Şifreleme etkin. Parola değiştirmek için ayrı güvenli anahtar döndürme işlemi gerekir.');
            const sealed = await seal({key: accessKey}, password, AAD);
            await putMeta('offline_access_v4', {version:1, database_id:databaseId, ...sealed});
            return true;
        },
        async unlockOfflineAccess(password, expectedDatabaseId) {
            const stored = await getMeta('offline_access_v4');
            if (!stored || stored.version !== 1) throw new Error('Bu telefonda çevrimdışı giriş ayarlanmamış.');
            if (!expectedDatabaseId || stored.database_id !== expectedDatabaseId) {
                throw new Error('Öğrenci kayıtlarıyla çevrimdışı erişim anahtarı farklı masaüstlerine ait.');
            }
            const decrypted = await unseal(stored, password, AAD);
            if (!decrypted || typeof decrypted.key !== 'string' || decrypted.key.length < 32) {
                throw new Error('Çevrimdışı giriş kaydı geçersiz.');
            }
            return decrypted.key;
        },
        async exportEncryptedBackup(password) {
            if (this.busy) throw new Error('Bir yedek işlemi devam ediyor.');
            this.busy = true;
            try {
                const data = await readBundle();
                if (!data.snapshot?.database_id) throw new Error('Önce bilgisayardan tam veri indirilmesi gerekli.');
                const backup = {kind: BACKUP_KIND, version:1, created_at:new Date().toISOString(),
                    database_id:data.snapshot.database_id, ...data};
                validateBundle(backup);
                const sealed = await seal(backup, password, AAD);
                const blob = new Blob([JSON.stringify({kind:BACKUP_KIND, version:1, encrypted:sealed})],
                    {type:'application/octet-stream'});
                if (blob.size > MAX_FILE_BYTES) {
                    throw new Error('Şifreli yedek 40 MB sınırını geçti; bu sürümde geri yüklenebilir dosya üretilemedi.');
                }
                return blob;
            } finally { this.busy = false; }
        },
        async importEncryptedBackup(file, password) {
            if (this.busy) throw new Error('Bir yedek işlemi devam ediyor.');
            if (!file || file.size > MAX_FILE_BYTES) throw new Error('Yedek dosyası çok büyük (en fazla 40 MB).');
            this.busy = true;
            try {
                const document = JSON.parse(await file.text());
                if (document.kind !== BACKUP_KIND || document.version !== 1 || !document.encrypted) {
                    throw new Error('Yedek dosyası biçimi geçersiz.');
                }
                const data = await unseal(document.encrypted, password, AAD);
                validateBundle(data);
                return await commitRestore(data);
            } finally { this.busy = false; }
        },
        async storageSummary() {
            const estimate = await navigator.storage?.estimate?.();
            const persistent = await navigator.storage?.persisted?.();
            return {usage: estimate?.usage ?? null, quota: estimate?.quota ?? null,
                    persistent: persistent === true};
        }
    };
    window.OfflineVault = OfflineVault;
})(window);
