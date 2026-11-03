from pathlib import Path
import hashlib,json
p=Path(__file__).resolve().parent
m=json.loads((p/'link-evidence.json').read_text())
checks=[]
for r in m['records']:
    raw=(p/r['artifact']).read_bytes()
    checks.append({'artifact':r['artifact'],'sha256_matches':hashlib.sha256(raw).hexdigest()==r['sha256'],'nonempty':bool(raw)})
raw=(p/'requests-README.original.md').read_bytes()
checks.append({'artifact':'requests-README.original.md','sha256_matches':hashlib.sha256(raw).hexdigest()==m['source_sha256'],'nonempty':bool(raw)})
result={'mode':'offline evidence replay; not a live link check','checks':checks,'passed':all(c['sha256_matches'] and c['nonempty'] for c in checks)}
(p/'fixture-results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
assert result['passed']
