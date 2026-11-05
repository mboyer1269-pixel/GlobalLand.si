# Worked-example transformation (not a product): flat supplier variant list -> Shopify product CSV row layout.
# Source rules: https://help.shopify.com/en/manual/products/import-export/using-csv (fetched 2026-11-05, sha256 b54405fa...).
import csv, io, json, re, sys, unicodedata
OUT_COLS = ['URL handle','Title','Description','Vendor','Type','Tags','Status','SKU','Option1 name','Option1 value','Option2 name','Option2 value','Price','Product image URL','Image position']
PRODUCT_ONLY = ['Title','Description','Vendor','Tags']  # doc: later variant rows skip these
def handle(title):
    s = unicodedata.normalize('NFKD', title).encode('ascii','ignore').decode().lower()
    return re.sub(r'-+','-', re.sub(r'[^a-z0-9]+','-', s)).strip('-')
def price(raw):
    s = raw.strip().replace('$','').replace('CAD','').replace('USD','').replace('€','').strip()
    if re.fullmatch(r'\d+,\d{1,2}', s): s = s.replace(',','.')
    if not re.fullmatch(r'\d+(\.\d{1,2})?', s): raise ValueError('unparseable price %r' % raw)
    return '%.2f' % float(s)
def transform(text):
    rows = list(csv.DictReader(io.StringIO(text)))
    errors, groups, order = [], {}, []
    for n, r in enumerate(rows, 2):
        t = (r.get('product') or '').strip()
        if not t: errors.append('line %d: empty product name' % n); continue
        h = handle(t)
        if h not in groups: groups[h] = []; order.append(h)
        try: p = price(r.get('price',''))
        except ValueError as e: errors.append('line %d: %s' % (n, e)); continue
        groups[h].append((t, r, p))
    out = []
    for h in order:
        seen = set(); first = True
        for t, r, p in groups[h]:
            combo = (r.get('colour','').strip(), r.get('size','').strip())
            if combo in seen: errors.append('%s: duplicate option combination %r' % (h, combo)); continue
            seen.add(combo)
            row = dict.fromkeys(OUT_COLS, '')
            row.update({'URL handle': h, 'SKU': r.get('sku','').strip(), 'Option1 value': combo[0], 'Option2 value': combo[1], 'Price': p})
            if first:
                row.update({'Title': t, 'Description': r.get('description','').strip(), 'Vendor': r.get('vendor','').strip(), 'Type': r.get('type','').strip(), 'Tags': r.get('tags','').strip(), 'Status': 'draft', 'Option1 name': 'Color', 'Option2 name': 'Size'})
                if r.get('image','').strip(): row.update({'Product image URL': r['image'].strip(), 'Image position': '1'})
            out.append(row); first = False
    buf = io.StringIO(); w = csv.DictWriter(buf, OUT_COLS, lineterminator='\n'); w.writeheader(); w.writerows(out)
    return buf.getvalue(), errors
if __name__ == '__main__':
    o, e = transform(open(sys.argv[1], encoding='utf-8').read())
    sys.stdout.write(o); sys.stderr.write(json.dumps(e))
