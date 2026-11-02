"""The non-broker brain turn uses a bounded, configurable deadline."""
import pathlib, sys, time, unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import controller
from controller import Controller

IMAGE = 'sha256:' + 'a' * 64


def make(**extra):
    config = {'mode': 'subscriptions', 'providers': ['codex'], 'image': IMAGE,
              'subscriptions_confirmed': True, 'extra_usage_disabled': True}
    config.update(extra)
    return Controller('/tmp/gl-timeout-test', None, None, {'controller': config})


class TurnTimeoutTests(unittest.TestCase):
    def turn_timeout(self, c):
        with patch('controller.run_brain', return_value=(0, b'{}')) as run:
            c.run_turn('codex', 'context')
        return run.call_args.kwargs['timeout']

    def test_default_keeps_the_previous_120_seconds(self):
        self.assertEqual(self.turn_timeout(make()), 120)

    def test_configured_value_reaches_the_brain_call(self):
        self.assertEqual(self.turn_timeout(make(timeout_seconds=300)), 300)

    def test_out_of_bounds_or_non_integer_values_are_refused_before_any_call(self):
        for bad in (29, 901, '120', True, 120.5, None):
            with self.subTest(bad=bad):
                c = make(timeout_seconds=bad)
                self.assertIn('timeout_seconds must be an integer from 30 to 900', c.readiness()['missing'])
                with patch('controller.run_brain') as run:
                    with self.assertRaisesRegex(ValueError, 'timeout_seconds'):
                        c.run_turn('codex', 'context')
                    run.assert_not_called()

    def test_a_slow_brain_is_stopped_at_the_deadline(self):
        argv = [sys.executable, '-c', 'import time; time.sleep(30)', '--name', 'globalland-brain-test']
        with patch('controller.cleanup_brain') as cleanup:
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                controller.run_brain(argv, timeout=1)
        self.assertLess(time.monotonic() - start, 5)
        cleanup.assert_called_once_with('globalland-brain-test')


if __name__ == '__main__':
    unittest.main()
