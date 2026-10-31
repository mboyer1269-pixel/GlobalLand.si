const test = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const calc = require('./calc.js');
const invoiceDoc = require('./invoice.js');

const NBSP = '\u00a0';
const cents = (value) => calc.parseMoneyToCents(value);
const forward = (subtotalCents) => calc.taxesFromSubtotalCents(subtotalCents);
const invoice = (lines, options) => calc.calculateInvoice(lines, options);
const totals = (result) => [result.subtotalCents, result.gstCents, result.qstCents, result.totalCents];

function calculationErrors(fn) {
  try {
    fn();
  } catch (error) {
    assert.ok(error instanceof calc.CalculationError, error.message);
    return error;
  }
  return assert.fail('expected a CalculationError');
}

test('money parsing accepts fr-CA and en-CA input', () => {
  assert.equal(cents(''), 0);
  assert.equal(cents('0'), 0);
  assert.equal(cents('12,34'), 1234);
  assert.equal(cents('12.3'), 1230);
  assert.equal(cents(',50'), 50);
  assert.equal(cents('12,'), 1200);
  assert.equal(cents('100 $'), 10000);
  assert.equal(cents(`1${NBSP}234,56${NBSP}$`), 123456);
  assert.equal(cents('1\u202f234,56 $'), 123456);
  assert.equal(cents('$1,234.56'), 123456);
  assert.equal(cents('1.234,56'), 123456);
  assert.equal(cents('1,234,567'), 123456700);
  assert.equal(cents('CA$ 5'), 500);
  assert.equal(cents('5 $ CAD'), 500);
  assert.equal(cents('999 999 999,99'), calc.MAX_CENTS);
});

test('money parsing accepts negative amounts for discounts and credit notes', () => {
  assert.equal(cents('-10,00'), -1000);
  assert.equal(cents('\u221210,00 $'), -1000);
  assert.equal(cents('-$10.00'), -1000);
  assert.equal(cents('-0'), 0);
});

test('money parsing rejects ambiguous, malformed and oversized input', () => {
  const rejects = (value, pattern) => assert.throws(() => cents(value), pattern, value);
  rejects('12.345', /2 décimales au maximum/);
  rejects('1,234', /2 décimales au maximum/);
  for (const value of ['abc', '$', '-', '--5', '5-', '1,2.3', '12,34.56', '1.2.3', '0x10', '1e3', '\u0661\u0662']) {
    rejects(value, /Montant invalide/);
  }
  rejects('1 000 000 000', /trop élevé/);
  rejects('100000000000000000000', /trop élevé/);
});

test('quantities are exact decimals and accept the fr-CA comma', () => {
  const line = (quantity, unitAmount) => calc.calculateLine({ quantity, unitAmount });
  // 0,29 × 0,50 $ = 14,5 ¢: binary floating point produced 14 ¢ (Codex review finding).
  assert.equal(line('0.29', '0.50').amountCents, 15);
  assert.equal(line('0,29', '0,50').amountCents, 15);
  assert.equal(line('1,5', '40,00').amountCents, 6000);
  assert.equal(line('3', '33,33').amountCents, 9999);
  assert.equal(line('2,25', '19,99').amountCents, 4498);
  assert.equal(line(2, '75').amountCents, 15000);
  assert.equal(line('', '10').amountCents, 0);
  assert.equal(line('1,5', '10').quantityText, '1,5');
  assert.equal(line('1500', '1').quantityText, `1${NBSP}500`);
});

test('quantities reject hex, exponents, ambiguous thousands and oversized values', () => {
  for (const quantity of ['0x10', '1e3', 'abc', '1/2']) {
    const { errors } = calculationErrors(() => calc.calculateLine({ quantity, unitAmount: '1' }));
    assert.deepEqual(errors.map((error) => error.field), ['quantity'], quantity);
  }
  const ambiguous = calculationErrors(() => calc.calculateLine({ quantity: '1,500', unitAmount: '1' }));
  assert.match(ambiguous.message, /Quantité\u00a0: 2 décimales au maximum/);
  const huge = calculationErrors(() => calc.calculateLine({ quantity: '1000000000', unitAmount: '1' }));
  assert.match(huge.message, /Quantité trop élevée/);
});

