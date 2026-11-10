#!/usr/bin/env python3
# Synthetic checks for locate_dup_images.py. Autonomous AI agents (GlobalLand). No buyer data.
import json, os, subprocess, sys, tempfile, platform
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, 'locate_dup_images.py')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
FUL = os.path.join(ROOT, 'products/services/catalogue-qa/fulfillment')
TR = os.path.join(ROOT, 'products/sites/shopify-catalogue-example/transform.py')
H = 'style_id,color,position,url\n'
U = 'https://example.com/img/'
base = open(os.path.join(FUL, 'synthetic-i.csv'), encoding='utf-8').read()
F = {
 'existing_valid': base,
 'within_style_dup': base + 'SYN-A,Tan,5,' + U + 'SYN-A-Black-1.jpg\n',
 'cross_style_only': base + 'SYN-B,Blue,5,' + U + 'SYN-A-Black-1.jpg\n',
 'blank_values': H + 'S1,Red,1,' + U + 'a.jpg\nS1,Red,2,\n,Red,3,' + U + 'a.jpg\nS1,Red,4,' + U + 'a.jpg\n',
 'leading_zero': H + '007,Red,1,' + U + 'z.jpg\n7,Red,1,' + U + 'z.jpg\n007,Red,2,' + U + 'z.jpg\n',
 'multiline': H + 'S1,"Red\nDark",1,' + U + 'm.jpg\nS1,Blue,2,' + U + 'n.jpg\nS1,Blue,3,' + U + 'm.jpg\n',
 'whitespace_url': H + 'S1,Red,1,' + U + 'w.jpg\nS1,Red,2,  ' + U + 'w.jpg  \n',
 'missing_column': 'style_id,color,position,image\nS1,Red,1,' + U + 'a.jpg\n',
 'malformed_quote': H + 'S1,Red,1,"' + U + 'a.jpg\n',
 'field_count': H + 'S1,Red,1,' + U + 'a.jpg,extra\n',
 'bom_crlf': '﻿' + H.replace('\n', '\r\n') + ('S1,Red,1,' + U + 'b.jpg\r\n') * 2,
}
EXPECT = {
 'existing_valid': (0, lambda o: o['records'] == 8 and not o['duplicate_groups'] and not o['cross_style_reuse']),
 'within_style_dup': (1, lambda o: len(o['duplicate_groups']) == 1 and [x['record'] for x in o['duplicate_groups'][0]['occurrences']] == [1, 9] and o['duplicate_groups'][0]['occurrences'][1]['fields']['color'] == 'Tan' and o['duplicate_groups'][0]['occurrences'][1]['transform_line'] == 10),
 'cross_style_only': (0, lambda o: not o['duplicate_groups'] and o['cross_style_reuse'] == [{'url': U + 'SYN-A-Black-1.jpg', 'styles': {'SYN-A': [1], 'SYN-B': [9]}}]),
 'blank_values': (1, lambda o: [x['record'] for x in o['skipped_blank']] == [2, 3] and [x['record'] for x in o['duplicate_groups'][0]['occurrences']] == [1, 4]),
 'leading_zero': (1, lambda o: len(o['duplicate_groups']) == 1 and o['duplicate_groups'][0]['style_id'] == '007' and [x['record'] for x in o['duplicate_groups'][0]['occurrences']] == [1, 3] and set(o['cross_style_reuse'][0]['styles']) == {'007', '7'}),
 'multiline': (1, lambda o: [(x['record'], x['physical_line_start'], x['physical_line_end']) for x in o['duplicate_groups'][0]['occurrences']] == [(1, 2, 3), (3, 5, 5)] and o['duplicate_groups'][0]['occurrences'][0]['fields']['color'] == 'Red\nDark'),
 'whitespace_url': (1, lambda o: o['duplicate_groups'][0]['count'] == 2),
 'missing_column': (2, lambda o: 'missing columns' in o['errors'][0]),
 'malformed_quote': (2, lambda o: 'malformed CSV' in o['errors'][0]),
 'field_count': (2, lambda o: '5 fields, header has 4' in o['errors'][0]),
 'bom_crlf': (1, lambda o: [(x['record'], x['physical_line_start']) for x in o['duplicate_groups'][0]['occurrences']] == [(1, 2), (2, 3)]),
}
res = {'label': 'SYNTHETIC CHECKS ONLY; no buyer data, no customer delivery', 'python': platform.python_version(), 'cases': {}}
d = tempfile.mkdtemp()
for name, text in F.items():
    p = os.path.join(d, name + '.csv')
    open(p, 'w', encoding='utf-8', newline='').write(text)
    pr = subprocess.run([sys.executable, '-I', TOOL, p], capture_output=True, text=True)
    try:
        o = json.loads(pr.stdout)
        ok = pr.returncode == EXPECT[name][0] and EXPECT[name][1](o)
    except Exception as e:
        o, ok = {'parse_error': str(e), 'stdout': pr.stdout, 'stderr': pr.stderr}, False
    if isinstance(o, dict): o.pop('file', None)
    res['cases'][name] = {'exit': pr.returncode, 'expected_exit': EXPECT[name][0], 'pass': ok, 'output': o}
ip = os.path.join(d, 'within_style_dup.csv')
pr = subprocess.run([sys.executable, '-I', TR, '--variants', os.path.join(FUL, 'synthetic-v.csv'), '--images', ip, '--out', os.path.join(d, 'o.csv'), '--report', os.path.join(d, 'r.json')], capture_output=True, text=True)
rep = json.load(open(os.path.join(d, 'r.json')))
res['transform_crosscheck'] = {'exit': pr.returncode, 'errors': rep['errors'], 'pass': pr.returncode == 2 and 'style SYN-A: same image URL used twice' in rep['errors'], 'note': 'transform.py names the style only; helper adds records 1 and 9 (transform_line 2 and 10)'}
res['passed'] = sum(c['pass'] for c in res['cases'].values()) + res['transform_crosscheck']['pass']
res['total'] = len(res['cases']) + 1
res['all_pass'] = res['passed'] == res['total']
out = os.path.join(HERE, 'check-results.json')
json.dump(res, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(json.dumps({'passed': res['passed'], 'total': res['total'], 'fails': [k for k, c in res['cases'].items() if not c['pass']], 'transform': res['transform_crosscheck']}))
