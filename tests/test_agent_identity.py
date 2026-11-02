"""Tool effects must belong to a live resident, including WORLD mutations."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from tools import Toolbox
from treasury import Treasury
from world import World


class AgentIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.world = World(self.root / 'world.db')
        self.world.bootstrap()
        self.bank = Treasury(self.root / 'bank.db')
        self.box = Toolbox(self.root, self.world, self.bank)
        self.sequence = 9000

    def task(self, agent='BUILDER', action='WORLD', **args):
        self.sequence += 1
        return dict(id='TASK-%d' % self.sequence, type='TOOL', submitted_by=agent,
                    created_at='2026-11-02T00:00:00Z', action=action, args=args,
                    estimated_cost_cad=0, approved_by=None)

    def test_resident_cannot_impersonate_another_in_world(self):
        for args in [dict(op='transfer_glc', from_agent='DIRECTOR', to_agent='BUILDER', amount=1),
                     dict(op='message', from_agent='DIRECTOR', to_agent='AUDITOR', body='forged'),
                     dict(op='claim_mission', mission_id='WORLD-FIRST-REVENUE', agent_id='DIRECTOR'),
                     dict(op='record_lesson', agent_id='DIRECTOR', lesson='forged'),
                     dict(op='review', reviewer='AUDITOR', subject='site:x', digest='a' * 64, verdict='APPROVE')]:
            with self.subTest(op=args['op']):
                before = self.world.snapshot()
                with self.assertRaisesRegex(ValueError, 'actor'):
                    self.box.run(self.task(**args))
                self.assertEqual(self.world.snapshot(), before)

    def test_economy_and_registration_require_director(self):
        for args in [dict(op='register_agent', agent_id='NEW', role='builder'),
                     dict(op='set_policy', maintenance_glc=0, interest_basis_points=0),
                     dict(op='reward_glc', agent_id='BUILDER', amount=100, evidence=['claimed']),
                     dict(op='cycle', cycle_id='forced')]:
            with self.subTest(op=args['op']), self.assertRaisesRegex(ValueError, 'DIRECTOR'):
                self.box.run(self.task(**args))

    def test_valid_transfer_and_host_administration_remain_possible(self):
        result, _ = self.box.run(self.task(op='transfer_glc', from_agent='BUILDER', to_agent='RESEARCHER', amount=5))
        self.assertEqual(json.loads(result['output']), {'transferred_glc': 5})
        self.world.apply('admin', dict(op='set_policy', maintenance_glc=0, interest_basis_points=0))
        self.assertEqual(self.world.snapshot()['policy']['maintenance_glc'], 0)

    def test_idempotency_key_is_bound_to_actor_too(self):
        args = dict(op='create_mission', mission_id='OWN', goal='Evidence')
        first = self.world.apply('bound', args, actor='BUILDER')
        self.assertEqual(self.world.apply('bound', args, actor='BUILDER'), first)
        with self.assertRaisesRegex(ValueError, 'bound'):
            self.world.apply('bound', args, actor='RESEARCHER')

    def test_malformed_operation_is_a_correctable_protocol_rejection(self):
        for op in ([], {}, None, 7):
            with self.subTest(op=op), self.assertRaisesRegex(ValueError, 'Unknown operation'):
                self.box.run(self.task(op=op))

    def test_new_residents_have_an_identity_the_tool_protocol_accepts(self):
        for agent_id in ('worker.one', 'worker', 'AGENT:ONE', 'A' * 65):
            with self.subTest(agent_id=agent_id), self.assertRaisesRegex(ValueError, 'agent ID'):
                self.box.run(self.task(agent='DIRECTOR', op='register_agent', agent_id=agent_id, role='Build'))
        self.box.run(self.task(agent='DIRECTOR', op='register_agent', agent_id='HELPER_1', role='Build'))
        result, _ = self.box.run(self.task(agent='HELPER_1', op='create_mission', mission_id='NEW-WORK', goal='Build'))
        self.assertEqual(result['status'], 'DONE')

    def test_disabled_and_unknown_residents_cannot_reach_any_effect(self):
        self.world.apply('policy', dict(op='set_policy', maintenance_glc=100, interest_basis_points=0))
        self.world.apply('cycle', dict(op='cycle', cycle_id='disable'))
        cases = [('EXEC', dict(argv=['node', '-p', '1'])),
                 ('FETCH', dict(url='https://example.com/', output='products/x.txt')),
                 ('SPEND', dict(request={})), ('RECONCILE', dict(operation_id='TASK-0001')),
                 ('PUBLISH_SITE', dict(site='x')), ('PUBLISH_ACTOR', dict(actor='x', title='X', description='X')),
                 ('ACTOR_STATS', dict(actor='x')), ('WORLD', dict(op='create_mission', mission_id='X', goal='X'))]
        with patch('tools.fetch_public') as fetch, patch('tools.bounded_run') as execute, patch('gateway.Gateway') as gateway:
            for agent in ('BUILDER', 'UNKNOWN'):
                for action, args in cases:
                    with self.subTest(agent=agent, action=action), self.assertRaisesRegex(ValueError, 'Agent disabled|Unknown agent_id'):
                        self.box.run(self.task(agent=agent, action=action, **args))
            fetch.assert_not_called()
            execute.assert_not_called()
            gateway.assert_not_called()
        # Observation remains available after liquidation.
        result, _ = self.box.run(self.task(action='STATUS'))
        self.assertEqual(result['status'], 'DONE')


if __name__ == '__main__':
    unittest.main()
