"""Operator scheduling preserves identities, approvals, journals and other jobs."""
import importlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))


class StartAutonomyTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('start_autonomy')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.root = self.base / 'globalland'
        for name in ('state/controller', 'control', 'backups', 'credentials/cursor'):
            (self.root / name).mkdir(parents=True)
        self.config = {'executor_enabled': True, 'controller': {
            'mode': 'subscriptions', 'providers': ['codex', 'claude', 'cursor'],
            'image': 'sha256:' + 'a' * 64, 'subscriptions_confirmed': True,
            'extra_usage_disabled': True}, 'other_setting': 'keep'}
        self.config_path = self.root / 'control/config.json'
        self.config_path.write_text(json.dumps(self.config))
        (self.root / 'control/REVISION').write_text('4' * 40 + '\n')
        for i, provider in enumerate(('codex', 'claude')):
            (self.root / f'state/controller/THINK-180000000{i}.json').write_text(
                json.dumps({'provider': provider, 'published': True}))
        self.cron = self.base / 'cron.d/globalland-think'
        self.cron.parent.mkdir()
        self.existing = self.cron.parent / 'globalland'
        self.existing.write_text('existing queue and daily jobs\n')
        self.oria = self.cron.parent / 'oria'
        self.oria.write_text('existing Oria job\n')
        self.log = self.base / 'logs/think.log'
        self.cursor = self.root / 'credentials/cursor/keep.txt'
        self.cursor.write_text('private login remains')

    def activate(self, verify=True):
        with patch.object(self.module.subprocess, 'run'):
            if verify:
                with patch.object(self.module.Controller, 'check_provider'):
                    return self.module.activate(self.root, self.cron, self.log)
            return self.module.activate(self.root, self.cron, self.log)

    def assert_original(self):
        self.assertEqual(json.loads(self.config_path.read_text()), self.config)
        self.assertFalse(self.cron.exists())
        self.assertEqual(list((self.root / 'backups').iterdir()), [])

    def test_working_brains_schedule_preserves_config_and_unrelated_jobs(self):
        report = self.activate()
        expected = json.loads(json.dumps(self.config))
        expected['controller']['providers'] = ['codex', 'claude']
        self.assertEqual(json.loads(self.config_path.read_text()), expected)
        self.assertEqual(self.existing.read_text(), 'existing queue and daily jobs\n')
        self.assertEqual(self.oria.read_text(), 'existing Oria job\n')
        self.assertEqual(self.cursor.read_text(), 'private login remains')
        self.assertEqual(self.cron.read_text(), self.module.JOB)
        self.assertTrue(self.cron.read_text().startswith('*/30 '))
        self.assertEqual(self.cron.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)
        backup = pathlib.Path(report['backup']) / 'config-before.json'
        self.assertEqual(json.loads(backup.read_text()), self.config)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(report['control_revision'], '4' * 40)

    def test_repeating_activation_does_not_duplicate_the_schedule(self):
        self.activate()
        self.activate()
        self.assertEqual(self.cron.read_text().count('supervisor.py think'), 1)

    def test_existing_conflicting_schedule_is_preserved(self):
        self.cron.write_text('custom existing schedule\n')
        with self.assertRaisesRegex(ValueError, 'existing schedule'):
            self.activate()
        self.assertEqual(self.cron.read_text(), 'custom existing schedule\n')
        self.assertEqual(json.loads(self.config_path.read_text()), self.config)
        self.assertEqual(list((self.root / 'backups').iterdir()), [])

    def test_native_published_turns_are_required_before_scheduling(self):
        path = self.root / 'state/controller/THINK-1800000001.json'
        path.write_text(json.dumps({'provider': 'claude', 'published': False}))
        with self.assertRaisesRegex(ValueError, 'published turn'):
            self.activate()
        self.assert_original()

    def test_missing_usage_confirmation_is_not_fabricated(self):
        self.config['controller']['extra_usage_disabled'] = False
        self.config_path.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, 'configuration missing'):
            self.activate(verify=False)
        self.assert_original()

    def test_auth_failure_leaves_configuration_and_schedule_unchanged(self):
        with patch.object(self.module.subprocess, 'run'), patch.object(
                self.module.Controller, 'check_provider', side_effect=ValueError('auth failed')):
            with self.assertRaisesRegex(ValueError, 'auth failed'):
                self.module.activate(self.root, self.cron, self.log)
        self.assert_original()

    def test_cron_replacement_failure_restores_the_original_configuration(self):
        original_replace = self.module.os.replace
        def replace(source, destination):
            if pathlib.Path(destination) == self.cron:
                raise OSError('fixture cron replacement failed')
            return original_replace(source, destination)
        with patch.object(self.module.os, 'replace', side_effect=replace):
            with self.assertRaisesRegex(OSError, 'cron replacement failed'):
                self.activate()
        self.assertEqual(json.loads(self.config_path.read_text()), self.config)
        self.assertFalse(self.cron.exists())
        backups = list((self.root / 'backups').glob('*/config-before.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text()), self.config)
        self.assertEqual(list(self.cron.parent.glob('.globalland-think-*')), [])


if __name__ == '__main__':
    unittest.main()
