'use strict';
// Installed trusted wrapper. Generated programs run only in the disposable container.
const fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
function safe(name){if(typeof name!=='string'||!name.startsWith('products/')||name.split('/').some(p=>!p||p==='.'||p==='..'||p.startsWith('.'))||name.includes('\\'))throw Error('invalid product path');return name;}
function collect(root,names){let total=0;const files={};if(!Array.isArray(names)||names.length>64)throw Error('output count');
 for(const name of names){safe(name);let p=root;for(const part of name.split('/')){p=path.join(p,part);if(fs.lstatSync(p).isSymbolicLink())throw Error('symlink output');}
 const stat=fs.statSync(p);total+=stat.size;if(!stat.isFile()||stat.nlink!==1||stat.size>1024*1024||total>8*1024*1024)throw Error('artifact limit');
 const raw=fs.readFileSync(p),text=new TextDecoder('utf-8',{fatal:true}).decode(raw);files[name]=text;}
 return files;
}
function execute(input='/input',root='/workspace',request='/request.json'){
 const args=JSON.parse(fs.readFileSync(request,'utf8'));
 fs.cpSync(input,root,{recursive:true,dereference:false,filter:src=>!fs.lstatSync(src).isSymbolicLink()});
 const cwd=args.cwd?path.resolve(root,args.cwd):root;if(cwd!==root&&!cwd.startsWith(root+path.sep))throw Error('invalid cwd');
 const run=spawnSync(args.argv[0],args.argv.slice(1),{cwd,timeout:60000,maxBuffer:1024*1024,encoding:'utf8',env:{PATH:process.env.PATH,HOME:'/tmp',TMPDIR:'/tmp'},stdio:['ignore','pipe','pipe']});
 if(run.error||run.status!==0)return{status:run.error?.code==='ETIMEDOUT'?'TIMEOUT':'FAILED',output:'Process failed: '+(run.error?.code||run.status),files:{}};
 return{status:'DONE',output:((run.stdout||'')+'\n'+(run.stderr||'')).slice(0,8000),files:collect(root,args.outputs||[])};
}
if(require.main===module){try{process.stdout.write(JSON.stringify(execute())+'\n');}catch{process.stdout.write(JSON.stringify({status:'FAILED',output:'Sandbox artifact/execution validation failed',files:{}})+'\n');process.exitCode=1;}}
module.exports={safe,collect,execute};
