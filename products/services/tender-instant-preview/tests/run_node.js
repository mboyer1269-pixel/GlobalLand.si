// SYNTHETIC parity runner. Made by autonomous AI agents (GlobalLand BUILDER).
const fs=require('fs');const c=require(require('path').resolve(process.argv[2]));
const text=fs.readFileSync(process.argv[3],'utf8');
c.analyse(text,process.argv[4],new Date(process.argv[5])).then(r=>{process.stdout.write(JSON.stringify(r));});
