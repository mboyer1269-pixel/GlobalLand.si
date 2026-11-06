// Usage: node run_dom_checks.js <delivery dir> <fixtures dir>. NOT a real browser.
const fs = require('fs'), path = require('path');
const S = require('./dom_stub_smoke.js');
const { scenario, html, scripts, V, I, A, D } = S;
const checks = [];
const c = (name, ok, detail) => checks.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
(async () => {
  let r = await scenario(V, I, {});
  c('fixture_download_byte_identical', r.links.length === 1 && r.links[0].text === A && r.links[0].name === 'shopify-products.csv', r.links.map(l => l.name));
  c('no_network_calls', r.net.length === 0, r.net);
  r = await scenario(V.replace('120.00', '120,00'), I, {});
  c('bad_price_no_download', r.links.length === 0 && /price/.test(r.report) && r.notes.length === 1, r.report.slice(0, 160));
  r = await scenario(V, I, { max: 11, out: 'out' });
  c('split_two_distinct_files', r.links.length === 2 && r.links[0].name === 'out-part1.csv' && r.links[1].name === 'out-part2.csv' && (r.links[0].text + r.links[1].text.split('\n').slice(1).join('\n')) === A, r.links.map(l => l.name));
  r = await scenario(null, I, {});
  c('missing_file_message', /Choose both CSV files/.test(r.report) && r.links.length === 0, r.report);
  r = await scenario(V.replace('barcode', 'ean'), I, {});
  c('missing_column_message', /missing columns/.test(r.report) && r.links.length === 0, r.report);
  c('static_no_network_apis', !/\bfetch\(|XMLHttpRequest|WebSocket|sendBeacon|import\(|<script src|<link /.test(html));
  c('csp_connect_none', /connect-src 'none'/.test(html) && /default-src 'none'/.test(html));
  c('ai_disclosure_en_fr', /autonomous AI agents/.test(html) && /agents d'IA autonomes/.test(html));
  c('limits_present', ['historical', 'not</strong> been tested', 'overwritten', 'Status and Published', 'one image per variant'].every(s => html.includes(s)));
  c('inline_core_matches_src', scripts[0].includes(fs.readFileSync(path.join(D, 'src/core.js'), 'utf8')));
})().catch(e => c('harness_exception', false, String(e.stack))).finally(() => {
  const passed = checks.filter(x => x.ok).length;
  fs.writeFileSync(path.join(D, 'dom-stub-results.json'), JSON.stringify({ test: 'index.html inline scripts under Node vm DOM stub', runtime: 'node ' + process.version + '; NOT a real browser', passed, total: checks.length, checks }, null, 1));
  console.log(JSON.stringify({ passed, total: checks.length, failing: checks.filter(x => !x.ok) }));
});
