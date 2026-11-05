"""Read-only economic context; cash authority remains in Treasury."""
import json
from pathlib import Path

from treasury import unavailable_journal


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate invoice key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('invalid invoice constant')


def _receivables(root):
    import payouts
    result = dict(state='UNAVAILABLE', unavailable_reason='INVOICE_LEDGER_UNAVAILABLE',
                  apify_receivable_usd_cents=None, apify_receivable_months=None,
                  note='Approved Apify invoices awaiting payout; not cash, never spendable.',
                  consistency='INDEPENDENT_INVOICE_LEDGER_MAY_LAG_SETTLEMENT',
                  consistency_note='Invoice records may lag bank settlement; a recorded receivable does not prove payment remains unpaid.')
    try:
        raw = (Path(root) / 'state/private/payouts.json').read_text(encoding='utf-8')
        entries = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if not isinstance(entries, dict):
            raise ValueError('invalid invoice ledger')
        for month, entry in entries.items():
            if (not payouts.MONTH.fullmatch(month) or not isinstance(entry, dict)
                    or entry.get('status') not in ('RECEIVABLE', 'PAID')):
                raise ValueError('invalid invoice entry')
            if entry['status'] == 'RECEIVABLE' or 'invoice_usd_cents' in entry:
                amount = entry.get('invoice_usd_cents')
                if type(amount) is not int or not 0 < amount <= payouts.MAX_PAYOUT_CENTS:
                    raise ValueError('invalid invoice amount')
        result.update(payouts.receivables(root, entries=entries))
        result.update(state='AVAILABLE', unavailable_reason=None)
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        pass
    return result


def project(root, bank):
    """Use one bank read; the independent optional invoice ledger may lag it."""
    if hasattr(bank, 'economic_snapshot'):
        economic = bank.economic_snapshot()
    else:
        # Lightweight snapshot-only callers keep their authoritative stop state.
        economic = dict(snapshot=bank.snapshot(), journal=unavailable_journal(),
                        commitments=dict(state='UNAVAILABLE', held_cents=None, unknown_cents=None))
    costs = dict(state='UNKNOWN', fees_cents=None, fees_state='UNKNOWN', profit_cents=None,
                 profit_state='UNKNOWN', margin=None, margin_state='UNKNOWN',
                 experiment_costs=None, experiment_costs_state='UNALLOCATED',
                 note='Settled amounts may already include fees; no fee estimate is added.',
                 founder_provided_services=[dict(service=name, outside_50cad_capital=True,
                     state='UNKNOWN', amount=None, currency=None, period=None, allocation=None,
                     allocation_state='UNALLOCATED') for name in ('VPS', 'MODEL_SUBSCRIPTIONS')])
    return dict(snapshot=economic['snapshot'], context=dict(journal=economic['journal'],
                commitments=economic['commitments'], receivables=_receivables(root), cost_coverage=costs))
