(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.TpsTvqCalculator = factory();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // Rates are fractions of 100 000 so that every step stays in exact integer arithmetic.
  const RATE_DENOMINATOR = 100000n;
  const GST_NUMERATOR = 5000n;
  const QST_NUMERATOR = 9975n;
  const TAX_INCLUDED_DENOMINATOR = RATE_DENOMINATOR + GST_NUMERATOR + QST_NUMERATOR;
  // Bounds every amount so that results convert back to Number exactly.
  const MAX_CENTS = 99999999999;
  const MAX_SCALED = BigInt(MAX_CENTS);
  const DECIMALS = 2;
  const SCALE = 100n;
  const NBSP = '\u00a0';
  const CURRENCY_PREFIX = /^(?:CA\$|\$CA|CAD|\$)/i;
  const CURRENCY_SUFFIX = /(?:\$CAD|CAD|CA\$|\$CA|\$)$/i;
  const MAX_TEXT = `999${NBSP}999${NBSP}999,99`;

  const MONEY_MESSAGES = {
    invalid: 'Montant invalide',
    decimals: `Montant${NBSP}: ${DECIMALS} décimales au maximum`,
    tooLarge: `Montant trop élevé (maximum ${MAX_TEXT}${NBSP}$)`,
  };
  const UNIT_MESSAGES = {
    invalid: 'Prix unitaire invalide',
    decimals: `Prix unitaire${NBSP}: ${DECIMALS} décimales au maximum`,
    tooLarge: `Prix unitaire trop élevé (maximum ${MAX_TEXT}${NBSP}$)`,
  };
  const QUANTITY_MESSAGES = {
    invalid: 'Quantité invalide',
    decimals: `Quantité${NBSP}: ${DECIMALS} décimales au maximum`,
    tooLarge: `Quantité trop élevée (maximum ${MAX_TEXT})`,
  };
  const LINE_TOO_LARGE = `Montant de la ligne trop élevé (maximum ${MAX_TEXT}${NBSP}$)`;
  const TOTAL_TOO_LARGE = `Total de la facture trop élevé (maximum ${MAX_TEXT}${NBSP}$)`;

  class CalculationError extends Error {
    constructor(message, errors) {
      super(message);
      this.name = 'CalculationError';
      this.errors = errors;
    }
  }

  function abs(value) {
    return value < 0n ? -value : value;
  }

  // Rounds half away from zero, so a credit note mirrors its invoice to the cent.
  function divideRounded(numerator, denominator) {
    const rounded = (2n * abs(numerator) + denominator) / (2n * denominator);
    return numerator < 0n ? -rounded : rounded;
  }

  function validGroups(groups) {
    return groups.length > 1
      && /^\d{1,3}$/.test(groups[0])
      && groups.slice(1).every((group) => /^\d{3}$/.test(group));
  }

  // A single "," or "." is the decimal separator (fr-CA or en-CA). Thousands separators are only
  // accepted when unambiguous: spaces, both "," and "." together, or a repeated separator.
  function splitDecimal(text) {
    if (!/^[\d.,]+$/.test(text) || !/\d/.test(text)) {
      return null;
    }

    const lastComma = text.lastIndexOf(',');
    const lastDot = text.lastIndexOf('.');
    if (lastComma >= 0 && lastDot >= 0) {
      const decimal = lastComma > lastDot ? ',' : '.';
      const group = decimal === ',' ? '.' : ',';
      const at = text.lastIndexOf(decimal);
      const groups = text.slice(0, at).split(group);
      const fraction = text.slice(at + 1);
      return validGroups(groups) && /^\d*$/.test(fraction) ? [groups.join(''), fraction] : null;
    }

    const separator = lastComma >= 0 ? ',' : (lastDot >= 0 ? '.' : null);
    if (!separator) {
      return [text, ''];
    }
    const pieces = text.split(separator);
    if (pieces.length === 2) {
      return pieces;
    }
    return validGroups(pieces) ? [pieces.join(''), ''] : null;
  }

  // Returns the value scaled by 100 as a BigInt, or null when the field is empty.
  function parseScaled(value, messages, allowCurrency) {
    let text = String(value ?? '').replace(/\s+/g, '').replace(/\u2212/g, '-');
    if (!text) {
      return null;
    }

    let negative = false;
    if (text[0] === '-' || text[0] === '+') {
      negative = text[0] === '-';
      text = text.slice(1);
    }
    if (allowCurrency) {
      text = text.replace(CURRENCY_PREFIX, '').replace(CURRENCY_SUFFIX, '');
    }

    const parts = splitDecimal(text);
    if (!parts) {
      throw new Error(messages.invalid);
    }
    const [integer, fraction] = parts;
    if (fraction.length > DECIMALS) {
      throw new Error(messages.decimals);
    }

    const scaled = BigInt(integer || '0') * SCALE + BigInt(fraction.padEnd(DECIMALS, '0'));
    if (scaled > MAX_SCALED) {
      throw new Error(messages.tooLarge);
    }
    return negative ? -scaled : scaled;
  }

  function assertCents(value, name) {
    if (!Number.isSafeInteger(value) || Math.abs(value) > MAX_CENTS) {
      throw new TypeError(`${name} must be an integer cent amount of at most ${MAX_CENTS} in magnitude`);
    }
  }

  function parseMoneyToCents(value) {
    try {
      return Number(parseScaled(value, MONEY_MESSAGES, true) ?? 0n);
    } catch (error) {
      throw new CalculationError(error.message, [{ field: 'amount', message: error.message }]);
    }
  }

  function formatMoneyFromCents(cents, locale) {
    if (!Number.isSafeInteger(cents)) {
      throw new TypeError('cents must be a safe integer');
    }
    return new Intl.NumberFormat(locale || 'fr-CA', {
      style: 'currency',
      currency: 'CAD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format((cents === 0 ? 0 : cents) / 100);
  }

  function formatQuantity(hundredths) {
    return new Intl.NumberFormat('fr-CA', { maximumFractionDigits: DECIMALS })
      .format(Number(hundredths) / 100);
  }

  function splitFromSubtotal(subtotal) {
    const gst = divideRounded(subtotal * GST_NUMERATOR, RATE_DENOMINATOR);
    const qst = divideRounded(subtotal * QST_NUMERATOR, RATE_DENOMINATOR);
    return { subtotal, gst, qst, total: subtotal + gst + qst };
  }

  // Tax-fraction method: each tax is extracted from the tax-included total, so the parts always
  // add back to it. Whenever a pre-tax amount produces this total exactly, this returns that amount
  // (checked exhaustively in test.js). Otherwise, for about 13 % of totals, a tax may differ by
  // 0,01 $ from the rate applied to the subtotal, and `exact` is false.
  function splitTaxIncluded(total) {
    const gst = divideRounded(total * GST_NUMERATOR, TAX_INCLUDED_DENOMINATOR);
    const qst = divideRounded(total * QST_NUMERATOR, TAX_INCLUDED_DENOMINATOR);
    const subtotal = total - gst - qst;
    const check = splitFromSubtotal(subtotal);
    return { subtotal, gst, qst, total, exact: check.gst === gst && check.qst === qst };
  }

  function toCents(split) {
    return {
      subtotalCents: Number(split.subtotal),
      gstCents: Number(split.gst),
      qstCents: Number(split.qst),
      totalCents: Number(split.total),
    };
  }

  function taxesFromSubtotalCents(subtotalCents) {
    assertCents(subtotalCents, 'subtotalCents');
    return toCents(splitFromSubtotal(BigInt(subtotalCents)));
  }

  function taxesFromTotalCents(totalCents) {
    assertCents(totalCents, 'totalCents');
    const split = splitTaxIncluded(BigInt(totalCents));
    return { ...toCents(split), exact: split.exact };
  }

  function calculateLine(line) {
    const source = line || {};
    const errors = [];
    const read = (field, value, messages, allowCurrency) => {
      try {
        return parseScaled(value, messages, allowCurrency);
      } catch (error) {
        errors.push({ field, message: error.message });
        return null;
      }
    };

    const quantity = read('quantity', source.quantity, QUANTITY_MESSAGES, false) ?? 0n;
    const unit = read('unitAmount', source.unitAmount, UNIT_MESSAGES, true);
    if (errors.length) {
      throw new CalculationError(errors[0].message, errors);
    }

    const unitCents = unit ?? 0n;
    const amount = divideRounded(quantity * unitCents, SCALE);
    if (abs(amount) > MAX_SCALED) {
      throw new CalculationError(LINE_TOO_LARGE, [{ field: 'line', message: LINE_TOO_LARGE }]);
    }

    const description = String(source.description ?? '').trim();
    return {
      description,
      blank: !description && unit === null,
      quantityHundredths: Number(quantity),
      quantityText: formatQuantity(quantity),
      unitCents: Number(unitCents),
      amountCents: Number(amount),
    };
  }

  // Taxes are computed once on the invoice subtotal (or extracted once from the tax-included
  // total), so the printed TPS and TVQ always match the rate applied to the printed subtotal.
  function calculateInvoice(lines, options) {
    const settings = options || {};
    const mode = settings.mode === 'ttc' ? 'ttc' : 'ht';
    const taxable = settings.taxable !== false;
    const errors = [];
    const calculated = (lines || []).map((line, index) => {
      try {
        return calculateLine(line);
      } catch (error) {
        if (!(error instanceof CalculationError)) {
          throw error;
        }
        error.errors.forEach((item) => errors.push({ index, ...item }));
        return null;
      }
    });
    if (errors.length) {
      throw new CalculationError(`Ligne ${errors[0].index + 1}${NBSP}: ${errors[0].message}`, errors);
    }

    const sum = calculated.reduce((total, line) => total + BigInt(line.amountCents), 0n);
    let split;
    if (!taxable) {
      split = { subtotal: sum, gst: 0n, qst: 0n, total: sum, exact: true };
    } else if (mode === 'ttc') {
      split = splitTaxIncluded(sum);
    } else {
      split = { ...splitFromSubtotal(sum), exact: true };
    }
    if (abs(split.total) > MAX_SCALED || abs(split.subtotal) > MAX_SCALED) {
      throw new CalculationError(TOTAL_TOO_LARGE, [{ index: null, field: 'total', message: TOTAL_TOO_LARGE }]);
    }

    return { mode, taxable, lines: calculated, ...toCents(split), exact: split.exact };
  }

  return {
    GST_RATE: Number(GST_NUMERATOR) / Number(RATE_DENOMINATOR),
    QST_RATE: Number(QST_NUMERATOR) / Number(RATE_DENOMINATOR),
    MAX_CENTS,
    CalculationError,
    parseMoneyToCents,
    formatMoneyFromCents,
    taxesFromSubtotalCents,
    taxesFromTotalCents,
    calculateLine,
    calculateInvoice,
  };
});
