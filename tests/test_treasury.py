import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from scripts.treasury import Treasury


def receipt(event, amount, kind='FUNDING', **extra):
    return dict(provider='test', account='owned', event_id=event, amount_cents=amount,
                currency='CAD', kind=kind, settled=True, **extra)


class TreasuryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'treasury.db'
        self.t = Treasury(self.path, verifier=lambda r: r.get('signature') == 'trusted')

    def evidence(self, event, amount, kind='FUNDING'):
        return receipt(event, amount, kind, signature='trusted')

    def fund(self):
        self.t.confirm_funding(self.evidence('initial', 5000))

    def test_full_capital_available_without_ceo_limits(self):
        self.assertEqual(self.t.snapshot()['state'], 'UNFUNDED')
        self.fund()
        self.t.reserve('all', 5000, 'hash')
        self.assertEqual(self.t.snapshot()['state'], 'ACTIVE')
        self.assertEqual(self.t.snapshot()['available_cents'], 0)
        with self.assertRaises(ValueError): self.t.reserve('extra', 1, 'h')

    def test_rejects_invalid_amounts_and_insufficient_balance(self):
        self.fund()
        for amount in (True, 1.0, -1, 2**63, 5001):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.t.reserve('bad', amount, 'h')

    def test_funding_requires_trusted_external_evidence(self):
        for t in (self.t, Treasury(self.path)):
            with self.assertRaises(ValueError): t.confirm_funding(receipt('fake', 5000))
        self.assertEqual(self.t.snapshot()['state'], 'UNFUNDED')
        self.t.reserve('free', 0, 'h')
        self.t.release('free')
        self.assertEqual(self.t.snapshot()['state'], 'UNFUNDED')

    def test_funding_and_request_replays_are_immutable(self):
        self.fund(); self.fund()
        self.t.reserve('one', 10, 'h'); self.t.reserve('one', 10, 'h')
        with self.assertRaises(ValueError): self.t.reserve('one', 11, 'h')
        with self.assertRaises(ValueError): self.t.confirm_funding(self.evidence('initial', 4999))

    def test_concurrent_reservations_cannot_overdraw(self):
        self.fund()
        def hold(i):
            try: Treasury(self.path).reserve(str(i), 3000, str(i)); return True
            except ValueError: return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(hold, range(2))), 1)
        self.assertEqual(self.t.snapshot()['reserved_cents'], 3000)

    def test_unknown_survives_restart_and_requires_cancel_evidence(self):
        self.fund(); self.t.reserve('op', 3000, 'h')
        self.assertEqual(self.t.mark_submitted('op')['idempotency_key'], 'op')
        restarted = Treasury(self.path, self.t.verifier)
        self.assertEqual(restarted.snapshot()['reserved_cents'], 3000)
        with self.assertRaises(ValueError): restarted.release('op')
        restarted.release('op', self.evidence('cancel', 0, 'CANCELLED'))
        self.assertEqual(restarted.snapshot()['available_cents'], 5000)

    def test_partial_settlement_and_global_receipt_deduplication(self):
        self.fund(); self.t.reserve('op', 3000, 'h'); self.t.mark_submitted('op')
        spend = self.evidence('spend', 2000, 'SPEND')
        self.t.settle('op', spend); self.t.settle('op', spend)
        self.assertEqual(self.t.snapshot()['cash_cents'], 3000)
        self.assertEqual(self.t.snapshot()['reserved_cents'], 0)
        with self.assertRaises(ValueError): self.t.credit(self.evidence('spend', 2000, 'REVENUE'))
        self.t.credit(self.evidence('sale', 7000, 'REVENUE'))
        self.t.credit(self.evidence('sale', 7000, 'REVENUE'))
        self.assertEqual(self.t.snapshot()['cash_cents'], 10000)

    def test_exact_zero_is_terminal(self):
        self.fund(); self.t.reserve('op', 5000, 'h'); self.t.mark_submitted('op')
        self.t.settle('op', self.evidence('spent', 5000, 'SPEND'))
        self.assertEqual(self.t.snapshot()['state'], 'EXTINCT')
        for call in (lambda: self.t.credit(self.evidence('revive', 1, 'REFUND')),
                     lambda: self.t.record_positions(self.evidence('pos', 5, 'POSITIONS')),
                     lambda: self.t.confirm_funding(self.evidence('new', 5000))):
            with self.assertRaises(ValueError): call()
        self.assertEqual(Treasury(self.path).snapshot()['cash_cents'], 0)

    def test_positions_and_uncertainty_preserve_life(self):
        self.fund(); self.t.record_positions(self.evidence('pos', 100, 'POSITIONS'))
        self.t.reserve('op', 5000, 'h'); self.t.mark_submitted('op')
        self.t.settle('op', self.evidence('spent', 5000, 'SPEND'))
        self.assertEqual(self.t.snapshot()['state'], 'ACTIVE')
        self.t.record_positions(self.evidence('pos-zero', 0, 'POSITIONS'))
        self.assertEqual(self.t.snapshot()['state'], 'RECONCILING')
        self.t.sync_receipts([], complete=True)
        self.assertEqual(self.t.snapshot()['state'], 'EXTINCT')

    def test_overcharge_records_debt_and_halts(self):
        self.fund(); self.t.reserve('op', 5000, 'h'); self.t.mark_submitted('op')
        self.t.settle('op', self.evidence('breach', 5100, 'SPEND'))
        self.assertEqual(self.t.snapshot()['cash_cents'], -100)
        self.assertEqual(self.t.snapshot()['state'], 'HALTED')
        with self.assertRaises(ValueError): self.t.reserve('next', 1, 'h')

    def test_funding_preserves_observed_prefunding_debt_and_halt(self):
        self.t.reserve('free', 0, 'h')
        self.t.mark_submitted('free')
        self.t.settle('free', self.evidence('unexpected-debit', 100, 'SPEND'))
        self.fund()
        self.assertEqual(self.t.snapshot()['cash_cents'], 4900)
        self.assertEqual(self.t.snapshot()['state'], 'HALTED')
        self.assertTrue(self.t.snapshot()['funding_verified'])
        self.assertIn('overcharge', self.t.snapshot()['extinction_reason'])

    def test_overcharge_to_true_zero_is_terminal_with_breach_provenance(self):
        self.fund()
        self.t.reserve('op', 4999, 'h')
        self.t.mark_submitted('op')
        self.t.settle('op', self.evidence('zero-breach', 5000, 'SPEND'))
        self.assertEqual(self.t.snapshot()['cash_cents'], 0)
        self.assertEqual(self.t.snapshot()['state'], 'EXTINCT')
        self.assertIn('overcharge', self.t.snapshot()['extinction_reason'])
        with self.assertRaises(ValueError):
            self.t.credit(self.evidence('resurrect', 100, 'REVENUE'))
        self.assertEqual(Treasury(self.path).snapshot()['state'], 'EXTINCT')

    def invested(self):
        self.fund()
        self.t.record_positions(self.evidence('invested', 5000, 'POSITIONS'))
        self.t.reserve('investment', 5000, 'investment-hash')
        self.t.mark_submitted('investment')
        self.t.settle('investment', self.evidence('investment-paid', 5000, 'SPEND'))

    def test_interleaved_liquidation_waits_for_complete_cash_evidence(self):
        self.invested()
        self.t.record_positions(self.evidence('liquidated', 0, 'POSITIONS'))
        self.assertEqual(self.t.snapshot()['state'], 'RECONCILING')
        self.t.credit(self.evidence('proceeds', 5100, 'REVENUE'))
        self.assertEqual(self.t.snapshot()['cash_cents'], 5100)
        self.assertEqual(self.t.snapshot()['available_cents'], 0)
        with self.assertRaises(ValueError): self.t.reserve('frozen', 1, 'h')
        self.t.sync_receipts([], complete=True)
        self.assertEqual(self.t.snapshot()['state'], 'ACTIVE')
        self.assertEqual(self.t.snapshot()['available_cents'], 5100)

    def test_atomic_liquidation_batch_is_order_independent_and_replay_safe(self):
        self.invested()
        positions = self.evidence('liquidated', 0, 'POSITIONS')
        proceeds = self.evidence('proceeds', 5100, 'REVENUE')
        self.t.sync_receipts([positions, proceeds], complete=True)
        self.assertEqual(self.t.snapshot()['state'], 'ACTIVE')
        self.assertEqual(self.t.snapshot()['cash_cents'], 5100)
        self.t.sync_receipts([proceeds, positions], complete=True)
        self.t.credit(proceeds)
        self.t.record_positions(positions)
        self.assertEqual(self.t.snapshot()['cash_cents'], 5100)
        with self.assertRaises(ValueError):
            self.t.sync_receipts([self.evidence('proceeds', 5200, 'REVENUE')], complete=True)
        self.assertEqual(self.t.snapshot()['cash_cents'], 5100)

    def test_partial_sync_requires_complete_sync_before_confirmed_loss(self):
        self.invested()
        self.t.sync_receipts([self.evidence('loss', 0, 'POSITIONS')])
        self.assertEqual(self.t.snapshot()['state'], 'RECONCILING')
        self.assertEqual(Treasury(self.path).snapshot()['state'], 'RECONCILING')
        self.t.sync_receipts([], complete=True)
        self.assertEqual(self.t.snapshot()['state'], 'EXTINCT')
        with self.assertRaises(ValueError):
            self.t.sync_receipts([self.evidence('late', 5100, 'REVENUE')], complete=True)

    def test_sync_invalid_proof_rolls_back_entire_batch_and_shared_funding_identity(self):
        initial = self.evidence('initial', 5000)
        self.t.sync_receipts([initial], complete=True)
        self.t.confirm_funding(initial)
        with self.assertRaises(ValueError):
            self.t.sync_receipts([self.evidence('sale', 100, 'REVENUE'), receipt('bad', 1, 'REFUND')], complete=True)
        self.assertEqual(self.t.snapshot()['cash_cents'], 5000)
        self.t.credit(self.evidence('sale', 100, 'REVENUE'))
        self.assertEqual(self.t.snapshot()['cash_cents'], 5100)
        with self.assertRaises(ValueError): Treasury(self.path).sync_receipts([], complete=True)

    # Sprint 0 regressions -------------------------------------------------

    def test_verified_revenue_before_initial_deposit_is_spendable(self):
        self.t.credit(self.evidence('first-sale', 700, 'REVENUE'))
        snap = self.t.snapshot()
        self.assertEqual((snap['state'], snap['cash_cents'], snap['available_cents']), ('ACTIVE', 700, 700))
        self.assertFalse(snap['funding_verified'])
        self.assertTrue(snap['revenue_verified'])
        with self.assertRaises(ValueError): self.t.reserve('too-much', 701, 'h')
        self.t.reserve('reinvest', 700, 'h'); self.t.mark_submitted('reinvest')
        self.t.settle('reinvest', self.evidence('reinvest-paid', 700, 'SPEND'))
        # Spending earned revenue to zero is not extinction: the founder's
        # deposit was never verified, so the world is merely out of cash.
        self.assertEqual(self.t.snapshot()['state'], 'ACTIVE')
        self.assertEqual(self.t.snapshot()['available_cents'], 0)
        self.fund()
        self.assertEqual(self.t.snapshot()['cash_cents'], 5000)
        self.assertTrue(self.t.snapshot()['funding_verified'])

    def test_unverified_revenue_never_activates_unfunded_bank(self):
        with self.assertRaises(ValueError): self.t.credit(receipt('forged', 700, 'REVENUE'))
        with self.assertRaises(ValueError): self.t.credit(self.evidence('empty', 0, 'REVENUE'))
        self.assertEqual(self.t.snapshot()['state'], 'UNFUNDED')
        with self.assertRaises(ValueError): self.t.reserve('nope', 1, 'h')

    def test_revenue_before_funding_preserves_halt(self):
        self.t.reserve('free', 0, 'h'); self.t.mark_submitted('free')
        self.t.settle('free', self.evidence('unexpected-debit', 100, 'SPEND'))
        self.t.credit(self.evidence('sale', 300, 'REVENUE'))
        self.assertEqual(self.t.snapshot()['state'], 'HALTED')
        self.assertEqual(self.t.snapshot()['cash_cents'], 200)

    def position(self, event, amount, account, asset=None):
        r = self.evidence(event, amount, 'POSITIONS'); r['account'] = account
        if asset is not None: r['asset'] = asset
        return r

    def test_positions_of_distinct_accounts_and_assets_are_summed(self):
        self.fund()
        self.t.record_positions(self.position('a1', 300, 'wallet-a'))
        self.t.record_positions(self.position('b1', 200, 'wallet-b', 'USDC'))
        self.t.record_positions(self.position('b2', 50, 'wallet-b', 'ETH'))
        self.assertEqual(self.t.snapshot()['position_cents'], 550)
        self.t.record_positions(self.position('b3', 120, 'wallet-b', 'USDC'))
        self.assertEqual(self.t.snapshot()['position_cents'], 470)
        self.assertEqual(Treasury(self.path).snapshot()['position_cents'], 470)

    def test_one_account_at_zero_does_not_hide_another_before_extinction(self):
        self.fund()
        self.t.record_positions(self.position('a', 2500, 'wallet-a'))
        self.t.record_positions(self.position('b', 2500, 'wallet-b'))
        self.t.reserve('buy', 5000, 'h'); self.t.mark_submitted('buy')
        self.t.settle('buy', self.evidence('buy-paid', 5000, 'SPEND'))
        self.t.record_positions(self.position('a-zero', 0, 'wallet-a'))
        self.t.sync_receipts([], complete=True)
        self.assertEqual(self.t.snapshot()['state'], 'ACTIVE')
        self.assertEqual(self.t.snapshot()['position_cents'], 2500)
        self.t.record_positions(self.position('b-zero', 0, 'wallet-b'))
        self.assertEqual(self.t.snapshot()['state'], 'RECONCILING')
        self.t.sync_receipts([], complete=True)
        self.assertEqual(self.t.snapshot()['state'], 'EXTINCT')

    def test_account_valued_whole_and_per_asset_is_rejected(self):
        self.fund()
        self.t.record_positions(self.position('whole', 300, 'wallet-a'))
        with self.assertRaises(ValueError):
            self.t.record_positions(self.position('part', 100, 'wallet-a', 'USDC'))
        for bad in (' ', 'x' * 257, 7):
            with self.subTest(asset=bad), self.assertRaises(ValueError):
                self.t.record_positions(self.position('bad-' + str(len(str(bad))), 1, 'wallet-c', bad))
        self.assertEqual(self.t.snapshot()['position_cents'], 300)

    def test_legacy_scalar_position_is_migrated_not_dropped(self):
        import sqlite3
        legacy = Path(self.tmp.name) / 'legacy.db'
        db = sqlite3.connect(str(legacy))
        db.executescript("""
            CREATE TABLE treasury (id INTEGER PRIMARY KEY CHECK(id=1), cash INTEGER NOT NULL DEFAULT 0,
                positions INTEGER NOT NULL DEFAULT 0, funded INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'UNFUNDED', reason TEXT, pending_sync INTEGER NOT NULL DEFAULT 0);
            INSERT INTO treasury(id, cash, positions, funded, state) VALUES(1, 0, 900, 1, 'ACTIVE');
        """)
        db.commit(); db.close()
        migrated = Treasury(legacy, verifier=self.t.verifier)
        self.assertEqual(migrated.snapshot()['position_cents'], 900)
        self.assertEqual(Treasury(legacy).snapshot()['position_cents'], 900)
        self.assertEqual(migrated.snapshot()['state'], 'ACTIVE')
        # The scalar was 'the latest reported total': a real valuation supersedes it
        # instead of being added to it forever.
        migrated.record_positions(self.position('real', 900, 'wallet-a'))
        self.assertEqual(migrated.snapshot()['position_cents'], 900)
        migrated.record_positions(self.position('sold', 0, 'wallet-a'))
        self.assertEqual(migrated.snapshot()['position_cents'], 0)

    def test_revenue_total_excludes_refunds_and_funding(self):
        self.fund()
        self.t.credit(self.evidence('sale', 700, 'REVENUE'))
        self.t.credit(self.evidence('refund', 300, 'REFUND'))
        snap = self.t.snapshot()
        self.assertEqual((snap['cash_cents'], snap['revenue_cents']), (6000, 700))


if __name__ == '__main__': unittest.main()
