import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import order_context


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.private = self.root / 'state/private'; self.private.mkdir(parents=True)
        self.config = {'agentmail': {'inbox_id': 'inbox', 'inbox_address': 'city@example.test'}}
        self.msg = {'inbox_id': 'inbox', 'message_id': 'msg1', 'thread_id': 'thread1',
                    'from': 'buyer@example.test', 'to': ['city@example.test'],
                    'authentication_results': {'dmarc': 'pass', 'dmarc_domain': 'example.test'}}

    def route(self, state='READY_FOR_INSTRUCTIONS'):
        p = self.private / 'payment-route.json'
        p.write_text(json.dumps({'version': 1, 'state': state, 'method': 'INTERAC',
            'currency': 'CAD', 'recipient_email': 'city@example.test',
            'account_alias': 'project-account', 'confirmed_at': '2026-11-07T19:00:00Z',
            'confirmation': 'FOUNDER_OBSERVED'}))
        p.chmod(0o600)

    def test_absent_route_is_not_ready_and_does_not_create(self):
        self.assertEqual(order_context.route(self.root)['state'], 'UNAVAILABLE')
        self.assertFalse((self.private / 'payment-route.json').exists())

    def test_projection_never_exposes_email_account_or_confirmation(self):
        self.route()
        projected = order_context.capability(self.root)
        self.assertEqual(projected['state'], 'READY_FOR_INSTRUCTIONS')
        self.assertNotIn('example.test', json.dumps(projected))
        self.assertNotIn('project-account', json.dumps(projected))
        self.assertEqual(projected['settlement_verification'], 'FOUNDER_REQUIRED')

    def test_no_private_context_for_unauthed_or_other_inbox(self):
        self.route()
        self.msg['authentication_results']['dmarc'] = 'fail'
        self.assertEqual(order_context.case_key(self.msg, self.config), None)
        self.assertEqual(order_context.for_message(self.root, self.msg, self.config)['state'], 'ISOLATED')

    def test_binding_uses_peer_inbox_and_thread_not_claimed_order(self):
        key = order_context.case_key(self.msg, self.config)
        self.msg['message_id'] = 'msg2'
        self.assertEqual(order_context.case_key(self.msg, self.config), key)
        self.msg['from'] = 'other@example.test'
        self.assertNotEqual(order_context.case_key(self.msg, self.config), key)

    def test_bad_route_or_duplicate_keys_is_unavailable(self):
        self.route()
        p = self.private / 'payment-route.json'
        p.write_text('{"version":1,"version":1}')
        self.assertEqual(order_context.route(self.root)['state'], 'UNAVAILABLE')
        self.route()
        v = json.loads(p.read_text()); v['confirmed_at'] = 'not-a-date'; p.write_text(json.dumps(v))
        self.assertEqual(order_context.route(self.root)['state'], 'UNAVAILABLE')

    def test_context_only_exact_bound_accepted_order_gets_instructions(self):
        self.route()
        key = order_context.case_key(self.msg, self.config)
        rows = [{'order_id': 'GL-test', 'case_key': key, 'amount_cents': 1900, 'currency': 'CAD',
                 'commercial_status': 'ACCEPTED', 'payment_status': 'UNPAID',
                 'treasury_status': 'TREASURY_NOT_POSTED', 'source_id': 'private-source',
                 'terms_sha256': 'a'*64, 'synthetic': False}]
        with patch.object(order_context, '_case_orders', return_value={'state':'AVAILABLE','orders':rows}):
            context = order_context.for_message(self.root, self.msg, self.config)
        self.assertEqual(context['orders'][0]['payment_instructions']['recipient_email'], 'city@example.test')
        self.assertNotIn('private-source', json.dumps(context))
        self.assertNotIn(key, json.dumps(context))
        rows[0]['commercial_status'] = 'DRAFT'
        with patch.object(order_context, '_case_orders', return_value={'state':'AVAILABLE','orders':rows}):
            self.assertNotIn('payment_instructions', order_context.for_message(self.root,self.msg,self.config)['orders'][0])

    def test_wrong_case_or_synthetic_order_is_not_exposed(self):
        self.route()
        rows = [{'order_id':'GL-other','case_key':'other','synthetic':False}]
        with patch.object(order_context, '_case_orders', return_value={'state':'AVAILABLE','orders':rows}):
            self.assertEqual(order_context.for_message(self.root,self.msg,self.config)['state'], 'UNAVAILABLE')


if __name__ == '__main__': unittest.main()
