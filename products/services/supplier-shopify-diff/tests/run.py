import csv,io,json,subprocess
from pathlib import Path
root=Path('products/services/supplier-shopify-diff')
def reference(a,b,c):
    out=[]
    def emit(t,s,r,o,k,f,v,w):out.append(dict(type=t,side=s,row=r,other_row=o,key=k,field=f,value=v,other_value=w))
    ka=a[0].index(c['keyA']);kb=b[0].index(c['keyB'])
    def index(rows,k,side):
        m={}
        for n,r in enumerate(rows[1:],2):
            key=r[k].strip()
            if not key:emit('missing_key',side,n,'','',rows[0][k],r[k],'')
            else:m.setdefault(key,[]).append((n,r))
        for key,rs in m.items():
            if len(rs)>1:
                for n,r in rs:emit('duplicate_key',side,n,'',key,rows[0][k],r[k],'')
        return m
    ma=index(a,ka,'supplier');mb=index(b,kb,'shopify')
    for rows,k,side in [(a,ka,'supplier'),(b,kb,'shopify')]:
        for n,r in enumerate(rows[1:],2):
            for f in c['fields']:
                name=f['a' if side=='supplier' else 'b'];v=r[rows[0].index(name)]
                if f['kind'] in ('price','stock') and not v.strip():emit('ambiguous_blank',side,n,'',r[k].strip(),name,v,'')
    for key,rs in ma.items():
        if key not in mb:
            for n,r in rs:emit('missing_in_shopify','supplier',n,'',key,a[0][ka],r[ka],'')
            continue
        if len(rs)!=1 or len(mb[key])!=1:continue
        n,r=rs[0];o,s=mb[key][0]
        for f in c['fields']:
            v=r[a[0].index(f['a'])].strip();w=s[b[0].index(f['b'])].strip()
            if f['kind'] in ('price','stock') and (not v or not w):continue
            if f.get('map',{}).get(v,v)!=w:emit(f['kind']+'_difference','supplier',n,o,key,f['a']+' → '+f['b'],v,w)
    for key,rs in mb.items():
        if key not in ma:
            for n,r in rs:emit('new_in_shopify','shopify',n,'',key,b[0][kb],r[kb],'')
    return out
def encode(rows):
    f=io.StringIO();csv.writer(f,lineterminator='\r\n').writerows(rows);return f.getvalue()
cfg={'keyA':'SKU','keyB':'SKU','fields':[{'a':'Price','b':'Price','kind':'price'},{'a':'Stock','b':'Stock','kind':'stock'},{'a':'Size','b':'Size','kind':'option','map':{'S':'Small'}}]}
h=['SKU','Price','Stock','Size']
a=[h,[' a ','10','2','S'],['b','20','','L'],['d','1','1','M'],['d','2','2','M'],['','5','1','X'],['missing','1','1','M'],['comma','1','2','red, blue'],['quote','1','1','a"b'],['multiline','1','1','red\nblue']]
b=[h,['a','11','2','Small'],['b','20','3','XL'],['d','1','1','M'],['new','2','2','M'],['comma','1','2','red, blue'],['quote','1','1','a"b'],['multiline','1','1','red\nblue']]
cases=[{'a':'\ufeff'+encode(a),'b':encode(b),'cfg':cfg}]
big=[h]+[[str(i),'10','1','S'] for i in range(10000)]
bigb=[h]+[[str(i),'10','1','Small'] for i in range(10000)]
cases.append({'a':encode(big),'b':encode(bigb),'cfg':cfg})
cases.append({'a':encode([h,['x','1','1','S']]),'b':encode([h,['x','1','1','Small']]),'cfg':cfg})
# Both duplicate sides, case-sensitive keys, blank prices, unknown mappings and quoted keys.
cases.append({'a':encode([h,['A','','1','Z'],['z','1','1','Q']]),'b':encode([h,['A','','1','Y'],['a','1','1','Q'],['z','1','1','Q'],['z','2','1','R']]),'cfg':cfg})
runner="""const fs=require('fs'),vm=require('vm');const c=require('./products/services/supplier-shopify-diff/core.js');const page=fs.readFileSync('products/sites/supplier-shopify-diff/index.html','utf8');new vm.Script(page.match(/<script>([\\s\\S]*)<\\/script>/)[1]);let data=JSON.parse(fs.readFileSync(0,'utf8'));let out=data.map(x=>{const a=c.parse(x.a),b=c.parse(x.b);return {a,b,diff:c.compare(a,b,x.cfg),csv:c.csv(c.compare(a,b,x.cfg))};});let invalid=['','A,A\\nx,y','A,B\\nx','A\\n\\"bad','A\\n\\"x\\"z'];let rejected=invalid.map(s=>{try{c.parse(s);return false}catch(e){return true}});process.stdout.write(JSON.stringify({out,rejected}));"""
proc=subprocess.run(['node','-e',runner],input=json.dumps(cases),text=True,capture_output=True)
checks=[{'name':'node_exit','pass':proc.returncode==0,'stderr':proc.stderr}]
if proc.returncode==0:
    actual=json.loads(proc.stdout)
    for i,(case,result) in enumerate(zip(cases,actual['out'])):
        pa=list(csv.reader(io.StringIO(case['a'].lstrip('\ufeff'))));pb=list(csv.reader(io.StringIO(case['b'])))
        checks.append({'name':'python_csv_parity_'+str(i),'pass':pa==result['a'] and pb==result['b']})
        checks.append({'name':'python_differ_parity_'+str(i),'pass':reference(pa,pb,case['cfg'])==result['diff'],'findings':len(result['diff'])})
        exported=list(csv.reader(io.StringIO(result['csv'])))
        checks.append({'name':'download_roundtrip_'+str(i),'pass':len(exported)==len(result['diff'])+1})
    types={r['type'] for r in actual['out'][0]['diff']}
    checks.append({'name':'expected_classes','pass':{'duplicate_key','missing_key','ambiguous_blank','missing_in_shopify','new_in_shopify','price_difference','option_difference'}<=types})
    checks.append({'name':'explicit_mapping_equal','pass':actual['out'][2]['diff']==[]})
    checks.append({'name':'10000_records','pass':len(actual['out'][1]['a'])==10001 and actual['out'][1]['diff']==[]})
    checks.append({'name':'five_malformed_rejected','pass':all(actual['rejected'])})
result={'synthetic_only':True,'browser_execution':'UNTESTED','shopify_import':'UNTESTED','checks':checks,'passed':sum(x['pass'] for x in checks),'total':len(checks)}
(p:=root/'tests/results.json').write_text(json.dumps(result,indent=2))
(root/'tests/supplier.csv').write_text(cases[0]['a'],encoding='utf-8')
(root/'tests/shopify.csv').write_text(cases[0]['b'],encoding='utf-8')
print(json.dumps(result))
raise SystemExit(0 if all(x['pass'] for x in checks) else 1)
