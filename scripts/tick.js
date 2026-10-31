#!/usr/bin/env node
'use strict';
const path=require('node:path');const {load,tick,journal,atomic}=require('./finance');
function daily(root,day){const l=tick(load(root),day);atomic(path.join(root,'ledger.json'),JSON.stringify(l,null,2)+'\n');atomic(path.join(root,'logs/transactions.log'),journal(l));return l;}
if(require.main===module){try{daily(process.argv[2]||path.resolve(__dirname,'..'));}catch(e){console.error(e.message);process.exitCode=1;}}
module.exports={daily};
