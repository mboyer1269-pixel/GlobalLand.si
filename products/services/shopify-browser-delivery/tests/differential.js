// Differential test: JS port (src/core.js) vs reference transform.py on identical inputs. Node + python3, offline.
const fs = require('fs'), os = require('os'), path = require('path'), cp = require('child_process');
const D = process.argv[2], PY = process.argv[3], FX = process.argv[4];
const core = require(path.resolve(D, 'src/core.js'));
const V = fs.readFileSync(FX + '/before-variants.csv', 'utf8'), I = fs.readFileSync(FX + '/before-images.csv', 'utf8');
const H = 'style_id,title,vendor,product_type,tags,color,size,sku,barcode,price\n', IH = 'style_id,color,position,url\n';
function big(n) { let v = H, im = IH, k = 0; for (let s = 0; k < n; s++) { for (const c of ['Black','Brown','Navy']) { for (let z = 36; z < 46 && k < n; z++, k++) v += `S${s},Style ${s},V,T,t,${c},${z},S${s}-${c}-${z},${4000000000000 + k},19.99\n`; for (let p = 1; p <= 5; p++) im += `S${s},${c},${p},https://cdn.example.com/s${s}/${c}-${p}.jpg\n`; } } return [v, im]; }
const cases = [
 ['fixture', V, I, {}],
 ['crlf_bom', '﻿' + V.replace(/\n/g, '\r\n'), I.replace(/\n/g, '\r\n'), {}],
 ['quoted_fields', H + 'Q1,"Shoe, ""Deluxe""","V, Inc",T,"a,b",Red,40,Q1-R,111,9.5\nQ1,"Shoe, ""Deluxe""","V, Inc",T,"a,b",Red,41,Q1-R2,"11;2:3",9.5\n', IH + 'Q1,red,1,https://x.example/a.jpg\n', {}],
 ['blank_lines_whitespace', H + '\n S1 ,Tee, V ,T,t, Red ,S, A1 ,1, 5 \n\n', IH + '\n', {}],
 ['bad_price', V.replace('120.00', '120,00').replace('45.00', '$45'), I, {}],
 ['dup_sku_barcode', V + 'BL-7,Leather Belt,Example Vendor,Belts,leather,Tan,110,BL7-TAN-90,2000000001005,45.00\n', I, {}],
 ['dup_combo_case', V + 'BL-7,Leather Belt,Example Vendor,Belts,leather,TAN,90,X1,999,45.00\n', I, {}],
 ['two_titles', V + 'BL-7,Belt 2,Example Vendor,Belts,leather,Tan,110,X2,998,45.00\n', I, {}],
 ['empty_fields', V + 'BL-7,,Example Vendor,Belts,leather,Tan,,X3,997,45.00\n', I + 'BL-7,Tan,,https://a.example/x.jpg\n', {}],
 ['bad_position_url', V, I + 'BL-7,Tan,x,https://a.example/x.jpg\nBL-7,Tan,3,ftp://a.example/y.jpg\n', {}],
 ['orphan_and_missing_images', V + 'BL-7,Leather Belt,Example Vendor,Belts,leather,Black,90,X4,996,45.00\n', I + 'ZZ-1,Red,1,https://a.example/z.jpg\n', {}],
 ['same_image_twice', V, I + 'BL-7,Tan,3,https://cdn.example.com/bl-7/tan-1.jpg\n', {}],
 ['handle_collision', H + 'A-1,Tee,V,T,t,Red,S,K1,1,5\nA 1,Tee,V,T,t,Red,S,K2,2,5\n', IH, {}],
 ['position_ties', V, I.replace('black-2.jpg', 'black-0.jpg').replace('Black,2,', 'Black,1,'), {}],
 ['barcode_type', V, I, { barcodeType: 'gtin' }],
 ['split_max1_noext', H + 'P1,One,V,T,t,Red,S,P1-R,1,5\nP2,Two,V,T,t,Red,S,P2-R,2,5\nP3,Three,V,T,t,Red,S,P3-R,3,5\n', IH, { maxRows: 1, out: 'output' }],
 ['split_max1_upper', H + 'P1,One,V,T,t,Red,S,P1-R,1,5\nP2,Two,V,T,t,Red,S,P2-R,2,5\nP3,Three,V,T,t,Red,S,P3-R,3,5\n', IH, { maxRows: 1, out: 'output.CSV' }],
 ['split_fixture_11', V, I, { maxRows: 11, out: 'out.csv' }],
 ['missing_column', V.replace('barcode', 'ean'), I, {}],
 ['scale_9000', ...big(9000), { maxRows: 5000, out: 'big.csv' }],
];
const results = []; let pass = 0;
for (const [name, v, im, o] of cases) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'd-')); fs.writeFileSync(tmp + '/v.csv', v); fs.writeFileSync(tmp + '/i.csv', im);
  const out = o.out || 'shopify-products.csv';
  const args = [PY, '--variants', 'v.csv', '--images', 'i.csv', '--out', out, '--report', 'rep.json'];
  if (o.maxRows) args.push('--max-rows-per-file', String(o.maxRows)); if (o.barcodeType) args.push('--barcode-type', o.barcodeType);
  const p = cp.spawnSync('python3', args, { cwd: tmp, encoding: 'utf8' });
  let py; try { py = JSON.parse(fs.readFileSync(tmp + '/rep.json', 'utf8')); } catch (e) { py = { fatal: (p.stderr || '').trim().split('\n').pop() }; }
  let js, t0 = Date.now(); try { js = core.run(v, im, { out, maxRows: o.maxRows || 0, barcodeType: o.barcodeType || '' }); } catch (e) { js = { fatal: e.message }; }
  const ms = Date.now() - t0; const d = [];
  if (py.fatal || js.fatal) { if (!(py.fatal && js.fatal)) d.push('fatal mismatch py=' + py.fatal + ' js=' + js.fatal); }
  else {
    for (const k of ['ok', 'products', 'rows', 'error_count', 'warning_count']) if (py[k] !== js[k]) d.push(k + ' py=' + py[k] + ' js=' + js[k]);
    if (JSON.stringify(py.errors) !== JSON.stringify(js.errors)) d.push('errors differ');
    if (JSON.stringify(py.warnings) !== JSON.stringify(js.warnings)) d.push('warnings differ');
    if (JSON.stringify(py.files) !== JSON.stringify(js.files.map(f => f.name))) d.push('file names differ py=' + JSON.stringify(py.files) + ' js=' + JSON.stringify(js.files.map(f => f.name)));
    else js.files.forEach(f => { if (fs.readFileSync(path.join(tmp, f.name), 'utf8') !== f.text) d.push('bytes differ ' + f.name); });
  }
  if (!d.length) pass++;
  results.push({ case: name, pass: !d.length, py_exit: p.status, ok: js.ok, rows: js.rows, error_count: js.error_count, warning_count: js.warning_count, files: js.files ? js.files.map(f => f.name) : null, fatal: js.fatal || null, js_ms: ms, diffs: d });
}
const summary = { test: 'differential JS core vs transform.py', runtime: 'node ' + process.version + ' (V8) + python3; NOT a browser', passed: pass, total: cases.length, results };
fs.writeFileSync(path.join(D, 'differential-results.json'), JSON.stringify(summary, null, 1));
console.log(JSON.stringify({ passed: pass, total: cases.length, failing: results.filter(r => !r.pass) }));
process.exit(pass === cases.length ? 0 : 1);
