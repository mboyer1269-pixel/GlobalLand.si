'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
// JSON.parse validates grammar; a token walk additionally rejects duplicate keys.
function parseStrict(raw){
 const parsed=JSON.parse(raw),tokens=raw.match(/"(?:\\[\s\S]|[^"\\])*"|[{}\[\]:,]|[^\s{}\[\]:,]+/g);let i=0;
 function walk(depth=0){
  if(depth>32)throw Error('JSON nesting limit');const token=tokens[i++];
  if(token==='{'){const keys=new Set();while(tokens[i]!=='}'){const key=JSON.parse(tokens[i++]);if(keys.has(key))throw Error('duplicate JSON key');keys.add(key);i++;walk(depth+1);if(tokens[i]===',')i++;}i++;}
  else if(token==='['){while(tokens[i]!==']'){walk(depth+1);if(tokens[i]===',')i++;}i++;}
 }
 walk();return parsed;
}
function regular(root,rel){
 if(typeof rel!=='string'||path.isAbsolute(rel)||rel.split('/').some(x=>!x||x==='.'||x==='..'))throw Error('unsafe path');
 let p=path.resolve(root);if(fs.lstatSync(p).isSymbolicLink())throw Error('symlink root');
 for(const part of rel.split('/')){p=path.join(p,part);if(fs.lstatSync(p).isSymbolicLink())throw Error('symlink');}
 if(!fs.statSync(p).isFile()||fs.statSync(p).size>1024*1024)throw Error('invalid file');return p;
}
function validateTask(t){
 const keys=['id','type','submitted_by','created_at','action','args','description','estimated_cost_cad','approved_by'];
 if(!t||typeof t!=='object'||Array.isArray(t)||Object.keys(t).some(k=>!keys.includes(k)))throw Error('unknown task fields');
 if(!/^TASK-[0-9]{4,12}$/.test(t.id)||t.type!=='SHELL')throw Error('invalid id/type; AGENT_CODE disabled');
 if(t.action!=='AUDIT'||!Array.isArray(t.args)||t.args.length)throw Error('only AUDIT with empty args is registered');
 if(typeof t.estimated_cost_cad!=='number'||!Number.isFinite(t.estimated_cost_cad)||t.estimated_cost_cad!==0||t.approved_by!==null)throw Error('only free unapproved tasks allowed');
 if(typeof t.submitted_by!=='string'||! /^[A-Z0-9_-]{1,64}$/.test(t.submitted_by))throw Error('invalid submitter');
 if(typeof t.created_at!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(t.created_at)||!Number.isFinite(Date.parse(t.created_at)))throw Error('invalid timestamp');
 if(t.description!==undefined&&(typeof t.description!=='string'||t.description.length>1000))throw Error('invalid description');return t;
}
function readTask(root,rel){if(!/^queue\/inbox\/TASK-[0-9]{4,12}\.json$/.test(rel))throw Error('invalid inbox path');const t=validateTask(parseStrict(new TextDecoder('utf-8',{fatal:true}).decode(fs.readFileSync(regular(root,rel)))));if(path.basename(rel)!==t.id+'.json')throw Error('filename/id mismatch');return t;}
function verifyApproval(raw,signature,publicKey){try{return crypto.verify(null,raw,publicKey,Buffer.from(signature,'base64'));}catch{return false;}}
module.exports={regular,validateTask,readTask,verifyApproval,parseStrict};
