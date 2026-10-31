const assert = require('node:assert/strict');
const calc = require('./calc.js');

function dollars(value) {
  return calc.parseMoneyToCents(value);
}

assert.equal(dollars('0'), 0);
assert.equal(dollars('12,34'), 1234);
assert.equal(dollars('12.3'), 1230);
assert.throws(() => dollars('12.345'), /Montant invalide/);

const hundred = calc.taxesFromSubtotalCents(dollars('100.00'));
assert.deepEqual(hundred, {
  subtotalCents: 10000,
  gstCents: 500,
  qstCents: 998,
  totalCents: 11498,
});

const centRounding = calc.taxesFromSubtotalCents(dollars('0.05'));
assert.deepEqual(centRounding, {
  subtotalCents: 5,
  gstCents: 0,
  qstCents: 0,
  totalCents: 5,
});

const taxIncluded = calc.taxesFromTotalCents(dollars('114.98'));
assert.deepEqual(taxIncluded, hundred);

for (const amount of ['1.00', '19.99', '100.00', '1234.56']) {
  const fromHt = calc.taxesFromSubtotalCents(dollars(amount));
  const fromTtc = calc.taxesFromTotalCents(fromHt.totalCents);
  assert.deepEqual(fromTtc, fromHt, `HT->TTC->HT round-trip failed for ${amount}`);
}

const invoice = calc.sumLines([
  { description: 'Design', quantity: 2, unitAmount: '75.00' },
  { description: 'Revision', quantity: 1.5, unitAmount: '40.00' },
], 'ht');
assert.equal(invoice.totals.subtotalCents, 21000);
assert.equal(invoice.totals.gstCents, 1050);
assert.equal(invoice.totals.qstCents, 2095);
assert.equal(invoice.totals.totalCents, 24145);

const includedInvoice = calc.sumLines([
  { description: 'Forfait', quantity: 1, unitAmount: '114.98' },
], 'ttc');
assert.equal(includedInvoice.totals.subtotalCents, 10000);
assert.equal(includedInvoice.totals.gstCents, 500);
assert.equal(includedInvoice.totals.qstCents, 998);
assert.equal(includedInvoice.totals.totalCents, 11498);

console.log('products/calc-tps-tvq/test.js: all tests passed');
