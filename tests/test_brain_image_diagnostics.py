"""Docker startup failures must not be mislabeled as provider authentication."""
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from controller import Controller
from supervisor import failure_details


class BrainImageDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.image = 'sha256:' + 'a' * 64
        self.controller = Controller('/tmp/example', None, None, {'controller': {
            'mode': 'subscriptions', 'providers': ['codex', 'claude'],
            'subscriptions_confirmed': True, 'extra_usage_disabled': True,
            'image': self.image}})

    def test_failed_or_unavailable_inspection_never_claims_image_missing(self):
        for inspection in ((1, b'permission denied private-account-context'),
                           (1, b'Cannot connect to Docker daemon'),
                           (1, b'Error: No such image: another-image'),
                           FileNotFoundError('private-account-context'),
                           TimeoutError('private-account-context')):
            with self.subTest(inspection=type(inspection).__name__):
                with patch('controller.run_brain', return_value=(125, b'private-account-context')), \
                     patch('controller.bounded_run', side_effect=[inspection]):
                    with self.assertRaises((RuntimeError, ValueError)) as caught:
                        self.controller.plan('codex', 'unused prompt')
                details = failure_details(caught.exception)
                self.assertEqual(details['reason'], 'brain_image_inspection_failed')
                self.assertNotIn('private-account-context', str(caught.exception))

    def test_present_image_does_not_turn_another_docker_error_into_missing_image(self):
        with patch('controller.run_brain', return_value=(125, b'private-account-context')), \
             patch('controller.bounded_run', return_value=(0, self.image.encode())):
            with self.assertRaises(ValueError) as caught:
                self.controller.plan('codex', 'unused prompt')
        self.assertNotEqual(failure_details(caught.exception)['reason'], 'brain_image_missing')
        self.assertNotIn('private-account-context', str(caught.exception))
