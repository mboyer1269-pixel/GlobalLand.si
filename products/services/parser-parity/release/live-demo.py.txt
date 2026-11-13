# SYNTHETIC parser-parity demo. Made by autonomous AI agents (GlobalLand BUILDER). Original code, MIT. Stdlib only, no network.
# Usage: put demo.py and demo.js in one folder, run: python3 demo.py (needs python3 and node on PATH). Writes results.json and results-table.md next to this script.
import json,re,sys,subprocess,pathlib,hashlib,tempfile,datetime as dt
O=pathlib.Path(__file__).resolve().parent;UTC=dt.timezone.utc
RE=re.compile(r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(Z|[+-]\d{2}:\d{2})$')
C=[('2026-02-30T12:00:00Z','calendar',None),('2026-04-31T12:00:00Z','calendar',None),('2027-02-29T12:00:00Z','calendar',None),('2100-02-29T12:00:00Z','calendar',None),('2026-13-01T12:00:00Z','calendar',None),('2026-00-10T12:00:00Z','calendar',None),('2026-12-00T12:00:00Z','calendar',None),
('2026-12-07T25:00:00Z','hour',None),('2026-12-07T24:00:00Z','hour',None),('2026-12-07T12:60:00Z','minute',None),('2026-12-07T12:00:60Z','second',None),
('2026-12-07T12:00:00+24:00','offset',None),('2026-12-07T12:00:00+05:60','offset',None),
('2028-02-29T12:00:00Z','valid','2028-02-29T12:00:00Z'),('2000-02-29T12:00:00Z','valid','2000-02-29T12:00:00Z'),('2026-12-31T23:59:59Z','valid','2026-12-31T23:59:59Z'),('2026-12-07T12:00:00-05:00','valid-offset','2026-12-07T17:00:00Z'),('2026-12-07T12:00:00+05:30','valid-offset','2026-12-07T06:30:00Z'),('2026-12-07T12:00:00+23:59','valid-offset','2026-12-06T12:01:00Z'),('2026-12-31T23:30:00-01:00','valid-offset','2027-01-01T00:30:00Z'),('2026-04-30T00:00:00+00:00','valid-offset','2026-04-30T00:00:00Z')]
f=lambda d:d.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
def py_raw(s):
  try:return f(dt.datetime.fromisoformat(s.replace('Z','+00:00')))
  except ValueError as e:return 'ValueError: '+str(e)
def py_strict(s):
  m=RE.match(s)
  if not m:return None
  Y,Mo,D,H,Mi,S=map(int,m.groups()[:6]);z=m.group(7);off=0
  if z!='Z':
    oh,om=int(z[1:3]),int(z[4:6])
    if oh>23 or om>59:return None
    off=(-1 if z[0]=='-' else 1)*(oh*60+om)
  try:return f(dt.datetime(Y,Mo,D,H,Mi,S,tzinfo=dt.timezone(dt.timedelta(minutes=off))))
  except ValueError:return None
cf=pathlib.Path(tempfile.mkdtemp())/'pp-cases.json';cf.write_text(json.dumps([c[0] for c in C]))
q=subprocess.run(['node',str(O/'demo.js'),str(cf)],capture_output=True,text=True,timeout=30)
if q.returncode!=0:sys.exit('demo.js failed (is node on PATH?): '+q.stderr[-500:])
J=json.loads(q.stdout)
rows=[];chk=[]
for (s,cat,exp),j in zip(C,J['results']):
  r=dict(j,category=cat,expected_strict=exp,py_raw_fromisoformat=py_raw(s),py_strict_app=py_strict(s));rows.append(r)
  chk.append({'check':s+': JS strict == expected','pass':r['js_strict_app']==exp})
  chk.append({'check':s+': Python strict == expected','pass':r['py_strict_app']==exp})
  chk.append({'check':s+': JS strict == Python strict','pass':r['js_strict_app']==r['py_strict_app']})
naive_silent=[r['input'] for r in rows if r['expected_strict'] is None and r['js_naive_app'] is not None]
js_raw_acc=[r['input'] for r in rows if r['expected_strict'] is None and r['js_raw_new_Date']!='Invalid Date']
py_raw_acc=[r['input'] for r in rows if r['expected_strict'] is None and not r['py_raw_fromisoformat'].startswith('ValueError')]
np=sum(c['pass'] for c in chk)
out={'synthetic':True,'made_by':'autonomous AI agents (GlobalLand BUILDER)','python':sys.version.split()[0],'node':J['node'],'demo_py_sha256':hashlib.sha256((O/'demo.py').read_bytes()).hexdigest(),'demo_js_sha256':hashlib.sha256((O/'demo.js').read_bytes()).hexdigest(),'passed':np,'total':len(chk),
'invalid_inputs_silently_normalized_by_naive_js_app':naive_silent,'invalid_inputs_accepted_by_raw_js_new_Date':js_raw_acc,'invalid_inputs_accepted_by_raw_python_fromisoformat':py_raw_acc,'rows':rows,'checks':chk}
(O/'results.json').write_text(json.dumps(out,indent=1),encoding='utf-8')
L=['| input | category | JS new Date | JS naive app | JS repaired | Py fromisoformat | Py repaired |','|---|---|---|---|---|---|---|']
for r in rows:L.append('| `%s` | %s | %s | %s | %s | %s | %s |'%(r['input'],r['category'],r['js_raw_new_Date'],r['js_naive_app'] or 'reject',r['js_strict_app'] or 'reject',r['py_raw_fromisoformat'][:40],r['py_strict_app'] or 'reject'))
(O/'results-table.md').write_text('Executed: Node %s, Python %s. Checks %d/%d.\n\n'%(J['node'],out['python'],np,len(chk))+'\n'.join(L)+'\n',encoding='utf-8')
print(np,'/',len(chk));print('naive_silent',naive_silent);print('js_raw',js_raw_acc);print('py_raw',py_raw_acc)
