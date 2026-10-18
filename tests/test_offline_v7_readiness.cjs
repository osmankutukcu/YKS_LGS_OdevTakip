'use strict';
// Headless Service Worker and audit tests. Browser/PWA hardware testing remains required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const SW = fs.readFileSync(path.join(__dirname, '../web_api/static/sw.js'), 'utf8');
const AUDIT = fs.readFileSync(path.join(__dirname, '../web_api/static/js/offline_health_v6.js'), 'utf8');
const mime = path => path === '/' ? 'text/html' : path.endsWith('.json') ? 'application/json' :
    path.endsWith('.js') ? 'text/javascript' : 'image/png';
function response(path) {return {ok:true, type:'basic',redirected:false,path,
  headers:{get:() => mime(path)},clone(){return response(path);}};}
function fixtures(failed=null) {
    const handlers = new Map(), stores = new Map();
    const storage = {
      async open(name) { if (!stores.has(name)) stores.set(name,new Map()); const map=stores.get(name);
        return {async put(key,value){map.set(key,value);},async match(key){return map.get(key)||null;}};},
      async keys(){return [...stores.keys()];}, async delete(name){return stores.delete(name);}
    };
    let fetches=0, claims=0;
    const self={location:{origin:'https://example.test'},clients:{claim:async()=>{claims++;}},
      addEventListener(name,handler){handlers.set(name,handler);}};
    const env={self,caches:storage,URL,Response:{error:()=>({error:true})},Set,
      fetch:async arg=>{fetches++;const p=typeof arg==='string' ? arg : new URL(arg.url).pathname;
          if(p===failed)throw new Error('offline fail');return response(p);}};
    vm.runInNewContext(SW,env,{filename:'sw.js'});
    async function fire(name,request) {
      let waiting,responded;
      const event={request,waitUntil:p=>{waiting=p;},respondWith:p=>{responded=p;},data:request?.data,ports:request?.ports};
      handlers.get(name)(event);
      if(waiting)await waiting;
      return responded ? await responded : undefined;
    }
    return {fire,storage,stores,claims:()=>claims,fetches:()=>fetches,handlers};
}
class Channel {
  constructor(){const a={onmessage:null,close(){}};const b={onmessage:null,close(){}};
    a.postMessage=v=>b.onmessage?.({data:v});b.postMessage=v=>a.onmessage?.({data:v});
    this.port1=a;this.port2=b;
  }
}
async function auditFixture(broken={}){
  const assets=['/', '/static/js/offline_secure_store_v5.js','/static/js/offline_vault.js',
    '/static/js/offline_coordinator_v7.js','/static/js/offline_paged_v8.js','/static/js/offline_delta_v9.js','/static/js/offline_resilience_v10.js','/static/js/offline_folder_v8.js','/static/js/offline_sync.js', '/static/js/offline_health_v6.js','/static/manifest.json',
    '/static/tailwindcss.js','/static/vue.js','/static/favicon.png',
    '/static/apple-touch-icon.png','/static/icon-192.png','/static/icon-512.png'];
  const readyVersion=broken.oldWorker ? 9 : 10;
  const env={window:null,isSecureContext:!broken.http,crypto:broken.http ? undefined : {subtle:{}},
    indexedDB:broken.noDb ? null : {},MessageChannel:Channel,console,Date,setTimeout,clearTimeout,
    OfflineSync:{pendingCount:7,lastSnapshot:broken.noSnapshot ? null :
      {version:1,database_id:'test-db',students:[{id:1}],curriculum:{1:{}}}},
    OfflineSecureStore:{enabled:async()=>!broken.noEncryption},
    OfflineVault:{configuredDatabaseId:async()=>broken.wrongDb?'wrong-db':'test-db'},
    caches:{open:async()=>({match:async p=>(broken.missingAsset && p===broken.missingAsset ? null : {ok:true})})},
    navigator:{storage:{estimate:async()=>({usage:100,quota:1000}),persisted:async()=>!broken.noPersistence},
      serviceWorker:{getRegistration:async()=>({active:{postMessage:(_,ports)=>{
        ports[0].postMessage({version:readyVersion,cache:'yks-kocluk-shell-v10'});
      }}})}}};
  env.window=env;
  vm.runInNewContext(AUDIT,env,{filename:'offline_health_v6.js'});
  assert.deepEqual([...env.OfflineHealthV6.requiredAssets],assets);
  return await env.OfflineHealthV6.audit();
}
async function main(){
  const f=fixtures();
  // Before activation old shell is still retained.
  const old=await f.storage.open('yks-kocluk-shell-v5');await old.put('/','old-html');
  await f.fire('install');
  assert.equal((await f.storage.keys()).length,2);
  const shell=await f.storage.open('yks-kocluk-shell-v10');
  assert((await shell.match('/static/js/offline_health_v6.js')));
  await f.fire('activate');
  assert.deepEqual(await f.storage.keys(),['yks-kocluk-shell-v10']);
  assert.equal(f.claims(),1);
  let req={method:'GET',mode:'navigate',url:'https://example.test/'};
  const fetchesBefore=f.fetches();
  assert.equal((await f.fire('fetch',req)).path,'/');
  assert.equal(f.fetches(),fetchesBefore,'offline app shell must be cache-first');
  assert.equal(await f.fire('fetch',{...req,url:'https://example.test/api/sync/snapshot'}),undefined,
    'personal API calls must be excluded');
  assert.equal(await f.fire('fetch',{...req,method:'POST'}),undefined);
  assert.equal(await f.fire('fetch',{...req,url:'https://untrusted.test/'}),undefined);
  let msg;
  await f.fire('message',{data:{type:'YKS_OFFLINE_VERSION'},ports:[{postMessage:data=>{msg=data;}}]});
  assert.equal(msg.version,10);

  const failed=fixtures('/static/js/offline_sync.js');
  const prev=await failed.storage.open('yks-kocluk-shell-v5');await prev.put('/','old-good-shell');
  await assert.rejects(()=>failed.fire('install'),/offline fail/);
  assert.deepEqual(await failed.storage.keys(),['yks-kocluk-shell-v5'],
    'failure must retain previous complete working shell');

  const healthy=await auditFixture();
  assert.equal(healthy.ready,true);
  assert.equal(healthy.pending,7);
  assert.equal(healthy.missing_assets.length,0);
  const encryptedWarning=await auditFixture({noEncryption:true,noPersistence:true});
  assert.equal(encryptedWarning.ready,true);
  assert(encryptedWarning.results.some(x=>x.code==='encrypted' && x.severity==='warning'));
  for (const failure of [{missingAsset:'/'},{oldWorker:true},{noSnapshot:true},
         {wrongDb:true},{noDb:true},{http:true}]) {
    const r=await auditFixture(failure);
    assert.equal(r.ready,false,'must fail closed: '+JSON.stringify(failure));
  }
  console.log('PASS V10: atomic shell install, safe upgrade, cache-first offline restart, API exclusion, version handshake, 8 readiness scenarios');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
