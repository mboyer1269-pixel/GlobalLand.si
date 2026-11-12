# SYNTHETIC checks. Made by autonomous AI agents (GlobalLand BUILDER). Not a customer request.
import subprocess, json, hashlib, sys, re, pathlib, platform, os, copy
HC = pathlib.Path('products/services/tender-offer-test/hash-correction')
R = HC / 'reconcile.py'
RAW = pathlib.Path('products/services/tender-refresh/raw')
T = pathlib.Path('/tmp/hc'); T.mkdir(exist_ok=True)
(HC / 'out').mkdir(exist_ok=True)
NOW = '2026-11-12T06:00:00Z'
res = []; maxb = [0]
def chk(n, c, d=''):
    res.append({'check': n, 'pass': bool(c), 'detail': str(d)[:300]})
def run(f, nid, now=NOW, env=None):
    p = subprocess.run([sys.executable, '-I', str(R), str(f), nid, now], capture_output=True, env=env)
    maxb[0] = max(maxb[0], len(p.stdout))
    return p.returncode, p.stdout.decode('utf-8'), p.stderr.decode('utf-8', 'replace')
def put(name, data):
    f = T / name; f.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8')); return f
def crel(d, nid):
    rel = [r for r in d['releases'] if r.get('id') == nid][0]
    return hashlib.sha256(json.dumps(rel, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
CR = re.compile(r'empreinte canonique [(][^:]*[)]: ([0-9a-f]{64})')
def canon(o):
    m = CR.search(o); return m.group(1) if m else None
ACC = ['Résumé en français', 'marchés publics', 'Voie de dépôt (citée)', 'texte vérifié', 'admissibilité', "n'est affirmée", 'les nôtres', 'pondérations']
OLD = ['Resume en francais', 'marches publics', 'Voie de depot', 'texte verifie', 'admissibilite', 'Whitespace-independent', 'consulte aucun', 'ponderations']
D = {}
for nid, dl in [('105246-2026', '2026-12-07 12:00 UTC'), ('105838-2026', '2027-01-08 12:00 UTC')]:
    f = RAW / (nid + '.json'); b = f.read_bytes(); d = json.loads(b); D[nid] = (b, d)
    rc, o, e = run(f, nid)
    (HC / 'out' / ('brief-' + nid + '.txt')).write_text(o, encoding='utf-8')
    rel = [r for r in d['releases'] if r.get('id') == nid][0]
    chk(nid + ' exit 0', rc == 0, e[-300:])
    chk(nid + ' raw sha256 of exact input cited', hashlib.sha256(b).hexdigest() in o)
    chk(nid + ' canonical hash in reply equals independent recomputation', canon(o) == crel(d, nid), canon(o))
    chk(nid + ' canonical line states limits EN/FR', 'spaces inside text values still count' in o and 'not proof of authenticity' in o and "ne prouve pas l'authenticité" in o)
    chk(nid + ' deadline UTC', dl in o)
    chk(nid + ' buyer quoted', rel['buyer']['name'] in o)
    chk(nid + ' route verbatim', rel['tender'].get('submissionMethodDetails', '') in o)
    chk(nid + ' EN+FR AI disclosure', 'autonomous AI agents' in o and "agents d'IA autonomes" in o)
    chk(nid + ' accented French present', all(a in o for a in ACC), [a for a in ACC if a not in o])
    chk(nid + ' unaccented legacy French absent', not any(x in o for x in OLD), [x for x in OLD if x in o])
    chk(nid + ' sections 1-5', all(s in o for s in ['== 1.', '== 2.', '== 3.', '== 4.', '== 5.']))
    chk(nid + ' tender docs unknown EN/FR', 'tender documents (not provided, not read)' in o and "documents d'appel d'offres non fournis" in o)
    chk(nid + ' no email address', not re.search(r'[\w.+-]+@[\w-]+[.][\w.-]+', o))
    chk(nid + ' no eligibility claim', not re.search(r'you (are eligible|qualify)|vous (etes|êtes) (admissible|eligible)', o, re.I))
    chk(nid + ' reply < 32000 chars and < 32000 UTF-8 bytes', len(o) < 32000 and len(o.encode('utf-8')) < 32000, (len(o), len(o.encode('utf-8'))))
o46 = (HC / 'out' / 'brief-105246-2026.txt').read_text(encoding='utf-8')
for k in ['ISO 9001', 'regulation 58', 'hasOptions=false', 'Quality 40']:
    chk('105246 retains ' + k, k in o46)
b46, d46 = D['105246-2026']; C0 = crel(d46, '105246-2026')
V = {'indent1': json.dumps(d46, indent=1, ensure_ascii=False), 'indent4': json.dumps(d46, indent=4, ensure_ascii=False), 'compact': json.dumps(d46, separators=(',', ':'), ensure_ascii=False), 'crlf_indent2': json.dumps(d46, indent=2, ensure_ascii=False).replace(chr(10), chr(13) + chr(10)), 'ascii_escaped_indent2': json.dumps(d46, indent=2), 'trailing_blank_lines': b46.decode('utf-8') + chr(10) * 3}
for k, s in V.items():
    f = put(k + '.json', s); n = f.stat().st_size
    rc, o, _ = run(f, '105246-2026')
    rd = hashlib.sha256(f.read_bytes()).hexdigest() != hashlib.sha256(b46).hexdigest()
    if n < 20000:
        chk('format ' + k + ': canonical unchanged', rc == 0 and canon(o) == C0, {'bytes': n, 'raw_hash_differs': rd})
    else:
        chk('format ' + k + ': over limit refused', rc == 2, {'bytes': n})
def rel46(d):
    return [r for r in d['releases'] if r.get('id') == '105246-2026'][0]
def alt(fn):
    d = copy.deepcopy(d46); fn(rel46(d)); return json.dumps(d, indent=1, ensure_ascii=False)
A = {
 'double space inside buyer name': lambda r: r['buyer'].__setitem__('name', r['buyer']['name'].replace(' ', '  ', 1)),
 'trailing space in title': lambda r: r['tender'].__setitem__('title', r['tender']['title'] + ' '),
 'one character changed in description': lambda r: r['tender'].__setitem__('description', 'X' + r['tender']['description'][1:]),
 'deadline altered': lambda r: r['tender']['tenderPeriod'].__setitem__('endDate', '2026-12-08T12:00:00Z'),
}
for k, fn in A.items():
    rc, o, _ = run(put('alt.json', alt(fn)), '105246-2026')
    chk('altered content (' + k + '): canonical hash changes', rc == 0 and canon(o) not in (None, C0), canon(o))
    if k == 'deadline altered':
        chk('altered deadline is reported as pasted (hash comparison is the only detection)', '2026-12-08 12:00 UTC' in o)
s1 = V['indent1']; i = s1.index('"title": "') + 15
M = {
 'truncated half': b46[:len(b46) // 2],
 'invalid UTF-8 byte': b46[:100] + bytes([255, 254]) + b46[100:],
 'line break inserted inside a string (email wrap)': (s1[:i] + chr(10) + s1[i:]).encode('utf-8'),
 'empty paste': b'',
 'JSON array instead of release package': b'[]',
 'exactly 20000 bytes': b46 + b' ' * (20000 - len(b46)),
}
for k, data in M.items():
    rc, o, _ = run(put('m.json', data), '105246-2026')
    chk('malformed (' + k + '): refused exit 2 with EN/FR message', rc == 2 and 'REFUSED / REFUSÉ' in o and 'EN: ' in o and 'FR: ' in o and "agents d'IA autonomes" in o, o[:200])
rc, o, _ = run(put('b.json', b46 + b' ' * (19999 - len(b46))), '105246-2026')
chk('19999 bytes accepted, canonical unchanged', rc == 0 and canon(o) == C0)
rc, o, _ = run(RAW / '105246-2026.json', '105838-2026')
chk('wrong notice id refused', rc == 2 and 'is not in the pasted text' in o and 'texte collé' in o, o[:200])
rc, o, _ = run(RAW / '105246-2026.json', '105246-2026', '2026-12-08T00:00:00Z')
chk('past deadline flagged', rc == 0 and 'has already passed' in o)
env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LC_ALL': 'C', 'LANG': 'C'}
rc, o, e = run(RAW / '105246-2026.json', '105246-2026', NOW, env)
chk('C locale: identical UTF-8 reply', rc == 0 and o == o46, e[-200:])
ins = json.loads((HC / 'inserted-sentences.json').read_text(encoding='utf-8'))
base = (HC / 'baseline-index.html').read_bytes(); cand = pathlib.Path('products/sites/open-software-tenders/index.html').read_bytes()
chk('baseline index equals live sha256 recorded in rehearsal', hashlib.sha256(base).hexdigest() == 'b962f53d7a9561d9e0fa003fad0f2cd7613bba0f981b6fa3f950e4ab75186707', hashlib.sha256(base).hexdigest())
ct = cand.decode('utf-8'); bt = base.decode('utf-8')
chk('removing the two sentences restores baseline bytes', ct.replace(ins['en'], '').replace(ins['fr'], '').encode('utf-8') == base)
en_blk = ct.split('<!--offer-test-en-->')[1].split('<!--/offer-test-en-->')[0]; fr_blk = ct.split('<!--offer-test-fr-->')[1].split('<!--/offer-test-fr-->')[0]
chk('EN sentence once, inside EN offer, after hash sentence', ct.count(ins['en']) == 1 and (ins['en_anchor'] + ins['en']) in en_blk)
chk('FR sentence once, inside FR offer, after hash sentence', ct.count(ins['fr']) == 1 and (ins['fr_anchor'] + ins['fr']) in fr_blk)
chk('sentences state non-authentication EN/FR', 'neither hash proves' in ins['en'] and 'aucune empreinte ne prouve' in ins['fr'])
for k in ['CAD 49', '49 CAD', 'under 20 KB', 'moins de 20 Ko', 'This listing expires at 2026-12-07 12:00 UTC', '2027-01-08 12:00 UTC', 'tender-deadlines.ics', 'Made by autonomous AI agents', "Conçu par des agents d'IA autonomes", 'globalland@agentmail.to', 'No attachments', 'unvalidated price hypothesis']:
    chk('preserved: ' + k, ct.count(k) == bt.count(k) and bt.count(k) > 0, (bt.count(k), ct.count(k)))
ok = sum(r['pass'] for r in res)
out = {'label': 'SYNTHETIC CHECKS - preparation only; not a customer request, delivery, order, payment or revenue', 'mission': 'TENDER-FULFILLMENT-HASH-CORRECTION', 'author': 'BUILDER (autonomous AI agent)', 'run_now_utc': NOW, 'python': platform.python_version(), 'reconcile_sha256': hashlib.sha256(R.read_bytes()).hexdigest(), 'candidate_index_sha256': hashlib.sha256(cand).hexdigest(), 'baseline_index_sha256': hashlib.sha256(base).hexdigest(), 'canonical_105246': C0, 'max_reply_bytes': maxb[0], 'passed': ok, 'total': len(res), 'checks': res}
(HC / 'hash-test-results.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print(ok, '/', len(res), 'maxbytes', maxb[0], out['reconcile_sha256'], out['candidate_index_sha256'])
for r in res:
    if not r['pass']:
        print('FAIL', r)
