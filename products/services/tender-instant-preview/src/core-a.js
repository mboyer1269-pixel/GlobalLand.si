/* GlobalLand tender preview core (part A). Made by autonomous AI agents (GlobalLand). Runs locally; no upload, no network. Port of hash-correction/reconcile.py. */
"use strict";
var LIMIT=20000;
var EM=/[\p{L}\p{N}_.+-]+@[\p{L}\p{N}_-]+(\.[\p{L}\p{N}_-]+)+/gu;
var PH=/\+\p{Nd}[\p{Nd} ()-]{7,}\p{Nd}/gu;
function PF(x){this.v=x;}
PF.prototype.valueOf=function(){return this.v;};
function fr(x){if(x===0&&1/x<0)return"-0.0";var a=Math.abs(x);
 if(a!==0&&(a>=1e16||a<1e-4)){var m=x.toExponential().match(/^(-?[\d.]+)e([+-])(\d+)$/);return m[1]+"e"+m[2]+(m[3].length<2?"0"+m[3]:m[3]);}
 var s=String(x);return Number.isInteger(x)?s+".0":s;}
function isD(v){return v!==null&&typeof v==="object"&&!Array.isArray(v)&&!(v instanceof PF);}
function parseJ(s){var i=0,st={big:false};
 function err(){var e=new SyntaxError("JSON at "+i);e.name="JSONDecodeError";throw e;}
 function ws(){while(i<s.length&&" \t\n\r".indexOf(s[i])>=0)i++;}
 var M={'"':'"',"\\":"\\","/":"/",b:"\b",f:"\f",n:"\n",r:"\r",t:"\t"};
 function str(){i++;var o="";for(;;){if(i>=s.length)err();var c=s[i++];if(c==='"')return o;
  if(c==="\\"){var e=s[i++];if(e==="u"){var h=s.substr(i,4);if(!/^[0-9a-fA-F]{4}$/.test(h))err();o+=String.fromCharCode(parseInt(h,16));i+=4;}
   else if(Object.prototype.hasOwnProperty.call(M,e))o+=M[e];else err();}
  else{if(c<" ")err();o+=c;}}}
 var NR=/-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?/y;
 function val(){ws();var c=s[i];
  if(c==="{"){i++;var o=Object.create(null);ws();if(s[i]==="}"){i++;return o;}
   for(;;){ws();if(s[i]!=='"')err();var k=str();ws();if(s[i]!==":")err();i++;o[k]=val();ws();if(s[i]===","){i++;continue;}if(s[i]==="}"){i++;return o;}err();}}
  if(c==="["){i++;var a=[];ws();if(s[i]==="]"){i++;return a;}
   for(;;){a.push(val());ws();if(s[i]===","){i++;continue;}if(s[i]==="]"){i++;return a;}err();}}
  if(c==='"')return str();
  if(s.startsWith("true",i)){i+=4;return true;}if(s.startsWith("false",i)){i+=5;return false;}if(s.startsWith("null",i)){i+=4;return null;}
  NR.lastIndex=i;var r=NR.exec(s);if(!r)err();i=NR.lastIndex;
  if(r[2]||r[3])return new PF(Number(r[0]));var n=Number(r[0]);if(!Number.isSafeInteger(n))st.big=true;return n;}
 var v=val();ws();if(i<s.length)err();return {v:v,big:st.big};}
function cmpCP(a,b){var A=Array.from(a),B=Array.from(b);for(var k=0;k<Math.min(A.length,B.length);k++){var x=A[k].codePointAt(0),y=B[k].codePointAt(0);if(x!==y)return x-y;}return A.length-B.length;}
var QM={'"':'\\"','\\':'\\\\','\n':'\\n','\r':'\\r','\t':'\\t','\b':'\\b','\f':'\\f'};
function q(s){return '"'+s.replace(/[\x00-\x1f"\\]/g,function(c){return QM[c]||"\\u"+("000"+c.charCodeAt(0).toString(16)).slice(-4);})+'"';}
function dump(v){if(v===null)return"null";if(v===true)return"true";if(v===false)return"false";if(v instanceof PF)return fr(v.v);
 if(typeof v==="number")return String(v);if(typeof v==="string")return q(v);if(Array.isArray(v))return"["+v.map(dump).join(",")+"]";
 return"{"+Object.keys(v).sort(cmpCP).map(function(k){return q(k)+":"+dump(v[k]);}).join(",")+"}";}
function hx(n,w){return("0000000"+n.toString(16)).slice(-w);}
function rs(s){var dq=s.indexOf("'")>=0&&s.indexOf('"')<0;var Q=dq?'"':"'";var o="";
 Array.from(s).forEach(function(ch){var c=ch.codePointAt(0);
  if(ch==="\\")o+="\\\\";else if(ch===Q)o+="\\"+Q;else if(ch==="\n")o+="\\n";else if(ch==="\r")o+="\\r";else if(ch==="\t")o+="\\t";
  else if(ch!==" "&&/[\p{C}\p{Z}]/u.test(ch))o+=c<256?"\\x"+hx(c,2):(c<65536?"\\u"+hx(c,4):"\\U"+hx(c,8));else o+=ch;});return Q+o+Q;}
function pr(v){if(v===null||v===undefined)return"None";if(v===true)return"True";if(v===false)return"False";if(v instanceof PF)return fr(v.v);
 if(typeof v==="number")return String(v);if(typeof v==="string")return rs(v);if(Array.isArray(v))return"["+v.map(pr).join(", ")+"]";
 return"{"+Object.keys(v).map(function(k){return rs(k)+": "+pr(v[k]);}).join(", ")+"}";}
function ps(v){return typeof v==="string"?v:pr(v);}
function tru(v){if(v instanceof PF)return v.v!==0;if(Array.isArray(v))return v.length>0;if(isD(v))return Object.keys(v).length>0;return !!v;}
function or(a,b){return tru(a)?a:b;}
function red(s){return ps(or(s,"")).replace(EM,"[email redacted]").replace(PH,"[phone redacted]");}
function utc(s){var m=/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2})(?::(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?)?)?(Z|[+-]\d{2}:?\d{2})?$/.exec(ps(s));
 if(!m||!m[8])return null;var off=0;if(m[8]!=="Z"){var z=m[8].replace(":","");off=(z[0]==="-"?-1:1)*(parseInt(z.substr(1,2),10)*60+parseInt(z.substr(3,2),10));}
 var t=Date.UTC(+m[1],+m[2]-1,+m[3],+(m[4]||0),+(m[5]||0),+(m[6]||0),m[7]?Math.floor(+("0."+m[7])*1000):0)-off*60000;return isNaN(t)?null:new Date(t);}
function p2(n){return(n<10?"0":"")+n;}
function fmt(d){return d.getUTCFullYear()+"-"+p2(d.getUTCMonth()+1)+"-"+p2(d.getUTCDate())+" "+p2(d.getUTCHours())+":"+p2(d.getUTCMinutes())+" UTC";}
async function sha(bytes){var b=await crypto.subtle.digest("SHA-256",bytes);return Array.from(new Uint8Array(b)).map(function(x){return hx(x,2);}).join("");}
function g(o,k){return isD(o)?o[k]:undefined;}
