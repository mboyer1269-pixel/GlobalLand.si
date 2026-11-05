import csv, json, os, subprocess, sys, time, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from verify import verify
B = os.path.dirname(HERE); T = os.path.join(B, 'transform.py')
FX = os.path.join(B, 'fixtures'); W = '/tmp/slc'
os.makedirs(FX, exist_ok=True); os.makedirs(W, exist_ok=True)
VH = ['style_id', 'title', 'vendor', 'product_type', 'tags', 'color', 'size', 'sku', 'barcode', 'price']
IH = ['style_id', 'color', 'position', 'url']


def ean(n):  # synthetic EAN-13 in the 200-299 restricted-circulation prefix (not real GTINs)
    s = '200' + str(n).zfill(9)
    c = (10 - sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(s)) % 10) % 10
    return s + str(c)


def wcsv(p, hdr, rows):
    with open(p, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n'); w.writerow(hdr); w.writerows(rows)


def gen(styles, colors, sizes, nimg):
    v, im, k = [], [], 0
    for s in range(styles):
        sid = 'ST%04d' % s
        for c in colors:
            for z in sizes:
                k += 1
                v.append([sid, 'Synthetic Shoe %d' % s, 'Example Vendor', 'Shoes', 'synthetic', c, z, '%s-%s-%s' % (sid, c[:3].upper(), z), ean(k), '89.00'])
            for p in range(1, nimg + 1):
                im.append([sid, c, str(p), 'https://cdn.example.com/%s/%s-%d.jpg' % (sid, c.lower(), p)])
    return v, im


def run(vp, ip, out, extra=()):
    t0 = time.time()
    r = subprocess.run([sys.executable, '-I', T, '--variants', vp, '--images', ip, '--out', out, '--report', out + '.report.json'] + list(extra), capture_output=True, text=True)
    rep = json.load(open(out + '.report.json')); os.remove(out + '.report.json')
    return r.returncode, rep, round(time.time() - t0, 3)


res = {'synthetic': True, 'note': 'Synthetic data only. Checks documented CSV layout rules; a live Shopify import was NOT tested.', 'cases': []}
v = [['SH-100', 'Oxford Leather Shoe', 'Example Vendor', 'Shoes', 'leather', c, z, 'SH100-%s-%s' % (c[:3].upper(), z), ean(i), '120.00']
     for i, (c, z) in enumerate([(c, z) for c in ('Black', 'Brown') for z in ('40', '41', '42')], 1)]
v += [['BL-7', 'Leather Belt', 'Example Vendor', 'Belts', 'leather', 'Tan', z, 'BL7-TAN-%s' % z, ean(100 + i), '45.00'] for i, z in enumerate(('90', '100'))]
im = [['SH-100', c, str(p), 'https://cdn.example.com/sh-100/%s-%d.jpg' % (c.lower(), p)] for c in ('Brown', 'Black') for p in (5, 4, 3, 2, 1)]
im += [['BL-7', 'Tan', str(p), 'https://cdn.example.com/bl-7/tan-%d.jpg' % p] for p in (1, 2)]
wcsv(os.path.join(FX, 'before-variants.csv'), VH, v); wcsv(os.path.join(FX, 'before-images.csv'), IH, im)
out = os.path.join(FX, 'after-shopify.csv')
rc, rep, sec = run(os.path.join(FX, 'before-variants.csv'), os.path.join(FX, 'before-images.csv'), out)
chk, nrows, nprod = verify([out], v, im)
res['cases'].append({'case': 'small_readable_fixture', 'rc': rc, 'rows': nrows, 'products': nprod, 'checks': chk, 'pass': rc == 0 and all(chk.values()) and nrows == 12 and nprod == 2})
ve = [list(x) for x in v]; ve[1][7] = ve[0][7]; ve[2][8] = ve[0][8]; ve[3][9] = 'EUR 12'
ime = [x for x in im if x[1] != 'Tan']
wcsv(W + '/ev.csv', VH, ve); wcsv(W + '/ei.csv', IH, ime)
rc, rep, sec = run(W + '/ev.csv', W + '/ei.csv', W + '/e.csv')
res['cases'].append({'case': 'error_fixture_dup_sku_dup_barcode_bad_price_missing_color_image', 'rc': rc, 'errors': rep['errors'], 'warnings': rep['warnings'],
                     'no_output_written': not os.path.exists(W + '/e.csv'),
                     'pass': rc == 2 and all(any(e in m for m in rep['errors']) for e in ('duplicate SKU', 'duplicate barcode', 'price')) and any('Tan' in w for w in rep['warnings']) and not os.path.exists(W + '/e.csv')})
v, im = gen(300, ['Black', 'Brown', 'Tan', 'Navy', 'Red'], ['39', '40', '41', '42', '43', '44'], 5)
wcsv(W + '/v.csv', VH, v); wcsv(W + '/i.csv', IH, im)
rc, rep, sec = run(W + '/v.csv', W + '/i.csv', W + '/out.csv')
chk, nrows, nprod = verify([W + '/out.csv'], v, im)
res['cases'].append({'case': 'scale_9000_barcodes_300_styles_5_colors_6_sizes_5_images_per_color', 'input_variants': len(v), 'input_images': len(im), 'rc': rc,
                     'rows': nrows, 'products': nprod, 'output_bytes': os.path.getsize(W + '/out.csv'),
                     'output_sha256': hashlib.sha256(open(W + '/out.csv', 'rb').read()).hexdigest(), 'transform_seconds': rep['seconds'],
                     'wall_seconds_incl_startup': sec, 'checks': chk, 'pass': rc == 0 and all(chk.values()) and nrows == 9000 and nprod == 300})
rc, rep, sec = run(W + '/v.csv', W + '/i.csv', W + '/sp.csv', ['--max-rows-per-file', '4000', '--barcode-type', 'gtin'])
chk, nrows, nprod = verify(rep['files'], v, im)
pref = all(r['Barcodes'].startswith('gtin:') for f in rep['files'] for r in csv.DictReader(open(f, newline='', encoding='utf-8')) if r['SKU'])
res['cases'].append({'case': 'split_max_4000_rows_whole_products_gtin_prefix', 'rc': rc, 'files': len(rep['files']), 'rows': nrows, 'checks': chk,
                     'gtin_prefix_on_all_variants': pref, 'pass': rc == 0 and all(chk.values()) and len(rep['files']) == 3 and pref})
res['passed'] = sum(c['pass'] for c in res['cases']); res['total'] = len(res['cases']); res['python'] = sys.version.split()[0]
json.dump(res, open(os.path.join(B, 'core-test-results.json'), 'w'), indent=1)
print(json.dumps({'passed': res['passed'], 'total': res['total']}))
for c in res['cases']:
    print(c['case'], c['pass'], {k: x for k, x in c.items() if k not in ('case', 'pass', 'checks')}, [k for k, x in c.get('checks', {}).items() if not x])
