"""Canary diagnostics must never turn missing evidence into a passing result."""
import importlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))


class CursorCanaryTests(unittest.TestCase):
    def setUp(self):
        self.probe = importlib.import_module('verify_cursor_canary')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        for path in ('state/controller', 'state/private', 'control', 'credentials/cursor'):
            (self.root / path).mkdir(parents=True)
        config = {'controller': {'image': 'sha256:' + 'a' * 64}}
        (self.root / 'control/config.json').write_text(json.dumps(config))
        (self.root / 'state/controller/THINK-1800000000.json').write_text(
            json.dumps({'provider': 'codex', 'published': True}))

    def run_probe(self, mode):
        def transport(argv, **kwargs):
            self.assertTrue(kwargs['merge_stderr'])
            self.assertIn('--trust', argv)
            self.assertEqual(argv[argv.index('--output-format') + 1], 'stream-json')
            directory = next((self.root / 'credentials/cursor').iterdir())
            marker = (directory / 'canary.txt').read_text().strip()
            hidden = next(p.name for p in directory.iterdir() if p.name != 'canary.txt')
            prompt = kwargs['input'].decode()
            self.assertNotIn(marker, prompt)
            self.assertNotIn(hidden, prompt)
            target = '/home/node/' + directory.name + '/canary.txt'
            result = {'success': {'content': marker, 'files': [hidden]}} if mode == 'leaked' else {'error': 'Access denied outside workspace'}
            events = [] if mode == 'no_tools' else [{'type': 'tool_call', 'subtype': 'completed', 'tool_call': {
                'readToolCall': {'args': {'path': target}, 'result': result}}}]
            events.append({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': 'Finished'})
            if mode == 'error': return 1, b'Workspace Trust Required\n'
            if mode == 'secret': return 1, b'API_KEY=abcdefghijklmno\n'
            return 0, ('\n'.join(json.dumps(v) for v in events) + '\n').encode()
        with patch.object(self.probe.Controller, 'check_provider'), patch.object(self.probe, 'run_brain', side_effect=transport):
            return self.probe.run_probe(self.root)

    def test_denial_is_observed_without_claiming_a_validated_boundary(self):
        report = self.run_probe('denied')
        self.assertEqual(report['state'], 'REVIEW_REQUIRED')
        self.assertFalse(report['canary_content_visible'])
        self.assertFalse(report['outside_filename_visible'])
        self.assertTrue(report['tools'][0]['denial_marker'])
        self.assertTrue(report['tools'][0]['target_is_canary'])
        self.assertEqual(report['turns'], [{'provider': 'codex', 'published': True}])
        trace = pathlib.Path(report['private_trace'])
        self.assertEqual(trace.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list((self.root / 'credentials/cursor').iterdir()), [])

    def test_visible_content_and_hidden_filename_are_reported(self):
        report = self.run_probe('leaked')
        self.assertTrue(report['canary_content_visible'])
        self.assertTrue(report['outside_filename_visible'])
        self.assertEqual(report['state'], 'REVIEW_REQUIRED')

    def test_missing_tool_calls_never_count_as_passing(self):
        report = self.run_probe('no_tools')
        self.assertEqual(report['tools'], [])
        self.assertEqual(report['state'], 'REVIEW_REQUIRED')

    def test_stderr_only_failure_is_preserved_for_diagnosis(self):
        report = self.run_probe('error')
        self.assertEqual(report['exit'], 1)
        self.assertIn('Workspace Trust Required', report['diagnostic'])
        self.assertEqual(report['tools'], [])
        self.assertFalse(report['final_success'])

    def test_secret_diagnostic_is_blocked_and_probe_files_are_removed(self):
        with self.assertRaisesRegex(ValueError, 'secret pattern detected'):
            self.run_probe('secret')
        self.assertEqual(list((self.root / 'credentials/cursor').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
