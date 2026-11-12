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
/* Strict validation: an invalid calendar date, time or offset returns null (deadline not determinable), as Python datetime.fromisoformat raises ValueError in reconcile.py. */
function utc(s){var m=/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2})(?::(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?)?)?(Z|[+-]\d{2}:?\d{2})?$/.exec(ps(s));
 if(!m||!m[8])return null;var Y=+m[1],Mo=+m[2],Dd=+m[3],H=+(m[4]||0),Mi=+(m[5]||0),Se=+(m[6]||0);var dim=[31,(Y%4===0&&(Y%100!==0||Y%400===0))?29:28,31,30,31,30,31,31,30,31,30,31];if(Y<1||Mo<1||Mo>12||Dd<1||Dd>dim[Mo-1]||H>23||Mi>59||Se>59)return null;var off=0;if(m[8]!=="Z"){var z=m[8].replace(":",""),oh=parseInt(z.substr(1,2),10),om=parseInt(z.substr(3,2),10);if(oh>23||om>59)return null;off=(z[0]==="-"?-1:1)*(oh*60+om);}
 var t=Date.UTC(+m[1],+m[2]-1,+m[3],+(m[4]||0),+(m[5]||0),+(m[6]||0),m[7]?Math.floor(+("0."+m[7])*1000):0)-off*60000;return isNaN(t)?null:new Date(t);}