test('line amounts round half away from zero and stay bounded', () => {
  const amount = (quantity, unitAmount) => calc.calculateLine({ quantity, unitAmount }).amountCents;
  assert.equal(amount('0,29', '-0,50'), -15);
  assert.equal(amount('-0,29', '0,50'), -15);
  const tooLarge = calculationErrors(() => calc.calculateLine({ quantity: '1000', unitAmount: '999 999 999,99' }));
  assert.deepEqual(tooLarge.errors.map((error) => error.field), ['line']);
});

test('subtotal taxes: TPS 5 %, TVQ 9,975 % on the price before TPS, half cent rounded up', () => {
  assert.deepEqual(forward(10000), { subtotalCents: 10000, gstCents: 500, qstCents: 998, totalCents: 11498 });
  assert.deepEqual(forward(5), { subtotalCents: 5, gstCents: 0, qstCents: 0, totalCents: 5 });
  assert.equal(forward(10).gstCents, 1);
  assert.equal(forward(2000).qstCents, 200);
  assert.deepEqual(forward(-10000), { subtotalCents: -10000, gstCents: -500, qstCents: -998, totalCents: -11498 });
  assert.equal(forward(-2000).qstCents, -200);
  assert.throws(() => forward(0.5), TypeError);
  assert.throws(() => forward(calc.MAX_CENTS + 1), TypeError);
});

test('invoice taxes are computed once on the subtotal, not summed line by line', () => {
  const tenCents = { quantity: '1', unitAmount: '0,10' };
  // Line-by-line rounding charged 3 ¢ of TPS on a 0,30 $ subtotal.
  assert.deepEqual(totals(invoice([tenCents, tenCents, tenCents])), [30, 2, 3, 35]);

  let seed = 7;
  const random = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed;
  };
  for (let i = 0; i < 2000; i += 1) {
    const lines = Array.from({ length: 1 + (random() % 6) }, () => ({
      quantity: String(1 + (random() % 5)),
      unitAmount: ((random() % 100000) / 100).toFixed(2),
    }));
    const result = invoice(lines);
    const expected = forward(result.subtotalCents);
    assert.deepEqual(totals(result), totals(expected));
  }
});

test('invoice examples: services, discount line and credit note', () => {
  const services = invoice([
    { description: 'Design', quantity: 2, unitAmount: '75.00' },
    { description: 'Révision', quantity: 1.5, unitAmount: '40.00' },
  ]);
  assert.deepEqual(totals(services), [21000, 1050, 2095, 24145]);

  const discounted = invoice([
    { description: 'Forfait', quantity: '1', unitAmount: '100' },
    { description: 'Rabais', quantity: '1', unitAmount: '-10' },
  ]);
  assert.deepEqual(totals(discounted), [9000, 450, 898, 10348]);

  assert.deepEqual(totals(invoice([{ quantity: '1', unitAmount: '-100' }])), [-10000, -500, -998, -11498]);
});

test('tax-included totals map back to the exact pre-tax amount whenever one exists', () => {
  assert.deepEqual(
    calc.taxesFromTotalCents(11498),
    { subtotalCents: 10000, gstCents: 500, qstCents: 998, totalCents: 11498, exact: true },
  );

  const reachable = new Set();
  for (let subtotal = -100000; subtotal <= 100000; subtotal += 1) {
    const expected = forward(subtotal);
    reachable.add(expected.totalCents);
    const split = calc.taxesFromTotalCents(expected.totalCents);
    if (split.subtotalCents !== subtotal || split.gstCents !== expected.gstCents
      || split.qstCents !== expected.qstCents || !split.exact) {
      assert.fail(`TTC ${expected.totalCents} did not map back to HT ${subtotal}: ${JSON.stringify(split)}`);
    }
  }

  let inexact = 0;
  const limit = forward(100000).totalCents;
  for (let total = -limit; total <= limit; total += 1) {
    const split = calc.taxesFromTotalCents(total);
    const check = forward(split.subtotalCents);
    const gstGap = Math.abs(check.gstCents - split.gstCents);
    const qstGap = Math.abs(check.qstCents - split.qstCents);
    if (split.subtotalCents + split.gstCents + split.qstCents !== total
      || split.exact !== reachable.has(total) || gstGap > 1 || qstGap > 1) {
      assert.fail(`bad tax-included split for ${total}: ${JSON.stringify(split)}`);
    }
    inexact += split.exact ? 0 : 1;
  }
  const share = inexact / (2 * limit + 1);
  assert.ok(share > 0.12 && share < 0.14, `unexpected share of inexact totals: ${share}`);
});

