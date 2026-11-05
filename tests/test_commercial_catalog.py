"""Commercial attribution survives paged worlds and sparse supervisor work."""
import json
import hashlib
import pathlib
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import commercial
from supervisor import Supervisor
from world import World


class CommercialCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def pages(self):
        # Use the producer's actual pagination, not an imagined envelope.
        world = World(self.root / 'world.db')
        with world._connect() as db:
            data = json.loads(db.execute('SELECT data FROM world').fetchone()[0])
            data['missions'] = [dict(mission_id='M%02d' % n, description='x' * 8000)
                                for n in range(40)]
            db.execute('UPDATE world SET data=?', (json.dumps(data),))
        for name, raw in world.public_files().items():
            self.write('work/' + name, json.loads(raw))
        status = json.loads((self.root / 'work/world/status.json').read_text())
        self.assertLess(len(status['missions']), 40)

    def git_source(self):
        repo = self.root / 'author'
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
        for key, value in [('user.name', 'Test'), ('user.email', 'test@example.invalid')]:
            subprocess.run(['git', '-C', str(repo), 'config', key, value], check=True)
        self.write('author/products/sites/demo/index.html', 'public example')
        self.git('add', '.')
        self.git('commit', '-qm', 'published example')
        subprocess.run(['git', 'clone', '-q', '--bare', str(repo), str(self.root / 'source.git')], check=True)
        subprocess.run(['git', '--git-dir=' + str(self.root / 'source.git'), 'update-ref',
                        'refs/globalland/published', 'HEAD'], check=True)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root / 'author'), *args],
                              check=True, capture_output=True).stdout.decode().strip()

    def test_mission_beyond_preview_reaches_prompt_and_private_observation(self):
        self.pages()
        allowed = commercial.allowed_experiments(self.root)
        self.assertIn('mission:M39', allowed['ids'])
        self.assertTrue(allowed['available'])
        self.assertFalse(allowed['truncated'])
        raw = dict(category='PRICE_QUESTION', audience='ORDINARY',
                   experiment_id='mission:M39', evidence=dict(field='text', quote='Price?'))
        observation = commercial.normalize_observation(raw, {'text': 'Price?'}, allowed,
                                                       'INBOUND_UNVERIFIED', 'claude')
        self.assertEqual(observation['experiment_id'], 'mission:M39')
        self.assertEqual(observation['attribution'], 'MODEL_INFERRED')
        self.assertIn('mission:M39', commercial.prompt(self.root, {'agentmail': {
            'commercial': {'enabled': True}}}))
        key = hashlib.sha256(b'inbox\0message').hexdigest()
        self.write('state/private/agentmail/' + key + '.json', dict(inbox_id='inbox',
            message_id='message', state='ACCEPTED', observation=observation))
        view = commercial.project(self.root, {'agentmail': {'inbox_id': 'inbox',
            'commercial': {'enabled': True}}})
        self.assertEqual(view['inferred_experiments']['mission:M39']['PRICE_QUESTION'], 1)
        self.assertNotIn('Price?', json.dumps(view))
        self.assertNotIn('revenue_cents', view)

    def test_sparse_refresh_retains_published_site_and_ignores_pending_head(self):
        self.git_source()
        self.write('author/products/sites/pending/index.html', 'not published')
        self.git('add', '.')
        self.git('commit', '-qm', 'pending publication')
        subprocess.run(['git', '--git-dir=' + str(self.root / 'source.git'), 'fetch', '-q',
                        str(self.root / 'author'), '+HEAD:refs/heads/main'], check=True)
        Supervisor(self.root).refresh_work()
        self.assertFalse((self.root / 'work/products').exists())
        for name, raw in World(self.root / 'world.db').public_files().items():
            self.write('work/' + name, json.loads(raw))
        allowed = commercial.allowed_experiments(self.root)
        self.assertEqual(allowed, dict(ids=['site:demo'], truncated=False, available=True))

    def test_mixed_or_missing_pages_are_unavailable_not_complete_preview(self):
        self.pages()
        path = self.root / 'work/world/pages/missions-1.json'
        page = json.loads(path.read_text())
        page['snapshot_sha256'] = 'f' * 64
        path.write_text(json.dumps(page))
        allowed = commercial.allowed_experiments(self.root)
        self.assertFalse(allowed['available'])
        self.assertEqual(allowed['ids'], [])
        path.unlink()
        self.assertFalse(commercial.allowed_experiments(self.root)['available'])

    def test_invalid_git_never_uses_stale_work_sites(self):
        (self.root / 'source.git').mkdir()
        (self.root / 'work/products/sites/stale').mkdir(parents=True)
        self.write('work/world/status.json', {'missions': []})
        allowed = commercial.allowed_experiments(self.root)
        self.assertFalse(allowed['available'])
        self.assertNotIn('site:stale', allowed['ids'])

    def test_malformed_projection_is_not_legacy_complete(self):
        for projection in [None, {}, {'collections': {}}, {'collections': {'missions': {}}}]:
            with self.subTest(projection=projection):
                self.write('work/world/status.json', {'missions': [], 'projection': projection})
                self.assertFalse(commercial.allowed_experiments(self.root)['available'])

    def test_missing_installed_world_is_partial_while_sites_remain_known(self):
        self.git_source()
        allowed = commercial.allowed_experiments(self.root)
        self.assertEqual(allowed['ids'], ['site:demo'])
        self.assertFalse(allowed['available'])

    def test_installed_preview_without_projection_cannot_claim_completeness(self):
        self.git_source()
        self.write('work/world/status.json', {'missions': [{'mission_id': 'ONLY-PREVIEW'}]})
        allowed = commercial.allowed_experiments(self.root)
        self.assertFalse(allowed['available'])
        self.assertEqual(allowed['ids'], ['site:demo'])

    def test_budget_exhaustion_is_explicit_and_does_not_read_beyond_limit(self):
        from unittest.mock import patch
        self.pages()
        with patch.object(commercial, 'MAX_MISSION_PAGES', 1):
            allowed = commercial.allowed_experiments(self.root)
        self.assertTrue(allowed['truncated'])
        self.assertTrue(allowed['available'])
        self.assertNotIn('mission:M39', allowed['ids'])
        self.git_source()
        with patch.object(commercial, 'MAX_SITE_ENTRIES', 0):
            allowed = commercial.allowed_experiments(self.root)
        self.assertTrue(allowed['truncated'])
        self.assertNotIn('site:demo', allowed['ids'])

    def test_mission_page_symlink_and_inconsistent_count_are_rejected(self):
        self.pages()
        path = self.root / 'work/world/pages/missions-1.json'
        page = json.loads(path.read_text())
        page['items'].pop()
        path.write_text(json.dumps(page))
        self.assertFalse(commercial.allowed_experiments(self.root)['available'])
        target = self.write('outside.json', page)
        path.unlink()
        path.symlink_to(target)
        self.assertFalse(commercial.allowed_experiments(self.root)['available'])


if __name__ == '__main__':
    unittest.main()
