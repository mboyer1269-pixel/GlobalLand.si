#!/usr/bin/env python3
"""Apify payouts → GlobalLand bank, by explicit founder attestation.

Apify exposes no payout API. Its payout invoice is issued on the 11th, is
approved in the console (3 days), and the money is paid between the 21st and
the 25th (minimum USD 20 by PayPal or Wise, USD 100 otherwise; smaller
amounts roll over). So the bank learns about it in two founder steps:

1. `invoice --month YYYY-MM --usd 23.40`: the approved invoice is recorded as
   a RECEIVABLE. It is not money and is never spendable.
2. `received --month YYYY-MM --cad-cents 3180 --method WISE --reference REF`:
   the amount actually received, in CAD, in GlobalLand's dedicated account,
   becomes a REVENUE receipt with `attestation: FOUNDER`.

The bank reports founder-attested revenue separately from automatically
verified revenue. Apify payouts are final for the developer (Apify never
charges the developer for other users' runs), so they carry no maturity date.
The attestation verifier accepts only the exact receipt this command built
in this process: nothing else can borrow it.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys

from supervisor import atomic_json
from treasury import Treasury

MONTH = re.compile(r'20[0-9]{2}-(0[1-9]|1[0-2])')
METHODS = ('WISE', 'PAYPAL', 'BANK')
MAX_PAYOUT_CENTS = 10_000_000  # 100 000 CAD: far above any plausible early payout
RATE_BOUNDS = (1.0, 2.0)       # CAD per USD accepted without --force (typo guard)


def _ledger(root):
    return pathlib.Path(root) / 'state' / 'private' / 'payouts.json'


def load(root):
    path = _ledger(root)
    return json.loads(path.read_text()) if path.exists() else {}


def _month(month):
    if not isinstance(month, str) or not MONTH.fullmatch(month):
        raise ValueError('month must be YYYY-MM')
    return month


def record_invoice(root, month, usd_cents):
    """An approved Apify payout invoice: a receivable, not money."""
    _month(month)
    if type(usd_cents) is not int or not 0 < usd_cents <= MAX_PAYOUT_CENTS:
        raise ValueError('invoice amount must be positive USD cents')
    ledger = load(root)
    entry = ledger.get(month, {})
    if entry.get('status') == 'PAID':
        raise ValueError('this month is already paid')
    entry.update(invoice_usd_cents=usd_cents, status='RECEIVABLE',
                 invoice_recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    ledger[month] = entry
    atomic_json(_ledger(root), ledger)
    return entry


def payout_receipt(month, cad_cents, method, reference, evidence=None):
    _month(month)
    if type(cad_cents) is not int or not 0 < cad_cents <= MAX_PAYOUT_CENTS:
        raise ValueError('received amount must be positive CAD cents')
    if method not in METHODS:
        raise ValueError('method must be one of ' + ', '.join(METHODS))
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 256:
        raise ValueError('transaction reference required')
    receipt = dict(provider='apify', account='payouts', event_id='apify-payout-' + month,
                   amount_cents=cad_cents, currency='CAD', kind='REVENUE', settled=True,
                   attestation='FOUNDER', method=method,
                   # Personal transaction data stays out of the record: only digests.
                   reference_sha256=hashlib.sha256(reference.strip().encode()).hexdigest())
    if evidence is not None:
        receipt['evidence_sha256'] = hashlib.sha256(evidence).hexdigest()
    return receipt


def plausible(invoice_usd_cents, cad_cents):
    rate = cad_cents / invoice_usd_cents
    return RATE_BOUNDS[0] <= rate <= RATE_BOUNDS[1]


def record_payout(root, month, cad_cents, method, reference, evidence=None, force=False, bank=None):
    """Credit the bank with a payout actually received, by founder attestation."""
    ledger = load(root)
    entry = ledger.get(_month(month), {})
    invoice = entry.get('invoice_usd_cents')
    if invoice is None and not force:
        raise ValueError('record the approved invoice first (or --force with a reason)')
    if invoice is not None and not plausible(invoice, cad_cents) and not force:
        raise ValueError('received CAD is implausible for the invoice USD (expected 1.0-2.0 CAD per USD); check for a typo or use --force')
    receipt = payout_receipt(month, cad_cents, method, reference, evidence)
    expected = json.dumps(receipt, sort_keys=True)

    def verifier(candidate):
        return json.dumps(candidate, sort_keys=True) == expected

    bank = bank or Treasury(pathlib.Path(root) / 'state' / 'private' / 'treasury.sqlite3')
    bank.verifier = verifier
    snapshot = bank.credit(receipt)
    entry.update(status='PAID', received_cad_cents=cad_cents, method=method,
                 paid_recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    ledger[month] = entry
    atomic_json(_ledger(root), ledger)
    return snapshot


def receivables(root):
    """Public projection: approved invoices not yet received (never money)."""
    pending = {m: e['invoice_usd_cents'] for m, e in load(root).items() if e.get('status') == 'RECEIVABLE'}
    return dict(apify_receivable_usd_cents=sum(pending.values()), apify_receivable_months=sorted(pending),
                note='Approved Apify invoices awaiting payout; not cash, never spendable.')


def main(argv=None, root='/opt/globalland', euid=os.geteuid):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='action', required=True)
    inv = sub.add_parser('invoice'); inv.add_argument('--month', required=True); inv.add_argument('--usd', required=True)
    rec = sub.add_parser('received')
    rec.add_argument('--month', required=True); rec.add_argument('--cad-cents', type=int, required=True)
    rec.add_argument('--method', required=True, choices=METHODS); rec.add_argument('--reference', required=True)
    rec.add_argument('--evidence', help='private statement file; only its hash is recorded')
    rec.add_argument('--force', action='store_true')
    sub.add_parser('status')
    args = p.parse_args(argv)
    if euid() != 0:
        raise ValueError('administrator required')
    if args.action == 'invoice':
        if not re.fullmatch(r'[0-9]{1,6}(\.[0-9]{1,2})?', args.usd):
            raise ValueError('--usd like 23.40')
        whole, _, frac = args.usd.partition('.')
        result = record_invoice(root, args.month, int(whole) * 100 + int((frac + '00')[:2]))
    elif args.action == 'received':
        evidence = pathlib.Path(args.evidence).read_bytes() if args.evidence else None
        result = record_payout(root, args.month, args.cad_cents, args.method, args.reference, evidence, args.force)
    else:
        result = dict(payouts=load(root), **receivables(root))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Payout recording refused: ' + str(error), file=sys.stderr)
        sys.exit(1)