test('tax-included invoice: the total is decomposed once and inexact totals are flagged', () => {
  const included = invoice([{ quantity: '2', unitAmount: '57,49' }], { mode: 'ttc' });
  assert.deepEqual(totals(included), [10000, 500, 998, 11498]);
  assert.equal(included.exact, true);

  const odd = invoice([{ quantity: '1', unitAmount: '0,06' }], { mode: 'ttc' });
  assert.equal(odd.exact, false);
  assert.equal(odd.subtotalCents + odd.gstCents + odd.qstCents, 6);
});

test('unregistered supplier: no TPS or TVQ is added in either mode', () => {
  const line = [{ quantity: '1', unitAmount: '100' }];
  assert.deepEqual(totals(invoice(line, { taxable: false })), [10000, 0, 0, 10000]);
  assert.deepEqual(totals(invoice(line, { taxable: false, mode: 'ttc' })), [10000, 0, 0, 10000]);
});

test('invoice validation reports every invalid field with its line number', () => {
  const error = calculationErrors(() => invoice([
    { quantity: 'x', unitAmount: '1' },
    { quantity: '1', unitAmount: '1,234' },
    { quantity: '1', unitAmount: 'abc' },
  ]));
  assert.deepEqual(error.errors.map(({ index, field }) => [index, field]), [[0, 'quantity'], [1, 'unitAmount'], [2, 'unitAmount']]);
  assert.match(error.message, /^Ligne 1\u00a0: Quantité invalide$/);

  const overflow = calculationErrors(() => invoice([
    { quantity: '1', unitAmount: '999 999 999,99' },
    { quantity: '1', unitAmount: '1' },
  ], { mode: 'ttc' }));
  assert.deepEqual(overflow.errors.map((item) => item.field), ['total']);
  const taxedOverflow = calculationErrors(() => invoice([{ quantity: '1', unitAmount: '900 000 000' }]));
  assert.deepEqual(taxedOverflow.errors.map((item) => item.field), ['total']);
});

test('empty invoices and blank lines', () => {
  assert.deepEqual(totals(invoice([])), [0, 0, 0, 0]);
  const blank = invoice([{ description: ' ', quantity: '1', unitAmount: '' }]);
  assert.equal(blank.lines[0].blank, true);
  assert.deepEqual(totals(blank), [0, 0, 0, 0]);
  assert.equal(invoice([{ description: 'Inclus', quantity: '1', unitAmount: '' }]).lines[0].blank, false);
});

test('fr-CA currency formatting, negatives and no negative zero', () => {
  assert.equal(calc.formatMoneyFromCents(123456), `1${NBSP}234,56${NBSP}$`);
  assert.equal(calc.formatMoneyFromCents(-1000), `-10,00${NBSP}$`);
  assert.equal(calc.formatMoneyFromCents(-0), `0,00${NBSP}$`);
  assert.throws(() => calc.formatMoneyFromCents(1.5), TypeError);
});

const sampleDetails = {
  sellerName: 'Studio Exemple',
  sellerAddress: '123, rue Principale\r\nMontréal (Québec)',
  gstNumber: '123456789 RT0001',
  qstNumber: '1234567890 TQ0001',
  clientName: 'Client inc.',
  clientAddress: '',
  invoiceNumber: '2026-001',
  invoiceDate: '2026-10-31',
  notes: 'Payable dans 30 jours.',
};

function sampleResult() {
  return calc.calculateInvoice([
    { description: 'Service de consultation', quantity: '1', unitAmount: '100,00' },
    { description: '', quantity: '1', unitAmount: '' },
  ]);
}

