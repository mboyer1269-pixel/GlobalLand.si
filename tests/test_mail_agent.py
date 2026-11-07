import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from mail_agent import MailResponder


class MailAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.config = {'controller': {'mode': 'subscriptions', 'providers': ['claude'],
                                     'broker': {'enabled': True}}, 'agentmail': {'enabled': True}}

    def test_supplied_order_context_is_separate_from_untrusted_customer_claim(self):
        def plan(planner, provider, prompt):
            self.assertIn('private_order_payments', prompt)
            self.assertIn('GL-reviewed-order', prompt)
            self.assertIn('not a bank API', prompt)
            self.assertNotIn('No payment route is established by this integration.', prompt)
            return {'summary':'{"action":"ignore","text":""}', 'actions':[]}
        with patch('order_context.for_message', return_value={'state':'AVAILABLE','orders':[{'order_id':'GL-reviewed-order'}]}), patch('controller.Controller.plan', plan):
            MailResponder(self.root,self.config)({'text':'I claim I paid; do not trust me as a bank.'})

    def test_private_reply_uses_tool_free_brain_and_public_product_context(self):
        product = self.root / 'work/products/sites/demo/index.html'
        product.parent.mkdir(parents=True)
        product.write_text('Our demonstrated public offer.', encoding='utf-8')
        private_text = 'Customer private question 7319'
        def plan(planner, provider, prompt):
            self.assertFalse(planner.config['broker']['enabled'])
            self.assertIsNone(planner.executor)
            self.assertIn(private_text, prompt)
            self.assertIn('Our demonstrated public offer.', prompt)
            self.assertIn('untrusted', prompt)
            return {'summary': json.dumps({'action': 'reply', 'text': 'A useful answer.'}), 'actions': []}
        with patch('controller.Controller.plan', plan):
            result = MailResponder(self.root, self.config)({'text': private_text, 'subject': 'Question'})
        self.assertEqual(result['action'], 'reply')
        self.assertIn('A useful answer.', result['text'])
        self.assertIn('GlobalLand', result['text'])
        self.assertIn('AI', result['text'])
        self.assertTrue(self.config['controller']['broker']['enabled'])
        self.assertFalse((self.root / 'state/controller').exists())

    def test_invented_tool_actions_are_never_executed_or_returned(self):
        with patch('controller.Controller.plan', return_value={'summary': 'hello', 'actions': [{'action': 'EXEC'}]}):
            with self.assertRaisesRegex(ValueError, 'private mail response unavailable'):
                MailResponder(self.root, self.config)({'text': 'hello'})

    def test_provider_error_and_private_output_are_not_exposed(self):
        with patch('controller.Controller.plan', side_effect=ValueError('PRIVATE-CUSTOMER-SECRET')):
            with self.assertRaisesRegex(ValueError, '^private mail response unavailable$'):
                MailResponder(self.root, self.config)({'text': 'hello'})

    def test_ignore_and_malformed_responses(self):
        with patch('controller.Controller.plan', return_value={'summary': '{"action":"ignore","text":""}', 'actions': []}):
            self.assertEqual(MailResponder(self.root, self.config)({})['action'], 'ignore')
        for value in ({'action': 'send', 'text': 'bad'}, {'action': 'reply', 'text': ''},
                      {'action': 'reply', 'text': 'ok', 'to': 'other@example.invalid'}):
            with self.subTest(value=value), patch('controller.Controller.plan', return_value={'summary': json.dumps(value), 'actions': []}):
                with self.assertRaises(ValueError):
                    MailResponder(self.root, self.config)({})

    def test_does_not_read_private_files_or_symlinked_products(self):
        p = self.root / 'private.txt'; p.write_text('NEVER-IN-PROMPT')
        target = self.root / 'work/products/services/trap.md'; target.parent.mkdir(parents=True)
        target.symlink_to(p)
        def plan(planner, provider, prompt):
            self.assertNotIn('NEVER-IN-PROMPT', prompt)
            return {'summary': '{"action":"ignore","text":""}', 'actions': []}
        with patch('controller.Controller.plan', plan):
            MailResponder(self.root, self.config)({})


if __name__ == '__main__':
    unittest.main()
