"""Private commercial evidence boundaries and the actual director prompt."""
import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch


CONFIG = {'agentmail': {'enabled': True, 'inbox_id': 'private-inbox',
          'inbox_address': 'city@example.test', 'commercial': {'enabled': True,
          'synthetic_senders': ['fixture@example.test']}},
          'controller': {'mode': 'subscriptions', 'providers': ['claude'],
          'subscriptions_confirmed': True, 'extra_usage_disabled': True,
          'image': 'brain@sha256:' + '1' * 64}}


class CommercialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.config = copy.deepcopy(CONFIG)
        self.message = dict(inbox_id='private-inbox', message_id='PRIVATE-SOURCE',
                            text='PRIVATE-MARKER What is the price?', labels=['received'],
                            **{'from': 'Person <buyer@example.test>'})
        status = self.root / 'work/world/status.json'
        status.parent.mkdir(parents=True)
        status.write_text(json.dumps({'missions': [{'mission_id': 'PUBLIC-EXPERIMENT'}]}))

    def commercial(self):
        self.assertIsNotNone(importlib.util.find_spec('commercial'),
                             'commercial feedback implementation is missing')
        import commercial
        return commercial

    def raw(self, **changes):
        value = dict(category='PRICE_QUESTION', audience='ORDINARY',
                     experiment_id='mission:PUBLIC-EXPERIMENT',
                     evidence={'field': 'text', 'quote': 'What is the price?'})
        value.update(changes)
        return value

    def normalize(self, **changes):
        c = self.commercial()
        return c.normalize_observation(self.raw(**changes), self.message,
                c.allowed_experiments(self.root), 'INBOUND_UNVERIFIED', 'claude')

    def record(self, observation, mid='PRIVATE-SOURCE'):
        import hashlib
        directory = self.root / 'state/private/agentmail'; directory.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(('private-inbox\0' + mid).encode()).hexdigest()
        path = directory / (name + '.json')
        value = dict(state='ACCEPTED', inbox_id='private-inbox', message_id=mid)
        if observation is not None: value['observation'] = observation
        path.write_text(json.dumps(value)); path.chmod(0o600)
        return path

    def test_grounded_categories_and_invalid_observation_stay_unknown(self):
        for category in ['PRICE_QUESTION', 'REJECTION']:
            self.assertEqual(self.normalize(category=category)['category'], category)
        for changes in [dict(category='SALE'), dict(extra='PRIVATE'),
                        dict(evidence={'field': 'subject', 'quote': 'What is the price?'}),
                        dict(evidence={'field': 'text', 'quote': 'fabricated'}),
                        dict(audience='VERIFIED')]:
            with self.subTest(changes=changes):
                self.assertEqual(self.normalize(**changes)['category'], 'UNKNOWN')
        self.assertIsNone(self.normalize(experiment_id='PRIVATE-MALICIOUS')['experiment_id'])

    def test_config_disabled_invalid_and_experiment_bounds(self):
        c = self.commercial()
        self.assertEqual(c.project(self.root, {})['state'], 'DISABLED')
        self.config['agentmail']['commercial']['enabled'] = 'yes'
        self.assertEqual(c.project(self.root, self.config)['state'], 'UNAVAILABLE')
        sites = self.root / 'work/products/sites'; sites.mkdir(parents=True)
        for n in range(110): (sites / ('site-%03d' % n)).mkdir()
        allowed = c.allowed_experiments(self.root)
        self.assertEqual(len(allowed['ids']), 100)
        self.assertTrue(allowed['truncated'])

    def test_unique_projection_revision_and_unsafe_scan(self):
        c = self.commercial(); path = self.record(self.normalize())
        first = c.project(self.root, self.config)
        self.assertEqual(first['counts']['PRICE_QUESTION'], 1)
        self.assertEqual(first['state'], 'AVAILABLE')
        self.assertEqual(first, c.project(self.root, self.config))
        self.record(self.normalize(category='REJECTION'))
        revised = c.project(self.root, self.config)
        self.assertEqual(revised['counts']['PRICE_QUESTION'], 0)
        self.assertEqual(revised['counts']['REJECTION'], 1)
        public = json.dumps(revised)
        for marker in ['PRIVATE', 'buyer@', 'What is the price?', 'claude']:
            self.assertNotIn(marker, public)
        path.write_text('{PRIVATE broken')
        self.assertEqual(c.project(self.root, self.config)['state'], 'PARTIAL')
        path.write_bytes(b'x' * (128 * 1024 + 1))
        self.assertEqual(c.project(self.root, self.config)['state'], 'PARTIAL')
        path.unlink(); path.symlink_to(self.root / 'work/world/status.json')
        self.assertEqual(c.project(self.root, self.config)['state'], 'PARTIAL')

    def test_mail_ready_journal_and_director_prompt_no_private_leak(self):
        self.commercial()
        from controller import Controller
        from mail import Mailbox
        from private_work import PrivateResponder
        from treasury import Treasury
        from world import World
        response = dict(actions=[], summary=json.dumps(dict(action='reply', text='A private answer.',
                        artifacts=[], observation=self.raw())))
        class Client:
            def list_received(inner): return [self.message]
            def get_message(inner, mid): return copy.deepcopy(self.message)
            def reply(inner, *args): return {'message_id': 'outbound'}
        responder = PrivateResponder(self.root, self.config)
        with patch('controller.Controller.plan', return_value=response):
            result = Mailbox(self.root, self.config, Client()).cycle(responder)
        self.assertEqual(result['accepted'], 1)
        journal = next((self.root / 'state/private/agentmail').glob('*.json'))
        self.assertEqual(json.loads(journal.read_text())['observation']['category'], 'PRICE_QUESTION')
        with patch('controller.Controller.plan', side_effect=AssertionError('READY must not recompute')):
            replay = PrivateResponder(self.root, self.config)
            replay(dict(self.message, text='changed'))
            self.assertEqual(replay.last_observation['category'], 'PRICE_QUESTION')
        world = World(self.root / 'world.db'); world.bootstrap()
        bank = Treasury(self.root / 'bank.db')
        prompts = []
        def plan(planner, provider, prompt):
            prompts.append(prompt); return dict(summary='Consider evidence.', actions=[])
        with patch('controller.Controller.plan', plan):
            Controller(self.root, world, bank, self.config).tick(now=1800000000)
        self.assertIn('PRICE_QUESTION', prompts[0]); self.assertIn('unverified', prompts[0].lower())
        for marker in ['PRIVATE-MARKER', 'PRIVATE-SOURCE', 'buyer@', 'What is the price?']:
            self.assertNotIn(marker, prompts[0])
        self.assertEqual(bank.snapshot()['revenue_cents'], 0)

    def test_synthetic_host_override_and_malformed_optional_reply_survives(self):
        c = self.commercial()
        from private_work import PrivateResponder
        self.message['from'] = 'Fixture <fixture@example.test>'
        response = dict(actions=[], summary=json.dumps(dict(action='reply', text='Useful answer',
                         artifacts=[], observation=self.raw())))
        responder = PrivateResponder(self.root, self.config)
        with patch('controller.Controller.plan', return_value=response):
            self.assertIn('Useful answer', responder(self.message)['text'])
        self.assertEqual(responder.last_observation['origin'], 'SYNTHETIC')
        self.record(responder.last_observation)
        self.assertEqual(c.project(self.root, self.config)['counts']['PRICE_QUESTION'], 0)
        self.message['message_id'] = 'another'
        response['summary'] = json.dumps(dict(action='reply', text='Still valid', artifacts=[], observation=['bad']))
        with patch('controller.Controller.plan', return_value=response):
            self.assertIn('Still valid', responder(self.message)['text'])
        self.assertEqual(responder.last_observation['category'], 'UNKNOWN')

    def test_progress_remembers_all_sources_across_missing_and_partial_scans(self):
        self.commercial(); path = self.record(self.normalize(category='UNKNOWN', evidence=None))
        import progress
        world = {'missions': [{'mission_id': 'M', 'status': 'RUNNING'}]}; bank = {'revenue_cents': 0}
        def turn(n):
            a = progress.assess(self.root, world, bank, self.config)
            progress.commit(self.root, 'THINK-' + str(n), a); return a
        turn(0)
        self.assertEqual(turn(1)['commercial_turns'], 1)
        saved = path.read_text(); path.unlink()
        self.assertIsNone(turn(2)['commercial_turns'])
        path.write_text(saved)
        self.record(self.normalize())
        world['missions'][0]['status'] = 'COMPLETED'
        a = turn(3)
        self.assertGreater(a['commercial_turns'], 0)
        self.assertEqual(a['revenue_turns'], 3)
        self.assertFalse(a['new_commercial_feedback'])
        self.record(self.normalize(), mid='new-source')
        self.assertEqual(turn(4)['commercial_turns'], 0)
        self.assertEqual(turn(5)['commercial_turns'], 1)

    def test_tool_free_ready_and_mixed_batch_never_reuse_previous_observation(self):
        self.commercial()
        from mail_agent import MailResponder
        from mail import Mailbox
        from private_work import PrivateDeferred
        response = dict(actions=[], summary=json.dumps(dict(action='reply', text='Answer',
                         observation=self.raw())))
        responder = MailResponder(self.root, self.config)
        with patch('controller.Controller.plan', return_value=response):
            responder(self.message)
        with patch('controller.Controller.plan', side_effect=AssertionError('no extra computation')):
            replay = MailResponder(self.root, self.config)
            replay(dict(self.message, text='changed'))
        self.assertEqual(replay.last_observation['category'], 'PRICE_QUESTION')
        self.message['message_id'] = 'second'
        invalid = dict(actions=[], summary=json.dumps(dict(action='reply', text='Valid reply', observation={})))
        with patch('controller.Controller.plan', return_value=invalid): responder(self.message)
        self.assertEqual(responder.last_observation['category'], 'UNKNOWN')
        self.message['message_id'] = 'third'
        with patch('controller.Controller.plan', side_effect=ValueError('failed')):
            with self.assertRaises(ValueError): responder(self.message)
        self.assertIsNone(responder.last_observation)
        # A filtered case never consumes the previous responder's side channel.
        messages = [dict(self.message, message_id='ignored', headers={'Auto-Submitted': 'auto-generated'})]
        class Client:
            def list_received(inner): return messages
            def get_message(inner, mid): return messages[0]
        responder.last_observation = self.normalize()
        Mailbox(self.root, self.config, Client()).cycle(responder)
        record = json.loads(next((self.root / 'state/private/agentmail').glob('*.json')).read_text())
        self.assertNotIn('observation', record)

    def test_partial_scan_remembers_unknown_sources_and_rejects_corrupt_normalized_data(self):
        c = self.commercial()
        self.record(self.normalize(category='UNKNOWN', evidence=None))
        broken = self.record(self.normalize(), mid='broken')
        value = json.loads(broken.read_text()); value['observation']['evidence'] = {'quote': 'private'}
        broken.write_text(json.dumps(value))
        self.assertEqual(c.project(self.root, self.config)['state'], 'PARTIAL')
        self.assertEqual(c.project(self.root, self.config)['counts']['PRICE_QUESTION'], 0)

    def test_no_observation_and_disabled_mode_preserve_legacy_reply(self):
        self.commercial()
        from mail_agent import MailResponder
        self.config['agentmail']['commercial']['enabled'] = False
        def plan(planner, provider, prompt):
            self.assertNotIn('Optionally add observation', prompt)
            return dict(actions=[], summary=json.dumps(dict(action='reply', text='Legacy reply')))
        responder = MailResponder(self.root, self.config)
        with patch('controller.Controller.plan', plan):
            self.assertIn('Legacy reply', responder(self.message)['text'])
        self.assertIsNone(responder.last_observation)
        self.assertFalse((self.root / 'state/private/fulfillment').exists())


if __name__ == '__main__': unittest.main()
