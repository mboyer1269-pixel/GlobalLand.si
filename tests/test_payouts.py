"""Sprint 2-B: Apify payouts reach the bank only by explicit founder attestation."""
import concurrent.futures
import json
import hashlib
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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

    def test_same_settlement_cannot_pay_a_second_month_even_with_force(self):
        for month in ('2026-10', '2026-11'):
            payouts.record_invoice(self.root, month, 1000)
        payouts.record_payout(self.root, '2026-10', 1400, 'WISE', ' SAME-TRANSFER ')
        for changes in ({}, {'cad_cents': 1500}, {'method': 'BANK'}, {'evidence': b'changed'}):
            args = dict(cad_cents=1400, method='WISE', reference='SAME-TRANSFER', force=True)
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                payouts.record_payout(self.root, '2026-11', **args)
        self.assertEqual((self.bank()['cash_cents'], self.bank()['founder_attested_revenue_cents']), (1400, 1400))
        self.assertEqual(payouts.load(self.root)['2026-11']['status'], 'RECEIVABLE')
        self.assertEqual(payouts.receivables(self.root)['apify_receivable_usd_cents'], 1000)

    def test_legacy_settlement_evidence_survives_restart_and_rejects_reattribution(self):
        # Literal pre-fix event format: the identity was only the invoice month.
        legacy = dict(provider='apify', account='payouts', event_id='apify-payout-2026-10',
                      amount_cents=1400, currency='CAD', kind='REVENUE', settled=True,
                      attestation='FOUNDER', method='WISE',
                      reference_sha256=hashlib.sha256(b'LEGACY-TRANSFER').hexdigest())
        Treasury(self.db, verifier=lambda r: r == legacy).credit(legacy)
        with sqlite3.connect(self.db) as db:
            original = db.execute('SELECT * FROM events').fetchall()
        payouts.record_invoice(self.root, '2026-11', 1000)
        with self.assertRaises(ValueError):
            payouts.record_payout(self.root, '2026-11', 1400, 'WISE', 'LEGACY-TRANSFER')
        self.assertEqual(payouts.record_payout(self.root, '2026-10', 1400, 'WISE', 'LEGACY-TRANSFER', force=True)['cash_cents'], 1400)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT * FROM events').fetchall(), original)

    def test_old_double_credit_requires_reconciliation_without_silent_cash_repair(self):
        first = payouts.payout_receipt('2026-10', 1400, 'WISE', 'OLD-DOUBLE')
        bank = Treasury(self.db, verifier=lambda r: True)
        bank.credit(first)
        second = dict(first, event_id='apify-payout-2026-11')
        body = json.dumps(second, sort_keys=True, separators=(',', ':'))
        with sqlite3.connect(self.db) as db:
            db.execute('INSERT INTO events(provider,account,event_id,digest,body,action) VALUES(?,?,?,?,?,?)',
                       ('apify', 'payouts', second['event_id'], hashlib.sha256(body.encode()).hexdigest(), body, 'CREDIT'))
            db.execute('UPDATE treasury SET cash=2800,revenue=2800,attested=2800')
        with self.assertRaises(ValueError):
            payouts.record_payout(self.root, '2026-10', 1400, 'WISE', 'OLD-DOUBLE', force=True)
        self.assertEqual(bank.snapshot()['cash_cents'], 2800)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0], 2)

    def test_retry_after_invoice_write_failure_does_not_recredit(self):
        payouts.record_invoice(self.root, '2026-11', 1000)
        with patch('payouts.atomic_json', side_effect=OSError('invoice write failed')):
            with self.assertRaises(OSError):
                payouts.record_payout(self.root, '2026-11', 1400, 'WISE', 'RETRY')
        self.assertEqual(payouts.record_payout(self.root, '2026-11', 1400, 'WISE', 'RETRY')['cash_cents'], 1400)

    def test_concurrent_month_assignments_credit_one_settlement_only(self):
        bank = Treasury(self.db, verifier=lambda r: True)
        receipts = [payouts.payout_receipt(month, 1400, 'WISE', 'CONCURRENT')
                    for month in ('2026-10', '2026-11')]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(bank.credit, receipt) for receipt in receipts]
            succeeded = rejected = 0
            for result in results:
                try:
                    result.result()
                    succeeded += 1
                except ValueError:
                    rejected += 1
        self.assertEqual((succeeded, rejected), (1, 1))
        self.assertEqual(bank.snapshot()['cash_cents'], 1400)

    def test_incomplete_legacy_settlement_history_cannot_authorize_another_credit(self):
        receipt = payouts.payout_receipt('2026-10', 1400, 'WISE', 'INCOMPLETE')
        bank = Treasury(self.db, verifier=lambda r: True)
        bank.credit(receipt)
        del receipt['reference_sha256']
        body = json.dumps(receipt, sort_keys=True, separators=(',', ':'))
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE events SET body=?,digest=?', (body, hashlib.sha256(body.encode()).hexdigest()))
        with self.assertRaises(ValueError):
            payouts.record_payout(self.root, '2026-11', 1400, 'WISE', 'INCOMPLETE', force=True)
        self.assertEqual(bank.snapshot()['cash_cents'], 1400)

    def test_receivable_projection_is_shared_and_unavailable_for_invalid_optional_data(self):
        import economic
        path = self.root / 'state/private/payouts.json'
        for raw in (None, '[]', '{', '{"2026-11":false}',
                    '{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":true}}',
                    '{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":1,"invoice_usd_cents":2}}',
                    '{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":NaN}}'):
            if raw is not None:
                path.write_text(raw)
            with self.subTest(raw=raw):
                result = payouts.receivables(self.root)
                self.assertEqual(result['state'], 'UNAVAILABLE')
                self.assertIsNone(result['apify_receivable_usd_cents'])
                self.assertEqual(result, economic.project(self.root, Treasury(self.db))['context']['receivables'])
        path.write_bytes(b'\xff')
        self.assertEqual(payouts.receivables(self.root)['state'], 'UNAVAILABLE')
        path.write_text(' ' * (1024 * 1024 + 1))
        self.assertEqual(payouts.receivables(self.root)['state'], 'UNAVAILABLE')

    def test_unavailable_projection_does_not_expose_read_errors_or_change_cash(self):
        bank = Treasury(self.db)
        before = bank.snapshot()
        with patch.object(pathlib.Path, 'open', side_effect=PermissionError('PRIVATE-READ-ERROR')):
            result = payouts.receivables(self.root)
        self.assertEqual(result['state'], 'UNAVAILABLE')
        self.assertNotIn('PRIVATE-READ-ERROR', json.dumps(result))
        self.assertEqual(bank.snapshot(), before)

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
