"""Private order reconciliation; fixture money never reaches production storage."""
import importlib.util
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.treasury import Treasury


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('scripts.orders'),
                             'private order register must exist')
        from scripts.orders import OrderRegister, project
        self.Register, self.project = OrderRegister, project
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.register = OrderRegister(self.root)
        self.path = self.root / 'state/private/orders.sqlite3'

    def order(self, source='order-1', amount=1000, currency='CAD', synthetic=False):
        return self.register.create_order('private-customer-case', amount, currency,
                                          'a' * 64, source, synthetic=synthetic)

    def deposit(self, reference='transfer-1', amount=1000, currency='CAD', **extra):
        return self.register.confirm_deposit('dedicated-account', reference, amount,
                    currency, '2026-11-07T12:00:00Z', 'b' * 64, **extra)

    def bank(self):
        bank = Treasury(self.root / 'state/private/treasury.sqlite3')
        bank.db_path.chmod(0o600)
        return bank

    def accept(self, order):
        return self.register.accept_order(order['order_id'], 'accept-' + order['order_id'])

    def test_acceptance_is_explicit_immutable_and_case_view_is_isolated(self):
        from scripts.orders import case_orders
        order = self.order()
        self.assertEqual(case_orders(self.root, 'other-case')['orders'], [])
        first = self.accept(order)
        self.assertEqual(self.accept(order), first)
        self.assertEqual(first['commercial_status'], 'ACCEPTED')
        with self.assertRaises(ValueError):
            self.register.accept_order(order['order_id'], 'changed-acceptance')
        view = case_orders(self.root, 'private-customer-case')
        self.assertEqual(view['orders'][0]['commercial_status'], 'ACCEPTED')
        for field in ('case_key', 'source_id', 'acceptance_source_id'):
            self.assertNotIn(field, view['orders'][0])
        self.assertEqual(case_orders(self.root / 'missing', 'case')['state'], 'UNAVAILABLE')

    def test_draft_excess_and_mismatch_are_blocked_from_posting(self):
        for source, amount, currency in (('draft', 1000, 'CAD'), ('excess', 1001, 'CAD'), ('mismatch', 1000, 'USD')):
            order = self.order(source, currency=currency)
            if source != 'draft': self.accept(order)
            deposit = self.deposit(source, amount)
            self.register.allocate(deposit['deposit_id'], order['order_id'])
            with self.assertRaises(ValueError): self.register.post(deposit['deposit_id'], self.bank())
        self.assertEqual(self.bank().snapshot()['cash_cents'], 0)

    def test_order_terms_are_immutable_and_ids_are_opaque(self):
        one = self.order()
        self.assertEqual(self.order(), one)
        self.assertNotIn('private-customer', one['order_id'])
        self.assertEqual(one['commercial_status'], 'DRAFT')
        for kwargs in ({'amount': 1001}, {'currency': 'USD'}, {'synthetic': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.order(**kwargs)

    def test_claims_are_idempotent_unverified_and_cannot_credit(self):
        order = self.order()
        claim = self.register.record_claim(order['order_id'], 'claim-1', 1000, 'CAD')
        self.assertEqual(claim['verification_status'], 'UNVERIFIED')
        self.assertEqual(claim, self.register.record_claim(order['order_id'], 'claim-1', 1000, 'CAD'))
        with self.assertRaises(ValueError):
            self.register.record_claim(order['order_id'], 'claim-1', 1001, 'CAD')
        self.assertEqual(self.register.get_order(order['order_id'])['payment_status'], 'CLAIMED_UNVERIFIED')
        self.assertFalse((self.path.parent / 'treasury.sqlite3').exists())

    def test_transfer_identity_independent_of_allocation_and_normalization(self):
        first, second = self.order(), self.order('order-2')
        deposit = self.deposit(' Transfer-1 ')
        self.assertEqual(deposit, self.deposit('transfer-1'))
        for extra in ({'amount': 1001}, {'currency': 'USD'}, {'synthetic': True}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.deposit(**extra)
        allocated = self.register.allocate(deposit['deposit_id'], first['order_id'])
        self.assertEqual(allocated, self.register.allocate(deposit['deposit_id'], first['order_id']))
        with self.assertRaises(ValueError):
            self.register.allocate(deposit['deposit_id'], second['order_id'])

    def test_partial_excess_wrong_currency_are_not_fully_paid(self):
        for amount, currency, expected in ((500, 'CAD', 'PARTIAL'), (1001, 'CAD', 'EXCESS'),
                                            (1000, 'USD', 'CURRENCY_MISMATCH')):
            with self.subTest(expected=expected):
                order = self.order(expected)
                deposit = self.deposit(expected, amount, currency)
                self.register.allocate(deposit['deposit_id'], order['order_id'])
                self.assertEqual(self.register.get_order(order['order_id'])['payment_status'], expected)

    def test_multiple_partial_deposits_sum_exactly_and_confirmation_is_not_posting(self):
        order = self.order()
        for ref in ('part-1', 'part-2'):
            deposit = self.deposit(ref, 500)
            self.register.allocate(deposit['deposit_id'], order['order_id'])
        view = self.register.get_order(order['order_id'])
        self.assertEqual(view['payment_status'], 'BANK_CONFIRMED')
        self.assertEqual(view['treasury_status'], 'TREASURY_NOT_POSTED')
        self.assertEqual(view['posted_cents'], 0)

    def test_post_is_explicit_attested_revenue_once_and_does_not_fund(self):
        order, deposit = self.order(), self.deposit()
        self.accept(order)
        bank = self.bank()
        with self.assertRaises(ValueError): self.register.post(deposit['deposit_id'], bank)
        self.assertEqual(bank.snapshot()['cash_cents'], 0)
        self.register.allocate(deposit['deposit_id'], order['order_id'])
        self.register.post(deposit['deposit_id'], bank)
        self.Register(self.root).post(deposit['deposit_id'], bank)
        snapshot = bank.snapshot()
        self.assertEqual(snapshot['cash_cents'], 1000)
        self.assertEqual(snapshot['founder_attested_revenue_cents'], 1000)
        self.assertFalse(snapshot['funding_verified'])
        with closing(sqlite3.connect(bank.db_path)) as db:
            receipt = json.loads(db.execute('SELECT body FROM events').fetchone()[0])
        self.assertNotIn('available_at', receipt)
        self.assertEqual(receipt['kind'], 'REVENUE')
        self.assertEqual(receipt['attestation'], 'FOUNDER')

    def test_crash_after_credit_replays_exact_receipt(self):
        order, deposit = self.order(), self.deposit()
        self.accept(order)
        self.register.allocate(deposit['deposit_id'], order['order_id'])
        bank = self.bank()
        credit = bank.credit
        def crash(receipt):
            credit(receipt)
            raise RuntimeError('simulated interruption after durable Treasury commit')
        bank.credit = crash
        with self.assertRaises(RuntimeError): self.register.post(deposit['deposit_id'], bank)
        self.assertEqual(bank.snapshot()['cash_cents'], 1000)
        self.assertEqual(self.register.get_order(order['order_id'])['treasury_status'], 'TREASURY_NOT_POSTED')
        bank.credit = credit
        self.Register(self.root).post(deposit['deposit_id'], bank)
        self.assertEqual(bank.snapshot()['cash_cents'], 1000)
        self.assertEqual(self.register.get_order(order['order_id'])['treasury_status'], 'TREASURY_POSTED')

    def test_synthetic_is_excluded_and_never_posted_or_mixed(self):
        order = self.order(synthetic=True)
        deposit = self.deposit(synthetic=True)
        self.register.allocate(deposit['deposit_id'], order['order_id'])
        with self.assertRaises(ValueError): self.register.post(deposit['deposit_id'], self.bank())
        real = self.deposit('real')
        with self.assertRaises(ValueError): self.register.allocate(real['deposit_id'], order['order_id'])
        projection = self.project(self.root)
        self.assertEqual(projection['orders_count'], 0)
        self.assertEqual(projection['bank_confirmed_deposits_count'], 1)
        self.assertEqual(projection['treasury_posted_cad_cents'], 0)

    def test_foreign_currency_cannot_post(self):
        order, deposit = self.order(currency='USD'), self.deposit(currency='USD')
        self.register.allocate(deposit['deposit_id'], order['order_id'])
        with self.assertRaises(ValueError): self.register.post(deposit['deposit_id'], self.bank())

    def test_halted_and_extinct_states_are_preserved(self):
        for state in ('HALTED', 'EXTINCT'):
            with self.subTest(state=state):
                order, deposit = self.order(state), self.deposit(state)
                self.accept(order)
                self.register.allocate(deposit['deposit_id'], order['order_id'])
                bank = self.bank()
                with closing(sqlite3.connect(bank.db_path)) as db:
                    db.execute('UPDATE treasury SET state=? WHERE id=1', (state,))
                    db.commit()
                if state == 'EXTINCT':
                    with self.assertRaises(ValueError): self.register.post(deposit['deposit_id'], bank)
                else:
                    self.register.post(deposit['deposit_id'], bank)
                self.assertEqual(bank.snapshot()['state'], state)

    def test_projection_contains_only_aggregates_and_no_private_identifiers(self):
        order, deposit = self.order(), self.deposit()
        self.register.record_claim(order['order_id'], 'private-claim-source', 1000, 'CAD')
        projection = self.project(self.root)
        self.assertEqual(projection['state'], 'AVAILABLE')
        self.assertEqual(projection['claimed_orders_count'], 1)
        self.assertEqual(projection['unallocated_deposits_count'], 1)
        encoded = json.dumps(projection)
        for private in ('private-customer', 'dedicated-account', 'transfer-1', 'private-claim-source', order['order_id'], deposit['deposit_id']):
            self.assertNotIn(private, encoded)

    def test_missing_and_corrupt_projection_is_unavailable_without_creation(self):
        missing = self.root / 'missing'
        self.assertEqual(self.project(missing)['state'], 'UNAVAILABLE')
        self.assertFalse(missing.exists())
        self.path.write_bytes(b'not a database: private content')
        self.assertEqual(self.project(self.root)['state'], 'UNAVAILABLE')
        with self.assertRaises((ValueError, sqlite3.Error)): self.Register(self.root)

    def test_semantically_corrupt_rows_make_projection_unavailable(self):
        self.order()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('PRAGMA ignore_check_constraints=ON')
            db.execute("UPDATE orders SET amount_cents=-1")
            db.commit()
        self.assertEqual(self.project(self.root)['state'], 'UNAVAILABLE')

    def test_malformed_schema_and_injected_private_order_id_fail_closed(self):
        from scripts.orders import case_orders
        order = self.order()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE orders SET order_id='private@example.test'")
            db.commit()
        self.assertEqual(self.project(self.root)['state'], 'UNAVAILABLE')
        self.assertEqual(case_orders(self.root, 'private-customer-case')['state'], 'UNAVAILABLE')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE orders SET order_id=?', (order['order_id'],))
            db.execute('ALTER TABLE orders RENAME COLUMN amount_cents TO wrong_column')
            db.commit()
        self.assertEqual(self.project(self.root)['state'], 'UNAVAILABLE')

    def test_default_post_uses_private_bank_and_partial_credit_stays_partial(self):
        order, deposit = self.order(), self.deposit(amount=400)
        self.accept(order)
        self.register.allocate(deposit['deposit_id'], order['order_id'])
        result = self.register.post(deposit['deposit_id'])
        self.assertEqual(result['treasury_status'], 'TREASURY_POSTED')
        self.assertEqual(self.bank().snapshot()['cash_cents'], 400)
        self.assertEqual(self.register.get_order(order['order_id'])['payment_status'], 'PARTIAL')

    def test_exact_verifier_cannot_be_borrowed_for_other_evidence_and_is_restored(self):
        order, deposit = self.order(), self.deposit()
        self.accept(order)
        self.register.allocate(deposit['deposit_id'], order['order_id'])
        bank = self.bank()
        previous = bank.verifier
        credit = bank.credit
        def inspect(receipt):
            altered = dict(receipt, amount_cents=1001)
            with self.assertRaises(ValueError): credit(altered)
            return credit(receipt)
        bank.credit = inspect
        self.register.post(deposit['deposit_id'], bank)
        self.assertIs(bank.verifier, previous)
        self.assertEqual(bank.snapshot()['cash_cents'], 1000)

    def test_sidecar_hardlink_is_rejected(self):
        original = self.root / 'sidecar-source'
        original.write_bytes(b'private')
        original.chmod(0o600)
        os.link(original, Path(str(self.path) + '-journal'))
        self.assertEqual(self.project(self.root)['state'], 'UNAVAILABLE')
        with self.assertRaises(ValueError): self.Register(self.root)

    def test_symlinked_register_is_rejected(self):
        original = self.root / 'original.sqlite3'
        self.path.rename(original)
        try:
            self.path.symlink_to(original)
        except OSError:
            self.skipTest('host does not permit creating symlinks')
        self.assertEqual(self.project(self.root)['state'], 'UNAVAILABLE')
        with self.assertRaises(ValueError): self.Register(self.root)

    @unittest.skipIf(os.name == 'nt', 'POSIX permission contract')
    def test_public_permissions_fail_closed(self):
        self.path.chmod(0o644)
        self.assertEqual(self.project(self.root)['state'], 'UNAVAILABLE')
        with self.assertRaises(ValueError): self.Register(self.root)

    def test_hardlinked_database_is_rejected(self):
        alias = self.root / 'alias'
        os.link(self.path, alias)
        self.assertEqual(self.project(self.root)['state'], 'UNAVAILABLE')
        with self.assertRaises(ValueError): self.Register(self.root)

    def test_invalid_evidence_and_authority_are_rejected(self):
        for kwargs in ({'attested_by': 'AGENT'}, {'amount': True}, {'amount': 0},
                       {'amount': 2**63}, {'reference': ''}, {'currency': 'cad'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.deposit(**kwargs)
        for observed_at in ('yesterday', '2026-11-07T12:00:00'):
            with self.assertRaises(ValueError):
                self.register.confirm_deposit('account', 'ref', 100, 'CAD', observed_at, 'b' * 64)
        with self.assertRaises(ValueError):
            self.register.confirm_deposit('account', 'ref', 100, 'CAD', '2026-11-07T12:00:00Z', 'bad-digest')

    def test_aggregate_amounts_cannot_exceed_integer_accounting_bound(self):
        self.order(amount=2**63 - 1)
        with self.assertRaises(ValueError): self.order('overflow', amount=1)
        self.deposit(amount=2**63 - 1)
        with self.assertRaises(ValueError): self.deposit('overflow', amount=1)
        self.assertEqual(self.project(self.root)['orders_count'], 1)
        self.assertEqual(self.project(self.root)['bank_confirmed_deposits_count'], 1)

    def test_projection_states_attestation_authority(self):
        projection = self.project(self.root)
        self.assertEqual(projection['evidence_authority'], 'FOUNDER_ATTESTATION')
        self.assertFalse(projection['bank_api_verified'])


if __name__ == '__main__':
    unittest.main()
