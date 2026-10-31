'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {collect,safe}=require('../scripts/executor');
test('generated product artifact is collected without host path access',t=>{const d=fs.mkdtempSync(path.join(os.tmpdir(),'gl-exec-'));t.after(()=>fs.rmSync(d,{force:true,recursive:true}));fs.mkdirSync(path.join(d,'products'));fs.writeFileSync(path.join(d,'products/a.txt'),'product');assert.deepEqual(collect(d,['products/a.txt']),{'products/a.txt':'product'});fs.symlinkSync('/etc/passwd',path.join(d,'products/link'));assert.throws(()=>collect(d,['products/link']));fs.linkSync(path.join(d,'products/a.txt'),path.join(d,'products/hard'));assert.throws(()=>collect(d,['products/hard']));});
test('publication stays inside visible products',()=>{for(const n of ['../oria','products/../x','/products/x','products/.env','scripts/control.py'])assert.throws(()=>safe(n));});
