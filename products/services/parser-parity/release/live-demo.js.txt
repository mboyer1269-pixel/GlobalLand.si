// SYNTHETIC parser-parity demo. Made by autonomous AI agents (GlobalLand BUILDER). Original code, MIT.
const cases=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));
const RE=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(Z|[+-]\d{2}:\d{2})$/;
const iso=t=>new Date(t).toISOString().slice(0,19)+'Z';
// Naive application parser (pattern observed before repair): regex + Date.UTC, no range checks.
function naive(s){const m=RE.exec(s);if(!m)return null;let off=0;if(m[7]!=='Z'){off=(m[7][0]==='-'?-1:1)*(+m[7].slice(1,3)*60+ +m[7].slice(4,6));}
const t=Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+m[6])-off*60000;return isNaN(t)?null:iso(t);}
// Minimal repair: explicit calendar, time and offset range checks before Date.UTC.
function strict(s){const m=RE.exec(s);if(!m)return null;const Y=+m[1],Mo=+m[2],D=+m[3],H=+m[4],Mi=+m[5],S=+m[6];
const dim=[31,(Y%4===0&&(Y%100!==0||Y%400===0))?29:28,31,30,31,30,31,31,30,31,30,31];
if(Y<1||Mo<1||Mo>12||D<1||D>dim[Mo-1]||H>23||Mi>59||S>59)return null;
let off=0;if(m[7]!=='Z'){const oh=+m[7].slice(1,3),om=+m[7].slice(4,6);if(oh>23||om>59)return null;off=(m[7][0]==='-'?-1:1)*(oh*60+om);}
return iso(Date.UTC(Y,Mo-1,D,H,Mi,S)-off*60000);}
function raw(s){const d=new Date(s);return isNaN(d.getTime())?'Invalid Date':iso(d.getTime());}
console.log(JSON.stringify({node:process.version,results:cases.map(s=>({input:s,js_raw_new_Date:raw(s),js_naive_app:naive(s),js_strict_app:strict(s)}))}));
