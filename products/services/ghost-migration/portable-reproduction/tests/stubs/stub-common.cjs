'use strict';
// STUB converter for harness control-flow tests ONLY. It is not Ghost and not @tryghost/kg-html-to-lexical.
function seg(html) { return html.replace(/<(?!br\s*\/?>)[^>]*>/gi, '').split(/<br\s*\/?>/i); }
function build(html, lossy) {
  const kids = [];
  seg(html).forEach((p, i) => { if (i > 0) kids.push({type: 'linebreak', version: 1}); if (p.length) kids.push({type: 'extended-text', text: p, version: 1}); });
  const isQuote = /<blockquote/i.test(html);
  let children = kids;
  if (isQuote && lossy && /<br/i.test(html) && !/<p[\s>]/i.test(html)) children = kids.filter(k => k.type === 'linebreak');
  return {root: {type: 'root', children: [{type: isQuote ? 'extended-quote' : 'paragraph', children}]}};
}
module.exports = {build};
