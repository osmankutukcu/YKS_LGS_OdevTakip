'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto}=require('node:crypto');
const source=fs.readFileSync(path.join(__dirname,'test_offline_secure_store_v5.cjs'),'utf8');
const prefix=source.slice(0,source.indexOf('async function main()'));
const {FDB,read,write}=new Function('require','structuredClone',prefix+'\nreturn {FDB,read,write};')(require,structuredClone);
const code=n=>fs.readFileSync(path.join(__dirname,'../web_api/static/js',n),'utf8');
function base(){return {version:1,database_id:'db-A',students:[{id:1}],curriculum:{'1':{lessons:[],topics:{},active_homeworks:[],status_fingerprints:{}}}};}
async function main(){
 const indexedDB=new FDB(), snapshot=base();
 let mode='invalid', calls=0;
 const env={indexedDB,crypto:webcrypto,isSecureContext:true,console,AbortController,setTimeout,clearTimeout,setInterval,clearInterval,
   navigator:{storage:{persist:async()=>true}},sessionStorage:{getItem:()=>''},
   fetch:async()=>({ok:true,json:async()=>({database_id:'db-A'})}),
   OfflineSecureStore:{busy:false,enabled:async()=>false,sealRecord:async(_s,_i,v)=>v,openRecord:async(_s,_i,v)=>v,openRecords:async(_s,v)=>v},
   _originalApi:async(url,_method,body)=>{
    if(url==='/api/sync/snapshot') {if(mode==='download-error')throw Error('snapshot offline');return structuredClone(snapshot);}
    if(url==='/api/sync/push') {
      calls++;
      if(mode==='invalid')return {results:[]};
      if(mode==='retry' && calls===1)throw new TypeError('Failed to fetch');
      return {results:body.mutations.map(m=>({id:m.id,status:'applied'}))};
    }
    throw Error('unexpected API: '+url);
   }};
 env.window=env;
 vm.runInNewContext(code('offline_coordinator_v7.js'),env);
 vm.runInNewContext(code('offline_sync.js'),env);
 // Remove backoff delay in a unit test; transport logic is independently tested.
 const originalRetry=env.OfflineCoordinatorV7.sendWithRetry;
 env.OfflineCoordinatorV7=Object.freeze({...env.OfflineCoordinatorV7,
   sendWithRetry:(send,opts)=>originalRetry(send,{...opts,delay:async()=>{}})});
 const db=await new Promise(ok=>{const r=indexedDB.open('YKS_Offline_Store_v1',3);r.onsuccess=()=>ok(r.result);});
 db.createObjectStore('snapshots',{keyPath:'key'});
 db.createObjectStore('outbox',{keyPath:'id'});
 db.createObjectStore('meta',{keyPath:'key'});
 await write(db,{snapshots:[{key:'current',value:snapshot}],meta:[{key:'next_seq',value:0}]});
 await env.OfflineSync.reloadLocal();
 const one=await env.OfflineSync.queueAssignHomework({student_id:1,lesson:'fizik',book:'K1',topics:['One'],due_date:'2026-10-30'});
 const two=await env.OfflineSync.queueAssignHomework({student_id:1,lesson:'fizik',book:'K2',topics:['Two'],due_date:'2026-10-30'});
 assert.equal(env.OfflineSync.pendingCount,2);
 await assert.rejects(()=>env.OfflineSync.pushSync(),/eksik veya geçersiz işlem onayı/);
 assert((await read(db,'outbox',one.id))?.id);assert((await read(db,'outbox',two.id))?.id);
 mode='retry';calls=0;
 const result=await env.OfflineSync.pushSync();
 assert.equal(result.success,true);assert.equal(result.remaining,0);assert.equal(result.acknowledged_count,2);
 assert.equal(calls,2);
 assert.equal(await read(db,'outbox',one.id),undefined);
 assert.equal(await read(db,'outbox',two.id),undefined);
 const three=await env.OfflineSync.queueAssignHomework({student_id:1,lesson:'fizik',book:'K3',topics:['Three'],due_date:'2026-10-30'});
 mode='download-error';calls=0;
 const incomplete=await env.OfflineSync.pushSync();
 assert.equal(incomplete.snapshot_refresh_needed,true);
 assert.equal(incomplete.success,false);
 assert.equal(incomplete.remaining,0);
 assert.equal(await read(db,'outbox',three.id),undefined);
 // When the desktop snapshot becomes available it can be downloaded normally.
 mode='ready';await env.OfflineSync.downloadSnapshot();
 assert.equal(env.OfflineSync.pendingCount,0);
 console.log('PASS V7: invalid acknowledgement leaves queue intact; network retry preserves IDs; successful receipts deleted; snapshot failure reported separately');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
