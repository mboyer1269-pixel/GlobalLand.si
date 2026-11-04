import json
import pathlib
import sys
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import test_autonomous_integration as fixtures


class PrivateMailIntegration(unittest.TestCase):
    setUp = fixtures.AutonomousIntegration.setUp
    git = fixtures.AutonomousIntegration.git

    def run(self, args=None, result=None):
        if not isinstance(args, list):
            return super().run(args if args is not None else result)
        return subprocess.run(args, check=True, capture_output=True).stdout

    def test_mail_cycle_does_not_publish_correspondence_or_run_public_queue(self):
        config = {'agentmail': {'enabled': True, 'inbox_id': 'test@example.invalid',
                               'inbox_address': 'test@example.invalid'}}
        (self.install / 'control/config.json').write_text(json.dumps(config))
        before = self.app.git('rev-parse', 'HEAD')
        def private_cycle(root, current):
            self.assertEqual(current['agentmail'], config['agentmail'])
            dest = root / 'state/private/agentmail/private.json'
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text('{"body":"PRIVATE-MAIL-MARKER","subject":"private subject"}')
            return {'enabled': True, 'accepted': 1}
        with patch('mail_agent.run_mail_cycle', side_effect=private_cycle) as cycle:
            self.app.cycle('mail')
        cycle.assert_called_once()
        self.assertEqual(self.app.git('rev-parse', 'HEAD'), before)
        tracked = self.app.git('ls-tree', '-r', '--name-only', 'HEAD')
        self.assertNotIn(b'private', tracked)
        self.assertEqual(list((self.install / 'state').glob('TASK-*.json')), [])
        for p in (self.install / 'work').rglob('*'):
            if p.is_file():
                self.assertNotIn(b'PRIVATE-MAIL-MARKER', p.read_bytes())

    def test_disabled_mail_never_initializes_mailbox_or_model(self):
        with patch('controller.Controller.plan') as brain, patch('mail.Mailbox') as mailbox:
            self.app.cycle('mail')
        brain.assert_not_called()
        mailbox.assert_not_called()

    def test_mail_error_does_not_expose_private_details(self):
        with patch('mail_agent.run_mail_cycle', side_effect=ValueError('PRIVATE-CUSTOMER')):
            with self.assertRaisesRegex(RuntimeError, '^Private mail cycle failed; inspect private mail status$'):
                self.app.cycle('mail')


if __name__ == '__main__':
    unittest.main()
