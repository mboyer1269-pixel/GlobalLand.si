"""Read-only economic context; cash authority remains in Treasury."""
from treasury import unavailable_journal


def _receivables(root):
    import payouts
    return payouts.receivables(root)


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
