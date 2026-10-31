(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.TpsTvqCalculator = factory();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const TAX_DENOMINATOR = 100000;
  const GST_NUMERATOR = 5000;
  const QST_NUMERATOR = 9975;
  const TOTAL_NUMERATOR = TAX_DENOMINATOR + GST_NUMERATOR + QST_NUMERATOR;

  function roundDivide(numerator, denominator) {
    return Math.round(numerator / denominator);
  }

  function assertCents(value, name) {
    if (!Number.isInteger(value) || value < 0) {
      throw new TypeError(`${name} must be a non-negative integer cent amount`);
    }
  }

  function parseMoneyToCents(value) {
    const normalized = String(value || '')
      .trim()
      .replace(/\s/g, '')
      .replace(',', '.');

    if (!normalized) {
      return 0;
    }

    if (!/^\d+(?:\.\d{0,2})?$/.test(normalized)) {
      throw new Error('Montant invalide');
    }

    const [dollars, cents = ''] = normalized.split('.');
    return Number(dollars) * 100 + Number(cents.padEnd(2, '0'));
  }

  function formatMoneyFromCents(cents, locale) {
    assertCents(cents, 'cents');
    return new Intl.NumberFormat(locale || 'fr-CA', {
      style: 'currency',
      currency: 'CAD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(cents / 100);
  }

  function taxesFromSubtotalCents(subtotalCents) {
    assertCents(subtotalCents, 'subtotalCents');
    const gstCents = roundDivide(subtotalCents * GST_NUMERATOR, TAX_DENOMINATOR);
    const qstCents = roundDivide(subtotalCents * QST_NUMERATOR, TAX_DENOMINATOR);
    return {
      subtotalCents,
      gstCents,
      qstCents,
      totalCents: subtotalCents + gstCents + qstCents,
    };
  }

  function taxesFromTotalCents(totalCents) {
    assertCents(totalCents, 'totalCents');
    const gstCents = roundDivide(totalCents * GST_NUMERATOR, TOTAL_NUMERATOR);
    const qstCents = roundDivide(totalCents * QST_NUMERATOR, TOTAL_NUMERATOR);
    const subtotalCents = totalCents - gstCents - qstCents;
    return {
      subtotalCents,
      gstCents,
      qstCents,
      totalCents,
    };
  }

  function calculateLine(line, inputMode) {
    const quantity = Number(line.quantity || 0);
    if (!Number.isFinite(quantity) || quantity < 0) {
      throw new Error('Quantite invalide');
    }

    const unitCents = typeof line.unitCents === 'number'
      ? line.unitCents
      : parseMoneyToCents(line.unitAmount || '0');
    assertCents(unitCents, 'unitCents');

    const enteredCents = Math.round(unitCents * quantity);
    const amounts = inputMode === 'ttc'
      ? taxesFromTotalCents(enteredCents)
      : taxesFromSubtotalCents(enteredCents);

    return {
      description: line.description || '',
      quantity,
      unitCents,
      enteredCents,
      inputMode: inputMode === 'ttc' ? 'ttc' : 'ht',
      ...amounts,
    };
  }

  function sumLines(lines, inputMode) {
    const calculatedLines = lines.map((line) => calculateLine(line, inputMode));
    const totals = calculatedLines.reduce((acc, line) => {
      acc.subtotalCents += line.subtotalCents;
      acc.gstCents += line.gstCents;
      acc.qstCents += line.qstCents;
      acc.totalCents += line.totalCents;
      return acc;
    }, { subtotalCents: 0, gstCents: 0, qstCents: 0, totalCents: 0 });

    return { lines: calculatedLines, totals };
  }

  return {
    GST_RATE: GST_NUMERATOR / TAX_DENOMINATOR,
    QST_RATE: QST_NUMERATOR / TAX_DENOMINATOR,
    TOTAL_RATE: TOTAL_NUMERATOR / TAX_DENOMINATOR,
    parseMoneyToCents,
    formatMoneyFromCents,
    taxesFromSubtotalCents,
    taxesFromTotalCents,
    calculateLine,
    sumLines,
  };
});
