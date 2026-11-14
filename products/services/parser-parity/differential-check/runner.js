// Runs the exact saved port_after source on a JSON corpus. Usage: node runner.js results.json corpus.json out.json
const fs=require('fs');const src=JSON.parse(fs.readFileSync(process.argv[2],'utf8')).port_after;
const toCents=new Function(src+';return toCents;')();
const cases=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const ser=v=>v===null?'null':(typeof v!=='number'?'TYPE:'+typeof v+':'+String(v):(Object.is(v,-0)?'-0':String(v)));
fs.writeFileSync(process.argv[4],JSON.stringify({node:process.version,out:cases.map(s=>{try{return ser(toCents(s))}catch(e){return 'THROW:'+e.message}})}));
