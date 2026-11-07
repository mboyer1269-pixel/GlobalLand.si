"""One physical bank deposit cannot fund two adapter receipt namespaces."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from scripts.treasury import Treasury


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def order_receipt(reference='bank-reference-1'):
    account = digest('dedicated-account')
    reference_hash = digest(reference.strip().casefold())
    return dict(provider='orders', account=account,
                event_id=digest(account + ':' + reference_hash),
                amount_cents=1000, currency='CAD', kind='REVENUE', settled=True,
                attestation='FOUNDER', reference_sha256=reference_hash,
                evidence_sha256='a' * 64, observed_at='2026-11-07T12:00:00+00:00')


def apify_receipt(reference='bank-reference-1', method='BANK'):
    # Exact existing payouts.payout_receipt shape, without importing its POSIX
    # admin/supervisor dependencies. Legacy hashing strips but preserves case.
    return dict(provider='apify', account='payouts', event_id='apify-payout-2026-11',
                amount_cents=1000, currency='CAD', kind='REVENUE', settled=True,
                attestation='FOUNDER', method=method,
                reference_sha256=digest(reference.strip()))


class CrossAdapterSettlementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bank = Treasury(Path(self.tmp.name) / 'treasury.sqlite3', verifier=lambda receipt: True)

    def test_order_bank_transfer_cannot_credit_apify_bank_again(self):
        self.bank.credit(order_receipt())
        with self.assertRaises(ValueError): self.bank.credit(apify_receipt())
        self.assertEqual(self.bank.snapshot()['cash_cents'], 1000)

    def test_apify_bank_transfer_cannot_credit_order_again(self):
        self.bank.credit(apify_receipt())
        with self.assertRaises(ValueError): self.bank.credit(order_receipt())
        self.assertEqual(self.bank.snapshot()['cash_cents'], 1000)

    def test_exact_same_event_replays_remain_idempotent(self):
        for receipt in (order_receipt(), apify_receipt('another-bank-reference')):
            self.bank.credit(receipt)
            self.bank.credit(dict(receipt))
        self.assertEqual(self.bank.snapshot()['cash_cents'], 2000)
        with self.assertRaises(ValueError):
            self.bank.credit(dict(order_receipt(), amount_cents=1001))

    def test_distinct_bank_references_are_not_blanket_blocked(self):
        self.bank.credit(order_receipt())
        self.bank.credit(apify_receipt('different-reference'))
        self.assertEqual(self.bank.snapshot()['cash_cents'], 2000)

    def test_non_bank_apify_methods_keep_their_own_reference_scope(self):
        for method in ('WISE', 'PAYPAL'):
            for order_first in (True, False):
                with self.subTest(method=method, order_first=order_first):
                    path = Path(self.tmp.name) / (method + str(order_first) + '.sqlite3')
                    bank = Treasury(path, verifier=lambda receipt: True)
                    receipts = [order_receipt(), apify_receipt(method=method)]
                    if not order_first: receipts.reverse()
                    for receipt in receipts: bank.credit(receipt)
                    self.assertEqual(bank.snapshot()['cash_cents'], 2000)

    def test_legacy_case_sensitive_hashes_cannot_be_recovered_from_digest(self):
        # Document the bounded guarantee: these legacy bytes cannot prove an
        # equal normalized bank reference. Do not silently rewrite old evidence.
        self.bank.credit(apify_receipt('BANK-REFERENCE-1'))
        self.bank.credit(order_receipt('BANK-REFERENCE-1'))
        self.assertEqual(self.bank.snapshot()['cash_cents'], 2000)


if __name__ == '__main__':
    unittest.main()
