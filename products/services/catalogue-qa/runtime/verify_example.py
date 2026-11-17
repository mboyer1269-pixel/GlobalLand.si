"""Minimal runnable example for verify.py. Made by autonomous AI agents (GlobalLand).
Usage: python3 verify_example.py VARIANTS.csv IMAGES.csv OUTPUT.csv [OUTPUT2.csv ...]
Inputs are read by header name (style_id,title,vendor,product_type,tags,color,size,sku,barcode,price and style_id,color,position,url).
Prints every check as JSON. Exit 0 = all checks passed, 1 = a check failed, 2 = bad usage.
It only re-reads files; it does not prove that Shopify will accept the import."""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify import verify
VC = ['style_id', 'title', 'vendor', 'product_type', 'tags', 'color', 'size', 'sku', 'barcode', 'price']
IC = ['style_id', 'color', 'position', 'url']


def rows(path, cols):
    with open(path, newline='', encoding='utf-8') as f:
        return [[r.get(c) or '' for c in cols] for r in csv.DictReader(f)]


if len(sys.argv) < 4:
    print(__doc__)
    sys.exit(2)
chk, nrows, nprod = verify(sys.argv[3:], rows(sys.argv[1], VC), rows(sys.argv[2], IC))
print(json.dumps({'rows': nrows, 'products': nprod, 'checks': chk, 'failed': [k for k, v in chk.items() if not v]}, indent=1))
sys.exit(0 if all(chk.values()) else 1)
