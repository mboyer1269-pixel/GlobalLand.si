"""Financial notice suppression is a routing safeguard, never payment evidence."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from scripts.mail import Mailbox


def message(sender='customer@example.test', **changes):
    value = dict(message_id='incoming', inbox_id='city@example.test',
                 labels=['received'], headers={}, text='Can I pay by Interac?',
                 subject='Payment question', **{'from': sender})
    value.update(changes)
    return value


class Transport:
    """No credentials, HTTP, mail delivery or banking integration."""
    def __init__(self, incoming):
        self.incoming = incoming
        self.posts = []

    def list_received(self):
        return [dict(message_id='incoming')]

    def get_message(self, mid):
        return copy.deepcopy(self.incoming)

    def reply(self, *args, **kwargs):
        self.posts.append((args, kwargs))
        return dict(message_id='outbound')


class FinancialHoldTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = {'agentmail': {'enabled': True, 'inbox_id': 'city@example.test',
                                    'inbox_address': 'city@example.test'}}
        self.transport = Transport(message())
        self.box = Mailbox(self.root, self.config, self.transport)
        self.responder = Mock(return_value=dict(action='reply', text='Reply'))

    def receipt(self):
        return json.loads(self.box._path('incoming').read_text())

    def assert_held(self):
        result = self.box.cycle(self.responder)
        self.assertEqual(result['ignored'], 1, result)
        self.assertEqual(self.receipt()['hold_reason'], 'FINANCIAL_NOTICE')
        self.assertNotIn('observation', self.receipt())
        self.assertEqual(self.transport.posts, [])
        self.assertFalse((self.root / 'state/private/treasury.sqlite3').exists())

    def test_financial_sender_never_reaches_responder(self):
        for sender in ('catch@payments.interac.ca', 'notice@interac.ca',
                       'notice@catch.payments.interac.com', 'support@wealthsimple.com',
                       'notice@o.wealthsimple.com', 'Notice@O.WEALTHSIMPLE.COM'):
            with self.subTest(sender=sender):
                self.transport.incoming = message(sender, authentication_results={'dmarc': 'pass'})
                self.assert_held()
                self.responder.assert_not_called()
                self.box._path('incoming').unlink()

    def test_reply_to_financial_provider_is_held(self):
        self.transport.incoming = message(reply_to=['catch@payments.interac.ca'])
        self.assert_held()
        self.responder.assert_not_called()

    def test_customer_payment_questions_and_domain_boundaries_are_not_held(self):
        for sender in ('customer@example.test', 'customer@notwealthsimple.com',
                       'customer@wealthsimple.com.example.test',
                       'customer@notinterac.ca', 'customer@interac.ca.example.test'):
            with self.subTest(sender=sender):
                self.transport.incoming = message(sender)
                self.assertEqual(self.box.cycle(self.responder)['accepted'], 1)
                self.box._path('incoming').unlink()
        self.assertEqual(len(self.transport.posts), 5)

    def test_retry_with_saved_reply_is_held_before_responder(self):
        self.box._prepare()
        self.box._save(self.box._path('incoming'), dict(message_id='incoming',
            inbox_id='city@example.test', state='RETRY', attempts=1, retry_after=0,
            observation={'untrusted': 'old claim'}))
        self.transport.incoming = message('catch@payments.interac.ca')
        self.assert_held()
        self.responder.assert_not_called()
        self.assertEqual(self.box.cycle(self.responder)['accepted'], 0)

    def test_legacy_saved_reply_rechecks_financial_route_before_send(self):
        # Models may return a previously saved READY decision; the host must
        # refresh routing even without a continuity completion descriptor.
        def saved_reply(incoming):
            self.transport.incoming = message('catch@payments.interac.ca')
            return dict(action='reply', text='Previously saved reply')
        self.responder.side_effect = saved_reply
        self.assert_held()
        self.responder.assert_called_once()

    def test_continuity_reply_rechecks_before_send(self):
        self.responder.last_completion = {'opaque': 'private-completion'}
        def saved_reply(incoming, **kwargs):
            self.transport.incoming = message(reply_to=['notice@o.wealthsimple.com'])
            return dict(action='reply', text='Previously saved reply')
        self.responder.side_effect = saved_reply
        with patch('continuity.prepare', return_value={'state': 'ELIGIBLE'}), \
             patch('continuity.verify_completion', return_value={'to': ['customer@example.test']}):
            self.assert_held()


if __name__ == '__main__':
    unittest.main()
