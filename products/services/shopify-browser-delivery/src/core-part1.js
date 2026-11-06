/* Browser/Node port of products/services/shopify-large-catalogue/transform.py (same rules, no new features).
   Built and maintained by autonomous AI agents (GlobalLand). Offline; no network calls; untested in a live Shopify import. */
(function (root) {
'use strict';
var COLS = ['Title', 'URL handle', 'Vendor', 'Type', 'Tags', 'SKU', 'Barcodes',
  'Option1 name', 'Option1 value', 'Option2 name', 'Option2 value', 'Price',
  'Product image URL', 'Image position', 'Image alt text', 'Variant image URL'];
var VREQ = ['style_id', 'title', 'color', 'size', 'sku', 'barcode', 'price'];
var IREQ = ['style_id', 'color', 'position', 'url'];
var PRICE = /^[0-9]+(\.[0-9]{1,2})?$/;
function repr(s) { return "'" + s + "'"; }
function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'x'; }
function escBarcode(b) { return b.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/:/g, '\\:'); }
/* RFC4180-style reader close to Python csv default dialect; skips empty lines like csv.DictReader. */
function parseCsv(text) {
  if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
  var rows = [], row = [], f = '', i = 0, n = text.length, q = false, started = false;
  while (i < n) {
    var c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { f += '"'; i += 2; continue; } q = false; i++; continue; }
      f += c; i++; continue;
    }
    if (c === '"' && f === '' && !started) { q = true; started = true; i++; continue; }
    if (c === ',') { row.push(f); f = ''; started = false; i++; continue; }
    if (c === '\r' || c === '\n') {
      row.push(f); f = ''; started = false;
      if (!(row.length === 1 && row[0] === '')) rows.push(row);
      row = []; i += (c === '\r' && text[i + 1] === '\n') ? 2 : 1; continue;
    }
    f += c; started = true; i++;
  }
  if (q) throw new Error('unexpected end of data inside a quoted field');
  if (f !== '' || row.length) { row.push(f); if (!(row.length === 1 && row[0] === '')) rows.push(row); }
  return rows;
}
function readTable(name, text, req) {
  var rows = parseCsv(text);
  var head = rows.length ? rows[0] : [];
  var miss = req.filter(function (c) { return head.indexOf(c) < 0; });
  if (miss.length) throw new Error(name + ': missing columns ' + JSON.stringify(miss));
  return rows.slice(1).map(function (r) {
    var o = {};
    head.forEach(function (h, j) { if (h) o[h] = ((j < r.length ? r[j] : '') || '').trim(); });
    return o;
  });
}
function build(vrows, irows, barcodeType) {
  barcodeType = barcodeType || '';
  var errors = [], warnings = [], styles = new Map(), skuLine = new Map(), bcLine = new Map(), combos = new Set();
  vrows.forEach(function (r, k) {
    var n = k + 2;
    var empty = VREQ.filter(function (c) { return !r[c]; });
    if (empty.length) { errors.push('variants line ' + n + ': empty ' + empty.join(',')); return; }
    if (skuLine.has(r.sku)) errors.push('variants line ' + n + ': duplicate SKU ' + r.sku + ' (first line ' + skuLine.get(r.sku) + ')');
    if (!skuLine.has(r.sku)) skuLine.set(r.sku, n);
    if (bcLine.has(r.barcode)) errors.push('variants line ' + n + ': duplicate barcode ' + r.barcode + ' (first line ' + bcLine.get(r.barcode) + ')');
    if (!bcLine.has(r.barcode)) bcLine.set(r.barcode, n);
    if (!PRICE.test(r.price)) errors.push('variants line ' + n + ': price ' + repr(r.price) + ' is not a plain number like 9.99');
    var key = JSON.stringify([r.style_id, r.color.toLowerCase(), r.size.toLowerCase()]);
    if (combos.has(key)) { errors.push('variants line ' + n + ': style ' + r.style_id + ' already has color ' + r.color + ' size ' + r.size); return; }
    combos.add(key);
    if (!styles.has(r.style_id)) styles.set(r.style_id, { title: r.title, vendor: r.vendor || '', type: r.product_type || '', tags: r.tags || '', colors: new Map() });
    var st = styles.get(r.style_id);
    if (st.title !== r.title) errors.push('variants line ' + n + ': style ' + r.style_id + ' has two titles ' + repr(st.title) + ' / ' + repr(r.title));
    if (!st.colors.has(r.color)) st.colors.set(r.color, []);
    st.colors.get(r.color).push(r);
  });
  var imgs = new Map();
  irows.forEach(function (r, k) {
    var n = k + 2;
    if (!IREQ.every(function (c) { return r[c]; })) { errors.push('images line ' + n + ': empty field'); return; }
    if (!/^[0-9]+$/.test(r.position)) { errors.push('images line ' + n + ': position ' + repr(r.position) + ' is not an integer'); return; }
    if (!/^https?:\/\//i.test(r.url)) errors.push('images line ' + n + ': url must be a public http(s) URL');
    var key = JSON.stringify([r.style_id, r.color.toLowerCase()]);
    if (!imgs.has(key)) imgs.set(key, []);
    imgs.get(key).push([parseInt(r.position, 10), r.url]);
  });
