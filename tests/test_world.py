import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from pathlib import Path
from scripts.world import World


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'world.db'
        self.now = 1000
        self.w = World(self.path, clock=lambda: self.now)
        self.w.bootstrap()
        self.i = 0

    def tearDown(self):
        self.tmp.cleanup()

    def op(self, op, **kw):
        self.i += 1
        return self.w.apply(str(self.i), dict(op=op, **kw))

    def test_bootstrap_replay_binding(self):
        self.w.bootstrap()
        s = self.w.snapshot()
        self.assertEqual(len(s['agents']), 5)
        self.assertTrue(all(a['wallet_glc'] == a['debt_glc'] == 100 for a in s['agents']))
        self.assertEqual(s['missions'][0]['mission_id'], 'WORLD-FIRST-REVENUE')
        a = dict(op='register_agent', agent_id='NEW', role='Global researcher')
        self.assertEqual(self.w.apply('register', a), self.w.apply('register', a))
        with self.assertRaises(ValueError):
            self.w.apply('register', dict(a, role='changed'))

    def test_missions_leases_and_evidence(self):
        with self.assertRaises(ValueError):
            self.op('create_mission', mission_id='child', goal='Research', parent_id='missing')
        self.op('create_mission', mission_id='child', goal='Research', parent_id='WORLD-FIRST-REVENUE')
        lease = self.op('claim_mission', mission_id='child', agent_id='BUILDER', lease_seconds=10)
        other = World(self.path, clock=lambda: self.now)
        with self.assertRaises(ValueError):
            other.apply('compete', dict(op='claim_mission', mission_id='child', agent_id='RESEARCHER'))
        with self.assertRaises(ValueError):
            self.op('complete_mission', mission_id='child', agent_id='BUILDER', lease_token=lease['lease_token'], evidence=[])
        self.now += 11
        new = self.op('claim_mission', mission_id='child', agent_id='RESEARCHER')
        with self.assertRaises(ValueError):
            self.op('complete_mission', mission_id='child', agent_id='BUILDER', lease_token=lease['lease_token'], evidence=['proof'])
        self.op('complete_mission', mission_id='child', agent_id='RESEARCHER', lease_token=new['lease_token'], evidence=['https://example.org/proof'])
        self.assertEqual(self.w.snapshot()['missions'][1]['status'], 'COMPLETED')

    def test_money_messages_policy_and_cycles(self):
        self.op('message', from_agent='DIRECTOR', to_agent='BUILDER', body='Explore worldwide demand')
        self.op('transfer_glc', from_agent='BUILDER', to_agent='RESEARCHER', amount=10)
        self.assertEqual(sum(a['wallet_glc'] for a in self.w.snapshot()['agents']), 500)
        for amount in [True, 1.1, -1, 1000]:
            with self.assertRaises(ValueError):
                self.op('transfer_glc', from_agent='BUILDER', to_agent='RESEARCHER', amount=amount)
        with self.assertRaises(ValueError):
            self.op('transfer_glc', from_agent='BUILDER', to_agent='BUILDER', amount=10)
        self.op('reward_glc', agent_id='BUILDER', amount=10, evidence=['artifact.txt'])
        self.op('claim_mission', mission_id='WORLD-FIRST-REVENUE', agent_id='BUILDER')
        self.op('set_policy', maintenance_glc=10000, interest_basis_points=500)
        self.op('cycle', cycle_id='week1')
        self.op('cycle', cycle_id='week1')
        s = self.w.snapshot()
        self.assertTrue(all(a['debt_glc'] == 105 and a['status'] == 'DISABLED' for a in s['agents']))
        self.assertIsNone(s['missions'][0]['agent_id'])
        self.assertEqual(s['missions'][0]['status'], 'OPEN')
        self.assertTrue(any(e['type'] == 'GLC_ISSUANCE' for e in s['events']))

    def test_concurrent_claims_and_replays(self):
        def claim(agent):
            try:
                return World(self.path, clock=lambda: self.now).apply(
                    'claim-' + agent, dict(op='claim_mission', mission_id='WORLD-FIRST-REVENUE', agent_id=agent))
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, ['BUILDER', 'RESEARCHER']))
        self.assertEqual(sum(r is not None for r in results), 1)
        args = dict(op='reward_glc', agent_id='AUDITOR', amount=7, evidence=['proof.txt'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: World(self.path).apply('same-reward', args), range(2)))
        self.assertEqual(results[0], results[1])
        auditor = next(a for a in self.w.snapshot()['agents'] if a['agent_id'] == 'AUDITOR')
        self.assertEqual(auditor['wallet_glc'], 107)

    def test_failure_and_strict_fields(self):
        lease = self.op('claim_mission', mission_id='WORLD-FIRST-REVENUE', agent_id='BUILDER')
        self.op('fail_mission', mission_id='WORLD-FIRST-REVENUE', agent_id='BUILDER',
                lease_token=lease['lease_token'], reason='No supported demand evidence')
        self.assertEqual(self.w.snapshot()['missions'][0]['status'], 'FAILED')
        for args in [dict(op='set_policy', maintenance_glc=1, interest_basis_points=10001),
                     dict(op='message', from_agent='DIRECTOR', to_agent='missing', body='test'),
                     dict(op='register_agent', agent_id='X', role='Role', arbitrary='ignored')]:
            with self.assertRaises(ValueError):
                self.w.apply('invalid', args)

    def test_extinction_persists_and_validation_rolls_back(self):
        before = self.w.snapshot()
        with self.assertRaises(ValueError):
            self.op('register_agent', agent_id='../bad', role='bad')
        self.assertEqual(before, self.w.snapshot())
        self.op('extinguish', reason='Real treasury exhausted')
        w = World(self.path)
        w.bootstrap()
        self.assertEqual(w.snapshot()['state'], 'EXTINCT')
        with self.assertRaises(ValueError):
            w.apply('new', dict(op='register_agent', agent_id='NO', role='No'))

if __name__ == '__main__':
    unittest.main()
