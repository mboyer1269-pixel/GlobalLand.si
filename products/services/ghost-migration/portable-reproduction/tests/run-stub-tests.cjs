'use strict';
// Control-flow tests of harness.cjs using STUB converters.
// STUB_ONLY: none of these runs executes @tryghost/kg-html-to-lexical or a Ghost import.
const {spawnSync} = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');
const root = path.join(__dirname, '..');
const H = path.join(root, 'harness.cjs');
function run(extra) {
  const r = spawnSync(process.execPath, [H, ...extra], {encoding: 'utf8', cwd: root});
  let j = null; try { j = JSON.parse(r.stdout); } catch (e) {}
  return {code: r.status, j, stdout: r.stdout};
}
const st = n => ['--module', path.join(__dirname, 'stubs', n)];
const byId = (j, id) => j.cases.find(c => c.id === id);
const tests = [
  ['default resolution without installed package exits 2 DEPENDENCY_ABSENT', () => { const r = run([]); return r.code === 2 && r.j.status === 'DEPENDENCY_ABSENT' && r.j.execution_kind === 'INSTALLED_PACKAGE' && r.j.error_code === 'MODULE_NOT_FOUND'; }],
  ['missing override module exits 2', () => { const r = run(st('does-not-exist.cjs')); return r.code === 2 && r.j.status === 'DEPENDENCY_ABSENT'; }],
  ['preserving stub: all cases and pair PASS, exit 0, labelled OVERRIDE_MODULE', () => { const r = run(st('stub-preserving.cjs')); return r.code === 0 && r.j.status === 'ALL_PASSED' && r.j.execution_kind === 'OVERRIDE_MODULE' && r.j.cases.length === 8 && r.j.cases.every(c => c.status === 'PASS') && r.j.pairs.every(p => p.status === 'PASS'); }],
  ['preserving stub: whitespace bytes observed, raw_text_equal false but normalized equal', () => { const r = run(st('stub-preserving.cjs')); const c = byId(r.j, 'q3-ws-before'); const p = r.j.pairs[0]; return JSON.stringify(c.texts) === JSON.stringify(['  a', 'b \n']) && p.raw_text_equal_observation === false && p.normalized_text_equal === true; }],
  ['preserving stub: nested cases keep all tokens in order', () => { const r = run(st('stub-preserving.cjs')); return byId(r.j, 'q4-nested-a').missing_tokens.length === 0 && byId(r.j, 'q4-nested-b').missing_tokens.length === 0; }],
  ['lossy stub: q1-before FAIL with a,b missing; q2-after PASS; exit 1', () => { const r = run(st('stub-lossy.cjs')); const q1 = byId(r.j, 'q1-before'); return r.code === 1 && r.j.status === 'ASSERTIONS_FAILED' && q1.status === 'FAIL' && JSON.stringify(q1.missing_tokens) === '["a","b"]' && q1.quote_linebreaks === 1 && byId(r.j, 'q2-after').status === 'PASS'; }],
  ['lossy stub: Q3 pair FAIL, nested FAIL, controls PASS', () => { const r = run(st('stub-lossy.cjs')); return r.j.pairs[0].status === 'FAIL' && byId(r.j, 'q4-nested-a').status === 'FAIL' && byId(r.j, 'control-plain-quote').status === 'PASS' && byId(r.j, 'control-paragraph-br').status === 'PASS'; }],
  ['throwing stub: every case and pair ERROR, exit 1', () => { const r = run(st('stub-throws.cjs')); return r.code === 1 && r.j.cases.every(c => c.status === 'ERROR') && r.j.pairs.every(p => p.status === 'ERROR') && r.j.summary.error === 9; }],
  ['module without htmlToLexical exits 3 API_MISMATCH', () => { const r = run(st('stub-noexport.cjs')); return r.code === 3 && r.j.status === 'API_MISMATCH' && JSON.stringify(r.j.exports) === '["somethingElse"]'; }],
  ['string-returning stub is parsed, exit 0', () => { const r = run(st('stub-string.cjs')); return r.code === 0 && r.j.status === 'ALL_PASSED'; }],
  ['unreadable fixtures exit 4 FIXTURE_ERROR', () => { const r = run(['--fixtures', path.join(root, 'nope.json')]); return r.code === 4 && r.j.status === 'FIXTURE_ERROR'; }],
  ['--out file equals stdout', () => { const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'repro-')), 'r.json'); const r = run([...st('stub-preserving.cjs'), '--out', f]); return fs.readFileSync(f, 'utf8') === r.stdout; }]
];
const results = [];
for (const [name, fn] of tests) { let ok = false, err = null; try { ok = !!fn(); } catch (e) { err = String(e.message); } results.push({name, ok, err}); }
const out = {label: 'STUB_ONLY: harness control-flow tests with stub converters; no upstream @tryghost/kg-html-to-lexical execution and no Ghost import occurred', made_by: 'autonomous AI agents (GlobalLand)', node: process.version, passed: results.filter(r => r.ok).length, total: results.length, results};
const dest = process.argv[2] || path.join(root, 'stub-test-results.json');
fs.writeFileSync(dest, JSON.stringify(out, null, 1) + '\n');
console.log(JSON.stringify(out, null, 1));
process.exitCode = out.passed === out.total ? 0 : 1;
