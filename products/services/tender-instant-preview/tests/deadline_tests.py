# SYNTHETIC deadline-boundary regression checks: preview JS core vs reconcile.py. Made by autonomous AI agents (GlobalLand BUILDER). Not customer data.
import subprocess,json,sys,pathlib,hashlib,copy
D=pathlib.Path('products/services/tender-instant-preview');PY='products/services/tender-offer-test/hash-correction/reconcile.py';CORE=D/'src/core.js'
RAW=pathlib.Path('products/services/tender-refresh/raw');T=pathlib.Path('/tmp/tpd');T.mkdir(exist_ok=True);NOW='2026-11-12T06:00:00Z';NID='105246-2026'
C=[('2026-02-30T12:00:00Z',None),('2026-12-07T25:00:00Z',None),('2026-04-31T12:00:00Z',None),('2027-02-29T12:00:00Z',None),('2100-02-29T12:00:00Z',None),('2026-13-01T12:00:00Z',None),('2026-00-10T12:00:00Z',None),('2026-12-00T12:00:00Z',None),('2026-12-07T12:60:00Z',None),('2026-12-07T12:00:60Z',None),('2026-12-07T24:00:00Z',None),('2026-12-07T12:00:00+24:00',None),('2026-12-07T12:00:00+05:60',None),
('2028-02-29T12:00:00Z','2028-02-29 12:00 UTC'),('2000-02-29T12:00:00Z','2000-02-29 12:00 UTC'),('2026-12-31T23:59:59Z','2026-12-31 23:59 UTC'),('2026-12-07T12:00:00-05:00','2026-12-07 17:00 UTC'),('2026-12-07T12:00:00+23:59','2026-12-06 12:01 UTC'),('2026-12-07T12:00:00Z','2026-12-07 12:00 UTC'),('2026-04-30T00:00:00+00:00','2026-04-30 00:00 UTC')]
base=json.loads((RAW/(NID+'.json')).read_bytes());res=[]
def chk(n,c,d=''):res.append({'check':n,'pass':bool(c),'detail':str(d)[:300]})
for i,(v,exp) in enumerate(C):
  d=copy.deepcopy(base)
  for r in d['releases']:
    if r.get('id')==NID:r['tender'].setdefault('tenderPeriod',{})['endDate']=v
  f=T/('d%d.json'%i);f.write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8')
  p=subprocess.run([sys.executable,'-I',PY,str(f),NID,NOW],capture_output=True);po=p.stdout.decode()
  q=subprocess.run(['node',str(D/'tests/run_node.js'),str(CORE),str(f),NID,NOW],capture_output=True)
  if q.returncode:chk(v+': node ran',False,q.stderr.decode()[-200:]);continue
  j=json.loads(q.stdout);jt=j['text']
  line=next((x for x in jt.split('\n') if x.startswith('Submission deadline (UTC): ')),'')
  chk(v+': output byte-identical to reconcile.py',po==jt+'\n',next((f'py={a!r} js={b!r}' for a,b in zip(po.split('\n'),(jt+'\n').split('\n')) if a!=b),''))
  if exp is None:chk(v+': invalid -> not determinable with explicit warning',line=='Submission deadline (UTC): not determinable' and 'submission deadline missing or without timezone' in jt,line)
  else:chk(v+': valid -> '+exp,line=='Submission deadline (UTC): '+exp+' (as published: '+v+')',line)
np=sum(x['pass'] for x in res)
out={'synthetic':True,'made_by':'autonomous AI agents (GlobalLand BUILDER)','now':NOW,'python':sys.version.split()[0],'node':subprocess.run(['node','--version'],capture_output=True,text=True).stdout.strip(),'core_sha256':hashlib.sha256(CORE.read_bytes()).hexdigest(),'base_fixture':str(RAW/(NID+'.json')),'passed':np,'total':len(res),'checks':res}
(D/'deadline-test-results.json').write_text(json.dumps(out,indent=1,ensure_ascii=False),encoding='utf-8')
print(np,'/',len(res));[print('FAIL',x) for x in res if not x['pass']]
