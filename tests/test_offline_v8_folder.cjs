'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const {webcrypto}=require('node:crypto');
const {TextEncoder}=require('node:util');
const {File}=require('node:buffer');
const source=fs.readFileSync(path.join(__dirname,'../web_api/static/js/offline_folder_v8.js'),'utf8');
let contents=new Map(),permission='granted',fail=false;
const handle={kind:'directory',name:'YKS-LGS-OdevTakip',queryPermission:async()=>permission,
 requestPermission:async()=>permission,
 getFileHandle:async(name,options)=>{
  assert(options.create);
  return {createWritable:async()=>({write:async(blob)=>{if(fail)throw Error('disk-full');contents.set(name,blob);},close:async()=>{},abort:async()=>{}}),
    getFile:async()=>contents.get(name)};
 }};
const env={window:null,crypto:webcrypto,TextEncoder,File,Blob,console,setTimeout,URL,
 isSecureContext:true,showDirectoryPicker:async()=>handle,
 document:{body:{append(){}},createElement:()=>({click(){},remove(){}})},
 navigator:{canShare:()=>true,share:async()=>{env.shared=true;}}};env.window=env;
vm.runInNewContext(source,env);
async function main(){
  const blob=new Blob(['{ "encrypted": "dummy-ciphertext-not-student-data" }']);
  const saved=await env.OfflineFolderV8.writeBackup(handle,blob,'backup1.yksbackup');
  assert.equal(saved,'backup1.yksbackup');
  assert.equal((await contents.get(saved).text()),(await blob.text()));
  fail=true;await assert.rejects(()=>env.OfflineFolderV8.writeBackup(handle,blob,'broken.yksbackup'),/disk-full/);
  assert(contents.has(saved),'failed write must not delete earlier backup');fail=false;
  permission='denied';await assert.rejects(()=>env.OfflineFolderV8.writeBackup(handle,blob,'denied.yksbackup'),/izni verilmedi/);
  permission='granted';
  const shared=await env.OfflineFolderV8.downloadOrShare(blob,'mobile.yksbackup');
  assert.equal(shared.method,'share');assert(env.shared);
  console.log('PASS V8 folder: verified encrypted blob write, failure preserves old backup, permission refusal, iOS share fallback');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
