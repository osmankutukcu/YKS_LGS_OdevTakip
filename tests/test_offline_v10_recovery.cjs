'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const dir=path.join(__dirname,'../web_api/static/js');
const js=fs.readFileSync(path.join(dir,'offline_resilience_v10.js'),'utf8');
const ctx={};ctx.window=ctx;vm.runInNewContext(js,ctx);
const fallback=ctx.OfflineResilienceV10.canUseFullSnapshot;
for(const httpStatus of [404,410,503]){
 assert.equal(fallback({httpStatus}),true,`transient ${httpStatus}`);
}
for(const httpStatus of [400,401,403,409,413,422,429,500,504]){
 assert.equal(fallback({httpStatus}),false,`fatal ${httpStatus}`);
}
for(const err of [new Error('SHA-256 failed'), new Error('Wrong database'),null,undefined,
 {httpStatus:'410'},{httpStatus:410.1},{}]){
 assert.equal(fallback(err),false,'cannot fallback without trusted numeric HTTP status');
}
const client=fs.readFileSync(path.join(dir,'offline_sync.js'),'utf8');
const view=fs.readFileSync(path.join(__dirname,'../web_api/templates/index.html'),'utf8');
const sw=fs.readFileSync(path.join(__dirname,'../web_api/static/sw.js'),'utf8');
assert(client.includes('OfflineResilienceV10?.canUseFullSnapshot(deltaError)'));
assert(client.includes('OfflinePagedV8.download('));
assert(view.includes('err.httpStatus = res.status'));
assert(view.indexOf('offline_resilience_v10.js')<view.indexOf('offline_sync.js'),
 'helper must load before runtime sync');
assert(sw.includes('offline_resilience_v10.js'));
console.log('PASS V10: transient 404/410/503 only, critical errors fail closed, scripts integrated');
