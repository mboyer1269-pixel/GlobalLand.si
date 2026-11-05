#!/usr/bin/env python3
# Synthetic acceptance tests (no customer data). Writes acceptance-results.json.
import json, os, subprocess, sys, tempfile
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import diagnostic as dg
S, E = dg.START, dg.END
def wrap(c): return 'Hello,\nplease check this synthetic sample.\n' + S + '\n' + c + '\n' + E + '\nThanks'
rows21 = 'Invoice,Amount\n' + '\n'.join('INV-%03d,1.00' % k for k in range(21))
rows20 = 'Invoice,Amount\n' + '\n'.join('INV-%03d,1.00' % k for k in range(20))
cases = [
 ('normal', wrap('Invoice,Customer,Amount\nINV-001,Example,125.00'), {'status':'CHECKED','structure_ok':True,'dataRows':1,'columns':3,'errors':[]}),
 ('quoted comma', wrap('A,B\n"x, y",2'), {'status':'CHECKED','structure_ok':True,'dataRows':1,'columns':2,'errors':[]}),
 ('ragged', wrap('A,B\n1'), {'status':'CHECKED','structure_ok':False,'errors':['Row 2 has 1 columns; expected 2']}),
 ('duplicate header', wrap('A,A\n1,2'), {'status':'CHECKED','errors':['Duplicate header: A']}),
 ('empty header', wrap('A,,C\n1,2,3'), {'status':'CHECKED','errors':['Empty header at column 2']}),
 ('unclosed quote', wrap('A,B\n"1,2'), {'status':'CHECKED','errors':['Unclosed quoted field','Row 2 has 1 columns; expected 2']}),
 ('crlf + bom', 'x\r\n' + S + '\r\n﻿A,B\r\n1,2\r\n' + E, {'status':'CHECKED','structure_ok':True,'dataRows':1,'columns':2}),
 ('exactly 20 rows', wrap(rows20), {'status':'CHECKED','dataRows':20}),
 ('21 rows declined', wrap(rows21), {'status':'DECLINED','reason':'TOO_MANY_ROWS','dataRows':21}),
 ('missing markers', 'A,B\n1,2', {'status':'DECLINED','reason':'MISSING_CSV_MARKERS'}),
 ('too large', wrap('A\n' + 'x' * 20001), {'status':'DECLINED','reason':'MESSAGE_TOO_LARGE'}),
 ('empty block', wrap(''), {'status':'CHECKED','structure_ok':False,'errors':['Empty file']}),
]
results = []
for name, body, exp in cases:
    out = dg.diagnose(body)
    ok = all(out.get(k) == v for k, v in exp.items())
    if out.get('status') == 'CHECKED':
        ok = ok and 'compatibility with Manager.io or any accounting platform' in out['not_checked']
    results.append({'name': name, 'expected_subset': exp, 'output': out, 'passed': ok})
# Parity with the live public JS checker on the same CSV texts
parity_inputs = [dg.extract(b) for n, b, e in cases if dg.extract(b) is not None and len(b) <= dg.MAX_CHARS]
js = r'''const fs=require('fs');const h=fs.readFileSync(process.argv[1],'utf8');const s=h.indexOf('function check(');const e=h.indexOf('document.getElementById("run")');eval(h.slice(s,e));const inp=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));console.log(JSON.stringify(inp.map(check)));'''
site = os.path.join(D, '..', '..', 'sites', 'invoice-preflight', 'index.html')
with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
    json.dump(parity_inputs, f)
try:
    js_out = json.loads(subprocess.run(['node', '-e', js, site, f.name], capture_output=True, text=True, timeout=30).stdout)
    py_out = [dg.check(t) for t in parity_inputs]
    parity = {'cases': len(parity_inputs), 'identical': js_out == py_out,
              'mismatches': [i for i, (a, b) in enumerate(zip(js_out, py_out)) if a != b]}
except Exception as ex:
    parity = {'cases': len(parity_inputs), 'identical': None, 'error': repr(ex)}
summary = {'scope': 'Synthetic messages only; private mail cycle not exercised by these tests',
           'passed': sum(r['passed'] for r in results), 'total': len(results),
           'js_parity_with_live_checker': parity, 'python': sys.version.split()[0], 'results': results}
json.dump(summary, open(os.path.join(D, 'acceptance-results.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: summary[k] for k in ('passed', 'total', 'js_parity_with_live_checker', 'python')}))
print([r['name'] for r in results if not r['passed']])
