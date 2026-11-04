'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {collect,safe,execute}=require('../scripts/executor');

test('UTF-8 collection preserves BOM, Unicode and line endings byte for byte',t=>{
 const d=fs.mkdtempSync(path.join(os.tmpdir(),'gl-utf8-'));
 t.after(()=>fs.rmSync(d,{force:true,recursive:true}));
 fs.mkdirSync(path.join(d,'products'));
 const original=Buffer.from('\uFEFFQuébec,24.00\r\n東京,7.00\n','utf8');
 fs.writeFileSync(path.join(d,'products/result.csv'),original);
 const result=collect(d,['products/result.csv']);
 assert.deepEqual(Buffer.from(result['products/result.csv'],'utf8'),original);
});
test('generated product artifact is collected without host path access',t=>{const d=fs.mkdtempSync(path.join(os.tmpdir(),'gl-exec-'));t.after(()=>fs.rmSync(d,{force:true,recursive:true}));fs.mkdirSync(path.join(d,'products'));fs.writeFileSync(path.join(d,'products/a.txt'),'product');assert.deepEqual(collect(d,['products/a.txt']),{'products/a.txt':'product'});fs.symlinkSync('/etc/passwd',path.join(d,'products/link'));assert.throws(()=>collect(d,['products/link']));fs.linkSync(path.join(d,'products/a.txt'),path.join(d,'products/hard'));assert.throws(()=>collect(d,['products/hard']));});
test('publication stays inside visible products',()=>{for(const n of ['../oria','products/../x','/products/x','products/.env','scripts/control.py'])assert.throws(()=>safe(n));});
test('binary artifacts explain how to recover without publishing partial files',t=>{
 const d=fs.mkdtempSync(path.join(os.tmpdir(),'gl-binary-exec-'));
 t.after(()=>fs.rmSync(d,{force:true,recursive:true}));
 const input=path.join(d,'input'),root=path.join(d,'work'),request=path.join(d,'request.json');
 fs.mkdirSync(input);fs.mkdirSync(path.join(input,'products'));fs.mkdirSync(root);
 const program="const f=require('fs');f.writeFileSync('products/note.txt','partial');f.writeFileSync('products/bundle.zip',Buffer.from([255,0,128]));";
 fs.writeFileSync(request,JSON.stringify({argv:[process.execPath,'-e',program],outputs:['products/note.txt','products/bundle.zip']}));
 const result=execute(input,root,request);
 assert.equal(result.status,'FAILED');assert.match(result.output,/UTF-8.*base64/);assert.deepEqual(result.files,{});
});
test('failed generated program reports its error without publishing partial products',t=>{
 const d=fs.mkdtempSync(path.join(os.tmpdir(),'gl-failed-exec-'));
 t.after(()=>fs.rmSync(d,{force:true,recursive:true}));
 const input=path.join(d,'input'),root=path.join(d,'work'),request=path.join(d,'request.json');
 fs.mkdirSync(input);fs.mkdirSync(path.join(input,'products'));fs.mkdirSync(root);
 const program="const fs=require('fs');fs.writeFileSync('products/partial.txt','unfinished');fs.writeSync(1,'fixture started');fs.writeSync(2,'AssertionError: expected 4 issues, got 5\\n'+'x'.repeat(12000));process.exitCode=1";
 fs.writeFileSync(request,JSON.stringify({argv:[process.execPath,'-e',program],outputs:['products/partial.txt']}));
 const result=execute(input,root,request);
 assert.equal(result.status,'FAILED');
 assert.match(result.output,/AssertionError: expected 4 issues, got 5/);
 assert.match(result.output,/Process failed: 1/);
 assert.match(result.output,/fixture started/);
 assert.ok(result.output.length<=8000);
 assert.deepEqual(result.files,{});
 assert.equal(fs.readFileSync(path.join(root,'products/partial.txt'),'utf8'),'unfinished');
});
