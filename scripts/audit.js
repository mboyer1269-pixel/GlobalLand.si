#!/usr/bin/env node
'use strict';
const {load,metrics}=require('./finance');
function audit(root){const l=load(root),m=metrics(l);return '# Audit GlobalLand — '+new Date().toISOString()+'\n\n'+JSON.stringify(m,null,2)+'\n\nCashflow réel des 7 jours UTC : '+m.weeklyNet+' CAD.\nRunway narratif (jours, null = illimité) : '+m.runwayDays+'.\nAucune preuve bancaire externe vérifiée par ce script.\nAucune destruction ni dépense automatique.\n';}
if(require.main===module){try{process.stdout.write(audit(process.argv[2]||require('node:path').resolve(__dirname,'..')));}catch(e){console.error(e.message);process.exitCode=1;}}
module.exports={audit};
