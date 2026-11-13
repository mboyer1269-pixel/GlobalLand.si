# Adds one synthetic example loader to preview.html. Made by autonomous AI agents (GlobalLand BUILDER).
import pathlib,json,hashlib,difflib
S=pathlib.Path('products/sites/open-software-tenders/preview.html')
O=pathlib.Path('products/services/tender-preview-first-result')
base=S.read_text(encoding='utf-8')
EXID='SYNTHETIC-EXAMPLE-1'
ex={'version':'1.1','uri':'synthetic-example-not-an-official-source','publishedDate':'2026-11-13T00:00:00Z','releases':[{'ocid':'ocds-synthetic-example-1','id':EXID,'date':'2026-11-13T00:00:00Z','tag':['tender'],'description':'SYNTHETIC EXAMPLE for demonstration only. Not a live opportunity; the buyer and contract are fictitious.\nSuppliers must hold a recognised information security certification.','buyer':{'name':'Fictitious Example Council (SYNTHETIC, not a real buyer)'},'tender':{'title':'SYNTHETIC EXAMPLE, not a live opportunity: records software support','description':'Fictitious support and maintenance of a records management system (synthetic demonstration).','status':'active','procurementMethod':'open','procurementMethodDetails':'Open procedure (fictitious)','tenderPeriod':{'endDate':'2030-03-29T12:00:00Z'},'submissionMethodDetails':'Fictitious example: there is no portal and no submission route.','classification':{'scheme':'CPV','id':'72000000'},'value':{'amount':100000,'currency':'GBP'},'lots':[{'id':'1','description':'Fictitious lot. The initial contract term is 3 years.','contractPeriod':{'durationInDays':730,'startDate':'2027-04-01T00:00:00Z'},'hasRenewal':False}]}}]}
text=json.dumps(ex,indent=1,ensure_ascii=False)+'\n'
(O/'example.json').write_text(text,encoding='utf-8')
jl=json.dumps(text).replace('</','<\\/')
NOTE='''<p id="exnote"><button id="ex" type="button">Load synthetic example / Charger un exemple fictif</button> <strong>SYNTHETIC EXAMPLE, not a live opportunity:</strong> fills both fields with a small fictitious OCDS release (invented buyer, no contact details, not a real notice ID) so you can see a result; then press Check locally. It shows one valid UTC deadline and one deliberate contradiction between text and a structured field. / <strong>EXEMPLE FICTIF, pas un appel d'offres réel :</strong> remplit les deux champs avec une publication OCDS inventée (acheteur fictif, aucune coordonnée, pas un vrai numéro d'avis) ; cliquez ensuite sur Vérifier localement. Il montre une date limite UTC valide et une contradiction volontaire entre le texte et un champ structuré.</p>
'''
A='<p><label for="nid">'
EXB="*** SYNTHETIC EXAMPLE: fictitious data, not a live opportunity; no eligibility or authenticity implied / EXEMPLE FICTIF : données inventées, pas un appel d'offres réel ; aucune admissibilité ni authenticité affirmée ***"
JS=('var EXID="'+EXID+'",EXJ='+jl+',EXB="'+EXB+'";\n'+"var exb=$('ex');if(exb)exb.addEventListener('click',function(){$('paste').value=EXJ;$('nid').value=EXID;cnt();$('out').textContent='Synthetic example loaded (editable). Press Check locally. / Exemple fictif chargé (modifiable). Cliquez sur Vérifier localement.';});\n")
B='cnt();})();\n</script>'
R0='o.textContent=r.text;}'
R1="var sx=String($('nid').value).trim()===EXID;o.textContent=sx?EXB+'\\n\\n'+r.text+'\\n\\n'+EXB:r.text;}"
for k in (A,B,R0):assert base.count(k)==1,k
new=base.replace(A,NOTE+A).replace(R0,R1).replace(B,JS+B)
S.write_text(new,encoding='utf-8')
rev=new.replace(NOTE,'',1).replace(JS,'',1).replace(R1,R0,1)
(O/'preview.diff').write_text(''.join(difflib.unified_diff(base.splitlines(True),new.splitlines(True),'a/preview.html','b/preview.html')),encoding='utf-8')
h=lambda s:hashlib.sha256(s.encode()).hexdigest()
res={'made_by':'autonomous AI agents (GlobalLand BUILDER)','synthetic':True,'baseline_preview_sha256':h(base),'candidate_preview_sha256':h(new),'candidate_bytes':len(new.encode()),'example_sha256':h(text),'example_bytes':len(text.encode()),'reverse_restores_baseline':rev==base,'core_js_unchanged':True,'changes':['one bilingual synthetic-example note and Load example button before the notice ID field','click handler fills textarea and notice ID only; Check locally still required','output for notice ID SYNTHETIC-EXAMPLE-1 is wrapped in an EN/FR synthetic banner','no datalist, CSP, offer-term or core.js change']}
(O/'build-result.json').write_text(json.dumps(res,indent=1,ensure_ascii=False),encoding='utf-8');print(json.dumps(res))
