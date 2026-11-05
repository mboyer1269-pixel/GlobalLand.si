#!/usr/bin/env python3
"""Color x Size catalogue -> Shopify product CSV layout (Python stdlib only).
Built and maintained by autonomous AI agents (GlobalLand). Offline; untested in a live Shopify import.
Input 1 (variants): style_id,title,color,size,sku,barcode,price[,vendor,product_type,tags] one row per barcode.
Input 2 (images): style_id,color,position,url  one row per picture (any number per color).
"""
import argparse, csv, json, re, sys, time
from collections import OrderedDict

COLS = ['Title', 'URL handle', 'Vendor', 'Type', 'Tags', 'SKU', 'Barcodes',
        'Option1 name', 'Option1 value', 'Option2 name', 'Option2 value', 'Price',
        'Product image URL', 'Image position', 'Image alt text', 'Variant image URL']
VREQ = ['style_id', 'title', 'color', 'size', 'sku', 'barcode', 'price']
IREQ = ['style_id', 'color', 'position', 'url']
PRICE = re.compile(r'^\d+(\.\d{1,2})?$')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-') or 'x'


def esc_barcode(b):
    return b.replace('\\', '\\\\').replace(';', '\\;').replace(':', '\\:')


def read(path, req):
    with open(path, newline='', encoding='utf-8-sig') as f:
        r = csv.DictReader(f)
        miss = [c for c in req if c not in (r.fieldnames or [])]
        if miss:
            raise SystemExit('%s: missing columns %s' % (path, miss))
        return [{k: (v or '').strip() for k, v in row.items() if k} for row in r]


def build(vrows, irows, barcode_type=''):
    errors, warnings = [], []
    styles = OrderedDict()
    sku_line, bc_line, combos = {}, {}, set()
    for n, r in enumerate(vrows, start=2):
        empty = [c for c in VREQ if not r.get(c)]
        if empty:
            errors.append('variants line %d: empty %s' % (n, ','.join(empty)))
            continue
        if r['sku'] in sku_line:
            errors.append('variants line %d: duplicate SKU %s (first line %d)' % (n, r['sku'], sku_line[r['sku']]))
        sku_line.setdefault(r['sku'], n)
        if r['barcode'] in bc_line:
            errors.append('variants line %d: duplicate barcode %s (first line %d)' % (n, r['barcode'], bc_line[r['barcode']]))
        bc_line.setdefault(r['barcode'], n)
        if not PRICE.match(r['price']):
            errors.append('variants line %d: price %r is not a plain number like 9.99' % (n, r['price']))
        key = (r['style_id'], r['color'].lower(), r['size'].lower())
        if key in combos:
            errors.append('variants line %d: style %s already has color %s size %s' % (n, r['style_id'], r['color'], r['size']))
            continue
        combos.add(key)
        st = styles.setdefault(r['style_id'], {'title': r['title'], 'vendor': r.get('vendor', ''),
                                              'type': r.get('product_type', ''), 'tags': r.get('tags', ''),
                                              'colors': OrderedDict()})
        if st['title'] != r['title']:
            errors.append('variants line %d: style %s has two titles %r / %r' % (n, r['style_id'], st['title'], r['title']))
        st['colors'].setdefault(r['color'], []).append(r)
    imgs = {}
    for n, r in enumerate(irows, start=2):
        if not all(r.get(c) for c in IREQ):
            errors.append('images line %d: empty field' % n)
            continue
        if not r['position'].isdigit():
            errors.append('images line %d: position %r is not an integer' % (n, r['position']))
            continue
        if not r['url'].lower().startswith(('http://', 'https://')):
            errors.append('images line %d: url must be a public http(s) URL' % n)
        imgs.setdefault((r['style_id'], r['color'].lower()), []).append((int(r['position']), r['url']))
    known = {(s, c.lower()) for s, st in styles.items() for c in st['colors']}
    for k in imgs:
        if k not in known:
            warnings.append('images for style %s color %s have no variants; ignored' % k)
    products, handles = [], {}
    for sid, st in styles.items():
        handle = slug(st['title']) + '-' + slug(sid)
        if handle in handles:
            errors.append('styles %s and %s produce the same URL handle %s' % (handles[handle], sid, handle))
        handles[handle] = sid
        images, first = [], {}
        for color in st['colors']:
            lst = sorted(imgs.get((sid, color.lower()), []))
            if not lst:
                warnings.append('style %s color %s has no image; Variant image URL left blank' % (sid, color))
            for _, url in lst:
                first.setdefault(color, url)
                images.append((url, '%s - %s' % (st['title'], color)))
        urls = [u for u, _ in images]
        if len(set(urls)) != len(urls):
            errors.append('style %s: same image URL used twice' % sid)
        variants = [v for c in st['colors'] for v in st['colors'][c]]
        rows = []
        for i in range(max(len(variants), len(images))):
            row = dict.fromkeys(COLS, '')
            row['URL handle'] = handle
            if i < len(variants):
                v = variants[i]
                if i == 0:
                    row.update({'Title': st['title'], 'Vendor': st['vendor'], 'Type': st['type'], 'Tags': st['tags']})
                row.update({'SKU': v['sku'],
                            'Barcodes': (barcode_type + ':' if barcode_type else '') + esc_barcode(v['barcode']),
                            'Option1 name': 'Color', 'Option1 value': v['color'],
                            'Option2 name': 'Size', 'Option2 value': v['size'], 'Price': v['price'],
                            'Variant image URL': first.get(v['color'], '')})
            if i < len(images):
                row.update({'Product image URL': images[i][0], 'Image position': str(i + 1), 'Image alt text': images[i][1]})
            rows.append(row)
        products.append(rows)
    return products, errors, warnings


def write(products, out, max_rows):
    files, chunk, cur = [], [], 0
    def flush():
        name = out if not max_rows else out.replace('.csv', '-part%d.csv' % (len(files) + 1))
        with open(name, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=COLS, lineterminator='\n')
            w.writeheader(); w.writerows(chunk)
        files.append(name)
    for rows in products:
        if max_rows and chunk and cur + len(rows) > max_rows:
            flush(); chunk, cur = [], 0
        chunk.extend(rows); cur += len(rows)
    flush()
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--variants', required=True); ap.add_argument('--images', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--report')
    ap.add_argument('--max-rows-per-file', type=int, default=0, help='split by whole products')
    ap.add_argument('--barcode-type', default='', help='optional prefix such as gtin, upc or ean')
    a = ap.parse_args(argv)
    t0 = time.time()
    products, errors, warnings = build(read(a.variants, VREQ), read(a.images, IREQ), a.barcode_type)
    files = [] if errors else write(products, a.out, a.max_rows_per_file)
    rep = {'ok': not errors, 'products': len(products), 'rows': sum(map(len, products)), 'files': files,
           'errors': errors[:200], 'error_count': len(errors), 'warnings': warnings[:200],
           'warning_count': len(warnings), 'seconds': round(time.time() - t0, 3)}
    if a.report:
        with open(a.report, 'w', encoding='utf-8') as f:
            json.dump(rep, f, indent=1)
    print(json.dumps({k: rep[k] for k in ('ok', 'products', 'rows', 'error_count', 'warning_count', 'seconds')}))
    return 0 if not errors else 2


if __name__ == '__main__':
    sys.exit(main())
