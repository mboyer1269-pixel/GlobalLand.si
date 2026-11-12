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
