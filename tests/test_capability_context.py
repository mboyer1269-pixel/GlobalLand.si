"""A tool in the protocol is not proof of a connected service."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from controller import Controller
from tools import Toolbox
from treasury import Treasury
from world import World


class CapabilityContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.world = World(self.root / 'world.db')
        self.world.bootstrap()
        self.bank = Treasury(self.root / 'bank.db')

    def test_prompt_identifies_missing_integrations_instead_of_implying_access(self):
        view = Controller(self.root, self.world, self.bank, {}).context()['capabilities']
        self.assertEqual(view['EXEC']['state'], 'NOT_CONFIGURED')
        for action in ('PUBLISH_SITE', 'PUBLISH_ACTOR', 'ACTOR_STATS', 'SPEND', 'RECONCILE'):
            self.assertEqual(view[action]['state'], 'NOT_CONFIGURED')
        self.assertEqual(view['FETCH']['state'], 'BUILT_IN')
        self.assertIn('no direct network', view['EXEC']['constraints'])

    def test_configured_is_not_verified_and_no_account_data_is_returned(self):
        token = self.root / 'credentials/cloudflare/token'
        token.parent.mkdir(parents=True)
        token.write_text('private-placeholder-never-read')
        token.chmod(0o600)
        config = {'executor_enabled': True, 'executor_image': 'node@sha256:' + '1' * 64,
                  'cloudflare': {'enabled': True, 'account_id': 'a' * 32}}
        view = Controller(self.root, self.world, self.bank, config).context()['capabilities']
        self.assertEqual(view['EXEC']['state'], 'CONFIGURED_UNVERIFIED')
        self.assertEqual(view['PUBLISH_SITE']['state'], 'CONFIGURED_UNVERIFIED')
        self.assertNotIn('private-placeholder', json.dumps(view))
        self.assertNotIn('a' * 32, json.dumps(view))
        token.chmod(0o644)
        self.assertEqual(Controller(self.root, self.world, self.bank, config).context()['capabilities']['PUBLISH_SITE']['state'], 'NOT_CONFIGURED')

    def test_status_has_the_same_capability_report_as_the_planner(self):
        config = {'cloudflare': {'enabled': True, 'account_id': 'invalid'}}
        box = Toolbox(self.root, self.world, self.bank, config)
        result, _ = box.run(dict(id='TASK-9100', type='TOOL', submitted_by='DIRECTOR',
                                created_at='2026-11-02T00:00:00Z', action='STATUS', args={},
                                estimated_cost_cad=0, approved_by=None))
        self.assertEqual(json.loads(result['output'])['capabilities'],
                         Controller(self.root, self.world, self.bank, config).context()['capabilities'])

    def test_private_mail_observation_exposes_only_counts_and_timestamp(self):
        token = self.root / 'credentials/agentmail/token'
        token.parent.mkdir(parents=True)
        token.write_text('DO-NOT-READ-PRIVATE-KEY'); token.chmod(0o600)
        status = self.root / 'state/private/agentmail-status.json'
        status.parent.mkdir(parents=True)
        status.write_text(json.dumps({'accepted': 1, 'failed': 0, 'body': 'PRIVATE-MAIL',
                                     'subject': 'PRIVATE-SUBJECT', 'ignored': 'PRIVATE-MAIL',
                                     'observed_at': '2026-11-04T19:00:00+00:00'}))
        config = {'agentmail': {'enabled': True, 'inbox_id': 'PRIVATE-INBOX',
                               'inbox_address': 'private@example.invalid'}}
        view = Controller(self.root, self.world, self.bank, config).context()['capabilities']['PRIVATE_MAIL']
        self.assertEqual(view['state'], 'CONFIGURED_UNVERIFIED')
        self.assertEqual(view['last_cycle'], {'accepted': 1, 'failed': 0,
                                             'observed_at': '2026-11-04T19:00:00+00:00'})
        self.assertNotIn('PRIVATE', json.dumps(view))
        self.assertNotIn('example.invalid', json.dumps(view))


if __name__ == '__main__':
    unittest.main()
