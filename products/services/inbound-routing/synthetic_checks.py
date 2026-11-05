# SYNTHETIC routing checks for routing-note-en-fr.md. Not customer messages.
import json, re, sys, subprocess
sys.path.insert(0, '../csv-text-diagnostic')
CSV_RE = re.compile(r'---CSV START---\n(.*?)\n---CSV END---', re.S)
WELFARE = re.compile(r'104449|bradford|welfare|tender|appel d.offres|conseil social', re.I)
CSV_HINT = re.compile(r'\bcsv\b', re.I)
def route(text):
    if len(text) > 20000: return 'CSV_DECLINE' if CSV_HINT.search(text) else 'CLARIFY'
    m = CSV_RE.search(text)
    w = bool(WELFARE.search(text))
    if m and w: return 'CLARIFY'
    if m:
        rows = [r for r in m.group(1).split('\n') if r.strip()]
        return 'CSV_DIAGNOSTIC' if 1 <= len(rows) - 1 <= 20 else 'CSV_DECLINE'
    if CSV_HINT.search(text) and not w: return 'CSV_DECLINE'
    if w: return 'WELFARE_BRIEF'
    if re.search(r'price|prix|order|commande|service|help|aide', text, re.I): return 'CLARIFY'
    return 'NONCOMMERCIAL'
def no_url_claim(reply):
    return not re.search(r'(I|we) (visited|reviewed|checked) (your )?(website|link)', reply, re.I)
rows21 = '\n'.join(['a,b'] + ['%d,x' % i for i in range(21)])
cases = [
 ('csv_ok', '---CSV START---\nid,name\n1,Alice Example\n---CSV END---', 'CSV_DIAGNOSTIC'),
 ('csv_no_markers', 'Can you check my csv? id,name 1,x', 'CSV_DECLINE'),
 ('csv_21_rows', '---CSV START---\n' + rows21 + '\n---CSV END---', 'CSV_DECLINE'),
 ('welfare_provider', 'We are a welfare advice charity considering lot 2 of the Bradford tender. Public site: https://example.org', 'WELFARE_BRIEF'),
 ('welfare_fr', 'Nous envisageons l appel d offres 104449-2026.', 'WELFARE_BRIEF'),
 ('mixed', 'Re the Bradford tender, also check: ---CSV START---\na,b\n1,2\n---CSV END---', 'CLARIFY'),
 ('vague_price', 'What is the price of your service?', 'CLARIFY'),
 ('noncommercial', 'Hello, nice weather today.', 'NONCOMMERCIAL'),
 ('oversize', 'csv ' + 'x' * 20001, 'CSV_DECLINE'),
]
results = []
for name, text, exp in cases:
    got = route(text)
    results.append({'case': name, 'synthetic': True, 'expected': exp, 'got': got, 'pass': got == exp})
# Actual diagnostic output for the eligible synthetic CSV case
d = subprocess.run([sys.executable, '-I', '../csv-text-diagnostic/diagnostic.py'], input=cases[0][1], capture_output=True, text=True)
try:
    dj = json.loads(d.stdout); diag_ok = dj.get('status') == 'CHECKED'
except Exception:
    dj = d.stdout[:300]; diag_ok = False
results.append({'case': 'csv_ok_diagnostic_executes', 'synthetic': True, 'got': dj, 'pass': diag_ok})
results.append({'case': 'reply_no_url_claim_guard', 'synthetic': True, 'pass': no_url_claim('Thanks; we did not open your link.') and not no_url_claim('We visited your website.')})
note = open('routing-note-en-fr.md', encoding='utf-8').read()
for key in ['autonomous AI agents', 'NOT verified', 'site:invoice-preflight', 'site:welfare-tender-brief', 'unvalidated price hypothesis', 'hypothèse de prix non validée', 'Accepted order: unavailable', '2026-12-04T17:00Z', 'cannot retrieve URLs']:
    results.append({'case': 'note_contains:' + key, 'pass': key in note})
out = {'label': 'SYNTHETIC routing checks; not customer data, not demand, not delivery', 'observed': '2026-11-05', 'passed': sum(r['pass'] for r in results), 'total': len(results), 'results': results}
open('synthetic-check-results.json', 'w', encoding='utf-8').write(json.dumps(out, indent=1, ensure_ascii=False))
print(out['passed'], '/', out['total']); [print(r['case'], r['pass'], r.get('got')) for r in results if not r['pass']]
