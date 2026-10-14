// Headless V4 IndexedDB + WebCrypto regression without real browser.
// The sandbox environment blocks all Chromium navigation; iOS/Android E2E is still required.
'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {webcrypto} = require('node:crypto');
const {TextEncoder, TextDecoder} = require('node:util');
class FakeIndexedDB {
    constructor() {this.databases = new Map();}
    open(name, version) {
        const req = {};
        queueMicrotask(() => {
            let db = this.databases.get(name);
            let isNew = false;
            if (!db) {db = new FakeDb(); this.databases.set(name, db); isNew=true;}
            req.result=db;
            if (isNew && req.onupgradeneeded) req.onupgradeneeded();
            req.onsuccess?.();
        });
        return req;
    }
}
class FakeDb {
    constructor() {this.stores = new Map();this.objectStoreNames={contains: name => this.stores.has(name)};}
    createObjectStore(name, opts) {this.stores.set(name, {keyPath:opts.keyPath, records:new Map()});}
    close() {}
    transaction(names, mode) {
        if (typeof names === 'string') names=[names];
        const tx = {waiting:0, aborted:false, completeScheduled:false,
            objectStore: (name) => {
                if (!names.includes(name)) throw new Error('Undeclared store');
                const store = this.stores.get(name);if(!store) throw new Error('Missing store '+name);
                function request(fn) {
                    const req={result:undefined, error:null};tx.waiting++;
                    queueMicrotask(()=>{
                        if(tx.aborted) {tx.waiting--; return;}
                        try {req.result=fn();req.onsuccess?.();}
                        catch(e) {console.error("IDB request error", e);req.error=e;req.onerror?.();tx.abort();}
                        tx.waiting--;
                        tx.maybeComplete();
                    });
                    return req;
                }
                return {
                    get: (id)=>request(()=>structuredClone(store.records.get(id))),
                    getAll: ()=>request(()=>Array.from(store.records.values(),v => structuredClone(v))),
                    add: (item)=>request(()=>{const id=item[store.keyPath];if(store.records.has(id)) throw new Error('duplicate key');store.records.set(id,structuredClone(item));}),
                    put: (item)=>request(()=>store.records.set(item[store.keyPath],structuredClone(item)))
                };
            },
            maybeComplete: ()=>{
                if(tx.waiting || tx.aborted || tx.completeScheduled) return;
                tx.completeScheduled = true;
                queueMicrotask(()=>{
                    tx.completeScheduled=false;
                    if(!tx.waiting && !tx.aborted) tx.oncomplete?.();
                });
            },
            abort:()=>{ if(tx.aborted)return;tx.aborted=true;queueMicrotask(()=>tx.onabort?.()); }
        };
        return tx;
    }
}
async function run() {
    const env={crypto:webcrypto,TextEncoder,TextDecoder,structuredClone,Blob,Uint8Array,
        navigator:{storage:{estimate:async()=>({usage:100,quota:500}), persisted:async()=>false}},
        btoa:s=>Buffer.from(s,'binary').toString('base64'),
        atob:s=>Buffer.from(s,'base64').toString('binary'),
        indexedDB:new FakeIndexedDB(),console};
    env.window=env;
    vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web_api/static/js/offline_vault.js'),'utf8'),env);
    const v=env.OfflineVault;
    assert.equal(await v.isConfigured(),false);  // initialize schema via vault
    const db=await new Promise(ok=>{const r=env.indexedDB.open('YKS_Offline_Store_v1',2);r.onsuccess=()=>ok(r.result)});
    const makeSnap=(id)=>({version:1,database_id:id,generated_at:'2026-10-14T12:00:00',students:[{id:1}],curriculum:{1:{}}});
    const seed=async(id, mutation)=> new Promise((ok,fail)=>{
        const t=db.transaction(['snapshots','outbox'],'readwrite');
        t.objectStore('snapshots').put({key:'current',value:makeSnap(id)});
        if (mutation) t.objectStore('outbox').put(mutation);
        t.oncomplete=ok;t.onabort=fail;
    });
    const item={id:'mutation-unique-1234',type:'ASSIGN_HOMEWORK',payload:{student_id:1,topics:['Fizik']},created_at:'2026-10-14T10:00:00Z',seq:1};
    await seed('desktop-A',item);
    assert.equal(await v.isConfigured(),false);
    await v.configureOfflineAccess('test-valid-token-12345678901234567890','a strong local passphrase!','desktop-A');
    assert.equal(await v.isConfigured(),true);
    assert.equal(await v.unlockOfflineAccess('a strong local passphrase!','desktop-A'),'test-valid-token-12345678901234567890');
    await assert.rejects(()=>v.unlockOfflineAccess('wrong wrong wrong','desktop-A'));
    await assert.rejects(()=>v.unlockOfflineAccess('a strong local passphrase!','desktop-B'));
    const encrypted=await v.exportEncryptedBackup('this recovery passphrase 123');
    assert(encrypted.size>500);
    const body=await encrypted.text();
    assert(!body.includes('test-valid-token'));
    assert(!body.includes('Fizik'));
    await assert.rejects(()=>v.importEncryptedBackup(encrypted,'incorrect recovery password'));
    assert.equal((await v.importEncryptedBackup(encrypted,'this recovery passphrase 123')).imported,0);
    // Clear all storage and recover a full backup.
    env.indexedDB = new FakeIndexedDB();
    const v2=env.OfflineVault;
    const after=await v2.importEncryptedBackup(encrypted,'this recovery passphrase 123');
    assert.equal(after.imported,1);
    assert.equal(await v2.unlockOfflineAccess('a strong local passphrase!','desktop-A'),'test-valid-token-12345678901234567890');
    const again=await v2.importEncryptedBackup(encrypted,'this recovery passphrase 123');
    assert.equal(again.imported,0);
    // Entire transaction refuses to restore an unrelated institution.
    const db2=await new Promise(ok=>{const r=env.indexedDB.open('YKS_Offline_Store_v1',2);r.onsuccess=()=>ok(r.result)});
    await new Promise(ok=>{const t=db2.transaction('snapshots','readwrite');t.objectStore('snapshots').put({key:'current',value:makeSnap('desktop-B')});t.oncomplete=ok;});
    await assert.rejects(()=>v2.importEncryptedBackup(encrypted,'this recovery passphrase 123'),/başka masaüstü/);
    const snap=await new Promise(ok=>{const t=db2.transaction('snapshots','readonly');const r=t.objectStore('snapshots').get('current');t.oncomplete=()=>ok(r.result.value);});
    assert.equal(snap.database_id,'desktop-B');
    console.log('PASS: local unlock, wrong password, AES-GCM backup, zero plaintext, full recovery, idempotent merge, cross-database rejection (7 checks)');
}
run().catch(e=>{console.error(e);process.exitCode=1});
