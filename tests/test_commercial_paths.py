"""Commercial path facts and public-only next-decision wiring, never market proof."""
import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch


class PathProjectionTests(unittest.TestCase):
    def paths(self, capabilities, bank):
        import tools
        self.assertTrue(callable(getattr(tools, 'commercial_paths', None)), 'commercial path projection missing')
        return tools.commercial_paths(capabilities, bank)

    def capabilities(self):
        return {k: {'state': s} for k, s in {
            'FETCH': 'BUILT_IN', 'EXEC': 'CONFIGURED_UNVERIFIED', 'PUBLISH_SITE': 'CONFIGURED_UNVERIFIED',
            'PUBLISH_ACTOR': 'CONFIGURED_UNVERIFIED', 'ACTOR_STATS': 'CONFIGURED_UNVERIFIED',
            'SPEND': 'NOT_CONFIGURED', 'RECONCILE': 'NOT_CONFIGURED', 'PRIVATE_MAIL': 'CONFIGURED_UNVERIFIED'}.items()}

    def test_unfunded_keeps_possible_work_without_inventing_collection_or_listing_permission(self):
        caps = self.capabilities()
        caps['PRIVATE_MAIL']['fulfillment'] = {'state': 'CONFIGURED_UNVERIFIED'}
        view = self.paths(caps, {'state': 'UNFUNDED'})
        paths = view['paths']
        self.assertEqual(view['work_state'], 'CONTINUE_WITH_AVAILABLE_TOOLS')
        self.assertEqual(paths['public_research']['state'], 'BUILT_IN')
        self.assertEqual(paths['offline_build']['state'], 'CONFIGURED_UNVERIFIED')
        self.assertEqual(paths['public_publication']['state'], 'CONFIGURED_UNVERIFIED')
        self.assertEqual(paths['private_fulfillment']['state'], 'CONFIGURED_UNVERIFIED')
        self.assertEqual(paths['marketplace_listing']['public_permission'], 'UNKNOWN_HOST_GATE')
        self.assertEqual(paths['collection']['state'], 'NOT_IMPLEMENTED')
        self.assertEqual(paths['collection']['platform_managed_monetization'], 'NOT_ASSESSED')
        self.assertEqual(paths['outgoing_acquisition']['state'], 'NOT_IMPLEMENTED')
        self.assertEqual(view['spend_prerequisite_state'], 'NOT_CONFIGURED')
        self.assertEqual(view['service_costs'], 'UNKNOWN')

    def test_projection_is_pure_bounded_and_drops_all_unrecognized_private_data(self):
        caps = self.capabilities()
        caps['FETCH'].update(missing=['PRIVATE-SENTINEL'], constraints='PRIVATE-SENTINEL')
        caps['PRIVATE_MAIL'].update(last_cycle={'body': 'PRIVATE-SENTINEL'}, fulfillment={'state': 'PRIVATE-SENTINEL'})
        caps['SPEND']['state'] = 'PRIVATE-SENTINEL'
        caps.update({('PRIVATE-SENTINEL' + str(n)): {'state': 'PRIVATE-SENTINEL'} for n in range(1000)})
        import tools
        self.assertTrue(callable(getattr(tools, 'commercial_paths', None)), 'commercial path projection missing')
        with patch('builtins.open', side_effect=AssertionError('no I/O')), \
             patch('pathlib.Path.read_text', side_effect=AssertionError('no I/O')), \
             patch('socket.create_connection', side_effect=AssertionError('no network')), \
             patch('subprocess.run', side_effect=AssertionError('no subprocess')):
            result = tools.commercial_paths(caps, {'state': 'UNFUNDED', 'reason': 'PRIVATE-SENTINEL'})
        public = json.dumps(result)
        self.assertNotIn('PRIVATE-SENTINEL', public)
        self.assertLess(len(public), 9000)
        self.assertEqual(len(result['paths']), 9)
        self.assertEqual(result['spend_prerequisite_state'], 'UNKNOWN')
        self.assertEqual(result['paths']['private_fulfillment']['state'], 'UNKNOWN')

    def test_ready_interac_is_visible_without_inventing_autonomous_checkout(self):
        caps = self.capabilities()
        caps['PRIVATE_MAIL']['order_payments'] = {
            'state': 'READY_FOR_INSTRUCTIONS', 'method': 'INTERAC', 'currency': 'CAD',
            'order_creation': 'ADMINISTRATIVE', 'contract_acceptance': 'NOT_AUTOMATED',
            'settlement_verification': 'FOUNDER_REQUIRED', 'bank_api_connected': False,
            'recipient_email': 'PRIVATE-SENTINEL', 'account_alias': 'PRIVATE-SENTINEL'}
        view = self.paths(caps, {'state': 'UNFUNDED'})
        collection = view['paths']['collection']
        self.assertEqual(collection['state'], 'ADMINISTRATIVE')
        self.assertEqual(collection['payment_instructions'], 'READY_FOR_INSTRUCTIONS')
        self.assertEqual(collection['order_acceptance'], 'NOT_AUTOMATED')
        self.assertEqual(collection['settlement_verification'], 'FOUNDER_REQUIRED')
        self.assertFalse(collection['bank_api_connected'])
        self.assertNotIn('PRIVATE-SENTINEL', json.dumps(view))
        self.assertNotIn('Missing collection blocks paid order acceptance', view['constraints'])

    def test_order_route_states_and_stopped_world_do_not_invent_ready_instructions(self):
        for route_state in ('UNAVAILABLE', 'CONFIGURING', 'READY_FOR_INSTRUCTIONS', 'PRIVATE-SENTINEL'):
            caps = self.capabilities()
            caps['PRIVATE_MAIL']['order_payments'] = {'state': route_state}
            for treasury in ('UNFUNDED', 'HALTED', 'EXTINCT'):
                with self.subTest(route=route_state, treasury=treasury):
                    collection = self.paths(caps, {'state': treasury})['paths']['collection']
                    self.assertEqual(collection['payment_instructions'],
                        route_state if route_state != 'PRIVATE-SENTINEL' else 'UNKNOWN')
                    self.assertEqual(collection['state'], 'STOPPED' if treasury != 'UNFUNDED' else
                        'ADMINISTRATIVE' if route_state == 'READY_FOR_INSTRUCTIONS' else
                        route_state if route_state != 'PRIVATE-SENTINEL' else 'UNKNOWN')
                    self.assertNotIn('PRIVATE-SENTINEL', json.dumps(collection))

    def test_stopped_and_unknown_treasury_are_explicit_and_unknown_capabilities_do_not_become_available(self):
        for state in ('HALTED', 'EXTINCT'):
            view = self.paths(self.capabilities(), {'state': state})
            self.assertEqual(view['work_state'], 'STOPPED')
            self.assertEqual(view['paths']['offline_build']['state'], 'STOPPED')
        view = self.paths({}, {'state': 'PRIVATE-SENTINEL'})
        self.assertEqual(view['treasury_state'], 'UNKNOWN')
        self.assertEqual(view['work_state'], 'UNKNOWN')
        self.assertEqual(view['paths']['public_research']['state'], 'UNKNOWN')


