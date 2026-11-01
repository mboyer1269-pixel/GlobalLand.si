"""Sprint 1: no-progress detector, blocker cards and world/blockers.json."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import progress
import test_autonomous_integration as integration
from controller import Controller
from world import World

CONFIG = {'controller': {'mode': 'subscriptions', 'providers': ['claude'], 'subscriptions_confirmed': True,
                         'extra_usage_disabled': True, 'image': 'brain@sha256:' + '1' * 64}}


def fp(products=None, missions=None, cash=0, funded=False):
    return dict(products=products or {}, missions=missions or {}, cash_cents=cash, funding_verified=funded)


class DeltaTests(unittest.TestCase):
    def test_what_counts_as_progress(self):
        base = fp({'products/research/a.json': '1', 'products/app/index.html': '1'}, {'M': 'RUNNING'})
        cases = {
            'new product outside research': (fp({**base['products'], 'products/app/new.js': '2'}, base['missions']), True),
            'mission completed': (fp(base['products'], {'M': 'COMPLETED'}), True),
            'mission failed (a decision)': (fp(base['products'], {'M': 'FAILED'}), True),
            'verified revenue': (fp(base['products'], base['missions'], cash=700), True),
            'research note only': (fp({**base['products'], 'products/research/b.json': '2'}, base['missions']), False),
            'rewrite of existing files': (fp({'products/research/a.json': '9', 'products/app/index.html': '9'}, base['missions']), False),
            'new mission or claim': (fp(base['products'], {'M': 'RUNNING', 'N': 'OPEN'}), False),
            'founder deposit is not earned': (fp(base['products'], base['missions'], cash=5000, funded=True), False),
        }
        for name, (current, expected) in cases.items():
            with self.subTest(name):
                self.assertIs(progress.delta(base, current)['productive'], expected)

    def test_deposit_plus_revenue_counts_only_the_revenue(self):
        change = progress.delta(fp(), fp(cash=5700, funded=True))
        self.assertEqual(change['net_cash_gain_cents'], 700)
        self.assertTrue(change['productive'])


class AssessCommitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / 'work/products').mkdir(parents=True)
        self.world = {'missions': [{'mission_id': 'M', 'status': 'RUNNING'}]}
        self.bank = {'cash_cents': 0, 'funding_verified': False}

    def turn(self, name, config=None):
        a = progress.assess(self.root, self.world, self.bank, config or {})
        progress.commit(self.root, name, a)
        return a

    def test_stall_counts_once_per_successful_turn_and_resets_on_progress(self):
        self.assertTrue(self.turn('THINK-1')['change']['baseline'])
        for n in (2, 3):
            self.assertEqual(self.turn('THINK-%d' % n)['stalled_turns'], n - 1)
        # A failed planning attempt assesses without committing: no double count.
        self.assertEqual(progress.assess(self.root, self.world, self.bank, {})['stalled_turns'], 3)
        alert = self.turn('THINK-4')
        self.assertEqual((alert['stalled_turns'], alert['alert']), (3, True))
        since = progress.load(self.root)['stalled_since']
        self.turn('THINK-5')
        self.assertEqual(progress.load(self.root)['stalled_since'], since)
        (self.root / 'work/products/app').mkdir()
        (self.root / 'work/products/app/index.html').write_text('<h1>new</h1>')
        reset = self.turn('THINK-6')
        self.assertEqual((reset['stalled_turns'], reset['alert']), (0, False))
        state = progress.load(self.root)
        self.assertEqual((state['last_productive_turn'], state['stalled_since']), ('THINK-6', None))

    def test_threshold_is_configurable_and_bounded(self):
        self.assertEqual(progress.stall_turns({'progress': {'stall_turns': 5}}), 5)
        self.assertEqual(progress.stall_turns({'progress': {'stall_turns': 0}}), 3)
        self.assertEqual(progress.stall_turns({}), 3)


class BlockerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.clock = iter(range(1793491200, 1793500000, 60))
        self.world = World(pathlib.Path(self.tmp.name) / 'w.sqlite3', clock=lambda: next(self.clock))
        self.world.bootstrap()

    def raise_(self, op_id, **extra):
        args = dict(op='raise_blocker', blocker_id='NO-HOSTING', agent_id='ACQUISITION', title='No hosting access',
                    category='ACCOUNT', needs_founder=True, detail='Cloudflare account and scoped token needed to publish.')
        args.update(extra)
        return self.world.apply(op_id, args)

    def test_repeated_reports_update_one_card_then_resolve_and_reopen(self):
        self.raise_('op-1')
        card = self.raise_('op-2', detail='Still missing after probe.')
        self.assertEqual((card['reports'], card['status'], card['detail']), (2, 'OPEN', 'Still missing after probe.'))
        self.assertEqual(len(self.world.snapshot()['blockers']), 1)
        done = self.world.apply('op-3', dict(op='resolve_blocker', blocker_id='NO-HOSTING', agent_id='ACQUISITION', resolution='Token installed; publish verified.'))
        self.assertEqual(done['status'], 'RESOLVED')
        with self.assertRaises(ValueError):
            self.world.apply('op-4', dict(op='resolve_blocker', blocker_id='NO-HOSTING', agent_id='ACQUISITION', resolution='again'))
        reopened = self.raise_('op-5')
        self.assertEqual((reopened['status'], reopened['reports']), ('OPEN', 1))
        self.assertNotIn('resolution', reopened)

    def test_invalid_blockers_are_refused(self):
        for bad in (dict(category='URGENT'), dict(needs_founder='yes'), dict(mission_id='NOPE'), dict(title='')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.raise_('bad-' + next(iter(bad)), **bad)

    def test_board_lists_founder_actions_first_and_the_system_card(self):
        self.raise_('op-1', blocker_id='AGENT-ONLY', needs_founder=False, category='OTHER')
        self.raise_('op-2')
        with tempfile.TemporaryDirectory() as d:
            board = progress.board(d, self.world.snapshot())
            self.assertEqual([c['id'] for c in board['open']], ['NO-HOSTING', 'AGENT-ONLY'])
            self.assertEqual(board['founder_actions'], 1)
            self.assertEqual(board['open'][0]['owner'], 'FOUNDER')
            state = pathlib.Path(d) / progress.STATE
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({'stalled_turns': 4, 'threshold': 3, 'stalled_since': '2026-11-01T00:00:00Z'}))
            board = progress.board(d, self.world.snapshot())
            system = [c for c in board['open'] if c['id'] == progress.SYSTEM_CARD]
            self.assertEqual(len(system), 1)
            self.assertIn('WORLD-FIRST-REVENUE', system[0]['detail'])
            self.assertEqual(board['open'][0]['id'], 'NO-HOSTING')


class DetectorIntegration(unittest.TestCase):
    setUp = integration.AutonomousIntegration.setUp
    git = integration.AutonomousIntegration.git
    submit = integration.AutonomousIntegration.submit

    def run(self, args=None, result=None):
        if isinstance(args, list):
            return subprocess.run(args, check=True, capture_output=True).stdout
        return super().run(args if args is not None else result)

    def board(self):
        return json.loads(self.run(['git', '--git-dir=' + str(self.remote), 'show', 'main:world/blockers.json']))

    def test_stalled_turns_alert_the_brain_and_open_a_card_until_progress(self):
        (self.install / 'control/config.json').write_text(json.dumps(CONFIG))
        prompts = []
        decision = {'summary': 'Look again', 'actions': [{'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}}]}
        reply = json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': decision}).encode()

        def brain(argv, **kwargs):
            prompts.append(kwargs['input'].decode())
            return 0, reply

        original = Controller.tick
        clock = iter(range(1793491200, 1793600000, 1800))
        with patch.object(Controller, 'check_provider'), patch('controller.run_brain', side_effect=brain), \
             patch.object(Controller, 'tick', lambda self, now=None: original(self, next(clock))):
            for _ in range(4):
                self.app.cycle('think')
            self.assertNotIn('PROGRESS ALERT', prompts[2])
            self.assertIn('PROGRESS ALERT: 3 consecutive turns', prompts[3])
            board = self.board()
            self.assertEqual(board['progress']['stalled_turns'], 3)
            self.assertEqual(board['open'][0]['id'], progress.SYSTEM_CARD)
            # A new product published between turns is progress: the card closes.
            self.git('pull', '--ff-only', 'origin', 'main')
            (self.seed / 'products/app').mkdir(parents=True)
            (self.seed / 'products/app/index.html').write_text('<h1>demo</h1>')
            self.git('add', '.'); self.git('commit', '-m', 'product'); self.git('push', 'origin', 'main')
            self.app.cycle('think')
        self.assertNotIn('PROGRESS ALERT', prompts[4])
        board = self.board()
        self.assertEqual(board['progress']['stalled_turns'], 0)
        self.assertEqual(board['open'], [])

    def test_agent_blocker_reaches_the_founder_board(self):
        self.submit(110, 'WORLD', {'op': 'raise_blocker', 'blocker_id': 'NO-HOSTING', 'agent_id': 'ACQUISITION',
                                   'title': 'No hosting access', 'category': 'ACCOUNT', 'needs_founder': True,
                                   'detail': 'Cloudflare account and a token scoped to one Pages project.',
                                   'expected_gain': 'Publish the demo and measure visits'})
        self.app.cycle('queue')
        board = self.board()
        self.assertEqual(board['founder_actions'], 1)
        card = board['open'][0]
        self.assertEqual((card['id'], card['owner'], card['category'], card['raised_by']),
                         ('NO-HOSTING', 'FOUNDER', 'ACCOUNT', 'ACQUISITION'))


if __name__ == '__main__':
    unittest.main()
