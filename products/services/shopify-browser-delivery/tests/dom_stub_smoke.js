// Runs the actual inline scripts of index.html in Node's vm with a minimal DOM/FileReader/Blob stub.
// This is NOT browser execution: real rendering, file picker and download behaviour remain untested.
const fs = require('fs'), vm = require('vm'), path = require('path');
const D = process.argv[2], FX = process.argv[3];
const html = fs.readFileSync(path.join(D, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const V = fs.readFileSync(FX + '/before-variants.csv', 'utf8'), I = fs.readFileSync(FX + '/before-images.csv', 'utf8'), A = fs.readFileSync(FX + '/after-shopify.csv', 'utf8');
function el(id) { return { id, value: '', files: null, textContent: '', children: [], listeners: {}, get firstChild() { return this.children[0] || null; }, removeChild(c) { this.children.splice(this.children.indexOf(c), 1); }, appendChild(c) { this.children.push(c); }, addEventListener(t, f) { this.listeners[t] = f; } }; }
async function scenario(v, im, opts) {
  const ids = {}; ['v', 'i', 'o', 'm', 'b', 'go', 'rep', 'dl'].forEach(k => ids[k] = el(k));
  ids.o.value = opts.out || 'shopify-products.csv'; ids.m.value = String(opts.max || 0); ids.b.value = '';
  ids.v.files = v === null ? [] : [{ name: 'v.csv', text: v }]; ids.i.files = [{ name: 'i.csv', text: im }];
  const blobs = new Map(); let n = 0; const net = [];
  const sandbox = { document: { getElementById: k => ids[k], createElement: t => ({ tag: t, children: [], appendChild(c) { this.children.push(c); } }) },
    FileReader: function () { this.readAsText = f => setTimeout(() => { this.result = f.text; this.onload(); }, 0); },
    Blob: function (parts, o) { this.text = parts.join(''); this.type = o.type; },
    URL: { createObjectURL: b => { const u = 'blob:' + (++n); blobs.set(u, b); return u; } },
    fetch: () => net.push('fetch'), XMLHttpRequest: function () { net.push('xhr'); }, Promise, setTimeout };
  sandbox.window = sandbox; vm.createContext(sandbox);
  scripts.forEach(s => vm.runInContext(s, sandbox));
  ids.go.listeners.click(); await new Promise(r => setTimeout(r, 100));
  const links = ids.dl.children.flatMap(p => p.children || []).filter(c => c.tag === 'a');
  return { report: ids.rep.textContent, links: links.map(a => ({ name: a.download, text: blobs.get(a.href).text })), notes: ids.dl.children.filter(p => !(p.children && p.children.length)).map(p => p.textContent), net };
}
module.exports = { scenario, html, scripts, V, I, A, D };
