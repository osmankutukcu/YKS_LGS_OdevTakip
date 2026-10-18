'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const {webcrypto,createHash}=require('node:crypto');
const {TextEncoder}=require('node:util');
const source=fs.readFileSync(path.join(__dirname,'../web_api/static/js/offline_paged_v8.js'),'utf8');
const payload={version:1,database_id:'desktop-A',students:Array.from({length:500},(_,id)=>({id:id+1,ad_soyad:'Öğrenci '+id})),curriculum:{}};
for(const s of payload.students)payload.curriculum[s.id]={lessons:[],books:{},topics:{}};
const original=JSON.stringify(payload); // source wire can use any valid exact JSON payload
const digest=createHash('sha256').update(original).digest('hex');
const PAGE=2500;
const all=[];
for(let p=0;p<original.length;p+=PAGE)all.push(original.slice(p,p+PAGE));
const meta={version:8,token:'token-is-opaque-at-least-thirty-chars-aaaaaaaa',database_id:'desktop-A',sha256:digest,pages:all.length,size:original.length,page_chars:PAGE,expires_in_seconds:720};
async function run(){
 const env={TextEncoder,crypto:webcrypto,console};env.window=env;
 vm.runInNewContext(source,env);
 let mode='good',counts=0,closed=0;
 const api=async(url,method)=>{
  if(url.endsWith('/start'))return {...meta};
  if(url.endsWith('/close')){closed++;return {ok:true};}
  const page=Number(url.slice(url.lastIndexOf('/')+1));counts++;
  if(mode==='missing' && page===1)throw Error('Connection lost');
  const chunk=(mode==='corrupt' && page===1) ? 'X'+all[page].slice(1):all[page];
  return {version:8,page,pages:all.length,sha256:digest,chunk};
 };
 const progress=[];
 const snap=await env.OfflinePagedV8.download({api,expectedDatabaseId:'desktop-A',progress:(n,t)=>progress.push([n,t])});
 assert.equal(snap.students.length,500);
 assert.equal(snap.students[0].ad_soyad,'Öğrenci 0');
 assert.equal(progress.length,all.length);
 assert.equal(closed,1);
 mode='missing';await assert.rejects(()=>env.OfflinePagedV8.download({api}),/Connection lost/);
 assert.equal(closed,2,'failed sessions are closed');
 mode='corrupt';await assert.rejects(()=>env.OfflinePagedV8.download({api}),/SHA-256/);
 assert.equal(closed,3);
 mode='good';counts=0;
 await assert.rejects(()=>env.OfflinePagedV8.download({api,expectedDatabaseId:'desktop-B'}),/kimliği farklı/);
 assert.equal(counts,0,'wrong desktop detected before downloading any data');
 console.log('PASS V8 paged: 500 students, progress, SHA256, dropped page, corrupted data, desktop mismatch');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