function fakeDocument() {
  const createElement = (tagName) => ({
    tagName,
    attributes: {},
    childNodes: [],
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    appendChild(child) {
      this.childNodes.push(child);
      return child;
    },
  });
  return { createElement, createTextNode: (data) => ({ data }) };
}

function collect(node, pick, found = []) {
  const value = pick(node);
  if (value !== undefined) {
    found.push(value);
  }
  (node.childNodes || []).forEach((child) => collect(child, pick, found));
  return found;
}

test('escapeHtml neutralises markup characters', () => {
  assert.equal(
    invoiceDoc.escapeHtml(`<img src=x onerror="alert('1')">&`),
    '&lt;img src=x onerror=&quot;alert(&#39;1&#39;)&quot;&gt;&amp;',
  );
});

test('downloaded invoice escapes every user value and carries a no-script policy', () => {
  const attack = '<img src=x onerror=alert(1)><script>alert(2)</script>"\'&';
  const details = Object.fromEntries(Object.keys(sampleDetails).map((field) => [field, attack]));
  const result = calc.calculateInvoice([{ description: attack, quantity: '1', unitAmount: '1' }]);
  const html = invoiceDoc.invoiceDocument(details, result);
  assert.ok(!html.includes('<img'), 'raw <img> in output');
  assert.ok(!/<script/i.test(html), 'raw <script> in output');
  const escaped = '&lt;img src=x onerror=alert(1)&gt;&lt;script&gt;alert(2)&lt;/script&gt;&quot;&#39;&amp;';
  assert.ok(html.split(escaped).length - 1 >= Object.keys(details).length, 'every field is escaped');
  assert.ok(html.startsWith('<!doctype html>\n<html lang="fr-CA">'));
  assert.ok(html.includes(
    '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;">',
  ));
});

test('renderers refuse code-like tag names, event handlers and style breakouts', () => {
  assert.throws(() => invoiceDoc.renderHtml(['img onerror=alert(1)', {}]), /refusé/);
  assert.throws(() => invoiceDoc.renderHtml(['p', { onclick: 'x' }]), /refusé/);
  assert.throws(() => invoiceDoc.renderHtml(['style', {}, 'a{}</style><script>']), /CSS refusé/);
  assert.throws(() => invoiceDoc.renderDom(['p', { onmouseover: 'x' }], fakeDocument()), /refusé/);
});

test('on-page preview is built from text nodes, never from parsed markup', () => {
  const attack = '<img src=x onerror=alert(1)>';
  const result = calc.calculateInvoice([{ description: attack, quantity: '1', unitAmount: '5' }]);
  const tree = invoiceDoc.invoiceTree({ sellerName: attack, clientName: 'Client' }, result, { headingLevel: 3 });
  const root = invoiceDoc.renderDom(tree, fakeDocument());
  const tags = collect(root, (node) => node.tagName);
  assert.equal(root.tagName, 'article');
  assert.ok(!tags.includes('img'));
  assert.ok(tags.includes('h3') && tags.includes('h4') && !tags.includes('h1'));
  assert.equal(collect(root, (node) => node.data).filter((text) => text === attack).length, 2);
});

test('invoice document shows seller, registration numbers, client, lines and totals', () => {
  const html = invoiceDoc.invoiceDocument(sampleDetails, sampleResult());
  const expected = [
    'Studio Exemple', `N° TPS${NBSP}: 123456789 RT0001`, `N° TVQ${NBSP}: 1234567890 TQ0001`, 'Client inc.',
    `N°${NBSP}: 2026-001`, `Date${NBSP}: 31 octobre 2026`, 'Service de consultation', 'Sous-total',
    `TPS (5${NBSP}%)`, `TVQ (9,975${NBSP}%)`, `114,98${NBSP}$`, 'Payable dans 30 jours.',
    '<title>Facture – 2026-001 – Studio Exemple</title>',
  ];
  expected.forEach((text) => assert.ok(html.includes(text), text));
  const linesTable = html.slice(html.indexOf('<table class="invoice-lines">'), html.indexOf('<table class="invoice-totals">'));
  assert.equal(linesTable.split('<tr>').length - 1, 2, 'header row plus the single non-blank line');
  assert.ok(!html.includes('Aucune ligne'));
});