class CommercialDecisionWiringTests(unittest.TestCase):
    def setUp(self):
        from world import World
        from treasury import Treasury
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.world = World(self.root / 'world.db'); self.world.bootstrap()
        self.bank = Treasury(self.root / 'bank.db')
        self.config = {'controller': {'mode': 'subscriptions', 'providers': ['claude'],
            'subscriptions_confirmed': True, 'extra_usage_disabled': True, 'image': 'brain@sha256:' + '1' * 64},
            'executor_enabled': True, 'executor_image': 'node@sha256:' + '1' * 64,
            'cloudflare': {'enabled': True, 'account_id': 'a' * 32},
            'agentmail': {'commercial': {'enabled': True}}}

    def test_confirmed_route_reaches_status_and_director_without_crediting_funds(self):
        from controller import Controller
        from tools import Toolbox
        private = self.root / 'state/private'
        private.mkdir(parents=True, exist_ok=True)
        route = private / 'payment-route.json'
        route.write_text(json.dumps(dict(version=1, state='READY_FOR_INSTRUCTIONS',
            method='INTERAC', currency='CAD', recipient_email='private@example.test',
            account_alias='PRIVATE-ACCOUNT', confirmed_at='2026-11-07T19:00:00Z',
            confirmation='FOUNDER_OBSERVED')))
        route.chmod(0o600)
        before = self.bank.snapshot()
        context = Controller(self.root, self.world, self.bank, self.config).context()
        task = dict(id='TASK-9101', type='TOOL', submitted_by='DIRECTOR',
                    created_at='2026-11-07T20:00:00Z', action='STATUS', args={},
                    estimated_cost_cad=0, approved_by=None)
        result, _ = Toolbox(self.root, self.world, self.bank, self.config).run(task)
        wire = json.loads(result['output'])
        collection = context['commercial_paths']['paths']['collection']
        self.assertEqual(collection['state'], 'ADMINISTRATIVE')
        self.assertEqual(collection, wire['commercial_paths']['paths']['collection'])
        self.assertEqual(before, self.bank.snapshot())
        self.assertFalse((private/'orders.sqlite3').exists())
        self.assertNotIn('private@example.test', json.dumps(context))
        self.assertNotIn('PRIVATE-ACCOUNT', json.dumps(wire))

    def test_status_and_context_share_paths_and_finance_changes_no_checkout_or_revenue(self):
        from controller import Controller
        from tools import Toolbox
        token = self.root / 'credentials/cloudflare/token'; token.parent.mkdir(parents=True)
        token.write_text('PRIVATE-TOKEN-SENTINEL'); token.chmod(0o600)
        self.config['private_sentinel'] = 'PRIVATE-CONFIG-SENTINEL'
        task = dict(id='TASK-9100', type='TOOL', submitted_by='DIRECTOR', created_at='2026-11-05T00:00:00Z',
                    action='STATUS', args={}, estimated_cost_cad=0, approved_by=None)
        def observe():
            with patch('pathlib.Path.read_bytes', side_effect=AssertionError('no token reads')):
                context = Controller(self.root, self.world, self.bank, self.config).context()
                status, _ = Toolbox(self.root, self.world, self.bank, self.config).run(task)
            wire = json.loads(status['output'])
            self.assertIn('commercial_paths', context)
            self.assertEqual(wire['commercial_paths'], context['commercial_paths'])
            return context
        before = observe()
        adapter = self.root / 'integrations/finance'; adapter.parent.mkdir()
        adapter.write_text('#!/bin/sh\nexit 0\n'); adapter.chmod(0o700)
        after = observe()
        self.assertEqual(before['commercial_paths']['paths']['public_publication']['state'], 'CONFIGURED_UNVERIFIED')
        self.assertEqual(after['capabilities']['SPEND']['state'], 'CONFIGURED_UNVERIFIED')
        self.assertEqual(after['capabilities']['RECONCILE']['state'], 'CONFIGURED_UNVERIFIED')
        self.assertEqual(after['commercial_paths']['paths']['collection'], before['commercial_paths']['paths']['collection'])
        self.assertEqual(after['commercial_paths']['paths']['outgoing_acquisition'], before['commercial_paths']['paths']['outgoing_acquisition'])
        self.assertEqual(after['treasury'], before['treasury'])
        self.assertNotIn('PRIVATE-', json.dumps(after['commercial_paths']))

    def write_observation(self, category, origin='INBOUND_UNVERIFIED'):
        import commercial
        message = dict(text='What is the price? No thanks.', extracted_text='')
        raw = dict(category=category, audience='ORDINARY', experiment_id=None,
                   evidence={'field': 'text', 'quote': 'What is the price?' if category == 'PRICE_QUESTION' else 'No thanks.'})
        normalized = commercial.normalize_observation(raw, message, {'ids': []}, origin, 'claude')
        directory = self.root / 'state/private/agentmail'; directory.mkdir(parents=True, exist_ok=True)
        source = hashlib.sha256(b'PRIVATE-INBOX\0PRIVATE-SOURCE').hexdigest()
        path = directory / (source + '.json')
        path.write_text(json.dumps(dict(state='ACCEPTED', inbox_id='PRIVATE-INBOX', message_id='PRIVATE-SOURCE', observation=normalized)))
        return path

    def test_actual_public_tick_prompt_has_feedback_paths_and_next_step_guide(self):
        from controller import Controller
        import progress
        for n, scenario in enumerate(('PRICE_QUESTION', 'REJECTION', 'PARTIAL', 'HISTORICAL', 'SYNTHETIC', 'UNAVAILABLE')):
            with self.subTest(scenario=scenario):
                path = self.write_observation('REJECTION' if scenario == 'REJECTION' else 'PRICE_QUESTION',
                                              'SYNTHETIC' if scenario == 'SYNTHETIC' else 'INBOUND_UNVERIFIED')
                if scenario == 'PARTIAL': path.write_text('{broken')
                if scenario == 'UNAVAILABLE': path.unlink(); path.parent.rmdir()
                if scenario == 'HISTORICAL':
                    a = progress.assess(self.root, self.world.snapshot(), self.bank.snapshot(), self.config)
                    progress.commit(self.root, 'HISTORICAL-BASELINE', a)
                prompts = []
                def plan(planner, provider, prompt):
                    prompts.append(prompt); return {'summary': 'Choose work from observed evidence.', 'actions': []}
                with patch.object(Controller, 'plan', plan):
                    planner = Controller(self.root, self.world, self.bank, self.config)
                    turn, _ = planner.tick(now=1800000000 + n)
                    planner.mark_published(turn)
                prompt = prompts[0]
                self.assertIn('COMMERCIAL NEXT ACTION:', prompt)
                self.assertIn('commercial_paths', prompt)
                self.assertIn('commercial_feedback', prompt)
                self.assertIn('not zero demand', prompt)
                self.assertIn('public summary', prompt)
                self.assertIn('attribution', prompt)
                self.assertIn('stable', prompt)
                self.assertNotIn('PRIVATE-INBOX', prompt)
                self.assertNotIn('PRIVATE-SOURCE', prompt)
                if scenario == 'PARTIAL': self.assertIn('"state": "PARTIAL"', prompt)
                if scenario == 'UNAVAILABLE': self.assertIn('"state": "UNAVAILABLE"', prompt)
                if scenario == 'SYNTHETIC': self.assertIn('"excluded_sources": 1', prompt)

    def test_public_next_action_guide_does_not_enter_either_private_responder(self):
        from controller import Controller
        from mail_agent import MailResponder
        from private_work import PrivateResponder
        for responder_class in (MailResponder, PrivateResponder):
            def plan(planner, provider, prompt):
                self.assertNotIn('COMMERCIAL NEXT ACTION:', prompt)
                summary = dict(action='reply', text='A private answer.')
                if responder_class is PrivateResponder: summary['artifacts'] = []
                return dict(actions=[], summary=json.dumps(summary))
            message = dict(inbox_id='private-inbox', message_id=responder_class.__name__,
                           text='A private question', **{'from': 'fixture@example.invalid'})
            with patch.object(Controller, 'plan', plan): responder_class(self.root, self.config)(message)

    def test_operational_alerts_qualify_market_outcomes_without_mandating_a_pivot(self):
        import progress
        alerts = progress.prompt_alerts(dict(alert=True, drought=True, stalled_turns=3, dry_turns=12))
        self.assertTrue(any('PROGRESS ALERT: 3' in text for text in alerts))
        self.assertTrue(any('OUTCOME ALERT: 12' in text for text in alerts))
        self.assertTrue(all('operational' in text.lower() and 'commercial success' in text.lower() for text in alerts))
        self.assertNotIn('This turn must', ' '.join(alerts))
        self.assertNotIn('pivot to a different mission', ' '.join(alerts))


if __name__ == '__main__': unittest.main()
