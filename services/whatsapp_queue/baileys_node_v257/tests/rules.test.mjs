import test from 'node:test';import assert from 'node:assert/strict';
import {phone,checkCommand,resultCode} from '../rules.mjs';
test('phone canonical',()=>{assert.equal(phone('0532 123 45 67'),'905321234567');assert.equal(phone('+905321234567'),'905321234567')});
test('invalid',()=>{for(const v of ['','abc','905321234567,905331111111','532123','02121234567'])assert.throws(()=>phone(v))});
test('single gated',()=>{assert.throws(()=>checkCommand({cmd:'send-test',phone:'05321234567'}));assert.deepEqual(checkCommand({cmd:'stop'}),{cmd:'stop'});assert.equal(checkCommand({cmd:'send-test',approval:'TEK TEST ONAYI',phone:'05321234567'}).phone,'905321234567')});
test('no delivery claim',()=>assert.equal(resultCode('a'),'ISTEMCI_KABUL_ETTI_TESLIM_BELIRSIZ'));
