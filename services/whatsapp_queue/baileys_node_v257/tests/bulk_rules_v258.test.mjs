import test from 'node:test';import assert from 'node:assert/strict';
import {validateSend,allowedToSend,MAX_BATCH,MIN_DELAY_MS} from '../bulk_rules_v258.mjs';
const req={cmd:'send-one',approval:'IZINLI_TOPLU_V258',id:'a'.repeat(32),phone:'905321234567',text:'Ödev hatırlatma'};
test('requires explicit approval and correct id',()=>{
 assert.equal(validateSend(req).phone,req.phone);
 for(const patch of [{approval:'yes'},{phone:'not a phone'},{text:''},{id:'abcd'},{text:'x'.repeat(3001)}])
  assert.throws(()=>validateSend({...req,...patch}));
});
test('cannot flood, duplicate or exceed 150',()=>{
 const baseline={connected:true,busy:false,count:0,previousAt:0,now:25000,seen:new Set()};
 assert.equal(allowedToSend(baseline,req),true);
 assert.equal(allowedToSend({...baseline,count:MAX_BATCH},req),false);
 assert.equal(allowedToSend({...baseline,busy:true},req),false);
 assert.equal(allowedToSend({...baseline,seen:new Set([req.phone])},req),false);
 assert.equal(allowedToSend({...baseline,previousAt:25000,now:25000+MIN_DELAY_MS-1},req),false);
 assert.equal(allowedToSend({...baseline,previousAt:25000,now:25000+MIN_DELAY_MS},req),true);
});
