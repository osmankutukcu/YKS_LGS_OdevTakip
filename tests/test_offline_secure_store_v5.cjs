'use strict';
// V5 headless IndexedDB transaction simulation + Node WebCrypto. This is
// not a replacement for browser/device end-to-end testing.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {webcrypto}=require('node:crypto');
const {TextEncoder,TextDecoder}=require('node:util');
const cloned = x => x===undefined ? undefined : structuredClone(x);
class FDB {
  constructor(){this.databases=new Map();}
  open(name,version){
    const r={};queueMicrotask(()=>{
      let d=this.databases.get(name),upgrade=false;
      if(!d){d=new FDatabase();this.databases.set(name,d);upgrade=true;}
      else if(version<d.version){r.error=new Error('VersionError');r.onerror?.();return;}
      else if(version>d.version){upgrade=true;}
      d.version=version;
      r.result=d;
      if(upgrade)r.onupgradeneeded?.();
      r.onsuccess?.({target:{result:d}});
    });return r;
  }
}
class FDatabase {
  constructor(){this.version=1;this.stores=new Map();this.objectStoreNames={contains:k=>this.stores.has(k)};}
  createObjectStore(k,opts){this.stores.set(k,{keyPath:opts.keyPath,data:new Map()});}
  close(){}
  transaction(stores,mode='readonly'){
    const names=Array.isArray(stores)?stores:[stores];
    const tx={pending:0,aborted:false,done:false,scheduled:false};
    const copies=new Map(names.map(n=>[n, new Map([...this.stores.get(n).data].map(([k,v])=>[k,cloned(v)]))]));
    function next(fn){
      const r={result:undefined,error:null};tx.pending++;
      queueMicrotask(()=>{
        if(tx.aborted)return;
        try{r.result=fn();r.onsuccess?.();}
        catch(e){console.error('FAKE IDB request error',e);r.error=e;r.onerror?.();tx.abort();}
        tx.pending--;schedule();
      });return r;
    }
    function schedule(){
      if(tx.aborted||tx.pending||tx.scheduled||tx.done)return;
      tx.scheduled=true;
      queueMicrotask(()=>{
        tx.scheduled=false;
        if(tx.pending||tx.aborted||tx.done)return;
        tx.done=true;
        if(mode==='readwrite') for(const [name,data] of copies) db.stores.get(name).data=data;
        tx.oncomplete?.();
      });
    }
    const db=this;
    tx.objectStore=function(name){
      if(!copies.has(name))throw Error('Missing store '+name);
      const dbStore=db.stores.get(name),map=copies.get(name);
      return {
        get:key=>next(()=>cloned(map.get(key))),
        getAll:()=>next(()=>[...map.values()].map(cloned)),
        count:()=>next(()=>map.size),
        put:v=>next(()=>{if(mode!=='readwrite')throw Error('readonly');map.set(v[dbStore.keyPath],cloned(v));}),
        add:v=>next(()=>{if(mode!=='readwrite')throw Error('readonly');const k=v[dbStore.keyPath];if(map.has(k))throw Error('Duplicate');map.set(k,cloned(v));}),
        delete:key=>next(()=>{if(mode!=='readwrite')throw Error('readonly');map.delete(key);})
      };
    };
    tx.abort=()=>{if(tx.aborted)return;tx.aborted=true;queueMicrotask(()=>tx.onabort?.());};
    return tx;
  }
}
async function write(db,objs){
  await new Promise((resolve,reject)=>{
    const tx=db.transaction(['snapshots','outbox','meta'],'readwrite');
    for(const [store,records] of Object.entries(objs))for(const r of records)tx.objectStore(store).put(r);
    tx.oncomplete=resolve;tx.onabort=reject;
  });
}
async function read(db,store,id){return new Promise((resolve,reject)=>{
  const tx=db.transaction(store,'readonly'),r=tx.objectStore(store).get(id);
  tx.oncomplete=()=>resolve(r.result);tx.onabort=reject;
});}
async function main(){
  const indexedDB=new FDB();
  const env={indexedDB,crypto:webcrypto,isSecureContext:true,TextEncoder,TextDecoder,structuredClone,Blob,Uint8Array,
    btoa:s=>Buffer.from(s,'binary').toString('base64'),atob:s=>Buffer.from(s,'base64').toString('binary'),
    console,AbortController,setTimeout,clearTimeout,sessionStorage:{getItem:()=> 'fake-test-access-key'},navigator:{storage:{estimate:async()=>({usage:0,quota:10485760}),persisted:async()=>true}}};
  env.window=env;
  const runScript=name=>vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web_api/static/js',name),'utf8'),env,{filename:name});
  runScript('offline_secure_store_v5.js');
  runScript('offline_vault.js');
  runScript('offline_sync.js');
  assert.equal(await env.OfflineSecureStore.enabled(),false);
  const db=await new Promise(ok=>{const r=indexedDB.open('YKS_Offline_Store_v1',3);r.onsuccess=()=>ok(r.result);});
  const snapshot={version:1,database_id:'desktop-A',generated_at:'2026-10-14T12:00:00Z',students:[{id:1,name:'TEST_STUDENT_SECRET'}],curriculum:{'1':{lessons:[],topics:{},active_homeworks:[]}}};
  const m={id:'mutation-12345678',type:'ASSIGN_HOMEWORK',seq:1,payload:{student_id:1,lesson:'Fizik',book:'TEST_SECRET_BOOK',topics:['Konu']},created_at:'2026-10-14T13:00:00Z'};
  await write(db,{snapshots:[{key:'current',value:snapshot}],outbox:[m],meta:[{key:'offline_access_v4',value:{version:1,database_id:'desktop-A'}}]});
  const secure=env.OfflineSecureStore;
  await assert.rejects(()=>secure.enable('a very secure password','wrongDB'),/kimliği/);
  const encrypted=await secure.enable('a very secure password','desktop-A');
  assert.equal(encrypted.encrypted_commands,1);
  let raw=await read(db,'snapshots','current'),q=await read(db,'outbox',m.id);
  assert.equal(raw.value.$sealed_v5,1);
  assert.equal(q.encrypted.$sealed_v5,1);
  assert.equal(q.payload,undefined);
  assert(!JSON.stringify(raw).includes('TEST_STUDENT_SECRET'));
  assert(!JSON.stringify(q).includes('TEST_SECRET_BOOK'));
  assert.equal((await secure.openRecord('snapshots','current',raw.value)).students[0].name,'TEST_STUDENT_SECRET');
  secure.lock();
  await assert.rejects(()=>secure.openRecord('snapshots','current',raw.value),/kilitli/);
  await assert.rejects(()=>secure.unlock('wrong wrong password','desktop-A'),/çözülemedi/);
  await assert.rejects(()=>secure.unlock('a very secure password','desktop-Z'),/kimliği/);
  await secure.unlock('a very secure password','desktop-A');
  assert.equal((await secure.openRecord('outbox',m.id,q.encrypted)).payload.book,'TEST_SECRET_BOOK');
  // A wrong associated-record identifier cannot be substituted.
  await assert.rejects(()=>secure.openRecord('outbox','otherId',q.encrypted),/çözülemedi/);
  // V4 backups still work over encrypted V5 stores.
  const blob=await env.OfflineVault.exportEncryptedBackup('another long export password');
  assert(!((await blob.text()).includes('TEST_STUDENT_SECRET')));
  const imported=await env.OfflineVault.importEncryptedBackup(blob,'another long export password');
  assert.equal(imported.imported,0);
  // New offline command remains ciphertext at rest.
  env.OfflineSync.lastSnapshot=snapshot;
  await env.OfflineSync.queueAssignHomework({student_id:1,lesson:'Fizik',book:'ANOTHER_SECRET',topics:['Konu'],due_date:'2026-10-20'});
  const rows=await new Promise(ok=>{const tx=db.transaction('outbox','readonly'),req=tx.objectStore('outbox').getAll();tx.oncomplete=()=>ok(req.result);});
  assert.equal(rows.length,2);
  assert(rows.every(x=>!x.payload&&x.encrypted?.$sealed_v5===1));
  await env.OfflineSync.reloadLocal();
  assert.equal(env.OfflineSync.pendingCount,2);
  assert.equal(await secure.enabled(),true);
  await assert.rejects(()=>secure.enable('a very secure password','desktop-A'),/zaten/);
  // Resolve only a server-verified conflict; discard all earlier synthetic
  // queue commands to model their prior acknowledged receipt.
  await new Promise(resolve=>{const t=db.transaction('outbox','readwrite');
    rows.forEach(x=>t.objectStore('outbox').delete(x.id));t.oncomplete=resolve;});
  const conflictSnap={...snapshot,curriculum:{'1':{...snapshot.curriculum['1'],
    active_homeworks:[{id:7,status:'devam'}],status_fingerprints:{'7':'server-old'}}}};
  const refreshed={...snapshot,generated_at:'2026-10-15T12:00:00Z',curriculum:{'1':{
    ...snapshot.curriculum['1'],active_homeworks:[{id:7,status:'tamam'}],status_fingerprints:{'7':'server-new'}}}};
  env.fetch=async()=>({ok:true,json:async()=>({database_id:'desktop-A'})});
  env._originalApi=async url => {
    assert.equal(url,'/api/sync/snapshot');
    return refreshed;
  };
  env.OfflineSync.lastSnapshot=conflictSnap;
  const status=await env.OfflineSync.queueSetHomeworkStatus({homework_ids:[7],status:'tamam'});
  env.OfflineSync.lastFailures=[{id:status.id,status:'conflict',reason:'Simulated'}];
  const resolve=await env.OfflineSync.resolveConflict(status.id,'mobile');
  assert.notEqual(resolve.replacement,status.id);
  let left=await new Promise(ok=>{const t=db.transaction('outbox','readonly'),r=t.objectStore('outbox').getAll();t.oncomplete=()=>ok(r.result);});
  assert.equal(left.length,1);
  assert.equal(left[0].encrypted.$sealed_v5,1);
  let mutation=await secure.openRecord('outbox',left[0].id,left[0].encrypted);
  assert.equal(mutation.payload.expected_statuses['7'],'tamam');
  assert.equal(mutation.payload.expected_fingerprints['7'],'server-new');
  env.OfflineSync.lastFailures=[{id:left[0].id,status:'conflict',reason:'Simulated'}];
  const removed=await env.OfflineSync.resolveConflict(left[0].id,'desktop');
  assert.equal(removed.replacement,null);
  left=await new Promise(ok=>{const t=db.transaction('outbox','readonly'),r=t.objectStore('outbox').getAll();t.oncomplete=()=>ok(r.result);});
  assert.equal(left.length,0);
  // Model seven days of 100 offline homework actions/day without relying
  // on actual clock passage or a persistent mobile browser process.
  const started=Date.now();
  env.OfflineSync.lastSnapshot=snapshot;
  for(let day=1;day<=7;day++) for(let n=0;n<100;n++) {
    await env.OfflineSync.queueAssignHomework({student_id:1,lesson:'Fizik',book:'BOOK_WEEK_'+day,
        topics:['Soru '+n],due_date:'2026-10-25'});
  }
  assert.equal(env.OfflineSync.pendingCount,700);
  const weekRows=await new Promise(ok=>{const t=db.transaction('outbox','readonly'),r=t.objectStore('outbox').getAll();t.oncomplete=()=>ok(r.result);});
  assert.equal(weekRows.length,700);
  assert(weekRows.every(x=>x.encrypted?.$sealed_v5===1 && !x.payload));
  secure.lock();
  await assert.rejects(()=>env.OfflineSync.reloadLocal(),/kilitli/);
  await secure.unlock('a very secure password','desktop-A');
  await env.OfflineSync.reloadLocal();
  assert.equal(env.OfflineSync.pendingCount,700);
  const weekBackup=await env.OfflineVault.exportEncryptedBackup('another long export password');
  assert.equal((await env.OfflineVault.importEncryptedBackup(weekBackup,'another long export password')).imported,0);
  console.log('PASS 7x100 simulated encrypted offline transactions; encrypted restore and re-entry; '+(Date.now()-started)+' ms in headless test runtime');
  console.log('PASS V5: migration, AES-256-GCM at rest, locked reader, wrong key, wrong DB, AAD integrity, V4 backup, encrypted outbox, two pending commands, explicit conflict reapply and desktop preserve');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
