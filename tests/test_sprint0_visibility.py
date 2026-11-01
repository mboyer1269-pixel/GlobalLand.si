"""Sprint 0: truthful public controller status and explicit tool rejections."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import test_autonomous_integration as integration
from controller import Controller
from tools import rejection_reason

CONFIG = {'controller': {'mode': 'subscriptions', 'providers': ['codex', 'claude'],
                         'subscriptions_confirmed': True, 'extra_usage_disabled': True,
                         'image': 'brain@sha256:' + '1' * 64}}
AT = '2026-11-01T00:00:00Z'
AT_SECONDS = 1793491200


class ControllerProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.controller = Controller(self.root, None, None, CONFIG)

    def record(self, state, provider='claude', at=AT):
        attempts = [dict(provider=provider or 'codex', status='SUCCEEDED' if state == 'DECISION_READY' else 'FAILED',
                         stage='planning', exception_type=None if state == 'DECISION_READY' else 'TimeoutError',
                         reason=None if state == 'DECISION_READY' else 'provider_timeout')]
        private = self.root / 'state/private'; private.mkdir(parents=True, exist_ok=True)
        (private / 'controller-run.json').write_text(json.dumps(dict(turn='THINK-1', at=at, state=state, provider=provider, attempts=attempts)))

    def test_fresh_process_reports_successful_turn_as_operational(self):
        # A fresh process has verified nothing itself: readiness alone says WAITING.
        self.assertEqual(self.controller.readiness()['state'], 'WAITING_SUBSCRIPTION_AUTH')
        self.record('DECISION_READY')
        status = self.controller.projection(now=AT_SECONDS + 600)
        self.assertEqual((status['state'], status['verified'], status['missing']), ('OPERATIONAL', True, []))
        self.assertEqual(status['last_turn']['provider'], 'claude')
        self.assertEqual(status['last_turn_age_seconds'], 600)
        self.assertFalse(status['account_settings_verified'])

    def test_retrying_blocked_and_stale_turns_are_not_operational(self):
        self.record('RETRYING', provider=None)
        self.assertEqual(self.controller.projection(now=AT_SECONDS)['state'], 'DEGRADED')
        self.record('BLOCKED', provider=None)
        self.assertEqual(self.controller.projection(now=AT_SECONDS)['state'], 'CONTROLLER_BLOCKED')
        self.record('DECISION_READY')
        self.assertEqual(self.controller.projection(now=AT_SECONDS + 7201)['state'], 'STALE')
        self.assertFalse(self.controller.projection(now=AT_SECONDS + 7201)['verified'])

    def test_without_turn_or_configuration_readiness_is_unchanged(self):
        self.assertEqual(self.controller.projection()['state'], 'WAITING_SUBSCRIPTION_AUTH')
        self.record('DECISION_READY')
        unconfigured = Controller(self.root, None, None, {})
        self.assertEqual(unconfigured.projection(now=AT_SECONDS)['state'], 'WAITING_CONTROLLER')


class RejectionReasonTests(unittest.TestCase):
    def test_fixed_protocol_rules_are_explained(self):
        self.assertEqual(rejection_reason(ValueError('unknown exec argument')),
                         'Tool request refused: unknown exec argument. See queue/PROTOCOL.md.')
        self.assertIn('Invalid goal', rejection_reason(ValueError('Invalid goal')))
        self.assertIn('HTTP 404', rejection_reason(ValueError('HTTP 404')))

    def test_dynamic_or_secret_text_is_withheld(self):
        for detail in ('token ghp_' + 'x' * 40, 'private-account-context', 'x' * 500):
            with self.subTest(detail=detail[:20]):
                text = rejection_reason(ValueError(detail))
                self.assertNotIn(detail, text)
                self.assertIn('detail withheld', text)
        self.assertIn('UnicodeDecodeError', rejection_reason(UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'bad')))


class PublicVisibilityIntegration(unittest.TestCase):
    setUp = integration.AutonomousIntegration.setUp
    git = integration.AutonomousIntegration.git
    submit = integration.AutonomousIntegration.submit

    def run(self, args=None, result=None):
        if isinstance(args, list):
            import subprocess
            return subprocess.run(args, check=True, capture_output=True).stdout
        return super().run(args if args is not None else result)

    def public(self, name):
        return json.loads(self.run(['git', '--git-dir=' + str(self.remote), 'show', 'main:' + name]))

    def test_successful_think_publishes_operational_controller(self):
        (self.install / 'control/config.json').write_text(json.dumps(CONFIG))
        decision = {'summary': 'Observe', 'actions': [{'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}}]}
        reply = json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': decision}).encode()
        def brain(argv, **kwargs):
            return 0, reply if 'claude' in argv else json.dumps(decision).encode()
        with patch.object(Controller, 'check_provider'), patch('controller.run_brain', side_effect=brain):
            self.app.cycle('think')
        self.assertEqual(self.public('world/controller.json')['state'], 'OPERATIONAL')
        self.app.cycle('queue')
        self.assertEqual(self.public('world/controller.json')['state'], 'OPERATIONAL')

    def test_rejected_task_explains_the_rule(self):
        self.submit(103, 'SPEND', {'request': {'purchase': 'tool'}})
        self.app.cycle('queue')
        result = self.public('queue/failed/TASK-0103.result.json')
        self.assertEqual(result['status'], 'REJECTED')
        self.assertIn('No bounded finance integration configured', result['output'])
        self.submit(104, 'EXEC', {'argv': ['true'], 'surprise': 1})
        self.app.cycle('queue')
        self.assertIn('unknown exec argument', self.public('queue/failed/TASK-0104.result.json')['output'])


if __name__ == '__main__':
    unittest.main()
