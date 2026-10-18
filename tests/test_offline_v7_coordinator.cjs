'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const fixture = fs.readFileSync(path.join(__dirname,'test_offline_secure_store_v5.cjs'),'utf8');
const prefix = fixture.slice(0,fixture.indexOf('async function main()'));
const {FDB} = new Function('require','structuredClone',prefix + '\nreturn {FDB};')(require,structuredClone);
const code = fs.readFileSync(path.join(__dirname,'../web_api/static/js/offline_coordinator_v7.js'),'utf8');
function context(indexedDB, locks) {
  const env={indexedDB,crypto:webcrypto,navigator:{locks},setInterval,clearInterval,setTimeout,clearTimeout,console,Date};
  env.window=env; vm.runInNewContext(code,env);return env.OfflineCoordinatorV7;
}
async function main(){
  const db = new FDB();
  const a=context(db,null),b=context(db,null);
  let done;const wait = new Promise(resolve => {done=resolve;});
  let started;
  const running=a.runExclusive(async guard=>{
    await guard.assertOwned();started=true;await wait;await guard.assertOwned();return 'ok';
  });
  for(let i=0;!started&&i<10;i++) await new Promise(r=>setImmediate(r));
  assert.equal(started,true);
  await assert.rejects(()=>b.runExclusive(async()=>{throw Error('must not run');}),/Başka bir sekmede/);
  done(); assert.equal(await running,'ok');
  assert.equal(await b.runExclusive(async()=> 'recovered'), 'recovered');
  assert.equal(await a.runExclusive(async()=> 'next'), 'next');
  let exclusive=false;
  const webLocks={request:async(_name,_options,callback)=>{if(exclusive)return callback(null);
    exclusive=true;try{return await callback({name:'lock'});}finally{exclusive=false;}}};
  const wl=context(new FDB(),webLocks);
  let release;const hold = new Promise(resolve=>release=resolve);
  let begun=false;
  const holder=wl.runExclusive(async()=>{begun=true;await hold;return 'done';});
  for(let i=0;!begun&&i<10;i++)await new Promise(r=>setImmediate(r));
  await assert.rejects(()=>wl.runExclusive(async()=> 'not allowed'),/Başka bir sekmede/);
  release(); assert.equal(await holder,'done');
  assert.equal(await wl.runExclusive(async()=> 'next lock'),'next lock');
  assert.equal(a.isTransient(new TypeError('Failed to fetch')),true);
  assert.equal(a.isTransient(Error('409 conflict')),false);
  assert.equal(a.isTransient(Error('Yetki hatası: Geçerli erişim anahtarı giriniz.')),false);
  let count=0;const delays=[];
  const outcome=await a.sendWithRetry(async()=>{
    count++;if(count<3)throw new TypeError('Failed to fetch');return {success:true};
  },{delay:async ms=>delays.push(ms)});
  assert.equal(outcome.success,true);assert.equal(count,3);assert.deepEqual(delays,[500,1000]);
  count=0;
  await assert.rejects(()=>a.sendWithRetry(async()=>{count++;throw Error('409 conflict');},
    {delay:async()=>{throw Error('must not wait');}}),/409 conflict/);
  assert.equal(count,1);
  count=0;
  await assert.rejects(()=>a.sendWithRetry(async()=>{count++;throw new TypeError('Failed to fetch');},
    {delay:async()=>{}}),/Failed to fetch/);
  assert.equal(count,3);
  let ownerChecked=0;
  await assert.rejects(()=>a.sendWithRetry(async()=>{throw new TypeError('Failed to fetch');},
    {delay:async()=>{},assertOwned:async()=>{if(++ownerChecked===2)throw Error('Lease lost');}}),/Lease lost/);
  assert.equal(ownerChecked,2);
  console.log('PASS V7: two-tab Web Locks; IndexedDB lease, release and recovery; bounded network retries; conflicts non-retry; lease-loss fail-closed');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
