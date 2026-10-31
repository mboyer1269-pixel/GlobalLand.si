'use strict';
const {test}=require('node:test'); const assert=require('node:assert/strict');
const fs=require('node:fs'), os=require('node:os'), path=require('node:path'), crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const base=path.resolve(__dirname,'..');
function temp(t){const d=fs.mkdtempSync(path.join(os.tmpdir(),'gl-test-'));t.after(()=>fs.rmSync(d,{recursive:true,force:true}));return d;}
const task={id:'TASK-0001',type:'SHELL',submitted_by:'AUDITOR',created_at:'2026-10-30T00:00:00Z',action:'AUDIT',args:[],estimated_cost_cad:0,approved_by:null};
test('task validation rejects shell commands and invalid values',()=>{
 const {validateTask}=require('../scripts/task');
 assert.deepEqual(validateTask(task),task);
 for(const patch of [{action:'node -p 1; printf bad'},{type:'UNKNOWN'},{estimated_cost_cad:-1},{estimated_cost_cad:Infinity},{estimated_cost_cad:'0'},{id:'../x'},{id:''},{args:['anything']},{approved_by:'CEO'},{extra:1},{type:'AGENT_CODE'}])assert.throws(()=>validateTask({...task,...patch}));
});
test('task input rejects paths, symlinks and filename/id mismatch',t=>{
 const {readTask}=require('../scripts/task'); const d=temp(t);fs.mkdirSync(path.join(d,'queue/inbox'),{recursive:true});
 const p=path.join(d,'queue/inbox/TASK-0001.json'); fs.writeFileSync(p,JSON.stringify(task));assert.equal(readTask(d,'queue/inbox/TASK-0001.json').id,task.id);
 assert.throws(()=>readTask(d,'../outside.json'));fs.renameSync(p,p+'.real');fs.symlinkSync(p+'.real',p);assert.throws(()=>readTask(d,'queue/inbox/TASK-0001.json'));
 fs.unlinkSync(p);fs.writeFileSync(p,JSON.stringify({...task,id:'TASK-0002'}));assert.throws(()=>readTask(d,'queue/inbox/TASK-0001.json'));
});
test('offline CEO approval binds exact task bytes, not a JSON label',()=>{
 const {verifyApproval}=require('../scripts/task'); const {publicKey,privateKey}=crypto.generateKeyPairSync('ed25519'); const raw=Buffer.from(JSON.stringify(task)); const sig=crypto.sign(null,raw,privateKey).toString('base64');
 assert.equal(verifyApproval(raw,sig,publicKey),true);assert.equal(verifyApproval(Buffer.concat([raw,Buffer.from(' ')]),sig,publicKey),false);assert.equal(verifyApproval(raw,'CEO',publicKey),false);
});
test('UTC tick is idempotent and journal matches ledger',t=>{
 const {tick,validateLedger,journal}=require('../scripts/finance'); const d=temp(t);let l=JSON.parse(fs.readFileSync(path.join(base,'tests/fixtures/genesis.json')));
 const a=tick(l,'2026-10-30'); assert.equal(a.grace_period_days_remaining,6);assert.deepEqual(tick(a,'2026-10-30'),a);assert.throws(()=>tick(a,'2026-10-29'));
 assert.ok(journal(a).includes('DAY_TICK'));assert.equal(validateLedger(a).current_balance,50);assert.equal(l.grace_period_days_remaining,7);
 assert.throws(()=>validateLedger({...a,current_balance:49}));assert.throws(()=>validateLedger({...a,transactions:[...a.transactions,a.transactions[0]]}));
});
test('audit counts real flows and keeps narrative/GLC separate',()=>{
 const {metrics}=require('../scripts/finance');let l=JSON.parse(fs.readFileSync(path.join(base,'tests/fixtures/genesis.json')));l.current_balance=58;
 l.transactions.push({id:'TX-0002',type:'REAL_REVENUE',amount:10,created_at:'2026-10-30T00:00:00Z',approved_by:'CEO',note:'fixture'}, {id:'TX-0003',type:'REAL_EXPENSE',amount:2,created_at:'2026-10-30T00:00:00Z',approved_by:'CEO',note:'fixture'}, {id:'TX-0004',type:'NARRATIVE_SERVER_TAX',amount:2,created_at:'2026-10-30T00:00:00Z',note:'fixture'}, {id:'TX-0005',type:'GLC_TRANSFER',amount:100,created_at:'2026-10-30T00:00:00Z',note:'fixture'});
 const m=metrics(l,'2026-10-30');assert.equal(m.revenue,10);assert.equal(m.weeklyNet,8);assert.equal(m.realBalance,58);assert.equal(m.narrativeTax,2);assert.equal(m.gLCVolume,100);
});
test('trusted worker completes only explicit audit and rejects legacy shell',t=>{
 const {runTask}=require('../scripts/run_task'); const d=temp(t);fs.mkdirSync(path.join(d,'queue/inbox'),{recursive:true});fs.copyFileSync(path.join(base,'tests/fixtures/genesis.json'),path.join(d,'ledger.json'));const p=path.join(d,'queue/inbox/TASK-0001.json');
 fs.writeFileSync(p,JSON.stringify(task));assert.equal(runTask(d,'queue/inbox/TASK-0001.json').status,'DONE');
 fs.writeFileSync(p,JSON.stringify({...task,action:'node -p 1'}));assert.throws(()=>runTask(d,'queue/inbox/TASK-0001.json'));
});
test('strict JSON refuses duplicate fields and arrays disguised as objects',t=>{
 const {parseStrict}=require('../scripts/task');assert.throws(()=>parseStrict('{"action":"AUDIT","action":"other"}'));
 assert.throws(()=>parseStrict('{"a":{"x":1,"x":2}}'));assert.deepEqual(parseStrict('{"a":[{"x":1},{"x":2}]}'),{a:[{x:1},{x:2}]});
});
test('missed UTC days catch up, backwards dates fail, zero tax means unlimited runway',()=>{
 const {tick,metrics}=require('../scripts/finance');const l=JSON.parse(fs.readFileSync(path.join(base,'tests/fixtures/genesis.json')));
 const a=tick(l,'2026-10-30');assert.equal(tick(a,'2026-11-02').grace_period_days_remaining,3);
 assert.equal(metrics({...l,weekly_server_tax_cad:0}).runwayDays,null);assert.throws(()=>tick(l,'2026-02-30'));
});
