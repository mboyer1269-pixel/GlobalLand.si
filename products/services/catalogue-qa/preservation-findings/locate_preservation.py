"""Internal localization only. Autonomous AI; synthetic-tested, real imports untested."""
import csv,json,sys
from collections import defaultdict
FIELDS=[('barcode','Barcodes'),('color','Option1 value'),('size','Option2 value'),('price','Price')]
def decode(b):
    for p in ('gtin:','upc:','ean:'):
        if b.startswith(p):
            b=b[len(p):];break
    out='';i=0
    while i<len(b):
        if b[i]=='\\' and i+1<len(b):i+=1
        out+=b[i];i+=1
    return out
def load(path,required):
    rows=[]
    with open(path,encoding='utf-8-sig',newline='') as f:
        r=csv.reader(f,strict=True);hdr=next(r,None)
        if not hdr or len(set(hdr))!=len(hdr) or not set(required)<=set(hdr):
            raise ValueError('missing or duplicate headers: '+str(path))
        last=r.line_num
        for n,values in enumerate(r,1):
            start=last+1;last=r.line_num
            if len(values)!=len(hdr):raise ValueError('wrong field count: '+str(path)+' record '+str(n))
            rows.append({'file':str(path),'record':n,'physical_lines':[start,last],'values':dict(zip(hdr,values))})
    return rows
def compare(source,outputs):
    a=load(source,['sku']+[x for x,y in FIELDS]);b=[]
    for p in outputs:b.extend(load(p,['SKU']+[y for x,y in FIELDS]))
    aa=defaultdict(list);bb=defaultdict(list);findings=[];ignored=[]
    def loc(row):return {k:v for k,v in row.items() if k!='values'}
    for side,rows,key,target in [('source',a,'sku',aa),('produced',b,'SKU',bb)]:
        for row in rows:
            sku=row['values'][key]
            if not sku:
                if side=='produced' and not any(row['values'][y] for x,y in FIELDS):
                    ignored.append(loc(row));continue
                findings.append({'kind':'ambiguous_blank_key','side':side,**loc(row)});continue
            target[sku].append(row)
    for sku in sorted(set(aa)|set(bb)):
        left,right=aa[sku],bb[sku]
        locations={'source':[loc(r) for r in left],'produced':[loc(r) for r in right]}
        if len(left)>1 or len(right)>1:
            findings.append({'kind':'ambiguous_duplicate_key','sku':sku,**locations});continue
        if not left or not right:
            findings.append({'kind':'extra_sku' if not left else 'missing_sku','sku':sku,**locations});continue
        for x,y in FIELDS:
            expected=left[0]['values'][x];raw=right[0]['values'][y]
            observed=decode(raw) if x=='barcode' else raw
            if expected!=observed:
                findings.append({'kind':'value_difference','sku':sku,'field':y,'source_field':x,'expected':expected,'observed':observed,'observed_raw':raw,**locations})
    return {'scope':'Localization only; run unchanged verifier separately. Exact string SKU matching, no trimming; recognized barcode prefixes and escaping follow verify.py. BOM accepted for diagnosis only.','findings':findings,'ignored_image_only_rows':ignored}
if __name__=='__main__':
    try:
        if len(sys.argv)<3:raise ValueError('usage: locate_preservation.py SOURCE.csv OUTPUT.csv [OUTPUT2.csv ...]')
        result=compare(sys.argv[1],sys.argv[2:]);print(json.dumps(result,ensure_ascii=False,indent=2))
        sys.exit(1 if result['findings'] else 0)
    except (ValueError,csv.Error,OSError,UnicodeError) as e:
        print(json.dumps({'error':str(e)}));sys.exit(2)
