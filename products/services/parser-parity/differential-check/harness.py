# Differential check of the synthetic decimal-string repair. Made by autonomous AI agents (GlobalLand BUILDER).
# Usage: python3 harness.py <fulfillment-rehearsal/results.json> <output-dir>   (python3 and node required, offline)
import json,re,subprocess,sys,hashlib,pathlib
src=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
R=json.loads(src.read_text(encoding='utf-8'))
ns={'re':re};exec(R['reference_source'],ns);ref=ns['to_cents']
A='0123456789'
def oracle(s):
    # independent, regex-free reading of the stated contract: optional '-', 1-12 ASCII digits, optional '.' plus 1-2 ASCII digits, nothing else
    neg=s[:1]=='-';t=s[1:] if neg else s
    ip,dot,fp=t.partition('.')
    if not(1<=len(ip)<=12) or any(ch not in A for ch in ip):return None
    if dot and (not(1<=len(fp)<=2) or any(ch not in A for ch in fp)):return None
    c=0
    for ch in ip:c=c*10+A.index(ch)
    f=(fp+'00')[:2];c=c*100+A.index(f[0])*10+A.index(f[1])
    return -c if neg else c
signs=['','-','+','--','−','- ']
ints=['','0','00','007','7','10','42']+['9'*n for n in range(1,15)]+['1'+'0'*(n-1) for n in range(2,15)]+['123456789012','1234567890123','999999999999','1000000000000']
fracs=[None,'','0','5','9','00','05','50','99','000','005','995','999','1.']
corpus=[s+i+('' if f is None else '.'+f) for s in signs for i in ints for f in fracs]
seeds=['0','-0','12.5','-3.07','999999999999.99','7']
W=[' ','\t','\n','\r','\r\n',' ',' ',' ','﻿','\x00','\x0b','\x0c','\x85','a','e1','%',',','_','.','\ud800']
for x in seeds:
    for w in W:corpus+=[w+x,x+w,w+x+w]
corpus+=['1 2','1_000','1,000','1\n2','12.\n5','12\n.5','١٢','١٢.٥','１２.５０','12.٥','-٠','1٢','१२','\U0001d7cf\U0001d7d0','1e2','1E2','0x10','0b1','0o7','NaN','Infinity','-Infinity','null','true','-','.','-.','-.5','.5','5.','--5','+-5','-+5','1.2.3','1..2','１','-0.0','-0.00','-00.00','-000000000000.00','0.1','0.01','-0.01','-0.1','1.10','1.01']
seen=set();corpus=[c for c in corpus if not(c in seen or seen.add(c))]
assert len(corpus)<=5000
cj=json.dumps(corpus,ensure_ascii=True)
(out/'corpus.json').write_text(cj,encoding='ascii')
runner=pathlib.Path(__file__).resolve().parent/'runner.js'
subprocess.run(['node',str(runner),str(src),str(out/'corpus.json'),str(out/'node-out.json')],check=True)
N=json.loads((out/'node-out.json').read_text(encoding='utf-8'))
ser=lambda v:'null' if v is None else str(v)
rows=[];mm_ref_oracle=[];mm_port_ref=[];mm_port_oracle=[];negzero=[]
for s,j in zip(corpus,N['out']):
    r=ser(ref(s));o=ser(oracle(s))
    if r!=o:mm_ref_oracle.append({'input':s,'reference':r,'oracle':o})
    if j=='-0':negzero.append(s)
    if j!=r:mm_port_ref.append({'input':s,'reference':r,'port':j})
    if j!=o:mm_port_oracle.append({'input':s,'oracle':o,'port':j})
    rows.append([s,r,o,j])
acc=[r for r in rows if r[1]!='null']
res={'synthetic':True,'customer':None,'made_by':'autonomous AI agents (GlobalLand BUILDER)','python':sys.version.split()[0],'node':N['node'],
 'source_results_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'corpus_sha256':hashlib.sha256(cj.encode()).hexdigest(),
 'corpus_size':len(corpus),'existing_25_cases_overlap':len(set(corpus)&{r['input'] for r in R['rows']}),
 'reference_accepts':len(acc),'reference_rejects':len(rows)-len(acc),
 'accepted_min':min(int(r[1]) for r in acc),'accepted_max':max(int(r[1]) for r in acc),
 'port_vs_reference_mismatches':len(mm_port_ref),'port_vs_oracle_mismatches':len(mm_port_oracle),'reference_vs_oracle_mismatches':len(mm_ref_oracle),
 'port_negative_zero_outputs':negzero,'port_nonstandard_outputs':[r for r in rows if r[3].startswith(('TYPE:','THROW:'))][:20],
 'mismatch_samples':{'port_vs_reference':mm_port_ref[:20],'port_vs_oracle':mm_port_oracle[:20],'reference_vs_oracle':mm_ref_oracle[:20]},
 'spot':{k:([r[1:] for r in rows if r[0]==k] or ['ABSENT'])[0] for k in ['-0','-0.00','999999999999.99','-999999999999.99','1000000000000','12.5\n','١٢','12.5 ','0.01','7.','1\ud800']},
 'limits':'Only this generated corpus on these runtime versions was executed. Synthetic; not a production guarantee, not a security audit, not customer delivery.'}
(out/'results.json').write_text(json.dumps(res,indent=1,ensure_ascii=True),encoding='ascii')
print(json.dumps(res,indent=1,ensure_ascii=True))
