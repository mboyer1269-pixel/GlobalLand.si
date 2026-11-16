import csv,json,subprocess,sys,copy
from pathlib import Path
D=Path(__file__).parent
S=['style_id','title','color','size','sku','barcode','price']
P=['SKU','Barcodes','Option1 value','Option2 value','Price']
s=[['A','Synthetic\nTitle','Blue','M','001','0001','9.00'],['B','Other','Red','L','002','0002','10.00']]
p=[['001','gtin:0001','Blue','M','9.00'],['002','ean:0002','Red','L','10.00']]
def write(path,header,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,lineterminator='\r\n');w.writerow(header);w.writerows(rows)
cases=[]
def run(name,sv,pv,check,code=1):
    sf=D/(name+'-source.csv');pf=D/(name+'-produced.csv')
    write(sf,S,sv);write(pf,P,pv)
    cmd=[sys.executable,str(D/'locate_preservation.py'),str(sf),str(pf)]
    proc=subprocess.run(cmd,text=True,capture_output=True)
    data=json.loads(proc.stdout)
    passed=proc.returncode==code and check(data)
    cases.append({'name':name,'command':cmd,'exit':proc.returncode,'passed':passed,'output':data})
run('valid',s,p,lambda d:not d['findings'],0)
for field,col in [('Barcodes',1),('Option1 value',2),('Option2 value',3),('Price',4)]:
    q=copy.deepcopy(p);q[0][col]='CHANGED'
    run('changed-'+field.replace(' ','_'),s,q,lambda d,f=field:len(d['findings'])==1 and d['findings'][0]['field']==f and d['findings'][0]['sku']=='001' and d['findings'][0]['source'][0]['physical_lines']==[2,3] and d['findings'][0]['produced'][0]['record']==1)
run('missing',s,p[:1],lambda d:d['findings'][0]['kind']=='missing_sku')
run('extra',s[:1],p,lambda d:d['findings'][0]['kind']=='extra_sku')
run('duplicate-source',s+[s[0]],p,lambda d:len(d['findings'])==1 and d['findings'][0]['kind']=='ambiguous_duplicate_key')
run('duplicate-produced',s,p+[p[0]],lambda d:len(d['findings'])==1 and len(d['findings'][0]['produced'])==2)
q=copy.deepcopy(s);q[0][4]=''
run('blank-source',q,p,lambda d:any(x['kind']=='ambiguous_blank_key' for x in d['findings']))
q=copy.deepcopy(p);q[0][0]=''
run('blank-produced',s,q,lambda d:any(x['kind']=='ambiguous_blank_key' for x in d['findings']))
run('image-only',s,p+[['','','','','']],lambda d:not d['findings'] and len(d['ignored_image_only_rows'])==1,0)
q=copy.deepcopy(s);q[0][5]='00;1:2\\3';r=copy.deepcopy(p);r[0][1]='upc:00\\;1\\:2\\\\3'
run('escaped-barcode',q,r,lambda d:not d['findings'],0)
result={'label':'SYNTHETIC ONLY; no customer delivery or real Shopify import','passed':sum(x['passed'] for x in cases),'total':len(cases),'cases':cases}
(D/'results.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
assert all(x['passed'] for x in cases)
