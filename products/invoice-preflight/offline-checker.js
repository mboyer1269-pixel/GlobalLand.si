function check(text){
text=text.replace(/^﻿/,'');let rows=[],row=[],cell='',quoted=false,closed=false,errors=[];
for(let i=0;i<text.length;i++){let c=text[i];if(quoted){if(c==='"'){if(text[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=c;continue;}
if(c==='"'){if(cell!==''||closed)errors.push('Unexpected quote near character '+(i+1));else quoted=true;}
else if(c===','){row.push(cell);cell='';closed=false;}
else if(c==='\n'||c==='\r'){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);rows.push(row);row=[];cell='';closed=false;}
else {if(closed)errors.push('Text after closing quote near character '+(i+1));cell+=c;}}
if(quoted)errors.push('Unclosed quoted field');if(cell!==''||row.length||closed){row.push(cell);rows.push(row);}
if(!rows.length)errors.push('Empty file');else{let width=rows[0].length;rows.forEach((r,i)=>{if(r.length!==width)errors.push('Row '+(i+1)+' has '+r.length+' columns; expected '+width);});let seen=new Set();rows[0].forEach((h,i)=>{if(!h.trim())errors.push('Empty header at column '+(i+1));if(seen.has(h.trim()))errors.push('Duplicate header: '+h);seen.add(h.trim());});}
return {dataRows:Math.max(0,rows.length-1),columns:rows.length?rows[0].length:0,errors};}

if(typeof module!=="undefined")module.exports={check};
