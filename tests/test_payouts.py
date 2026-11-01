"""Sprint 2-B: Apify payouts reach the bank only by explicit founder attestation."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import payouts
import test_autonomous_integration as integration
from treasury import Treasury


class PayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / 'state/private').mkdir(parents=True)
        self.db = self.root / 'state/private/treasury.sqlite3'

    def bank(self):
        return Treasury(self.db).snapshot()

    def test_invoice_is_a_receivable_never_money(self):
        payouts.record_invoice(self.root, '2026-11', 2340)
        self.assertEqual(self.bank()['cash_cents'], 0)
        self.assertEqual(self.bank()['state'], 'UNFUNDED')
        self.assertEqual(payouts.receivables(self.root)['apify_receivable_usd_cents'], 2340)

    def test_received_payout_becomes_attested_spendable_revenue_once(self):
        payouts.record_invoice(self.root, '2026-11', 2340)
        snap = payouts.record_payout(self.root, '2026-11', 3180, 'WISE', 'TX-123', evidence=b'statement')
        self.assertEqual((snap['state'], snap['cash_cents'], snap['available_cents']), ('ACTIVE', 3180, 3180))
        self.assertEqual((snap['revenue_cents'], snap['founder_attested_revenue_cents']), (3180, 3180))
        self.assertFalse(snap['funding_verified'])
        self.assertEqual(payouts.receivables(self.root)['apify_receivable_usd_cents'], 0)
        # Same command again: a no-op. A different amount for the same month: refused.
        self.assertEqual(payouts.record_payout(self.root, '2026-11', 3180, 'WISE', 'TX-123', evidence=b'statement')['cash_cents'], 3180)
        with self.assertRaises(ValueError):
            payouts.record_payout(self.root, '2026-11', 3500, 'WISE', 'TX-123', evidence=b'statement')
        stored = json.dumps(payouts.load(self.root))
        self.assertNotIn('TX-123', stored)

    def test_typos_and_missing_invoice_need_force(self):
        with self.assertRaisesRegex(ValueError, 'invoice first'):
            payouts.record_payout(self.root, '2026-11', 3180, 'WISE', 'TX-1')
        payouts.record_invoice(self.root, '2026-11', 2340)
        with self.assertRaisesRegex(ValueError, 'implausible'):
            payouts.record_payout(self.root, '2026-11', 318000, 'WISE', 'TX-1')
        self.assertEqual(payouts.record_payout(self.root, '2026-11', 318000, 'WISE', 'TX-1', force=True)['cash_cents'], 318000)
        for bad in (dict(month='2026-13'), dict(method='CASH'), dict(cad_cents=0), dict(reference=' ')):
            args = dict(month='2026-12', cad_cents=100, method='WISE', reference='TX-2', force=True)
            args.update(bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                payouts.record_payout(self.root, **args)

    def test_attestation_verifier_accepts_only_the_receipt_it_built(self):
        bank = Treasury(self.db)
        payouts.record_invoice(self.root, '2026-11', 2340)
        payouts.record_payout(self.root, '2026-11', 3180, 'WISE', 'TX-123', bank=bank)
        forged = dict(payouts.payout_receipt('2026-12', 999999, 'WISE', 'X'))
        with self.assertRaises(ValueError):
            bank.credit(forged)  # the same Treasury still carries the closure verifier
        self.assertEqual(bank.snapshot()['cash_cents'], 3180)

    def test_cli_requires_administrator_and_parses_usd(self):
        with self.assertRaisesRegex(ValueError, 'administrator'):
            payouts.main(['status'], root=str(self.root), euid=lambda: 1000)
        payouts.main(['invoice', '--month', '2026-11', '--usd', '23.4'], root=str(self.root), euid=lambda: 0)
        self.assertEqual(payouts.load(self.root)['2026-11']['invoice_usd_cents'], 2340)


class ReceivableProjectionTests(unittest.TestCase):
    setUp = integration.AutonomousIntegration.setUp
    git = integration.AutonomousIntegration.git
    submit = integration.AutonomousIntegration.submit

    def run(self, args=None, result=None):
        if isinstance(args, list):
            return subprocess.run(args, check=True, capture_output=True).stdout
        return super().run(args if args is not None else result)

    def test_bank_status_shows_receivables_apart_from_cash(self):
        (self.install / 'state/private').mkdir(parents=True, exist_ok=True)
        payouts.record_invoice(self.install, '2026-11', 2340)
        self.submit(130, 'STATUS', {})
        self.app.cycle('queue')
        status = json.loads(self.run(['git', '--git-dir=' + str(self.remote), 'show', 'main:bank/status.json']))
        self.assertEqual(status['receivables']['apify_receivable_usd_cents'], 2340)
        self.assertEqual((status['cash_cents'], status['state']), (0, 'UNFUNDED'))


if __name__ == '__main__':
    unittest.main()
