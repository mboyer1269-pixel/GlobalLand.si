# SYNTHETIC parity checks: browser-preview JS core vs reconcile.py. Made by autonomous AI agents (GlobalLand BUILDER). Not a customer request.
import subprocess, json, hashlib, sys, pathlib, copy, platform
D = pathlib.Path('products/services/tender-instant-preview')
PY = pathlib.Path('products/services/tender-offer-test/hash-correction/reconcile.py')
CORE = D / 'src/core.js'
RAW = pathlib.Path('products/services/tender-refresh/raw')
T = pathlib.Path('/tmp/tp'); T.mkdir(exist_ok=True)
NOW = '2026-11-12T06:00:00Z'
res = []
def chk(n, c, d=''):
    res.append({'check': n, 'pass': bool(c), 'detail': str(d)[:400]})
def put(name, data):
    f = T / name; f.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8')); return f
def py(f, nid):
    p = subprocess.run([sys.executable, '-I', str(PY), str(f), nid, NOW], capture_output=True)
    return p.returncode, p.stdout.decode('utf-8')
def js(f, nid):
    p = subprocess.run(['node', 'products/services/tender-instant-preview/tests/run_node.js', str(CORE), str(f), nid, NOW], capture_output=True)
    if p.returncode: return None, p.stderr.decode()[-300:]
    r = json.loads(p.stdout); return r, None
def canon(rel):
    return hashlib.sha256(json.dumps(rel, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
cases = []
P = {}
for nid in ['105246-2026', '105838-2026']:
    b = (RAW / (nid + '.json')).read_bytes(); P[nid] = json.loads(b)
    cases.append(('official ' + nid, RAW / (nid + '.json'), nid, True))
d = P['105246-2026']
cases.append(('re-indented 105246-2026', put('reindent.json', json.dumps(d, indent=2, ensure_ascii=False)), '105246-2026', True))
b = (RAW / '105838-2026.json').read_bytes()
cases.append(('malformed truncated', put('trunc.json', b[:len(b)//2]), '105838-2026', False))
cases.append(('wrong notice id', RAW / '105838-2026.json', '999999-2026', False))
cases.append(('oversized', put('big.json', '{"releases":[{"id":"X","pad":"' + 'a'*20100 + '"}]}'), 'X', False))
cases.append(('missing fields', put('missing.json', json.dumps({'releases': [{'id': 'M-1', 'tender': {}}]})), 'M-1', True))
h = copy.deepcopy(P['105838-2026']); r = [x for x in h['releases'] if x.get('id') == '105838-2026'][0]
r['buyer']['name'] = '<script>alert(1)</script> & <b>Buyer</b> "q" \'s'
r['tender']['title'] = '<img src=x onerror=alert(2)> Contact bids@example.org or +44 20 7946 0000'
r['description'] = (r.get('description') or '') + '\nSuppliers must not <iframe> paste HTML.'
cases.append(('HTML-like and contact strings', put('html.json', json.dumps(h, ensure_ascii=False)), '105838-2026', True))
fl = '{"releases":[{"id":"F-1","tag":["tender"],"tender":{"status":"planned","value":{"amount":1000.0,"currency":"GBP"},"tenderPeriod":{"endDate":"2026-12-01T12:00:00"},"lots":[{"id":"1","value":{"amount":1e-5,"currency":"EUR"},"hasOptions":false,"description":"An option to extend. The initial term will be 2 years.","contractPeriod":{"durationInDays":800},"renewal":{"description":"line1\\nline2 \\u00a0x"}}]}}]}'
cases.append(('float values, naive deadline, flags', put('float.json', fl), 'F-1', True))
cases.append(('past deadline', RAW / '105246-2026.json', '105246-2026', True))
for name, f, nid, ok in cases:
    now = NOW
    if name == 'past deadline':
        p = subprocess.run([sys.executable, '-I', str(PY), str(f), nid, '2027-01-01T00:00:00Z'], capture_output=True); rc, po = p.returncode, p.stdout.decode()
        q = subprocess.run(['node', str(D / 'tests/run_node.js'), str(CORE), str(f), nid, '2027-01-01T00:00:00Z'], capture_output=True); jr = json.loads(q.stdout)
    else:
        rc, po = py(f, nid); jr, err = js(f, nid)
        if jr is None: chk(name + ': node ran', False, err); continue
    chk(name + ': exit code parity', rc == jr['code'], (rc, jr['code']))
    chk(name + ': output text byte-identical to reconcile.py', po == jr['text'] + '\n', '' if po == jr['text'] + '\n' else next((f'line {i}: py={a!r} js={b!r}' for i, (a, b) in enumerate(zip(po.split('\n'), (jr['text'] + '\n').split('\n'))) if a != b), 'length differs'))
    chk(name + ': expected outcome', (rc == 0) == ok, rc)
re1 = js(RAW / '105246-2026.json', '105246-2026')[0]; re2 = js(T / 'reindent.json', '105246-2026')[0]
rel = [x for x in d['releases'] if x.get('id') == '105246-2026'][0]
chk('canonical hash equals Python recomputation and is formatting-independent', re1['canonical'] == canon(rel) == re2['canonical'], re1['canonical'])
chk('HTML-like strings kept as inert text in output (rendered via textContent in UI)', '<script>alert(1)</script>' in js(T / 'html.json', '105838-2026')[0]['text'])
chk('email/phone redacted in JS output', '[email redacted]' in js(T / 'html.json', '105838-2026')[0]['text'] and '[phone redacted]' in js(T / 'html.json', '105838-2026')[0]['text'])
np = sum(1 for x in res if x['pass'])
out = {'synthetic': True, 'made_by': 'autonomous AI agents (GlobalLand BUILDER)', 'now': NOW, 'python': platform.python_version(),
       'node': subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip(),
       'core_sha256': hashlib.sha256(CORE.read_bytes()).hexdigest(), 'reconcile_sha256': hashlib.sha256(PY.read_bytes()).hexdigest(),
       'execution': 'Node.js only (no browser available in sandbox); actual browser execution untested', 'passed': np, 'total': len(res), 'checks': res}
(D / 'parity-results.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print(np, '/', len(res)); [print('FAIL', x) for x in res if not x['pass']]
