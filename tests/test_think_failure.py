import contextlib
import io
import json
import subprocess
import traceback
import unittest
from unittest.mock import patch

import test_autonomous_integration as integration
from controller import Controller
from supervisor import Supervisor


class ThinkFailureTests(unittest.TestCase):
    # Reuse the real Git repositories without inheriting unrelated test cases.
    setUp = integration.AutonomousIntegration.setUp
    git = integration.AutonomousIntegration.git

    def run(self, args=None, result=None):
        if isinstance(args, list):
            return subprocess.run(args, check=True, capture_output=True).stdout
        return super().run(args if args is not None else result)

    def configure_controller(self):
        config = {'controller': {
            'mode': 'subscriptions', 'providers': ['codex'],
            'subscriptions_confirmed': True, 'extra_usage_disabled': True,
            'image': 'brain@sha256:' + '1' * 64,
        }}
        (self.install / 'control/config.json').write_text(json.dumps(config))

    def public_controller(self):
        return json.loads(self.run([
            'git', '--git-dir=' + str(self.remote),
            'show', 'main:world/controller.json',
        ]))

    def assert_no_failed_plan_work(self):
        self.assertEqual(list((self.install / 'state').glob('THINK-*.json')), [])
        self.assertEqual(list((self.install / 'state/controller').glob('THINK-*.json')), [])
        tracked = self.app.git('ls-tree', '-r', '--name-only', 'HEAD').decode().splitlines()
        self.assertFalse(any(name.startswith(('queue/inbox/TASK-', 'queue/done/', 'queue/failed/')) for name in tracked))

    def test_provider_failure_publishes_blocked_state_then_raises(self):
        self.configure_controller()
        # Keep the real planner and decision/outbox validation; replace only Docker I/O.
        with patch('controller.run_brain', side_effect=TimeoutError('command timed out')):
            with self.assertRaisesRegex(RuntimeError, 'Controller planning failed'):
                self.app.cycle('think')

        self.assertEqual(self.public_controller()['state'], 'CONTROLLER_BLOCKED')
        self.assertEqual(self.public_controller()['reason_code'], 'provider_timeout')
        diagnostic = json.loads((self.install / 'state/private/controller-failure.json').read_text())
        self.assertEqual(diagnostic['exception_type'], 'TimeoutError')
        self.assertEqual(diagnostic['providers'], ['codex'])
        self.assertEqual(diagnostic['stage'], 'planner.tick')
        self.assert_no_failed_plan_work()

    def test_private_diagnostic_and_visible_failure_never_include_error_secrets(self):
        self.configure_controller()
        secret = 'sk-' + 'x' * 32
        opaque = 'private-account-context-without-a-secret-prefix'
        raw_error = ValueError('provider rejected API_KEY=' + secret + ' ' + opaque)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), patch.object(Controller, 'tick', side_effect=raw_error):
            try:
                self.app.cycle('think')
            except RuntimeError as error:
                visible_error = ''.join(traceback.format_exception(error))
            else:
                self.fail('A failed think must raise so the CLI exits nonzero')

        self.assertIn('Controller planning failed', visible_error)
        diagnostic_path = self.install / 'state/private/controller-failure.json'
        diagnostic = json.loads(diagnostic_path.read_text())
        self.assertEqual(diagnostic['exception_type'], 'ValueError')
        self.assertTrue(diagnostic['reason'])
        self.assertEqual(diagnostic_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(diagnostic_path.parent.stat().st_mode & 0o777, 0o700)
        public_history = self.app.git('log', '--all', '-p').decode()
        for output in (visible_error, stderr.getvalue(), public_history, diagnostic_path.read_text()):
            self.assertNotIn(secret, output)
            self.assertNotIn(opaque, output)
        self.assertEqual(self.public_controller()['state'], 'CONTROLLER_BLOCKED')
        self.assert_no_failed_plan_work()

    def test_missing_brain_image_is_preserved_in_private_and_public_diagnosis(self):
        self.configure_controller()
        path = self.install / 'control/config.json'
        config = json.loads(path.read_text())
        config['controller']['providers'] = ['codex', 'claude']
        path.write_text(json.dumps(config))
        image = config['controller']['image']
        calls = []
        secret = b'private-account-context'

        def docker(argv, **kwargs):
            calls.append(argv)
            if argv[:3] == ['docker', 'image', 'inspect']:
                self.assertEqual(argv[-1], image)
                return 1, b'Error response from daemon: No such image: ' + image.encode() + b'\n'
            self.assertIn('--help', argv)  # Neither auth nor inference may run.
            return 125, secret

        with patch('controller.bounded_run', side_effect=docker), patch('controller.cleanup_brain'):
            with self.assertRaisesRegex(RuntimeError, 'Controller planning failed'):
                self.app.cycle('think')
        private = (self.install / 'state/private/controller-failure.json').read_text()
        public = self.public_controller()
        self.assertEqual(json.loads(private)['reason'], 'brain_image_missing')
        self.assertEqual(public['reason_code'], 'brain_image_missing')
        self.assertEqual(public['last_turn']['attempts'][0]['reason'], 'brain_image_missing')
        self.assertEqual(len(calls), 2)
        self.assertNotIn(secret.decode(), private + json.dumps(public))
        self.assert_no_failed_plan_work()

    def test_invalid_provider_output_has_a_safe_specific_private_reason(self):
        self.configure_controller()
        # Authentication and CLI execution are external; parse the provider output for real.
        with patch.object(Controller, 'check_provider'), patch('controller.run_brain', return_value=(0, b'not a JSON decision')):
            with self.assertRaisesRegex(RuntimeError, 'Controller planning failed'):
                self.app.cycle('think')
        diagnostic = json.loads((self.install / 'state/private/controller-failure.json').read_text())
        self.assertEqual(diagnostic['reason'], 'invalid_provider_structured_output')
        self.assertEqual(self.public_controller()['state'], 'CONTROLLER_BLOCKED')
        self.assertEqual(self.public_controller()['reason_code'], 'invalid_provider_structured_output')
        self.assert_no_failed_plan_work()

    def test_fallback_diagnostics_survive_queue_publication_without_exposing_raw_errors(self):
        self.configure_controller()
        path = self.install / 'control/config.json'
        config = json.loads(path.read_text())
        config['controller']['providers'] = ['codex', 'claude']
        path.write_text(json.dumps(config))
        secret = 'private-account-context'
        decision = {'summary': 'Observe', 'actions': [{'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}}]}
        def run(argv, **kwargs):
            if 'codex' in argv: raise TimeoutError(secret)
            return 0, json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': decision}).encode()
        with patch.object(Controller, 'check_provider'), patch('controller.run_brain', side_effect=run):
            self.app.cycle('think')
        status = self.public_controller()['last_turn']
        self.assertEqual(status['provider'], 'claude')
        self.assertEqual(status['attempts'][0]['reason'], 'provider_timeout')
        self.app.cycle('queue')
        self.assertEqual(self.public_controller()['last_turn'], status)
        self.assertNotIn(secret, self.app.git('log', '--all', '-p').decode())

    def test_failed_blocked_push_keeps_private_diagnostic_and_retries_without_planning(self):
        self.configure_controller()
        secret = 'ghp_' + 'x' * 40

        class FailingPush(Supervisor):
            fail_next_push = True

            def git(self, *args, **kwargs):
                if args[0] == 'push' and self.fail_next_push:
                    self.fail_next_push = False
                    raise RuntimeError('remote credential ' + secret)
                return super().git(*args, **kwargs)

        self.app = FailingPush(self.install)
        with patch.object(Controller, 'tick', side_effect=ValueError('invalid controller decision')):
            try:
                self.app.cycle('think')
            except RuntimeError as error:
                visible_error = ''.join(traceback.format_exception(error))
            else:
                self.fail('Failure publication must not make a failed think successful')

        self.assertIn('Controller planning failed', visible_error)
        self.assertNotIn(secret, visible_error)
        diagnostic_path = self.install / 'state/private/controller-failure.json'
        self.assertEqual(json.loads(diagnostic_path.read_text())['exception_type'], 'ValueError')
        # Existing Git recovery pushes the blocked commit before considering queue work.
        self.app.cycle('queue')
        self.assertEqual(self.public_controller()['state'], 'CONTROLLER_BLOCKED')
        self.assert_no_failed_plan_work()


if __name__ == '__main__':
    unittest.main()
