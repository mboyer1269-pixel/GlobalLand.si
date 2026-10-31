#!/usr/bin/env node
'use strict';
const {readTask}=require('./task');const {audit}=require('./audit');
function runTask(root,rel){readTask(root,rel);return {status:'DONE',output:audit(root)};}
if(require.main===module){try{process.stdout.write(JSON.stringify(runTask(process.argv[2],process.argv[3]))+'\n');}catch(e){console.error('Task refused: '+e.message);process.exitCode=2;}}
module.exports={runTask};
