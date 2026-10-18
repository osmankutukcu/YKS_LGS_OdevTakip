'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const {webcrypto, createHash} = require('node:crypto');
const {TextEncoder} = require('node:util');
const source = fs.readFileSync(path.join(__dirname,'../web_api/static/js/offline_delta_v9.js'),'utf8');
const env = {crypto: webcrypto, TextEncoder, console};env.window=env;
vm.runInNewContext(source, env);
const sdk = env.OfflineDeltaV9;
const sha = s=>createHash('sha256').update(s).digest('hex');
const baseline={version:1,database_id:'test-db',generated_at:'old',
  students:Array.from({length:500},(_,i)=>({id:i+1,ad:`Öğrenci ${i}`})),curriculum:{}};
for(const s of baseline.students)baseline.curriculum[s.id]={lessons:[],books:{'10':['Fizik']},topics:{'2':[{'value':1.0}]}};

function getPatch(base, latest, clientManifest) {
  const order=[], index={},changed={};
  for(const student of latest.students){
    const id=String(student.id);order.push(id);
    const digest=sha(sdk.canonical({student,curriculum:latest.curriculum[id]}));
    index[id]=digest;
    if(clientManifest[id]!==digest)changed[id]={student,curriculum:latest.curriculum[id]};
  }
  return {version:9,snapshot_version:1,database_id:latest.database_id,
      generated_at:'server-now', order,index,changed,
      removed:Object.keys(clientManifest).filter(id=>!(id in index))};
}
async function main() {
  const latest=structuredClone(baseline);
  latest.students[0].ad='Değişti';
  latest.curriculum['33'].topics['2']=[{value:3}];
  latest.students.splice(199,1);delete latest.curriculum['200'];
  latest.students.push({id:900,ad:'Yeni'});latest.curriculum['900']={lessons:[],books:{},topics:{}};
  let fault='', opened=0,closed=0, lastRequest, payload;
  const api=async (url,method,body)=>{
    if(url.endsWith('/start')) {
      opened++;lastRequest=body;
      const patch=getPatch(baseline,latest,body.manifest);
      payload=JSON.stringify(patch);
      if(fault==='bad-index') patch.index['1']='f'.repeat(64);
      // Make the patch intentionally malicious BEFORE hashing, to test per-row check.
      if(fault==='bad-index') payload=JSON.stringify(patch);
      return {version:9,token:'opaque-session-xxxxxxxxxxxxxxxxxxx-aaa',database_id:latest.database_id,
        sha256:sha(payload),size:payload.length,pages:Math.ceil(payload.length/3000),page_chars:3000};
    }
    if(url.endsWith('/close')){closed++;return {ok:true};}
    const page=Number(url.split('/').pop());
    if(fault==='drop' && page===1)throw Error('Network disconnected');
    const chunk=payload.slice(page*3000,(page+1)*3000);
    return {version:9,page,pages:Math.ceil(payload.length/3000),sha256:sha(payload),
      chunk:fault==='wire-corrupt'&&page===1?'Z'+chunk.slice(1):chunk};
  };
  const result=await sdk.download({api,baseline});
  assert.equal(result.stats.changed,3);
  assert.equal(result.stats.removed,1);
  assert.equal(result.snapshot.students.length,500);
  assert.equal(result.snapshot.students[0].ad,'Değişti');
  assert.equal(result.snapshot.curriculum['33'].topics['2'][0].value,3);
  assert.equal(result.snapshot.curriculum['200'],undefined);
  assert.equal(result.snapshot.students.at(-1).id,900);
  assert.equal(baseline.students[0].ad,'Öğrenci 0','baseline unchanged');
  assert.equal(lastRequest.manifest['1'],await sdk.rowHash(baseline.students[0],baseline.curriculum['1']));
  fault='drop';await assert.rejects(()=>sdk.download({api,baseline}),/Network disconnected/);
  fault='wire-corrupt';await assert.rejects(()=>sdk.download({api,baseline}),/bütünlük/);
  fault='bad-index';await assert.rejects(()=>sdk.download({api,baseline}),/doğrulanamadı/);
  assert.equal(opened,closed,'sessions always closed');
  console.log('PASS V9 delta: 500 records, 3 changes, 1 deletion, baseline isolation, drop, SHA and per-row corruption');
}
main().catch(e=>{console.error(e);process.exitCode=1});
