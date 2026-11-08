#!/usr/bin/env node
'use strict';
// Portable reproduction harness for Ghost forum report t/60053 (blockquote + <br>).
// Built by autonomous AI agents (GlobalLand). Its authors have NOT run it against the upstream package.
const fs = require('fs');
const path = require('path');
const PKG = '@tryghost/kg-html-to-lexical';
const PINNED = '1.4.4';
function args(argv) {
  const o = {module: null, fixtures: path.join(__dirname, 'fixtures.json'), out: null};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--module') o.module = argv[++i];
    else if (argv[i] === '--fixtures') o.fixtures = argv[++i];
    else if (argv[i] === '--out') o.out = argv[++i];
  }
  return o;
}
function emit(o, report, code) {
  report.exit_code = code;
  const s = JSON.stringify(report, null, 1);
  if (o.out) fs.writeFileSync(o.out, s + '\n');
  process.stdout.write(s + '\n');
  process.exitCode = code;
}
function findPkgVersion(entry) {
  let d = path.dirname(entry);
  for (let i = 0; i < 6; i++) {
    const p = path.join(d, 'package.json');
    if (fs.existsSync(p)) {
      try { const j = JSON.parse(fs.readFileSync(p, 'utf8')); if (j.name === PKG) return j.version; } catch (e) {}
    }
    d = path.dirname(d);
  }
  return null;
}
function walk(n, acc, inQuote) {
  if (!n || typeof n !== 'object') return;
  const t = String(n.type || '');
  const isQ = /quote/i.test(t);
  if (isQ) acc.quote_types.push(t);
  const q = inQuote || isQ;
  if (t === 'linebreak') { acc.linebreaks++; if (q) acc.quote_linebreaks++; }
  if (typeof n.text === 'string') { acc.texts.push(n.text); if (q) acc.quote_texts.push(n.text); }
  if (Array.isArray(n.children)) for (const c of n.children) walk(c, acc, q);
}
function missingInOrder(hay, tokens) {
  let pos = 0; const missing = [];
  for (const t of tokens) { const i = hay.indexOf(t, pos); if (i < 0) missing.push(t); else pos = i + t.length; }
  return missing;
}
const norm = a => a.map(s => s.replace(/\s+/g, ' ').trim()).filter(Boolean);
function main() {
  const o = args(process.argv.slice(2));
  const report = {tool: 'ghost-blockquote-br-repro harness', made_by: 'autonomous AI agents (GlobalLand)', node: process.version, package: PKG, pinned_version: PINNED};
  let fixtures;
  try { fixtures = JSON.parse(fs.readFileSync(o.fixtures, 'utf8')); }
  catch (e) { report.status = 'FIXTURE_ERROR'; report.error = String(e.message); return emit(o, report, 4); }
  let mod, entry;
  try {
    if (o.module) { report.execution_kind = 'OVERRIDE_MODULE'; entry = path.resolve(o.module); report.module_path = entry; }
    else { report.execution_kind = 'INSTALLED_PACKAGE'; entry = require.resolve(PKG); report.installed_version = findPkgVersion(entry); }
    mod = require(entry);
  } catch (e) {
    report.status = 'DEPENDENCY_ABSENT'; report.error_code = e.code || null; report.error = String(e.message).split('\n')[0];
    report.hint = 'Run npm install in this directory with Node ^22.22.2 || ^24.15.0.';
    return emit(o, report, 2);
  }
  if (report.execution_kind === 'INSTALLED_PACKAGE' && report.installed_version !== PINNED) report.version_warning = 'installed ' + report.installed_version + ' differs from pinned ' + PINNED;
  let fn = null;
  if (mod && typeof mod.htmlToLexical === 'function') fn = mod.htmlToLexical;
  else if (mod && mod.default && typeof mod.default.htmlToLexical === 'function') fn = mod.default.htmlToLexical;
  if (!fn) { report.status = 'API_MISMATCH'; report.exports = mod ? Object.keys(mod) : []; return emit(o, report, 3); }
  const results = {};
  for (const c of fixtures.cases) {
    const r = {id: c.id, question: c.question, html: c.html};
    try {
      let out = fn(c.html);
      if (typeof out === 'string') out = JSON.parse(out);
      const acc = {texts: [], quote_texts: [], quote_types: [], linebreaks: 0, quote_linebreaks: 0};
      walk(out && out.root ? out.root : out, acc, false);
      Object.assign(r, acc);
      const checks = {};
      r.missing_tokens = missingInOrder(acc.texts.join(''), c.tokens || []);
      checks.text_tokens_in_order = r.missing_tokens.length === 0;
      if (c.quote_tokens) { r.missing_quote_tokens = missingInOrder(acc.quote_texts.join(''), c.quote_tokens); checks.quote_tokens_in_order = r.missing_quote_tokens.length === 0; }
      if (typeof c.min_quote_nodes === 'number') checks.min_quote_nodes = acc.quote_types.length >= c.min_quote_nodes;
      if (typeof c.quote_linebreaks === 'number') checks.quote_linebreaks = acc.quote_linebreaks === c.quote_linebreaks;
      r.checks = checks;
      r.status = Object.values(checks).every(Boolean) ? 'PASS' : 'FAIL';
      r.lexical = out;
    } catch (e) { r.status = 'ERROR'; r.error = String((e && e.message) || e).split('\n')[0]; }
    results[c.id] = r;
  }
  const pairs = [];
  for (const p of fixtures.pairs || []) {
    const a = results[p.a], b = results[p.b];
    const pr = {a: p.a, b: p.b, question: p.question};
    if (!a || !b || a.status === 'ERROR' || b.status === 'ERROR') pr.status = 'ERROR';
    else {
      pr.normalized_text_equal = JSON.stringify(norm(a.texts)) === JSON.stringify(norm(b.texts));
      pr.linebreaks_equal = a.linebreaks === b.linebreaks;
      pr.raw_text_equal_observation = JSON.stringify(a.texts) === JSON.stringify(b.texts);
      pr.status = pr.normalized_text_equal && pr.linebreaks_equal ? 'PASS' : 'FAIL';
    }
    pairs.push(pr);
  }
  report.cases = Object.values(results);
  report.pairs = pairs;
  const all = report.cases.map(x => x.status).concat(pairs.map(x => x.status));
  report.summary = {pass: all.filter(s => s === 'PASS').length, fail: all.filter(s => s === 'FAIL').length, error: all.filter(s => s === 'ERROR').length};
  report.scope_note = 'Converter-level observation only; this is not a real Ghost universal import (Q5).';
  const bad = report.summary.fail || report.summary.error;
  report.status = bad ? 'ASSERTIONS_FAILED' : 'ALL_PASSED';
  return emit(o, report, bad ? 1 : 0);
}
main();
