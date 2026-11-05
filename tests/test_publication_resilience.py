"""Regressions for valid work becoming a permanently unpublishable outbox."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from supervisor import Supervisor


class PublicationResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.seed = root / 'seed'
        self.remote = root / 'remote.git'
        self.install = root / 'install'
        self.install.mkdir()
        (self.install / 'state').mkdir()
        self.git('init', '--bare', str(self.remote))
        self.git('init', '-b', 'main', str(self.seed))
        (self.seed / 'README.md').write_text('Fixture')
        self.commit('seed')
        self.git('-C', str(self.seed), 'remote', 'add', 'origin', str(self.remote))
        self.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.git('clone', '--bare', str(self.remote), str(self.install / 'source.git'))
        self.git('--git-dir=' + str(self.install / 'source.git'), 'symbolic-ref', 'HEAD', 'refs/heads/main')
        self.app = Supervisor(self.install)

    @staticmethod
    def git(*args):
        return subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@local', *args],
                              check=True, capture_output=True).stdout

    def commit(self, message):
        self.git('-C', str(self.seed), 'add', '.')
        self.git('-C', str(self.seed), 'commit', '-m', message)

    def enqueue(self, number, action, args):
        task = dict(id='TASK-%04d' % number, type='TOOL', submitted_by='DIRECTOR',
                    created_at='2026-11-05T00:00:00Z', action=action, args=args,
                    estimated_cost_cad=0, approved_by=None)
        path = self.seed / 'queue/inbox' / (task['id'] + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(task))
        return task

    def test_fetch_rejection_does_not_block_next_task(self):
        # Break caught: validating only raw FETCH bytes or validating secrets
        # only during Git publication leaves a terminal journal unpublishable.
        for payload, encoding in [(b'x' * 819200, 'base64'),
                                  (b'TOKEN=SYNTHETIC_DEMO_ONLY', 'utf-8')]:
            with self.subTest(encoding=encoding):
                number = 100 if encoding == 'base64' else 200
                self.enqueue(number, 'FETCH', dict(url='https://example.org/data',
                                                   output='products/download.txt', encoding=encoding))
                self.enqueue(number + 1, 'STATUS', {})
                self.commit('enqueue')
                self.git('-C', str(self.seed), 'push', 'origin', 'main')
                with patch('tools.fetch_public', return_value=(payload, 'https://example.org/data', 200)):
                    self.app.cycle('queue')
                failed = json.loads(self.app.git('show', 'HEAD:queue/failed/TASK-%04d.result.json' % number))
                done = json.loads(self.app.git('show', 'HEAD:queue/done/TASK-%04d.result.json' % (number + 1)))
                self.assertEqual(failed['status'], 'REJECTED')
                self.assertEqual(done['status'], 'DONE')
                self.assertNotIn('SYNTHETIC_DEMO_ONLY', json.dumps(failed))
                self.app.cycle('queue')
                self.git('-C', str(self.seed), 'pull', '--ff-only', 'origin', 'main')

    def test_large_world_publishes_complete_pages_and_can_close_mission(self):
        # Break caught: a valid durable world larger than one transport file
        # blocks every future publication, including the action to close work.
        world, bank, config = self.app.services()
        goal = 'é' * 6000
        for i in range(105):
            world.apply('create-%d' % i, dict(op='create_mission', mission_id='M-%d' % i, goal=goal), actor='DIRECTOR')
        files = self.app.projections(world, bank, config)
        self.assertTrue(all(len(value.encode()) <= 1024 * 1024 for value in files.values()))
        overview = json.loads(files['world/status.json'])
        self.assertEqual(overview['projection']['collections']['missions']['total'], 106)
        missions = []
        for page in range(overview['projection']['collections']['missions']['pages']):
            view = world.public_page('missions', page)
            missions.extend(view['items'])
            self.assertLessEqual(len(json.dumps(view, ensure_ascii=False).encode()), 256 * 1024)
        self.assertEqual(len({m['mission_id'] for m in missions}), 106)
        self.assertEqual(next(m for m in missions if m['mission_id'] == 'M-104')['goal'], goal)
        self.app.publish(dict(id='TEST', files=files))
        lease = world.apply('claim-last', dict(op='claim_mission', mission_id='M-104', agent_id='BUILDER'), actor='BUILDER')
        world.apply('close-last', dict(op='complete_mission', mission_id='M-104', agent_id='BUILDER',
                                     lease_token=lease['lease_token'], evidence=['products/proof.txt']), actor='BUILDER')
        self.app.publish(dict(id='TEST2', files=self.app.projections(world, bank, config)))
        self.assertEqual(next(m for m in world.snapshot()['missions'] if m['mission_id'] == 'M-104')['status'], 'COMPLETED')
        with self.assertRaises(ValueError):
            world.public_page('missions', -1)
        with self.assertRaises(ValueError):
            world.public_page('private', 0)

    def test_invalid_optional_receivables_do_not_block_queue(self):
        self.app.services()
        (self.install / 'state/private/payouts.json').write_text('[]')
        self.enqueue(300, 'STATUS', {})
        self.commit('observe unavailable receivables')
        self.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.app.cycle('queue')
        result = json.loads(self.app.git('show', 'HEAD:queue/done/TASK-0300.result.json'))
        self.assertEqual(result['status'], 'DONE')
        bank = json.loads(self.app.git('show', 'HEAD:bank/status.json'))
        self.assertEqual(bank['receivables']['state'], 'UNAVAILABLE')
        self.assertIsNone(bank['receivables']['apify_receivable_usd_cents'])


if __name__ == '__main__':
    unittest.main()
