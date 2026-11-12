(function () {
  'use strict';

  const calc = window.TpsTvqCalculator;
  const invoice = window.TpsTvqInvoice;
  const NBSP = '\u00a0';
  const DETAIL_FIELDS = [
    'sellerName', 'sellerAddress', 'gstNumber', 'qstNumber',
    'clientName', 'clientAddress', 'invoiceNumber', 'invoiceDate', 'notes',
  ];
  // Screen readers hear the new total once typing pauses, not on every keystroke.
  const ANNOUNCE_DELAY_MS = 1000;
  const METHOD_NOTES = {
    ht: 'TPS et TVQ calculées une seule fois sur le sous-total, puis arrondies au cent le plus proche.',
    ttc: 'TPS et TVQ extraites du total taxes incluses (fractions 5/114,975 et 9,975/114,975), puis arrondies au cent le plus proche.',
    none: `Aucune taxe ajoutée${NBSP}: le total est la somme des lignes.`,
  };
  const PAGE_TITLE = document.title;

  const byId = (id) => document.getElementById(id);
  const linesEl = byId('lines');
  const taxableEl = byId('taxable');
  const modeEl = byId('mode');
  const previewEl = byId('invoice-preview');
  const statusEl = byId('action-status');
  const linesStatusEl = byId('lines-status');
  const announcerEl = byId('total-announcer');
  const totalsErrorEl = byId('totals-error');
  const roundingNoteEl = byId('rounding-note');
  const methodNoteEl = byId('method-note');
  const registrationHintEl = byId('registration-hint');
  const copyWrapEl = byId('copy-fallback-wrap');
  const copyTextEl = byId('copy-fallback');
  const totalEls = { subtotal: byId('subtotal'), gst: byId('gst'), qst: byId('qst'), total: byId('total') };

  const touched = new Set();
  const pendingMessages = new Map();
  let nextKey = 1;
  let attempted = false;
  let current = { details: null, result: null, error: '' };
  let announceTimer = 0;
  let announced = null;

  // Clearing first makes screen readers repeat a message identical to the previous one.
  function tell(element, message) {
    clearTimeout(pendingMessages.get(element));
    element.textContent = '';
    if (message) {
      pendingMessages.set(element, setTimeout(() => {
        element.textContent = message;
      }, 100));
    }
  }

  function money(cents) {
    return calc.formatMoneyFromCents(cents);
  }

  function selectedMode() {
    return document.querySelector('input[name="mode"]:checked').value;
  }

  function lineTree(key) {
    const id = (name) => `line-${key}-${name}`;
    const field = (name, label, attributes) => ['div', { class: `field field-${name}` },
      ['label', { class: `field-label ${name}-label`, for: id(name) }, label],
      ['input', { id: id(name), class: name, type: 'text', autocomplete: 'off', ...attributes }]];
    return ['div', { class: 'line', role: 'group', 'aria-labelledby': id('title'), 'data-key': String(key) },
      ['p', { class: 'line-title', id: id('title') }],
      field('description', 'Description', { maxlength: '200' }),
      field('quantity', 'Quantité', {
        inputmode: 'decimal', maxlength: '16', 'aria-describedby': `${id('quantity-error')} ${id('line-error')}`,
      }),
      field('unit', 'Prix unitaire', {
        inputmode: 'decimal', maxlength: '20', placeholder: '0,00',
        'aria-describedby': `${id('unit-error')} ${id('line-error')}`,
      }),
      ['p', { class: 'line-amount' },
        ['span', { class: 'field-label amount-label' }, 'Montant'], ' ',
        ['span', { class: 'amount', id: id('amount') }]],
      ['div', { class: 'line-remove' }, ['button', { type: 'button', class: 'secondary remove' }, 'Retirer']],
      ['p', { class: 'line-errors' },
        ['span', { class: 'error', id: id('quantity-error') }],
        ['span', { class: 'error', id: id('unit-error') }],
        ['span', { class: 'error', id: id('line-error') }]]];
  }

  function lineParts(line) {
    const part = (name) => byId(`line-${line.dataset.key}-${name}`);
    return {
      line,
      title: part('title'),
      description: part('description'),
      quantity: part('quantity'),
      unit: part('unit'),
      amount: part('amount'),
      remove: line.querySelector('.remove'),
      errors: { quantity: part('quantity-error'), unit: part('unit-error'), line: part('line-error') },
    };
  }

  function allLines() {
    return Array.from(linesEl.children, (line) => lineParts(line));
  }

  function renumber() {
    allLines().forEach((parts, index) => {
      parts.title.textContent = `Ligne ${index + 1}`;
      parts.remove.setAttribute('aria-label', `Retirer la ligne ${index + 1}`);
    });
  }

  function addLine(values) {
    const line = invoice.renderDom(lineTree(nextKey), document);
    nextKey += 1;
    linesEl.appendChild(line);
    const parts = lineParts(line);
    parts.description.value = values.description || '';
    parts.quantity.value = values.quantity || '1';
    parts.unit.value = values.unitAmount || '';
    renumber();
    return parts;
  }

  function forget(parts) {
    touched.delete(parts.quantity.id);
    touched.delete(parts.unit.id);
  }

  function removeLine(parts) {
    const lines = allLines();
    const index = lines.findIndex((item) => item.line === parts.line);
    forget(parts);
    if (lines.length === 1) {
      parts.description.value = '';
      parts.quantity.value = '1';
      parts.unit.value = '';
      update();
      parts.description.focus();
      tell(linesStatusEl, 'Ligne 1 effacée.');
      return;
    }
    const next = lines[index + 1] || lines[index - 1];
    parts.line.remove();
    renumber();
    update();
    next.description.focus();
    tell(linesStatusEl, `Ligne ${index + 1} retirée.`);
  }

  function labelPrices(included) {
    const suffix = included ? ' (taxes incluses)' : '';
    document.querySelectorAll('.unit-label, .unit-heading').forEach((element) => {
      element.textContent = `Prix unitaire${suffix}`;
    });
    document.querySelectorAll('.amount-label, .amount-heading').forEach((element) => {
      element.textContent = `Montant${suffix}`;
    });
  }

  // A field shows its error once the user has left it or tried to print, download or copy.
  function showLineErrors(parts, errors) {
    const messages = { quantity: '', unit: '', line: '' };
    errors.forEach(({ field, message }) => {
      messages[field === 'unitAmount' ? 'unit' : field] = message;
    });
    const visible = (input) => attempted || touched.has(input.id);
    ['quantity', 'unit'].forEach((name) => {
      const input = parts[name];
      parts.errors[name].textContent = visible(input) ? messages[name] : '';
      if (visible(input) && (messages[name] || messages.line)) {
        input.setAttribute('aria-invalid', 'true');
      } else {
        input.removeAttribute('aria-invalid');
      }
    });
    parts.errors.line.textContent = visible(parts.quantity) || visible(parts.unit) ? messages.line : '';
  }

  function readDetails() {
    return Object.fromEntries(DETAIL_FIELDS.map((field) => [field, byId(field).value]));
  }

  function showTotals(result, error, taxable, mode) {
    document.querySelectorAll('.tax-row').forEach((row) => {
      row.hidden = !taxable;
    });
    const cents = result && {
      subtotal: result.subtotalCents, gst: result.gstCents, qst: result.qstCents, total: result.totalCents,
    };
    Object.entries(totalEls).forEach(([name, element]) => {
      element.textContent = cents ? money(cents[name]) : '—';
    });
    totalsErrorEl.hidden = !error;
    totalsErrorEl.textContent = error ? `Totaux indisponibles — ${error}` : '';
    roundingNoteEl.hidden = !result || result.exact;
    methodNoteEl.textContent = METHOD_NOTES[taxable ? mode : 'none'];
  }

  function showPreview(details, result) {
    const tree = result
      ? invoice.invoiceTree(details, result, { headingLevel: 3 })
      : ['p', { class: 'preview-unavailable' }, `Aperçu indisponible${NBSP}: corrigez la saisie des lignes de la facture.`];
    previewEl.textContent = '';
    previewEl.appendChild(invoice.renderDom(tree, document));
  }

  function announce(text) {
    clearTimeout(announceTimer);
    if (announced === null) {
      announced = text;
      return;
    }
    announceTimer = setTimeout(() => {
      if (text !== announced) {
        announced = text;
        announcerEl.textContent = text;
      }
    }, ANNOUNCE_DELAY_MS);
  }

  function update() {
    const taxable = taxableEl.checked;
    const mode = selectedMode();
    modeEl.disabled = !taxable;
    labelPrices(taxable && mode === 'ttc');
    tell(statusEl, '');
    copyWrapEl.hidden = true;

    const lines = allLines();
    const values = lines.map((parts) => ({
      description: parts.description.value, quantity: parts.quantity.value, unitAmount: parts.unit.value,
    }));
    let error = '';
    lines.forEach((parts, index) => {
      let errors = [];
      try {
        parts.amount.textContent = money(calc.calculateLine(values[index]).amountCents);
      } catch (caught) {
        if (!(caught instanceof calc.CalculationError)) {
          throw caught;
        }
        errors = caught.errors;
        parts.amount.textContent = '—';
        error = error || `Ligne ${index + 1}${NBSP}: ${errors[0].message}`;
      }
      showLineErrors(parts, errors);
    });

    let result = null;
    if (!error) {
      try {
        result = calc.calculateInvoice(values, { mode, taxable });
      } catch (caught) {
        if (!(caught instanceof calc.CalculationError)) {
          throw caught;
        }
        error = caught.message;
      }
    }
    const details = readDetails();
    current = { details, result, error };
    showTotals(result, error, taxable, mode);
    showPreview(details, result);
    registrationHintEl.hidden = !taxable || Boolean(details.gstNumber.trim() && details.qstNumber.trim());
    announce(result ? `Total${NBSP}: ${money(result.totalCents)}` : 'Totaux indisponibles');
  }

  function readyFor(action) {
    update();
    if (current.result) {
      return current;
    }
    attempted = true;
    update();
    tell(statusEl, `${action} impossible — ${current.error}`);
    const invalid = linesEl.querySelector('[aria-invalid="true"]');
    if (invalid) {
      invalid.focus();
    }
    return null;
  }

  function todayIso() {
    const now = new Date();
    const pad = (value) => String(value).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  }

  linesEl.addEventListener('input', update);
  linesEl.addEventListener('focusout', (event) => {
    if (event.target.matches('.quantity, .unit')) {
      touched.add(event.target.id);
      update();
    }
  });
  linesEl.addEventListener('click', (event) => {
    const button = event.target.closest('.remove');
    if (button) {
      removeLine(lineParts(button.closest('.line')));
    }
  });
  byId('add-line').addEventListener('click', () => {
    const parts = addLine({});
    update();
    parts.description.focus();
  });
  taxableEl.addEventListener('change', update);
  modeEl.addEventListener('change', update);
  byId('details').addEventListener('input', update);

  byId('print-invoice').addEventListener('click', () => {
    if (readyFor('Impression')) {
      window.print();
    }
  });
  // Browsers suggest the page title as the PDF file name.
  window.addEventListener('beforeprint', () => {
    if (current.result) {
      document.title = invoice.invoiceFileName(current.details, current.result).replace(/\.html$/, '');
    }
  });
  window.addEventListener('afterprint', () => {
    document.title = PAGE_TITLE;
  });

  byId('download-invoice').addEventListener('click', () => {
    const state = readyFor('Téléchargement');
    if (!state) {
      return;
    }
    const name = invoice.invoiceFileName(state.details, state.result);
    const blob = new Blob([invoice.invoiceDocument(state.details, state.result)], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.hidden = true;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    tell(statusEl, `Téléchargement lancé${NBSP}: ${name}`);
  });

  byId('copy-invoice').addEventListener('click', async () => {
    const state = readyFor('Copie');
    if (!state) {
      return;
    }
    const text = invoice.invoiceText(state.details, state.result);
    try {
      await navigator.clipboard.writeText(text);
      tell(statusEl, 'Texte de la facture copié.');
    } catch (error) {
      copyTextEl.value = text;
      copyWrapEl.hidden = false;
      copyTextEl.focus();
      copyTextEl.select();
      tell(statusEl, `Copie automatique impossible${NBSP}: le texte est sélectionné ci-dessous, copiez-le manuellement.`);
    }
  });

  const invoiceStyle = document.createElement('style');
  invoiceStyle.textContent = invoice.INVOICE_CSS;
  document.head.appendChild(invoiceStyle);
  byId('invoiceDate').value = todayIso();
  addLine({ description: 'Service de consultation', quantity: '1', unitAmount: '100,00' });
  update();
})();
