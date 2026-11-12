# SYNTHETIC page-level checks. Made by autonomous AI agents (GlobalLand BUILDER).
import subprocess, json, sys, pathlib, re, hashlib
D = pathlib.Path('products/services/tender-instant-preview'); S = pathlib.Path('products/sites/open-software-tenders')
PY = 'products/services/tender-offer-test/hash-correction/reconcile.py'; RAW = pathlib.Path('products/services/tender-refresh/raw')
H = S / 'preview.html'; html = H.read_text(encoding='utf-8'); res = []
def chk(n, c, d=''): res.append({'check': n, 'pass': bool(c), 'detail': str(d)[:300]})
script = html.split('<script>')[1].split('</script>')[0]
chk('one inline script, core embedded byte-identical', html.count('<script>') == 1 and (D / 'src/core.js').read_text(encoding='utf-8') in script)
chk('no network APIs, innerHTML, eval or external URLs in script', not re.search(r'fetch\(|XMLHttpRequest|innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(|new Function|https?://|importScripts|WebSocket|sendBeacon', script))
chk('CSP forbids network (default-src none) and forms', "default-src 'none'" in html and "form-action 'none'" in html)
chk('EN/FR AI disclosure', 'Made by autonomous AI agents' in html and "agents d'IA autonomes" in html)
chk('free preview not an order; CAD 49 hypothesis; administrative acceptance', 'it is not an order' in html and 'unvalidated price hypothesis' in html and 'administrative acceptance' in html and 'hypothèse non validée' in html)
chk('user-supplied vs authenticated stated', 'not authenticated official data' in html and "n'est pas une donnée officielle authentifiée" in html)
chk('input limit stated', 'under 20,000 bytes' in html and 'moins de 20 000 octets' in html)
chk('browser execution honestly untested', 'not yet tested in a real browser' in html)
for nid in ['105246-2026', '105838-2026']:
    f = RAW / (nid + '.json')
    p = subprocess.run(['node', str(D / 'tests/ui_stub.js'), str(H), str(f), nid], capture_output=True)
    if p.returncode: chk(nid + ' stub ran', False, p.stderr.decode()[-300:]); continue
    r = json.loads(p.stdout)
    py = subprocess.run([sys.executable, '-I', PY, str(f), nid], capture_output=True).stdout.decode()
    a = py.split('\n'); b = (r['out'] + '\n').split('\n')
    chk(nid + ' page click output equals reconcile.py (same real clock)', py == r['out'] + '\n', next((f'{x!r} vs {y!r}' for x, y in zip(a, b) if x != y), ''))
    chk(nid + ' no network calls during run', r['net'] == [], r['net'])
    chk(nid + ' byte counter shown', '/ 20000 bytes' in r['bytes'], r['bytes'])
idx = (S / 'index.html').read_text(encoding='utf-8')
chk('index links preview in EN and FR', idx.count('href="preview.html"') == 2)
np = sum(x['pass'] for x in res)
out = {'synthetic': True, 'execution': 'Node.js vm with DOM stub; no real browser in sandbox', 'node': subprocess.run(['node', '--version'], capture_output=True, text=True).stdout.strip(), 'preview_sha256': hashlib.sha256(H.read_bytes()).hexdigest(), 'passed': np, 'total': len(res), 'checks': res}
(D / 'ui-test-results.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print(np, '/', len(res)); [print('FAIL', x) for x in res if not x['pass']]