function p2(n){return(n<10?"0":"")+n;}
function fmt(d){return d.getUTCFullYear()+"-"+p2(d.getUTCMonth()+1)+"-"+p2(d.getUTCDate())+" "+p2(d.getUTCHours())+":"+p2(d.getUTCMinutes())+" UTC";}
async function sha(bytes){var b=await crypto.subtle.digest("SHA-256",bytes);return Array.from(new Uint8Array(b)).map(function(x){return hx(x,2);}).join("");}
function g(o,k){return isD(o)?o[k]:undefined;}
/* GlobalLand tender preview core (part B; continues in part C). Made by autonomous AI agents (GlobalLand). */
var DISC="Produced by autonomous AI agents (GlobalLand). Not legal or procurement advice. / Produit par des agents d'IA autonomes (GlobalLand). Ce n'est pas un avis juridique ni en marchés publics.";
function refuse(en,frt){return{code:2,text:"REFUSED / REFUSÉ\nEN: "+en+"\nFR: "+frt+"\n"+DISC,canonical:null};}
function cut(s,n){return Array.from(s).slice(0,n).join("");}
async function analyse(text,nid0,now){
 var nid=String(nid0).trim();var raw=new TextEncoder().encode(text);var n=raw.length;
 if(n>=LIMIT)return refuse("pasted text is "+n+" bytes; this offer accepts under "+LIMIT+" bytes.","le texte collé fait "+n+" octets ; l'offre accepte moins de "+LIMIT+" octets.");
 var h=await sha(raw);var P;
 try{P=parseJ(text);}catch(e){return refuse("pasted text is not complete UTF-8 OCDS JSON (JSONDecodeError); sha256 "+h+". Please paste the full release package text.","le texte collé n'est pas un JSON OCDS UTF-8 complet ; sha256 "+h+". Collez le paquet complet.");}
 var doc=P.v;var rels=isD(doc)?("releases" in doc?doc.releases:[doc]):[];if(!Array.isArray(rels))rels=[];
 var rel=null;for(var r of rels){if(isD(r)&&r.id===nid){rel=r;break;}}
 if(rel===null){var ids=rels.filter(isD).map(function(r){return r.id;});
  return refuse("notice "+nid+" is not in the pasted text (release ids found: "+pr(ids)+"); sha256 "+h+".","l'avis "+nid+" n'est pas dans le texte collé (identifiants : "+pr(ids)+") ; sha256 "+h+".");}
 var cj=dump(rel);var canon=(P.big||/[\uD800-\uDFFF]/u.test(cj))?null:await sha(new TextEncoder().encode(cj));
 var t=or(rel.tender,{});var lots=or(g(t,"lots"),[]);if(!Array.isArray(lots))lots=[];
 var flags=[];var unk=["tender documents (not provided, not read)","clarification deadline (not in the pasted structured fields)","your eligibility and portal registration requirements"];
 var st=g(t,"status");if(st!=="active")flags.push("tender.status is "+pr(st)+", not 'active': check whether this is still an open tender.");
 var end=g(or(g(t,"tenderPeriod"),{}),"endDate");var endu=tru(end)?utc(end):null;var dl;
 if(endu===null){flags.push("submission deadline missing or without timezone (tenderPeriod.endDate="+pr(end)+").");dl="not determinable";}
 else{dl=fmt(endu)+" (as published: "+ps(end)+")";if(endu<=now)flags.push("deadline "+fmt(endu)+" has already passed at "+fmt(now)+".");}
 var alltext=[ps(or(rel.description,"")),ps(or(g(t,"description"),""))].concat(lots.map(function(l){return ps(or(g(l,"description"),""));})).join(" ");
 var vals=[];var tv=g(t,"value");if(isD(tv))vals.push("tender: "+ps(tv.amount)+" "+ps(tv.currency));
 lots.forEach(function(l){var lv=g(l,"value");if(isD(lv))vals.push("lot "+ps(g(l,"id"))+": "+ps(lv.amount)+" "+ps(lv.currency));});
 if(!vals.length)unk.push("contract value and currency (no value field in the pasted release)");
 var L=[];
 lots.forEach(function(l){var cp=or(g(l,"contractPeriod"),{});var lid=g(l,"id");
  var cr=or(g(or(g(l,"awardCriteria"),{}),"criteria"),[]);if(!Array.isArray(cr))cr=[];
  var crit=cr.map(function(c){return ps(or(g(c,"name"),g(c,"type")))+" "+ps(g(c,"description"));}).join("; ");
  L.push("  Lot "+ps(lid)+": "+red(g(l,"description"))+"\n    durationInDays="+ps(g(cp,"durationInDays"))+" startDate="+ps(g(cp,"startDate"))+" maxExtentDate="+ps(g(cp,"maxExtentDate"))+" hasRenewal="+ps(g(l,"hasRenewal"))+" renewal="+pr(red(g(or(g(l,"renewal"),{}),"description")))+" hasOptions="+ps(g(l,"hasOptions"))+"\n    Award weights: "+(crit||"not stated"));
  var d=ps(or(g(l,"description"),""));var du=g(cp,"durationInDays");
  var m=/initial (?:contract )?term (?:will be|is) (\d+) years?/i.exec(d);
  if(m&&tru(du)){var diff=Number(du)-parseInt(m[1],10)*365;if(Math.abs(diff)>7)flags.push("lot "+ps(lid)+": text says initial term "+m[1]+" years; structured durationInDays="+ps(du)+" ("+(diff>=0?"+":"")+diff+" days vs "+m[1]+"x365). Minor; confirm in tender documents.");}
  var mo=/[^.]*\boptions?\b[^.]*/i.exec(d);
  if(mo&&g(l,"hasOptions")===false)flags.push("lot "+ps(lid)+": text mentions an option ('"+mo[0].trim()+"') but structured hasOptions=false (hasRenewal="+ps(g(l,"hasRenewal"))+"); the extension may be coded as renewal only.");
  var s=utc(g(cp,"startDate")),x=utc(g(cp,"maxExtentDate"));var mm=/maximum[^.]{0,80}?\(?(\d+)\)?\s*years/i.exec(alltext);
  if(s&&x&&mm){var yrs=Math.floor((x-s)/86400000)/365.25;if(Math.abs(yrs-parseInt(mm[1],10))>0.5)flags.push("lot "+ps(lid)+": text states a maximum of "+mm[1]+" years but structured startDate..maxExtentDate spans "+yrs.toFixed(1)+" years.");}});
 var must=[];var sc=or(g(or(g(t,"selectionCriteria"),{}),"criteria"),[]);if(!Array.isArray(sc))sc=[];
 var srcs=[ps(or(rel.description,""))].concat(sc.map(function(c){return ps(or(g(c,"description"),""));}));
 srcs.forEach(function(s_){s_.split("\n").forEach(function(line){if(/\bmust\b|\bshall\b|\bmay be excluded\b/i.test(line))must.push(cut(red(line.trim()),500));});});
 var route=red(g(t,"submissionMethodDetails"))||"not stated in pasted text";
 var cpv=[g(or(g(t,"classification"),{}),"id")];var its=g(t,"items");if(Array.isArray(its))its.forEach(function(it){var ac=g(it,"additionalClassifications");if(Array.isArray(ac))ac.forEach(function(c){cpv.push(g(c,"id"));});});
 var buyer=red(g(or(rel.buyer,{}),"name"));
 var o=["GlobalLand one-notice source-reconciliation brief / Note de rapprochement des sources (un avis)",DISC,
  "Notice / Avis: "+nid+"   OCID: "+ps(rel.ocid)+"   release date: "+ps(rel.date)+"   tags: "+ps(rel.tag),
  "SHA-256 of the exact pasted text we checked / empreinte du texte vérifié : "+h+" ("+n+" bytes)",
  "Formatting-independent SHA-256 of the selected release (canonical JSON: sorted keys, no spaces between elements; spaces inside text values still count; not proof of authenticity) / empreinte canonique (clés triées ; tolère la mise en forme, pas les espaces dans les valeurs ; ne prouve pas l'authenticité): "+(canon||"not computed in this browser preview (unsupported number or character) / non calculée"),
  "We did not visit any link or portal and cannot confirm this text matches the live official record; compare the hashes and fields yourself. / Nous n'avons consulté aucun lien ni portail ; comparez vous-même les empreintes et les champs.",
  "","== 1. Stated facts (quoted from your pasted text) ==","Buyer: "+buyer,"Title: "+red(g(t,"title")),"Scope (tender.description): "+red(g(t,"description")),
  "Status: "+ps(st)+"   Procedure: "+ps(or(g(t,"procurementMethodDetails"),g(t,"procurementMethod")))+"   CPV: "+cpv.filter(tru).map(ps).join(", "),
  "Submission deadline (UTC): "+dl,"Value / currency: "+(vals.length?vals.join("; "):"none stated in pasted release"),"Submission route (verbatim): "+route,"Lots:"].concat(L.length?L:["  none stated"]);
 o=o.concat(["","== 2. Contradictions and checks =="],flags.length?flags.map(function(f){return"  - "+f;}):["  - none detected by our checks"]);
 o=o.concat(["","== 3. Requirements stated in the pasted text (wording must/shall/may be excluded) =="],must.length?must.map(function(m){return"  - "+m;}):["  - none found in the pasted text"]);
 o=o.concat(["","== 4. Our recommendations (not buyer requirements) ==","  - Confirm the deadline on the official notice and leave a buffer before it.","  - Obtain the full tender pack through the submission route above before deciding.","  - Check each stated requirement in section 3 against your own certificates and policies.","  - Compare the award weights with your pricing position.","  - Bid only if every unknown in section 5 is resolved in your favour."]);
 o=o.concat(["","== 5. Unknowns =="],unk.map(function(u){return"  - "+u;}));
 o=o.concat(["","== Résumé en français ==","Avis : "+nid+" ; acheteur : "+buyer,"Date limite (UTC) : "+dl,"Valeur : "+(vals.length?vals.join("; "):"aucune valeur dans la publication collée"),"Voie de dépôt (citée) : "+route,
  "Contradictions signalées : "+flags.length+" ; exigences citées (en anglais, section 3) : "+must.length+".",
  "Recommandations (les nôtres) : confirmer la date limite sur l'avis officiel ; obtenir le dossier complet par la voie de dépôt ; vérifier chaque exigence ; comparer les pondérations avec votre prix.",
  "Inconnues : documents d'appel d'offres non fournis ni lus ; date limite de clarification ; votre admissibilité et inscription"+(vals.length?".":" ; valeur et devise."),"Aucune admissibilité n'est affirmée. / No eligibility is asserted."]);
 return{code:0,text:o.join("\n"),canonical:canon,flags:flags.length,must:must.length};}
if(typeof module!=="undefined")module.exports={analyse:analyse,LIMIT:LIMIT};
