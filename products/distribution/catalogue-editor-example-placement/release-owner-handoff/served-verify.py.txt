"""Independent verifier for transform.py output (re-reads written CSV files)."""
import csv
EXP = ['Title', 'URL handle', 'Vendor', 'Type', 'Tags', 'SKU', 'Barcodes', 'Option1 name', 'Option1 value', 'Option2 name', 'Option2 value', 'Price', 'Product image URL', 'Image position', 'Image alt text', 'Variant image URL']


def unesc(b):
    out, i = '', 0
    while i < len(b):
        if b[i] == '\\' and i + 1 < len(b):
            out += b[i + 1]; i += 2
        else:
            out += b[i]; i += 1
    return out


def strip_type(b):
    for p in ('gtin:', 'upc:', 'ean:'):
        if b.startswith(p):
            return b[len(p):]
    return b


def verify(files, v, im):
    """v rows: style_id,title,vendor,type,tags,color,size,sku,barcode,price; im rows: style_id,color,position,url"""
    chk = {}
    raw = b''.join(open(f, 'rb').read() for f in files)
    chk['utf8_no_bom_lf_only'] = (not raw.startswith(b'\xef\xbb\xbf')) and b'\r' not in raw and bool(raw.decode('utf-8'))
    rows, fileof, hdr_ok, split_ok = [], {}, True, True
    for f in files:
        with open(f, newline='', encoding='utf-8') as fh:
            r = csv.DictReader(fh)
            hdr_ok = hdr_ok and r.fieldnames == EXP
            for row in r:
                h = row['URL handle']
                if h in fileof and fileof[h] != f:
                    split_ok = False
                fileof[h] = f
                rows.append(row)
    chk['header_matches_documented_names'] = hdr_ok
    chk['no_product_split_across_files'] = split_ok
    contiguous, title_first, prev, seen, groups = True, True, None, set(), {}
    for row in rows:
        h = row['URL handle']
        if h != prev:
            if h in seen:
                contiguous = False
            seen.add(h)
            title_first = title_first and bool(row['Title'])
        elif row['Title']:
            title_first = False
        prev = h
        groups.setdefault(h, []).append(row)
    chk['handle_rows_contiguous'] = contiguous
    chk['title_only_on_first_row'] = title_first
    var = [r for r in rows if r['SKU']]
    skus = [r['SKU'] for r in var]
    chk['sku_unique'] = len(skus) == len(set(skus))
    inmap = {x[7]: (x[8], x[5], x[6], x[9]) for x in v}
    outmap = {r['SKU']: (unesc(strip_type(r['Barcodes'])), r['Option1 value'], r['Option2 value'], r['Price']) for r in var}
    chk['identifiers_preserved_sku_barcode_color_size_price'] = inmap == outmap and len(var) == len(v)
    want, sid_of = {}, {x[7]: x[0] for x in v}
    for x in im:
        want.setdefault(x[0], []).append(x)
    ok = dict.fromkeys(['color_size_combo_unique_per_product', 'image_positions_1_to_n', 'all_input_images_present_once_per_product',
                        'variant_image_is_first_image_of_its_color', 'image_only_rows_have_no_variant_fields'], True)
    for h, g in groups.items():
        cmb = [(r['Option1 value'], r['Option2 value']) for r in g if r['SKU']]
        ok['color_size_combo_unique_per_product'] &= len(cmb) == len(set(cmb))
        pos = [int(r['Image position']) for r in g if r['Product image URL']]
        ok['image_positions_1_to_n'] &= pos == list(range(1, len(pos) + 1))
        sid = sid_of[next(r['SKU'] for r in g if r['SKU'])]
        urls = [r['Product image URL'] for r in g if r['Product image URL']]
        ok['all_input_images_present_once_per_product'] &= sorted(urls) == sorted(x[3] for x in want.get(sid, []))
        firsts = {}
        for x in sorted(want.get(sid, []), key=lambda x: int(x[2]), reverse=True):
            firsts[x[1]] = x[3]
        for r in g:
            if r['SKU']:
                ok['variant_image_is_first_image_of_its_color'] &= r['Variant image URL'] == firsts.get(r['Option1 value'], '') and (r['Variant image URL'] in urls or not r['Variant image URL'])
            else:
                ok['image_only_rows_have_no_variant_fields'] &= not any(r[c] for c in ('Option1 value', 'Option2 value', 'Price', 'Barcodes', 'Variant image URL', 'Title'))
    chk.update(ok)
    return chk, len(rows), len(groups)
