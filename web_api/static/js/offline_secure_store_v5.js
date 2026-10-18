/**
 * V5 opt-in encrypted-at-rest IndexedDB adapter.
 * All snapshot content and outbox payloads are AES-256-GCM encrypted; metadata
 * leaks only an opaque command ID/sequence and encrypted-store existence.
 * The password is NEVER written to storage, and the key lives only in memory.
 * IMPORTANT: secure context (HTTPS) + previously downloaded V4 recovery backup.
 */
(function (window) {
    'use strict';
    const DB_NAME = 'YKS_Offline_Store_v1';
    const DB_VERSION = 3;
    const CONFIG = 'encrypted_storage_v5';
    const ROUNDS = 310000;
    const encode = s => new TextEncoder().encode(s);
    const decode = b => new TextDecoder('utf-8', {fatal:true}).decode(b);
    let key = null;
    let activeDatabase = null;
    let migrationBusy = false;

    function toB64(buffer) { return btoa(String.fromCharCode(...new Uint8Array(buffer))); }
    function fromB64(str) {
        if (typeof str !== 'string' || str.length > 100 * 1024 * 1024 || !/^[A-Za-z0-9+/]*={0,2}$/.test(str)) throw Error('Şifreli kayıt biçimi geçersiz.');
        return Uint8Array.from(atob(str), c => c.charCodeAt(0));
    }
    function ensureCrypto() {
        if (!window.isSecureContext || !window.crypto?.subtle || !window.crypto?.getRandomValues)
            throw Error('Yerel şifreleme için HTTPS güvenli bağlantısı gerekir.');
    }
    function open() {
        return new Promise((resolve,reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = () => {
                const db=req.result;
                if (!db.objectStoreNames.contains('snapshots')) db.createObjectStore('snapshots',{keyPath:'key'});
                if (!db.objectStoreNames.contains('outbox')) db.createObjectStore('outbox',{keyPath:'id'});
                if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta',{keyPath:'key'});
            };
            req.onblocked = () => reject(Error('Diğer açık sekmeler yerel veritabanını kilitliyor. Diğer sekmeleri kapatın.'));
            req.onerror = () => reject(req.error);
            req.onsuccess = () => {const db=req.result;db.onversionchange=()=>db.close();resolve(db);};
        });
    }
    async function getConfig() {
        const db=await open();
        return new Promise((resolve,reject) => {
            const t=db.transaction('meta','readonly'), r=t.objectStore('meta').get(CONFIG);
            t.oncomplete=()=>{db.close();resolve(r.result?.value || null);};
            t.onerror=()=>{db.close();reject(t.error);};
            t.onabort=()=>{db.close();reject(t.error);};
        });
    }
    async function keyFor(password,salt,rounds=ROUNDS) {
        const raw=await crypto.subtle.importKey('raw',encode(password),'PBKDF2',false,['deriveKey']);
        return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:rounds,hash:'SHA-256'},raw,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
    }
    function aad(store,id,databaseId) {return encode('YKS-LGS|V5|'+databaseId+'|'+store+'|'+id);}
    async function encryptWith(workKey,dbid,store,id,data) {
        const iv=crypto.getRandomValues(new Uint8Array(12));
        const bytes=encode(JSON.stringify(data));
        const ciphertext=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:aad(store,id,dbid)},workKey,bytes);
        return {$sealed_v5:1,iv:toB64(iv),ciphertext:toB64(ciphertext)};
    }
    async function decryptWith(workKey,dbid,store,id,data) {
        if (!data || data.$sealed_v5!==1) throw Error('Şifreli çalışma alanında şifresiz/bozuk kayıt tespit edildi. Senkronizasyon durduruldu.');
        const iv=fromB64(data.iv);
        if (iv.length!==12) throw Error('Şifreli kayıt IV bilgisi geçersiz.');
        try {
            const result=await crypto.subtle.decrypt({name:'AES-GCM',iv,additionalData:aad(store,id,dbid)},workKey,fromB64(data.ciphertext));
            return JSON.parse(decode(result));
        } catch (_) {throw Error('Yerel veri çözülemedi. Parola veya kayıt bütünlüğü geçersiz.');}
    }
    function collect() {
        return open().then(db=>new Promise((resolve,reject)=>{
            const t=db.transaction(['snapshots','outbox','meta'],'readonly');
            const snap=t.objectStore('snapshots').get('current');
            const queue=t.objectStore('outbox').getAll();
            const cfg=t.objectStore('meta').get(CONFIG);
            const vault=t.objectStore('meta').get('offline_access_v4');
            t.oncomplete=()=>{db.close();resolve({snapshot:snap.result||null,queue:queue.result||[],config:cfg.result?.value||null,vault:vault.result?.value||null});};
            t.onerror=()=>{db.close();reject(t.error);};
            t.onabort=()=>{db.close();reject(t.error);};
        }));
    }
    async function sealRecord(store,id,value) {
        const config=await getConfig();
        if (!config) return value;
        if (!key || activeDatabase!==config.database_id) throw Error('Şifreli yerel çalışma alanı kilitli. Önce şifrenizle açın.');
        return encryptWith(key,activeDatabase,store,id,value);
    }
    async function openRecord(store,id,value) {
        const config=await getConfig();
        if (!config) {
            if (value?.$sealed_v5===1) throw Error('Şifreli kayıt anahtarı kayıp; veriye yazma engellendi.');
            return value;
        }
        if (!key || activeDatabase!==config.database_id) throw Error('Şifreli yerel çalışma alanı kilitli. Önce şifrenizle açın.');
        return decryptWith(key,activeDatabase,store,id,value);
    }
    async function openRecords(store, rows) {
        const cfg=await getConfig();
        if(!cfg) {
            if(rows.some(x=>x.encrypted))throw Error('Şifreli kayıt var ancak yerel anahtar yok.');
            return rows;
        }
        if(!key || activeDatabase!==cfg.database_id)throw Error('Şifreli çalışma alanı kilitli.');
        const decoded=[];
        for(const row of rows) {
            if(!row.encrypted)throw Error('Şifreli depoda açık/bozuk kayıt var; işlem durduruldu.');
            decoded.push({...await decryptWith(key,activeDatabase,store,row.id,row.encrypted),seq:row.seq});
        }
        return decoded;
    }
    const Store={
        get busy(){return migrationBusy;},
        get unlocked(){return !!key;},
        async enabled(){return !!(await getConfig());},
        async databaseId(){return (await getConfig())?.database_id||null;},
        lock(){key=null;activeDatabase=null;},
        sealRecord,openRecord,openRecords,
        async unlock(password,expectedId) {
            ensureCrypto();
            const config=await getConfig();
            if (!config || config.version!==1 || config.rounds!==ROUNDS || !config.database_id ||
                (expectedId && config.database_id!==expectedId)) throw Error('Şifreli çalışma alanı veya masaüstü kimliği uyuşmuyor.');
            if (typeof password!=='string'|| password.length<12) throw Error('Geçerli parolayı girin.');
            const attempt=await keyFor(password,fromB64(config.salt));
            const check=await decryptWith(attempt,config.database_id,'meta',CONFIG,config.verifier);
            if (check?.database_id!==config.database_id) throw Error('Şifre çözme kontrolü başarısız.');
            key=attempt;activeDatabase=config.database_id;
            return true;
        },
        // Migration runs only with the V4 local unlock password. Existing data
        // is first read and encrypted outside the IDB transaction. Within one
        // atomic write transaction, it verifies the sources have not changed.
        async enable(password,databaseId) {
            ensureCrypto();
            if (migrationBusy) throw Error('Şifreleme zaten devam ediyor.');
            if (!databaseId||typeof password!=='string'||password.length<12) throw Error('Masaüstü ve güçlü parola gerekli.');
            if (await getConfig()) throw Error('Yerel veriler zaten şifrelenmiş.');
            migrationBusy=true;
            try {
                const {snapshot,queue,config,vault}=await collect();
                if (config) throw Error('Şifreleme zaten etkin.');
                if (!snapshot?.value || snapshot.value.database_id!==databaseId || vault?.database_id!==databaseId)
                    throw Error('Masaüstü kimliği ve V4 erişim kaydı doğrulanamadı.');
                if (queue.some(x=>!x.id||x.$sealed_v5||x.encrypted ||x.payload===undefined ||
                    !Number.isSafeInteger(x.seq) || x.seq<=0) ||
                    new Set(queue.map(x=>x.seq)).size!==queue.length)
                    throw Error('Bilinmeyen/şifrelenmiş işlem bulundu. Şifreleme durduruldu.');
                const salt=crypto.getRandomValues(new Uint8Array(16));
                const workKey=await keyFor(password,salt);
                const configValue={version:1,database_id:databaseId,salt:toB64(salt),rounds:ROUNDS,
                    verifier:await encryptWith(workKey,databaseId,'meta',CONFIG,{database_id:databaseId})};
                const encryptedSnapshot=await encryptWith(workKey,databaseId,'snapshots','current',snapshot.value);
                const encryptedQueue=[];
                for(const m of queue) encryptedQueue.push({id:m.id,seq:m.seq,
                    encrypted:await encryptWith(workKey,databaseId,'outbox',m.id,m)});
                const db=await open();
                await new Promise((resolve,reject)=>{
                    const tx=db.transaction(['snapshots','outbox','meta'],'readwrite');
                    const s=tx.objectStore('snapshots').get('current');
                    const o=tx.objectStore('outbox').getAll();
                    const c=tx.objectStore('meta').get(CONFIG);
                    let cause=null,ready=0;
                    function check(){
                        if(++ready!==3)return;
                        if (c.result||JSON.stringify(s.result)!==JSON.stringify(snapshot)||
                            JSON.stringify(o.result)!==JSON.stringify(queue)) {
                            cause=Error('Şifreleme sırasında yeni bir işlem oluştu. Hiçbir değişiklik yapılmadı.');
                            tx.abort();return;
                        }
                        tx.objectStore('snapshots').put({key:'current',value:encryptedSnapshot});
                        const store=tx.objectStore('outbox');
                        encryptedQueue.forEach(x=>store.put(x));
                        tx.objectStore('meta').put({key:CONFIG,value:configValue});
                    }
                    s.onsuccess=check;o.onsuccess=check;c.onsuccess=check;
                    tx.oncomplete=()=>{db.close();resolve();};
                    tx.onabort=()=>{db.close();reject(cause||tx.error||Error('Şifreleme geri alındı.'));};
                    tx.onerror=()=>{db.close();};
                });
                key=workKey;activeDatabase=databaseId;
                return {encrypted_commands:queue.length,database_id:databaseId};
            } finally {migrationBusy=false;}
        }
    };
    window.OfflineSecureStore=Store;
})(window);
