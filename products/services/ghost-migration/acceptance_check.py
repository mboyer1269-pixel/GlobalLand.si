import json, re, sys, copy, hashlib, importlib.util
sp = importlib.util.spec_from_file_location('w', 'products/services/ghost-migration/wrap_blockquote_br.py'); w = importlib.util.module_from_spec(sp); sp.loader.exec_module(w)
def text(h): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h)).strip()
src = json.load(open('products/services/ghost-migration/fixtures/synthetic-import.json'))
out = copy.deepcopy(src); n = w.fix_doc(out)
P0 = src['db'][0]['data']['posts']; P1 = out['db'][0]['data']['posts']
checks = []
def c(name, ok): checks.append({'check': name, 'pass': bool(ok)})
c('posts changed == 2 (s1, s4)', n == 2)
c('s1 wrapped in p', P1[0]['html'] == '<p>Intro</p><blockquote><p>Line one<br>Line two<br/>Line three</p></blockquote><p>End</p>')
c('s2 unchanged (no br)', P1[1]['html'] == P0[1]['html'])
c('s3 unchanged (already p)', P1[2]['html'] == P0[2]['html'])
c('s4 both quotes wrapped, attrs kept', P1[3]['html'] == '<blockquote class="q"><p><em>Ital</em><br><a href="https://example.com/">link</a></p></blockquote><blockquote><p>x<br>y</p></blockquote>')
c('s5 untouched', P1[4] == P0[4])
c('visible text preserved in every post', all(text(a.get('html') or '') == text(b.get('html') or '') for a, b in zip(P0, P1)))
c('br count preserved', all(len(w.BR.findall(a.get('html') or '')) == len(w.BR.findall(b.get('html') or '')) for a, b in zip(P0, P1)))
again = copy.deepcopy(out); c('idempotent', w.fix_doc(again) == 0 and again == out)
c('non-post fields unchanged', out['db'][0]['meta'] == src['db'][0]['meta'])
res = {'synthetic_fixtures_only': True, 'ghost_import_tested': False, 'passed': sum(x['pass'] for x in checks), 'total': len(checks), 'checks': checks, 'script_sha256': hashlib.sha256(open('products/services/ghost-migration/wrap_blockquote_br.py','rb').read()).hexdigest()}
json.dump(res, open('products/services/ghost-migration/acceptance-results.json', 'w'), indent=2)
print(json.dumps(res, indent=1)); sys.exit(0 if res['passed'] == res['total'] else 1)
