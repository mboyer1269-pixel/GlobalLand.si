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
