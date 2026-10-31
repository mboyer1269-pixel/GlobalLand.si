'use strict';
const {runTask}=require('./run_task');const {load,tick,journal,metrics}=require('./finance');const {audit}=require('./audit');
try{
 const kind=process.argv[2],root=process.argv[4]||'/workspace';let result;
 if(kind==='task'){try{result=runTask(root,process.argv[3]);}catch{result={status:'REJECTED',output:'Invalid task. Only free SHELL/AUDIT with empty args is allowed.'};}}
 else if(kind==='daily'){
  const day=process.argv[3],l=tick(load(root),day);
  result={'ledger.json':JSON.stringify(l,null,2)+'\n','logs/transactions.log':journal(l),['bank/audits/audit-'+day+'.md']:'# Audit UTC '+day+'\n\n'+JSON.stringify({legacy_metrics:metrics(l,day),treasury_snapshot:require('node:fs').existsSync(root+'/bank/status.json')?JSON.parse(require('node:fs').readFileSync(root+'/bank/status.json','utf8')):null},null,2)+'\nAucune vérification bancaire externe. Aucun paiement ni arrêt automatique.\n'};
 }else throw Error('unknown worker mode');
 process.stdout.write(JSON.stringify(result)+'\n');
}catch(e){console.error('Worker refused: '+e.message);process.exitCode=2;}
