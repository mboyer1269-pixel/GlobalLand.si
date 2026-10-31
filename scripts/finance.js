'use strict';
const fs=require('node:fs'),path=require('node:path');const {regular,parseStrict}=require('./task');
function cents(n){if(typeof n!=='number'||!Number.isFinite(n)||n<0||!Number.isSafeInteger(Math.round(n*100))||Math.abs(n*100-Math.round(n*100))>1e-6)throw Error('invalid money');return Math.round(n*100);}
function date(s){if(typeof s!=='string'||!/^\d{4}-\d\d-\d\d$/.test(s)||new Date(s+'T00:00:00Z').toISOString().slice(0,10)!==s)throw Error('invalid UTC date');return s;}
function validateLedger(l){
 if(!l||l.currency!=='CAD'||!Array.isArray(l.transactions)||!l.transactions.length)throw Error('invalid ledger');
 for(const k of ['initial_capital','current_balance','locked_reserve','available_for_agents_without_ceo_approval','weekly_server_tax_cad','kpi_target_balance'])cents(l[k]);
 if(l.initial_capital!==50||!Number.isInteger(l.grace_period_days_remaining)||l.grace_period_days_remaining<0||l.grace_period_days_remaining>7)throw Error('invalid genesis/grace');
 const ids=new Set();let balance=0;
 for(const [i,t] of l.transactions.entries()){
  if(!t||typeof t.id!=='string'||!/^TX-[0-9]{4,12}$/.test(t.id)||ids.has(t.id))throw Error('duplicate/invalid transaction');ids.add(t.id);const n=cents(t.amount);
  if(i===0){if(t.type!=='GENESIS_DEPOSIT'||n!==5000||t.approved_by!=='CEO')throw Error('invalid genesis');balance+=n;continue;}
  if(typeof t.created_at!=='string'||!Number.isFinite(Date.parse(t.created_at)))throw Error('transaction timestamp required');
  if(t.type==='REAL_REVENUE'||t.type==='REAL_EXPENSE'){if(t.approved_by!=='CEO')throw Error('unverified real transaction');balance+=t.type==='REAL_REVENUE'?n:-n;}
  else if(t.type==='DAY_TICK'){if(n!==0)throw Error('tick must be zero');}
  else if(!['NARRATIVE_SERVER_TAX','SERVER_TAX_NARRATIVE','GLC_TRANSFER'].includes(t.type))throw Error('unknown transaction type');
 }
 if(balance!==cents(l.current_balance))throw Error('ledger does not reconcile');
 if(l.locked_reserve>l.current_balance||l.available_for_agents_without_ceo_approval>l.current_balance-l.locked_reserve)throw Error('reserve invariant');
 if(l.last_tick_date!==undefined)date(l.last_tick_date);return l;
}
function tick(input,day=new Date().toISOString().slice(0,10)){
 validateLedger(input);date(day);const l=structuredClone(input);
 if(l.last_tick_date&&day<l.last_tick_date)throw Error('clock moved backwards');if(l.last_tick_date===day)return l;
 const days=l.last_tick_date?Math.round((Date.parse(day)-Date.parse(l.last_tick_date))/86400000):1;
 l.grace_period_days_remaining=Math.max(0,l.grace_period_days_remaining-days);l.last_tick_date=day;
 const next=Math.max(...l.transactions.map(t=>Number(t.id.slice(3))))+1;
 l.transactions.push({id:'TX-'+String(next).padStart(4,'0'),type:'DAY_TICK',amount:0,created_at:day+'T00:00:00Z',approved_by:'AUTO_AUDITOR',note:'UTC tick; elapsed days: '+days});return validateLedger(l);
}
function metrics(l,day=new Date().toISOString().slice(0,10)){
 validateLedger(l);date(day);let revenue=0,weekly=0,narrative=0,glc=0;const end=Date.parse(day)+86400000,start=end-7*86400000;
 for(const t of l.transactions){const n=cents(t.amount);if(t.type==='REAL_REVENUE')revenue+=n;if(['NARRATIVE_SERVER_TAX','SERVER_TAX_NARRATIVE'].includes(t.type))narrative+=n;if(t.type==='GLC_TRANSFER')glc+=n;
 const time=Date.parse(t.created_at);if(time>=start&&time<end){if(t.type==='REAL_REVENUE')weekly+=n;if(t.type==='REAL_EXPENSE')weekly-=n;}}
 return {realBalance:l.current_balance,revenue:revenue/100,weeklyNet:weekly/100,narrativeTax:narrative/100,gLCVolume:glc/100,runwayDays:l.weekly_server_tax_cad?Math.max(0,Math.floor((cents(l.current_balance)-narrative)/cents(l.weekly_server_tax_cad)*7))+l.grace_period_days_remaining:null};
}
function journal(l){validateLedger(l);return '# GlobalLand — journal dérivé du ledger validé (CAD et GLC séparés)\n'+l.transactions.map(t=>[t.created_at||'2026-10-30T00:00:00Z',t.id,t.type,t.amount.toFixed(2)+(t.type==='GLC_TRANSFER'?' GLC':' CAD'),t.approved_by||'NARRATIVE',String(t.note||'').replace(/[\r\n|]/g,' ')].join(' | ')).join('\n')+'\n';}
function atomic(p,data){fs.mkdirSync(path.dirname(p),{recursive:true});const tmp=p+'.tmp-'+process.pid;const fd=fs.openSync(tmp,'wx',0o600);try{fs.writeFileSync(fd,data);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(tmp,p);}
function load(root){return validateLedger(parseStrict(new TextDecoder('utf-8',{fatal:true}).decode(fs.readFileSync(regular(root,'ledger.json')))));}
module.exports={cents,date,validateLedger,tick,metrics,journal,atomic,load};
