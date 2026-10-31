#!/usr/bin/env node
'use strict';
const {load,metrics}=require('./finance');
function audit(root){const l=load(root),m=metrics(l),fs=require('node:fs'),path=require('node:path');let bank=null;
 const file=path.join(root,'bank/status.json');if(fs.existsSync(file))bank=JSON.parse(fs.readFileSync(file,'utf8'));
 const report={legacy_declared_balance_cad:l.current_balance,legacy_metrics:m,verified_treasury:bank};
 return '# Audit GlobalLand — '+new Date().toISOString()+'\n\n'+JSON.stringify(report,null,2)+'\n\nLe ledger historique est déclaratif. Seule la trésorerie privée rapprochée définit les fonds utilisables. UNFUNDED ne signifie pas faillite.\nAucun paiement ne découle de cet audit.\n';}

if(require.main===module){try{process.stdout.write(audit(process.argv[2]||require('node:path').resolve(__dirname,'..')));}catch(e){console.error(e.message);process.exitCode=1;}}
module.exports={audit};
