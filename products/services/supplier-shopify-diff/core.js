'use strict';
// CSV state machine adapted from products/invoice-preflight/offline-checker.js.
function parse(text){
text=text.replace(/^\uFEFF/,'');let rows=[],row=[],cell='',quoted=false,closed=false;
for(let i=0;i<text.length;i++){let c=text[i];
if(quoted){if(c==='"'){if(text[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=c;continue;}
if(c==='"'){if(cell!==''||closed)throw Error('Unexpected quote');quoted=true;}
else if(c===','){row.push(cell);cell='';closed=false;}
else if(c==='\n'||c==='\r'){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);rows.push(row);row=[];cell='';closed=false;}
else{if(closed)throw Error('Text after closing quote');cell+=c;}}
if(quoted)throw Error('Unclosed quoted field');
if(cell!==''||row.length||closed){row.push(cell);rows.push(row);}
if(!rows.length)throw Error('Empty file');
const heads=rows[0];if(heads.some(x=>!x.trim())||new Set(heads).size!==heads.length)throw Error('Empty or duplicate header');
if(rows.some(r=>r.length!==heads.length))throw Error('Inconsistent row width');
return rows;
}
function compare(a,b,cfg){
const keyA=a[0].indexOf(cfg.keyA),keyB=b[0].indexOf(cfg.keyB);
if(keyA<0||keyB<0)throw Error('Select existing key columns');
if(!Array.isArray(cfg.fields)||!cfg.fields.length)throw Error('Select at least one field pair');
for(const f of cfg.fields){if(a[0].indexOf(f.a)<0||b[0].indexOf(f.b)<0)throw Error('Unknown field');if(!['price','stock','option','value'].includes(f.kind))throw Error('Unknown field type');}
const out=[],emit=(type,side,row,other_row,key,field,value,other_value)=>out.push({type,side,row,other_row,key,field,value,other_value});
function index(rows,k,side){const m=new Map();rows.slice(1).forEach((r,i)=>{let key=r[k].trim(),n=i+2;if(!key){emit('missing_key',side,n,'','',rows[0][k],r[k],'');return;}if(!m.has(key))m.set(key,[]);m.get(key).push({r,n});});
for(const [key,rs] of m)if(rs.length>1)for(const x of rs)emit('duplicate_key',side,x.n,'',key,rows[0][k],x.r[k],'');return m;}
const ma=index(a,keyA,'supplier'),mb=index(b,keyB,'shopify');
function blanks(rows,side){for(let i=1;i<rows.length;i++)for(const f of cfg.fields){let name=side==='supplier'?f.a:f.b,j=rows[0].indexOf(name);if(['price','stock'].includes(f.kind)&&!rows[i][j].trim())emit('ambiguous_blank',side,i+1,'',rows[i][side==='supplier'?keyA:keyB].trim(),name,rows[i][j],'');}}
blanks(a,'supplier');blanks(b,'shopify');
for(const [key,rs] of ma){if(!mb.has(key)){for(const x of rs)emit('missing_in_shopify','supplier',x.n,'',key,a[0][keyA],x.r[keyA],'');continue;}
if(rs.length!==1||mb.get(key).length!==1)continue;const x=rs[0],y=mb.get(key)[0];
for(const f of cfg.fields){let v=x.r[a[0].indexOf(f.a)].trim(),w=y.r[b[0].indexOf(f.b)].trim();
if(['price','stock'].includes(f.kind)&&(!v||!w))continue;
const mapped=f.map&&Object.prototype.hasOwnProperty.call(f.map,v)?String(f.map[v]):v;
if(mapped!==w)emit(f.kind+'_difference','supplier',x.n,y.n,key,f.a+' → '+f.b,v,w);}}
for(const [key,rs] of mb)if(!ma.has(key))for(const y of rs)emit('new_in_shopify','shopify',y.n,'',key,b[0][keyB],y.r[keyB],'');
return out;
}
const headers=['type','side','row','other_row','key','field','value','other_value'];
function csv(rows){return [headers,...rows.map(r=>headers.map(k=>r[k]))].map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(',')).join('\r\n')+'\r\n';}
if(typeof module!=='undefined')module.exports={parse,compare,csv};
