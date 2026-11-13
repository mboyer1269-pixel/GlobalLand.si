# SYNTHETIC tests for the example loader. Made by autonomous AI agents (GlobalLand BUILDER).
import subprocess,json,sys,pathlib,re,hashlib
O=pathlib.Path('products/services/tender-preview-first-result');H=pathlib.Path('products/sites/open-software-tenders/preview.html')
PY='products/services/tender-offer-test/hash-correction/reconcile.py'
html=H.read_text(encoding='utf-8');res=[]
def chk(n,c,d=''):res.append({'check':n,'pass':bool(c),'detail':str(d)[:300]})
ex=(O/'example.json').read_text(encoding='utf-8');EXID='SYNTHETIC-EXAMPLE-1'
chk('one Load example button',html.count('id="ex"')==1)
chk('input guidance labels synthetic EN/FR','SYNTHETIC EXAMPLE, not a live opportunity' in html and "EXEMPLE FICTIF, pas un appel d'offres réel" in html)
chk('CSP unchanged',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'" in html)
chk('core.js embedded unchanged',pathlib.Path('products/services/tender-instant-preview/src/core.js').read_text(encoding='utf-8') in html)
chk('example under input limit',len(ex.encode())<20000,len(ex.encode()))
chk('example has no email, phone or URL',not re.search(r'@|\+\d|https?://|www\.',ex))
chk('example id not a Find a Tender notice id',not re.search(r'\d{6}-\d{4}',ex))
chk('datalist unchanged (3 real options, no example)',html.count('<option value=')==3 and '<option value="SYNTHETIC' not in html)
p=subprocess.run(['node',str(O/'tools/ex_stub.js'),str(H)],capture_output=True);r=None
if p.returncode:chk('stub ran',False,p.stderr.decode()[-300:])
else:r=json.loads(p.stdout)
if r:
 L=r['load'];chk('load fills editable fields only, no result yet',L['paste']==ex and L['nid']==EXID and '== 1.' not in L['out'] and 'Press Check locally' in L['out'],L['out'])
 chk('byte counter updated on load',L['bytes'].startswith(str(len(ex.encode()))+' / 20000'),L['bytes'])
 o=r['run1']
 chk('output starts and ends with synthetic banner',o.startswith('*** SYNTHETIC EXAMPLE') and o.endswith('authenticité affirmée ***'),o[:120])
 chk('valid UTC deadline shown','Submission deadline (UTC): 2030-03-29 12:00 UTC' in o)
 chk('deliberate contradiction flagged','text says initial term 3 years; structured durationInDays=730 (-365 days' in o and 'Contradictions signalées : 1 ;' in o)
 chk('no eligibility asserted',"Aucune admissibilité n'est affirmée. / No eligibility is asserted." in o)
 inner=o.split('\n\n',1)[1].rsplit('\n\n',1)[0]
 tmp=O/'tmp-ex.json';tmp.write_text(ex,encoding='utf-8')
 py=subprocess.run([sys.executable,'-I',PY,str(tmp),EXID],capture_output=True).stdout.decode();tmp.unlink()
 a=py.split('\n');b=(inner+'\n').split('\n')
 chk('example output between banners equals reconcile.py',py==inner+'\n',next((f'{x!r} vs {y!r}' for x,y in zip(a,b) if x!=y),''))
 chk('edited input is used','Submission deadline (UTC): 2030-04-30 12:00 UTC' in r['run2'])
 chk('other notice id gets no banner',not r['run3'].startswith('***') and 'REFUSED' in r['run3'],r['run3'][:100])
 chk('no network calls',r['net']==[],r['net'])
suites={}
for t in ['parity.py','ui_test.py','deadline_tests.py']:
 q=subprocess.run([sys.executable,'products/services/tender-instant-preview/tests/'+t],capture_output=True,text=True)
 m=re.findall(r'(\d+) / (\d+)',q.stdout);suites[t]={'rc':q.returncode,'stdout':q.stdout[-400:],'stderr':q.stderr[-400:]}
 chk('existing '+t+' all assertions pass',bool(m) and m[-1][0]==m[-1][1],q.stdout.strip()[-200:]+q.stderr[-200:])
np=sum(x['pass'] for x in res)
out={'synthetic':True,'made_by':'autonomous AI agents (GlobalLand BUILDER)','execution':'Node.js vm with DOM stub; no real browser in sandbox','node':subprocess.run(['node','--version'],capture_output=True,text=True).stdout.strip(),'preview_sha256':hashlib.sha256(H.read_bytes()).hexdigest(),'passed':np,'total':len(res),'checks':res,'existing_suites':suites,'example_output':r and r['run1']}
(O/'test-results.json').write_text(json.dumps(out,indent=1,ensure_ascii=False),encoding='utf-8')
print(np,'/',len(res));[print('FAIL',x) for x in res if not x['pass']]
