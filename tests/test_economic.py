"""Economic facts stay distinct from cash authority and unknown costs."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from treasury import MAX_CENTS, Treasury


class EconomicFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'state/private').mkdir(parents=True)
        self.path = self.root / 'state/private/treasury.sqlite3'
        self.bank = Treasury(self.path, verifier=lambda r: True, clock=lambda: 1000)

    def receipt(self, event, amount, kind, **extra):
        return dict(provider='PRIVATE-PROVIDER', account='PRIVATE-ACCOUNT', event_id=event,
                    amount_cents=amount, kind=kind, currency='CAD', settled=True,
                    private_reference='PRIVATE-REFERENCE', **extra)

    def fixture(self):
        self.funding = self.receipt('PRIVATE-FUNDING', 5000, 'FUNDING')
        self.revenue = self.receipt('PRIVATE-REVENUE', 1000, 'REVENUE')
        self.spend = self.receipt('PRIVATE-SPEND', 250, 'SPEND', purpose='investment')
        self.refund = self.receipt('PRIVATE-REFUND', 50, 'REFUND')
        self.reversal = self.receipt('PRIVATE-REVERSAL', 100, 'REVERSAL')
        self.bank.confirm_funding(self.funding)
        self.bank.credit(self.revenue)
        self.bank.reserve('PRIVATE-OPERATION', 400, 'PRIVATE-REQUEST')
        self.bank.mark_submitted('PRIVATE-OPERATION')
        self.bank.settle('PRIVATE-OPERATION', self.spend)
        self.bank.credit(self.refund)
        self.bank.reverse(self.reversal)
        self.bank.reserve('PRIVATE-HELD', 200, 'PRIVATE-REQUEST-HELD')
        self.bank.reserve('PRIVATE-UNKNOWN', 300, 'PRIVATE-REQUEST-UNKNOWN')
        self.bank.mark_submitted('PRIVATE-UNKNOWN')

    def sql(self, query, args=()):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(query, args)

    def dump(self):
        with closing(sqlite3.connect(self.path)) as db:
            return list(db.iterdump())

    def assert_journal_unavailable(self, result):
        journal = result['journal']
        self.assertEqual(journal['state'], 'UNAVAILABLE')
        self.assertIsNone(journal['history_coverage'])
        for key in ('known_funding_cents', 'known_revenue_credits_cents',
                    'known_spend_debits_cents', 'known_expense_refunds_cents',
                    'known_customer_reversals_cents'):
            self.assertIsNone(journal[key])


class EconomicTreasuryTests(EconomicFixture):
    def test_cash_gross_revenue_and_unresolved_commitments_are_distinct(self):
        self.fixture()
        result = self.bank.economic_snapshot()
        self.assertEqual(result['snapshot'], self.bank.snapshot())
        snap, journal = result['snapshot'], result['journal']
        self.assertEqual((snap['cash_cents'], snap['available_cents'], snap['reserved_cents'],
                          snap['revenue_cents']), (5700, 5200, 500, 900))
        self.assertEqual(journal, dict(state='AVAILABLE', history_coverage='UNKNOWN',
            coverage_reason='NO_COMPLETENESS_MARKER', known_funding_cents=5000,
            known_revenue_credits_cents=1000, known_spend_debits_cents=250,
            known_expense_refunds_cents=50, known_customer_reversals_cents=100))
        self.assertEqual(result['commitments'], dict(state='AVAILABLE', held_cents=200, unknown_cents=300))

    def test_restart_replay_actual_debit_positions_and_releases(self):
        self.fixture()
        before = self.bank.economic_snapshot()
        self.bank = Treasury(self.path, verifier=lambda r: True, clock=lambda: 1000)
        self.bank.confirm_funding(self.funding)
        self.bank.credit(self.revenue)
        self.bank.settle('PRIVATE-OPERATION', self.spend)
        self.bank.credit(self.refund)
        self.bank.reverse(self.reversal)
        self.assertEqual(self.bank.economic_snapshot(), before)
        self.bank.record_positions(self.receipt('positions', 250, 'POSITIONS'))
        self.bank.reserve('cancel', 20, 'h')
        self.bank.release('cancel', self.receipt('cancelled', 0, 'CANCELLED'))
        self.bank.reserve('free', 0, 'h')
        self.bank.release('free')
        after = self.bank.economic_snapshot()
        self.assertEqual(after['journal'], before['journal'])
        self.assertEqual(after['commitments'], before['commitments'])
        self.assertEqual(after['snapshot']['position_cents'], 250)

    def test_reversal_flooring_and_attestation_keep_authoritative_net(self):
        self.bank.confirm_funding(self.receipt('fund', 5000, 'FUNDING'))
        self.bank.credit(self.receipt('attested', 100, 'REVENUE', attestation='FOUNDER'))
        self.bank.reverse(self.receipt('reverse', 200, 'REVERSAL'))
        self.bank.credit(self.receipt('later', 50, 'REVENUE'))
        result = self.bank.economic_snapshot()
        self.assertEqual(result['snapshot']['revenue_cents'], 50)
        self.assertEqual(result['snapshot']['founder_attested_revenue_cents'], 100)
        self.assertEqual(result['journal']['known_revenue_credits_cents'], 150)
        self.assertEqual(result['journal']['known_customer_reversals_cents'], 200)

    def test_legacy_missing_funding_spend_or_cash_mismatch_is_incomplete(self):
        for change in ("DELETE FROM events WHERE action='FUNDING'",
                       "DELETE FROM events WHERE action='SPEND'",
                       'UPDATE treasury SET cash=cash+1'):
            with self.subTest(change=change):
                self.setUp()
                self.fixture()
                self.sql(change)
                before = self.dump()
                result = self.bank.economic_snapshot()
                self.assertEqual(result['journal']['state'], 'AVAILABLE')
                self.assertEqual(result['journal']['history_coverage'], 'INCOMPLETE')
                self.assertEqual(self.dump(), before)

    def test_consistent_missing_offsetting_history_and_empty_history_are_unknown(self):
        self.assertEqual(self.bank.economic_snapshot()['journal']['history_coverage'], 'UNKNOWN')
        self.fixture()
        self.bank.credit(self.receipt('offset-credit', 25, 'REFUND'))
        self.bank.reverse(self.receipt('offset-debit', 25, 'REVERSAL'))
        self.sql("DELETE FROM events WHERE event_id IN ('offset-credit','offset-debit')")
        self.assertEqual(self.bank.economic_snapshot()['journal']['history_coverage'], 'UNKNOWN')

    def test_bad_history_is_unavailable_without_losing_cash_or_commitments(self):
        changes = ("UPDATE events SET body='{'", "UPDATE events SET digest='wrong'",
                   "UPDATE events SET action='SPEND' WHERE action='CREDIT'",
                   "UPDATE events SET account='wrong'", "UPDATE events SET operation_id=NULL WHERE action='SPEND'",
                   'DROP TABLE events')
        for change in changes:
            with self.subTest(change=change):
                self.setUp()
                self.fixture()
                self.sql(change)
                before = self.dump()
                result = self.bank.economic_snapshot()
                self.assert_journal_unavailable(result)
                self.assertEqual(result['snapshot']['cash_cents'], 5700)
                self.assertEqual(result['commitments']['held_cents'], 200)
                self.assertEqual(result['commitments']['unknown_cents'], 300)
                self.assertEqual(self.dump(), before)

    def test_canonical_digest_does_not_excuse_invalid_receipt_types_or_uses(self):
        self.fixture()
        original = dict(self.revenue)
        for change in ({'amount_cents': True}, {'amount_cents': -1}, {'amount_cents': MAX_CENTS + 1},
                       {'currency': 'USD'}, {'settled': 1}, {'kind': 'SPEND'}, {'provider': ' '}):
            with self.subTest(change=change):
                body = json.dumps(dict(original, **change), sort_keys=True, separators=(',', ':'), allow_nan=False)
                self.sql("UPDATE events SET body=?,digest=? WHERE event_id='PRIVATE-REVENUE'",
                         (body, hashlib.sha256(body.encode()).hexdigest()))
                self.assert_journal_unavailable(self.bank.economic_snapshot())

    def test_actual_spend_can_exceed_hold_and_halt_without_disappearing(self):
        self.bank.confirm_funding(self.receipt('fund', 5000, 'FUNDING'))
        self.bank.reserve('over', 100, 'h')
        self.bank.mark_submitted('over')
        self.bank.settle('over', self.receipt('overcharge', 120, 'SPEND'))
        result = self.bank.economic_snapshot()
        self.assertEqual(result['journal']['known_spend_debits_cents'], 120)
        self.assertEqual(result['journal']['history_coverage'], 'UNKNOWN')
        self.assertEqual((result['snapshot']['state'], result['snapshot']['available_cents']), ('HALTED', 0))

    def test_maturity_floor_and_terminal_states_remain_authoritative(self):
        self.fixture()
        self.sql("INSERT INTO credits VALUES('p','a','maturing',100,2000)")
        self.bank.set_reserve_floor(50)
        result = self.bank.economic_snapshot()
        self.assertEqual((result['snapshot']['cash_cents'], result['snapshot']['available_cents']), (5700, 5050))
        for state in ('HALTED', 'EXTINCT'):
            self.sql('UPDATE treasury SET state=?', (state,))
            result = self.bank.economic_snapshot()
            self.assertEqual((result['snapshot']['state'], result['snapshot']['available_cents']), (state, 0))

    def test_lifetime_totals_use_python_integers(self):
        # Each event is bounded; lifetime gross turnover need not fit SQLite SUM.
        for number in range(2):
            self.bank.credit(self.receipt('large-credit-' + str(number), MAX_CENTS, 'REVENUE'))
            self.bank.reverse(self.receipt('large-reverse-' + str(number), MAX_CENTS, 'REVERSAL'))
        result = self.bank.economic_snapshot()
        self.assertEqual(result['journal']['known_revenue_credits_cents'], 2 * MAX_CENTS)
        self.assertEqual(result['journal']['known_customer_reversals_cents'], 2 * MAX_CENTS)
        self.assertEqual(result['journal']['history_coverage'], 'UNKNOWN')

    def test_projection_is_read_only_and_does_not_finish_or_verify(self):
        self.fixture()
        before = self.dump()
        connect = sqlite3.connect
        statements = []
        def read_only_connection(database, **options):
            self.assertTrue(database.endswith('?mode=ro'))
            self.assertIs(options.get('uri'), True)
            db = connect(database, **options)
            db.set_trace_callback(statements.append)
            return db
        with (patch.object(self.bank, '_tx', side_effect=AssertionError('write transaction')),
              patch.object(Treasury, '__init__', side_effect=AssertionError('initializer')),
              patch('treasury.sqlite3.connect', side_effect=read_only_connection),
              patch.object(self.bank, '_finish', side_effect=AssertionError('finish')),
              patch.object(self.bank, 'verifier', side_effect=AssertionError('verifier'))):
            result = self.bank.economic_snapshot()
        self.assertEqual(result['snapshot']['cash_cents'], 5700)
        self.assertEqual(statements[0], 'BEGIN')
        self.assertTrue(all(statement.startswith('SELECT ') for statement in statements[1:]))
        self.assertEqual(self.dump(), before)

    def test_snapshot_journal_and_commitments_share_one_sqlite_read(self):
        self.fixture()
        original = self.bank._view
        other = Treasury(self.path, verifier=lambda r: True, clock=lambda: 1000)
        def concurrent_change(db):
            snapshot = original(db)
            other.credit(self.receipt('concurrent', 10, 'REVENUE'))
            other.reserve('concurrent-hold', 30, 'h')
            return snapshot
        with patch.object(self.bank, '_view', side_effect=concurrent_change):
            result = self.bank.economic_snapshot()
        self.assertEqual(result['snapshot']['cash_cents'], 5700)
        self.assertEqual(result['journal']['known_revenue_credits_cents'], 1000)
        self.assertEqual(result['commitments']['held_cents'], 200)
        self.assertEqual(result['journal']['history_coverage'], 'UNKNOWN')
        self.assertEqual(self.bank.economic_snapshot()['snapshot']['cash_cents'], 5710)

    def test_authoritative_failure_propagates_without_initializing_missing_database(self):
        self.bank.db_path = self.root / 'absent.sqlite3'
        with self.assertRaises(sqlite3.OperationalError):
            self.bank.economic_snapshot()
        self.assertFalse(self.bank.db_path.exists())


@unittest.skipUnless(os.name == 'posix', 'consumer imports require POSIX fcntl/geteuid; no shim')
class EconomicConsumerTests(EconomicFixture):
    def project(self):
        import economic
        return economic.project(self.root, self.bank)

    def ledger(self, raw):
        (self.root / 'state/private/payouts.json').write_text(raw)

    def test_receivable_usd_stays_separate_and_stale_invoice_is_labelled(self):
        self.fixture()
        self.ledger('{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":2340,"reference":"PRIVATE-INVOICE"}}')
        first = self.project()
        self.assertEqual((first['snapshot']['cash_cents'], first['snapshot']['available_cents']), (5700, 5200))
        self.assertEqual(first['context']['receivables']['apify_receivable_usd_cents'], 2340)
        # A bank payout can be committed before the invoice's PAID update.
        self.bank.credit(self.receipt('apify-admitted', 3180, 'REVENUE', attestation='FOUNDER'))
        result = self.project()
        receivable = result['context']['receivables']
        self.assertEqual((result['snapshot']['cash_cents'], result['snapshot']['available_cents']), (8880, 8380))
        self.assertEqual(receivable['apify_receivable_usd_cents'], 2340)
        self.assertEqual(receivable['apify_receivable_months'], ['2026-11'])
        self.assertEqual(receivable['consistency'], 'INDEPENDENT_INVOICE_LEDGER_MAY_LAG_SETTLEMENT')
        self.assertIn('never spendable', receivable['note'])
        self.assertNotIn('PRIVATE-', json.dumps(result['context']))

    def test_missing_invalid_or_unreadable_invoice_is_unavailable_not_zero(self):
        for raw in (None, '{', '[]', '{"2026-13":{}}', '{"2026-11":false}',
                    '{"2026-11":{"status":"OTHER"}}',
                    '{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":true}}',
                    '{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":-1}}',
                    '{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":0}}',
                    '{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":10000001}}',
                    '{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":1,"invoice_usd_cents":2}}'):
            with self.subTest(raw=raw):
                if raw is not None:
                    self.ledger(raw)
                receivable = self.project()['context']['receivables']
                self.assertEqual(receivable['state'], 'UNAVAILABLE')
                self.assertIsNone(receivable['apify_receivable_usd_cents'])
                self.assertIsNone(receivable['apify_receivable_months'])
        with patch.object(Path, 'open', side_effect=PermissionError('PRIVATE-ERROR')):
            result = self.project()
        self.assertEqual(result['context']['receivables']['state'], 'UNAVAILABLE')
        self.assertNotIn('PRIVATE-ERROR', json.dumps(result))

    def test_valid_empty_and_paid_without_invoice_and_helper_does_not_reload(self):
        import payouts
        for raw in ('{}', '{"2026-11":{"status":"PAID","received_cad_cents":3000}}'):
            self.ledger(raw)
            result = self.project()['context']['receivables']
            self.assertEqual((result['state'], result['apify_receivable_usd_cents'],
                              result['apify_receivable_months']), ('AVAILABLE', 0, []))
        self.ledger('{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":2340}}')
        open_file = Path.open
        reads = []
        def invoice_read(path, *args, **options):
            reads.append(path)
            return open_file(path, *args, **options)
        with (patch('payouts.load', side_effect=AssertionError('second ledger read')),
              patch.object(Path, 'open', autospec=True, side_effect=invoice_read)):
            self.assertEqual(self.project()['context']['receivables']['apify_receivable_usd_cents'], 2340)
            self.assertEqual(payouts.receivables(self.root, entries={})['apify_receivable_usd_cents'], 0)
        self.assertEqual(reads, [self.root / 'state/private/payouts.json'])

    def test_costs_profit_subscription_periods_and_allocation_remain_unknown(self):
        costs = self.project()['context']['cost_coverage']
        for key in ('fees_cents', 'profit_cents', 'margin', 'experiment_costs'):
            self.assertIsNone(costs[key])
        self.assertEqual(costs['state'], 'UNKNOWN')
        self.assertEqual(costs['experiment_costs_state'], 'UNALLOCATED')
        for service in costs['founder_provided_services']:
            self.assertTrue(service['outside_50cad_capital'])
            self.assertEqual(service['state'], 'UNKNOWN')
            for key in ('amount', 'currency', 'period', 'allocation'):
                self.assertIsNone(service[key])
        self.assertNotIn('monthly', json.dumps(costs))

    def test_snapshot_only_double_preserves_authority_and_unavailable_details(self):
        import economic
        class SnapshotOnly:
            def snapshot(self):
                return {'state': 'UNFUNDED'}
        result = economic.project(self.root, SnapshotOnly())
        self.assertEqual(result['snapshot'], {'state': 'UNFUNDED'})
        self.assert_journal_unavailable(result['context'])
        self.assertEqual(result['context']['commitments'], dict(state='UNAVAILABLE', held_cents=None, unknown_cents=None))
        with patch.object(SnapshotOnly, 'snapshot', side_effect=ValueError('authority failed')):
            with self.assertRaisesRegex(ValueError, 'authority failed'):
                economic.project(self.root, SnapshotOnly())

    def test_director_and_status_reuse_same_pair_and_preserve_privacy(self):
        from controller import Controller
        from tools import Toolbox
        from world import World
        self.fixture()
        self.ledger('{"2026-11":{"status":"RECEIVABLE","invoice_usd_cents":2340,"reference":"PRIVATE-INVOICE"}}')
        world = World(self.root / 'world.db'); world.bootstrap()
        controller = Controller(self.root, world, self.bank, {'controller': {}})
        before = self.dump()
        # Projection consumers must not assemble the displayed pair from snapshot().
        with patch.object(self.bank, 'snapshot', side_effect=AssertionError('extra snapshot')):
            director = controller.prepare_context()['context']
        task = dict(id='TASK-0100', type='TOOL', submitted_by='DIRECTOR', created_at='2026-11-05T00:00:00Z',
                    action='STATUS', args={}, estimated_cost_cad=0, approved_by=None)
        guard = self.bank.snapshot
        calls = []
        def stop_guard_only():
            calls.append(1)
            if len(calls) > 1:
                raise AssertionError('extra display snapshot')
            return guard()
        with (patch.object(self.bank, 'snapshot', side_effect=stop_guard_only),
              patch.object(self.bank, 'verifier', side_effect=AssertionError('verifier'))):
            status, files = Toolbox(self.root, world, self.bank).run(task)
        status = json.loads(status['output'])
        self.assertEqual(status['bank'], director['treasury'])
        self.assertEqual(status['economic_context'], director['economic_context'])
        self.assertEqual(director['treasury']['cash_cents'], 5700)
        self.assertEqual(files, {})
        self.assertEqual(self.dump(), before)
        for serialized in (json.dumps(status), json.dumps(director)):
            self.assertNotIn('PRIVATE-', serialized)
            self.assertNotIn(hashlib.sha256(json.dumps(self.spend, sort_keys=True, separators=(',', ':')).encode()).hexdigest(), serialized)

    def test_status_and_director_tick_stop_guards_remain(self):
        from controller import Controller
        from tools import Toolbox
        from world import World
        self.fixture()
        world = World(self.root / 'world.db'); world.bootstrap()
        task = dict(id='TASK-0100', type='TOOL', submitted_by='DIRECTOR', created_at='2026-11-05T00:00:00Z',
                    action='STATUS', args={}, estimated_cost_cad=0, approved_by=None)
        for state in ('HALTED', 'EXTINCT'):
            self.sql('UPDATE treasury SET state=?', (state,))
            with self.assertRaisesRegex(ValueError, 'stopped'):
                Toolbox(self.root, world, self.bank).run(task)
            with self.assertRaisesRegex(ValueError, 'stopped'):
                Controller(self.root, world, self.bank, {'controller': {}}).tick(now=1800000000)


if __name__ == '__main__':
    unittest.main()
