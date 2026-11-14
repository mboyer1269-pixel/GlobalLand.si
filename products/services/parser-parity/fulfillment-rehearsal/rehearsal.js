const cases=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));const show=v=>v===null?null:(Number.isFinite(v)?v:String(v));
const naive=(function(){function toCents(s){
  const v=parseFloat(s);
  return isNaN(v)?null:Math.round(v*100);
}
 return toCents;})();const strict=(function(){function toCents(s){
  const m=/^(-?)([0-9]{1,12})(?:\.([0-9]{1,2}))?$/.exec(s);
  if(!m||/[\r\n]/.test(s))return null;
  const c=Number(m[2])*100+Number((m[3]||'').padEnd(2,'0'));
  return m[1]&&c!==0?-c:c;
}
 return toCents;})();
console.log(JSON.stringify({node:process.version,unicode_digit_matches_js_backslash_d:/^\d$/.test('\u0661'),results:cases.map(s=>({input:s,js_port_before:show(naive(s)),js_port_after:show(strict(s))}))}));
