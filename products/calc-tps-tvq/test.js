const test = require('node:test');
const assert = require('node:assert/strict');
const calc = require('./calc.js');

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