test('tax-included, unregistered and credit-note invoices are labelled accordingly', () => {
  const included = calc.calculateInvoice([{ description: 'Forfait', quantity: '1', unitAmount: '114,98' }], { mode: 'ttc' });
  const includedHtml = invoiceDoc.invoiceDocument({}, included);
  assert.ok(includedHtml.includes('Prix unitaire (taxes incluses)'));
  assert.ok(includedHtml.includes('Les prix indiqués incluent la TPS et la TVQ.'));

  const untaxed = calc.calculateInvoice([{ quantity: '1', unitAmount: '100' }], { taxable: false });
  const untaxedText = invoiceDoc.invoiceText({}, untaxed);
  assert.ok(!/TPS|TVQ|Sous-total/.test(invoiceDoc.invoiceDocument({}, untaxed)));
  assert.ok(untaxedText.endsWith(`Total${NBSP}: 100,00${NBSP}$`));

  const credit = calc.calculateInvoice([{ quantity: '1', unitAmount: '-50' }]);
  assert.ok(invoiceDoc.invoiceDocument({}, credit).includes('Note de crédit'));
  assert.equal(invoiceDoc.invoiceFileName({ invoiceNumber: '7' }, credit), 'note-de-credit-7.html');
  assert.ok(invoiceDoc.invoiceDocument({}, calc.calculateInvoice([])).includes('Aucune ligne'));
});

test('copied text summary uses French typography and skips blank lines', () => {
  assert.equal(invoiceDoc.invoiceText(sampleDetails, sampleResult()), [
    `Facture n°${NBSP}2026-001 — 31 octobre 2026`,
    '',
    `De${NBSP}:`, 'Studio Exemple', '123, rue Principale', 'Montréal (Québec)',
    `N° TPS${NBSP}: 123456789 RT0001`, `N° TVQ${NBSP}: 1234567890 TQ0001`,
    '',
    `Facturé à${NBSP}:`, 'Client inc.',
    '',
    `1. Service de consultation — 1 × 100,00${NBSP}$ = 100,00${NBSP}$`,
    '',
    `Sous-total${NBSP}: 100,00${NBSP}$`, `TPS (5${NBSP}%)${NBSP}: 5,00${NBSP}$`,
    `TVQ (9,975${NBSP}%)${NBSP}: 9,98${NBSP}$`, `Total${NBSP}: 114,98${NBSP}$`,
    '',
    `Notes${NBSP}:`, 'Payable dans 30 jours.',
  ].join('\n'));
});

test('invoice dates are calendar dates whatever the time zone', () => {
  assert.equal(invoiceDoc.formatInvoiceDate('2026-10-31'), '31 octobre 2026');
  assert.equal(invoiceDoc.formatInvoiceDate('2026-02-30'), '2026-02-30');
  assert.equal(invoiceDoc.formatInvoiceDate('31/10/2026'), '31/10/2026');
  const script = "process.stdout.write(require('./invoice.js').formatInvoiceDate('2026-10-31'))";
  for (const zone of ['America/Vancouver', 'America/Toronto', 'Pacific/Kiritimati']) {
    const output = execFileSync(process.execPath, ['-e', script], { cwd: __dirname, env: { ...process.env, TZ: zone } });
    assert.equal(output.toString(), '31 octobre 2026', zone);
  }
});

test('download file names are safe and descriptive', () => {
  const result = sampleResult();
  assert.equal(invoiceDoc.invoiceFileName({ invoiceNumber: 'Facture 2026/001 é<x>' }, result), 'facture-Facture-2026-001-e-x.html');
  assert.equal(invoiceDoc.invoiceFileName({ invoiceNumber: '../../etc/passwd' }, result), 'facture-etc-passwd.html');
  assert.equal(invoiceDoc.invoiceFileName({ invoiceDate: '2026-10-31' }, result), 'facture-2026-10-31.html');
  assert.equal(invoiceDoc.invoiceFileName({}, result), 'facture.html');
});
