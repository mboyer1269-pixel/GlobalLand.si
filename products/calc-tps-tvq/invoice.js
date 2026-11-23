(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./calc.js'));
  } else {
    root.TpsTvqInvoice = factory(root.TpsTvqCalculator);
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function (calc) {
  'use strict';

  const NBSP = '\u00a0';
  const GST_LABEL = `TPS (5${NBSP}%)`;
  const QST_LABEL = `TVQ (9,975${NBSP}%)`;
  const DETAIL_FIELDS = [
    'sellerName', 'sellerAddress', 'gstNumber', 'qstNumber',
    'clientName', 'clientAddress', 'invoiceNumber', 'invoiceDate', 'notes',
  ];
  const TAG = /^[a-z][a-z0-9]*$/;
  const ATTRIBUTE = /^(?!on)[a-z][a-z0-9-]*$/;
  const VOID_TAGS = new Set(['br', 'input', 'meta']);
  const HTML_ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  // The downloaded file contains no script; this policy also blocks any that escaping missed.
  const DOCUMENT_POLICY = "default-src 'none'; style-src 'unsafe-inline'";

  const INVOICE_CSS = `
.invoice { color: #172033; background: #fff; font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; max-width: 820px; margin: 0 auto; padding: 32px; border: 1px solid #d8dee9; border-radius: 12px; }
.invoice p { margin: 0 0 4px; }
.invoice-top { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
.invoice-meta { margin-left: auto; text-align: right; }
.invoice-title { margin: 0 0 8px; font-size: 1.8rem; line-height: 1.1; text-transform: uppercase; letter-spacing: 0.03em; }
.invoice-subtitle { margin: 0 0 4px; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: #5f6b7a; }
.invoice-name { font-weight: 700; }
.invoice-multiline { white-space: pre-line; }
.invoice-client { margin-bottom: 24px; }
.invoice table { width: 100%; border-collapse: collapse; }
.invoice-lines th, .invoice-lines td { padding: 8px 6px; border-bottom: 1px solid #d8dee9; text-align: left; vertical-align: top; }
.invoice-lines th { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: #5f6b7a; }
.invoice-lines td:first-child { overflow-wrap: anywhere; }
.invoice .num { text-align: right; font-variant-numeric: tabular-nums; }
.invoice td.num { white-space: nowrap; }
.invoice-empty { color: #5f6b7a; text-align: center; }
.invoice .invoice-totals { width: auto; min-width: 280px; margin: 16px 0 0 auto; }
.invoice-totals th, .invoice-totals td { padding: 6px; font-weight: 400; text-align: left; }
.invoice-totals td { text-align: right; }
.invoice-grand-total th, .invoice-grand-total td { border-top: 2px solid #172033; font-weight: 800; font-size: 1.1rem; }
.invoice-note { margin-top: 16px; color: #5f6b7a; }
.invoice-notes { margin-top: 24px; }
@media (max-width: 560px) {
  .invoice { padding: 18px; }
  .invoice-meta { margin-left: 0; text-align: left; }
  .invoice .invoice-totals { min-width: 0; width: 100%; }
}
@media print {
  .invoice { max-width: none; padding: 0; border: 0; border-radius: 0; }
  .invoice-lines tr { break-inside: avoid; }
}
`;

  const DOCUMENT_CSS = `
@page { margin: 15mm; }
body { margin: 0; padding: 24px 12px; background: #f5f7fb; }
@media print { body { padding: 0; background: #fff; } }
`;

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => HTML_ESCAPES[char]);
  }

  function isSkipped(node) {
    return node === null || node === undefined || node === false || node === '';
  }

  function checkName(pattern, name) {
    if (!pattern.test(name)) {
      throw new Error(`Nom HTML refusé${NBSP}: ${name}`);
    }
  }

  function attributeEntries(attributes) {
    return Object.entries(attributes || {}).filter(([name, value]) => {
      checkName(ATTRIBUTE, name);
      return value !== null && value !== undefined && value !== false;
    });
  }

  // Trees are [tag, attributes, ...children]. A string child is always text, never markup.
  function renderHtml(node) {
    if (isSkipped(node)) {
      return '';
    }
    if (!Array.isArray(node)) {
      return escapeHtml(node);
    }
    const [tag, attributes, ...children] = node;
    checkName(TAG, tag);
    const attributeText = attributeEntries(attributes)
      .map(([name, value]) => (value === true ? ` ${name}` : ` ${name}="${escapeHtml(value)}"`))
      .join('');
    const open = `<${tag}${attributeText}>`;
    if (VOID_TAGS.has(tag)) {
      return open;
    }
    if (tag === 'style') {
      const css = children.join('');
      if (css.includes('</')) {
        throw new Error('CSS refusé');
      }
      return `${open}${css}</style>`;
    }
    return `${open}${children.map(renderHtml).join('')}</${tag}>`;
  }

  function renderDom(node, doc) {
    if (isSkipped(node)) {
      return null;
    }
    if (!Array.isArray(node)) {
      return doc.createTextNode(String(node));
    }
    const [tag, attributes, ...children] = node;
    checkName(TAG, tag);
    const element = doc.createElement(tag);
    attributeEntries(attributes).forEach(([name, value]) => {
      element.setAttribute(name, value === true ? '' : String(value));
    });
    children.forEach((child) => {
      const rendered = renderDom(child, doc);
      if (rendered) {
        element.appendChild(rendered);
      }
    });
    return element;
  }

  function normalizeDetails(details) {
    const source = details || {};
    const normalized = {};
    DETAIL_FIELDS.forEach((field) => {
      normalized[field] = String(source[field] ?? '').replace(/\r\n?/g, '\n').trim();
    });
    return normalized;
  }

  // Parses YYYY-MM-DD as a calendar date: new Date('2026-10-31') is UTC midnight and shows the
  // previous day west of Greenwich.
  function formatInvoiceDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) {
      return value;
    }
    const [year, month, day] = match.slice(1).map(Number);
    const date = new Date(Date.UTC(year, month - 1, day));
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
      return value;
    }
    return new Intl.DateTimeFormat('fr-CA', { dateStyle: 'long', timeZone: 'UTC' }).format(date);
  }

  function documentTitle(result) {
    return result.totalCents < 0 ? 'Note de crédit' : 'Facture';
  }

  function money(cents) {
    return calc.formatMoneyFromCents(cents);
  }

  function totalRows(result) {
    if (!result.taxable) {
      return [['Total', result.totalCents]];
    }
    return [
      ['Sous-total', result.subtotalCents],
      [GST_LABEL, result.gstCents],
      [QST_LABEL, result.qstCents],
      ['Total', result.totalCents],
    ];
  }

  function taxIncluded(result) {
    return result.taxable && result.mode === 'ttc';
  }

  function printedLines(result) {
    return result.lines.filter((line) => !line.blank);
  }

  function invoiceTree(details, result, options) {
    const info = normalizeDetails(details);
    const level = Math.min(Math.max((options && options.headingLevel) || 1, 1), 5);
    const heading = `h${level}`;
    const subheading = `h${level + 1}`;
    const included = taxIncluded(result);
    const lines = printedLines(result);
    const date = info.invoiceDate && formatInvoiceDate(info.invoiceDate);
    const rows = totalRows(result);

    const lineRows = lines.length
      ? lines.map((line) => ['tr', {},
        ['td', {}, line.description || '—'],
        ['td', { class: 'num' }, line.quantityText],
        ['td', { class: 'num' }, money(line.unitCents)],
        ['td', { class: 'num' }, money(line.amountCents)]])
      : [['tr', {}, ['td', { class: 'invoice-empty', colspan: '4' }, 'Aucune ligne']]];

    return ['article', { class: 'invoice' },
      ['div', { class: 'invoice-top' },
        ['div', { class: 'invoice-party' },
          info.sellerName && ['p', { class: 'invoice-name' }, info.sellerName],
          info.sellerAddress && ['p', { class: 'invoice-multiline' }, info.sellerAddress],
          info.gstNumber && ['p', {}, `N° TPS${NBSP}: ${info.gstNumber}`],
          info.qstNumber && ['p', {}, `N° TVQ${NBSP}: ${info.qstNumber}`]],
        ['div', { class: 'invoice-meta' },
          [heading, { class: 'invoice-title' }, documentTitle(result)],
          info.invoiceNumber && ['p', {}, `N°${NBSP}: ${info.invoiceNumber}`],
          date && ['p', {}, `Date${NBSP}: ${date}`]]],
      (info.clientName || info.clientAddress) && ['section', { class: 'invoice-client' },
        [subheading, { class: 'invoice-subtitle' }, 'Facturé à'],
        info.clientName && ['p', { class: 'invoice-name' }, info.clientName],
        info.clientAddress && ['p', { class: 'invoice-multiline' }, info.clientAddress]],
      ['table', { class: 'invoice-lines' },
        ['thead', {}, ['tr', {},
          ['th', { scope: 'col' }, 'Description'],
          ['th', { scope: 'col', class: 'num' }, 'Qté'],
          ['th', { scope: 'col', class: 'num' }, included ? 'Prix unitaire (taxes incluses)' : 'Prix unitaire'],
          ['th', { scope: 'col', class: 'num' }, included ? 'Montant (taxes incluses)' : 'Montant']]],
        ['tbody', {}, ...lineRows]],
      ['table', { class: 'invoice-totals' },
        ['tbody', {}, ...rows.map(([label, cents], index) => ['tr',
          index === rows.length - 1 ? { class: 'invoice-grand-total' } : {},
          ['th', { scope: 'row' }, label],
          ['td', { class: 'num' }, money(cents)]])]],
      included && ['p', { class: 'invoice-note' }, 'Les prix indiqués incluent la TPS et la TVQ.'],
      info.notes && ['section', { class: 'invoice-notes' },
        [subheading, { class: 'invoice-subtitle' }, 'Notes'],
        ['p', { class: 'invoice-multiline' }, info.notes]]];
  }

  function invoiceDocument(details, result) {
    const info = normalizeDetails(details);
    const title = [documentTitle(result), info.invoiceNumber, info.sellerName].filter(Boolean).join(' – ');
    const tree = ['html', { lang: 'fr-CA' },
      ['head', {},
        ['meta', { charset: 'utf-8' }],
        ['meta', { 'http-equiv': 'Content-Security-Policy', content: DOCUMENT_POLICY }],
        ['meta', { name: 'viewport', content: 'width=device-width, initial-scale=1' }],
        ['title', {}, title],
        ['style', {}, DOCUMENT_CSS + INVOICE_CSS]],
      ['body', {}, invoiceTree(info, result, { headingLevel: 1 })]];
    return `<!doctype html>\n${renderHtml(tree)}\n`;
  }

  function invoiceText(details, result) {
    const info = normalizeDetails(details);
    const date = info.invoiceDate && formatInvoiceDate(info.invoiceDate);
    const number = info.invoiceNumber ? ` n°${NBSP}${info.invoiceNumber}` : '';
    const blocks = [[[`${documentTitle(result)}${number}`, date].filter(Boolean).join(' — ')]];

    const seller = [
      info.sellerName,
      info.sellerAddress,
      info.gstNumber && `N° TPS${NBSP}: ${info.gstNumber}`,
      info.qstNumber && `N° TVQ${NBSP}: ${info.qstNumber}`,
    ].filter(Boolean);
    if (seller.length) {
      blocks.push([`De${NBSP}:`, ...seller]);
    }
    const client = [info.clientName, info.clientAddress].filter(Boolean);
    if (client.length) {
      blocks.push([`Facturé à${NBSP}:`, ...client]);
    }

    const lines = printedLines(result);
    blocks.push(lines.length
      ? lines.map((line, index) => `${index + 1}. ${line.description || 'Sans description'} — `
        + `${line.quantityText} × ${money(line.unitCents)} = ${money(line.amountCents)}`)
      : ['Aucune ligne']);
    blocks.push(totalRows(result).map(([label, cents]) => `${label}${NBSP}: ${money(cents)}`));
    if (taxIncluded(result)) {
      blocks.push(['Les prix indiqués incluent la TPS et la TVQ.']);
    }
    if (info.notes) {
      blocks.push([`Notes${NBSP}:`, info.notes]);
    }
    return blocks.map((block) => block.join('\n')).join('\n\n');
  }

  function invoiceFileName(details, result) {
    const info = normalizeDetails(details);
    const base = result && result.totalCents < 0 ? 'note-de-credit' : 'facture';
    const slug = (info.invoiceNumber || info.invoiceDate)
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^A-Za-z0-9_-]+/g, '-')
      .slice(0, 60)
      .replace(/^-+|-+$/g, '');
    return `${slug ? `${base}-${slug}` : base}.html`;
  }

  return {
    INVOICE_CSS,
    escapeHtml,
    renderHtml,
    renderDom,
    formatInvoiceDate,
    invoiceTree,
    invoiceDocument,
    invoiceText,
    invoiceFileName,
  };
});
