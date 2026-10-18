'use strict';
// Reuses the V5 headless IDB harness for V6 server-baseline / outbox isolation.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {webcrypto}=require('node:crypto');
const fixture=fs.readFileSync(path.join(__dirname,'test_offline_secure_store_v5.cjs'),'utf8');
const source=fixture.slice(0,fixture.indexOf('async function main()'));
const {FDB,write,read}=new Function('require','structuredClone',source+'\nreturn {FDB,write,read};')(require,structuredClone);
const baseline=(status,tag)=>({version:1,database_id:'same-db',students:[{id:1,ad_soyad:'Sentetik'}],
 curriculum:{'1':{lessons:[],topics:{},status_fingerprints:{'10':'token'},active_homeworks:[{id:10,status,tag}]}}});
async function main(){
  const indexedDB=new FDB(); let remote=baseline('devam','SERVER-B');
  let inject=null;
  const env={indexedDB,crypto:webcrypto,isSecureContext:true,console,AbortController,setTimeout,clearTimeout,
    navigator:{storage:{persist:async()=>true}},sessionStorage:{getItem:()=>''},
    OfflineSecureStore:{busy:false,sealRecord:async(_,__,value)=>{if(inject){const f=inject;inject=null;await f();}return value;},
      openRecord:async(_,__,value)=>value,openRecords:async(_,rows)=>rows,enabled:async()=>false},
    _originalApi:async()=>structuredClone(remote)};
  env.window=env;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web_api/static/js/offline_sync.js'),'utf8'),env,
      {filename:'offline_sync.js'});
  const db=await new Promise(resolve=>{const r=indexedDB.open('YKS_Offline_Store_v1',3);r.onsuccess=()=>resolve(r.result);});
  db.createObjectStore('snapshots',{keyPath:'key'});
  db.createObjectStore('outbox',{keyPath:'id'});
  db.createObjectStore('meta',{keyPath:'key'});
  await write(db,{snapshots:[{key:'current',value:baseline('devam','SERVER-A')}],
    meta:[{key:'next_seq',value:0}]});
  await env.OfflineSync.reloadLocal();
  const mut=await env.OfflineSync.queueSetHomeworkStatus({homework_ids:[10],status:'tamam'});
  assert.equal((await read(db,'snapshots','current')).value.curriculum['1'].active_homeworks[0].status,'devam',
      'queued edit must never be baked into the server baseline');
  await env.OfflineSync.reloadLocal();
  assert.equal(env.OfflineSync.lastSnapshot.curriculum['1'].active_homeworks[0].status,'tamam');
  await env.OfflineSync.downloadSnapshot();
  assert.equal((await read(db,'snapshots','current')).value.curriculum['1'].active_homeworks[0].tag,'SERVER-B');
  assert.equal((await read(db,'snapshots','current')).value.curriculum['1'].active_homeworks[0].status,'devam');
  assert.equal(env.OfflineSync.lastSnapshot.curriculum['1'].active_homeworks[0].status,'tamam');
  // Another tab changes the outbox after we read it but before baseline commit.
  remote=baseline('devam','SERVER-C');
  inject=async()=>write(db,{outbox:[{id:'other-mutation-id',seq:2,
    type:'ASSIGN_HOMEWORK',payload:{student_id:1,lesson:'Fizik',topics:['Konu'],book:'Kitap'},created_at:'2026-10-15T10:00:00Z'}]});
  await assert.rejects(()=>env.OfflineSync.downloadSnapshot(),/kuyruğu indirme sırasında değişti/);
  assert.equal((await read(db,'snapshots','current')).value.curriculum['1'].active_homeworks[0].tag,'SERVER-B',
      'race must retain last valid baseline');
  assert.equal((await read(db,'outbox',mut.id)).id,mut.id,
      'race must not erase the original local command');
  await env.OfflineSync.reloadLocal();
  assert.equal(env.OfflineSync.pendingCount,2);
  console.log('PASS V6: durable server baseline separate from local projection; reload replays queued status; race rejected; 2 queued mutations intact');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
