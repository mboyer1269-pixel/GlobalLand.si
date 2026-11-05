"""Catalog consumers retain access with a sparse public work directory."""
import base64
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from broker import read_handlers
import mail_agent
import progress


class CatalogConsumerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.repo = self.root / 'author'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        for n in range(520):
            self.write('products/items/%04d.txt' % n, b'old')
        self.large = ('a' * 65535 + '\U0001f680' + 'é' * 40000).encode()
        self.write('products/large.txt', self.large)
        self.write('products/unrelated.dat', b'x' * (17 * 1024 * 1024))
        self.write('products/services/demo/main.py', b'print("version one")\n')
        self.write('products/services/demo/README.md', b'Helpful service')
        self.write('products/receipts/TASK-1234.json', b'{"private":"receipt"}')
        self.commit()
        subprocess.run(['git', 'clone', '-q', '--bare', str(self.repo), str(self.root / 'source.git')], check=True)
        (self.root / 'work').mkdir()
        self.handlers = read_handlers(self.root, None, None, lambda: {})

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True).stdout.decode().strip()

    def write(self, path, raw):
        destination = self.repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')

    def advance(self):
        self.commit()
        subprocess.run(['git', '--git-dir=' + str(self.root / 'source.git'), 'fetch', '-q', str(self.repo), '+HEAD:refs/heads/' + self.git('branch', '--show-current')], check=True)

    def test_every_product_can_be_paged_after_head_changes(self):
        first = self.handlers['list_products'](limit=37)
        revision = first['revision']
        found = [e['path'] for e in first['entries']]
        self.write('products/new.txt', b'new')
        self.advance()
        cursor = first['next_cursor']
        while cursor:
            page = self.handlers['list_products'](revision=revision, cursor=cursor, limit=37)
            self.assertEqual(page['revision'], revision)
            found.extend(e['path'] for e in page['entries'])
            cursor = page['next_cursor']
        self.assertEqual(len(found), len(set(found)))
        self.assertIn('products/items/0519.txt', found)
        self.assertNotIn('products/new.txt', found)
        self.assertFalse(any('/receipts/' in p for p in found))
        self.assertIn('products/new.txt', [e['path'] for e in self.handlers['list_products'](prefix='products/new.txt')['entries']])

    def test_ranged_utf8_and_binary_reads_preserve_exact_bytes(self):
        raw = bytearray()
        offset = 0
        revision = self.handlers['list_products']()['revision']
        while offset < len(self.large):
            chunk = self.handlers['read_product']('products/large.txt', revision=revision, offset=offset, limit=65536)
            raw.extend(chunk['content'].encode() if chunk['encoding'] == 'utf-8' else base64.b64decode(chunk['content']))
            self.assertGreater(chunk['next_offset'], offset)
            offset = chunk['next_offset']
        self.assertEqual(bytes(raw), self.large)
        with self.assertRaises(ValueError):
            self.handlers['read_product']('products/receipts/TASK-1234.json')

    def test_binary_chunks_are_decoded_before_secret_screening(self):
        self.write('products/binary.dat', b'\xff\x00\x80binary')
        self.write('products/secret.dat', b'\xff' + b'sk-' + b'x' * 24)
        self.advance()
        chunk = self.handlers['read_product']('products/binary.dat', limit=3)
        self.assertEqual(chunk['encoding'], 'base64')
        self.assertEqual(base64.b64decode(chunk['content']), b'\xff\x00\x80')
        with self.assertRaisesRegex(ValueError,'secret pattern'):
            self.handlers['read_product']('products/secret.dat')

    def test_default_broker_reads_follow_confirmed_publication_not_pending_head(self):
        old = self.git('rev-parse','HEAD')
        bare = ['git','--git-dir=' + str(self.root / 'source.git')]
        subprocess.run(bare + ['update-ref','refs/globalland/published',old],check=True)
        self.write('products/items/0519.txt',b'pending replacement')
        self.advance()
        new = self.git('rev-parse','HEAD')
        visible = self.handlers['read_product']('products/items/0519.txt')
        self.assertEqual((visible['revision'],visible['content']),(old,'old'))
        pending = self.handlers['read_product']('products/items/0519.txt',revision=new)
        self.assertEqual(pending['content'],'pending replacement')
        subprocess.run(bare + ['update-ref','refs/globalland/published',new],check=True)
        visible = self.handlers['read_product']('products/items/0519.txt')
        self.assertEqual((visible['revision'],visible['content']),(new,'pending replacement'))

    def test_full_progress_and_frozen_private_source_ignore_sparse_work(self):
        with patch('public_source.PublicSource.read', side_effect=AssertionError('progress read a blob body')):
            before = progress.fingerprint(self.root, {}, {})
        self.assertIn('products/items/0519.txt', before['products'])
        self.assertFalse(any('/receipts/' in p for p in before['products']))
        frozen = mail_agent.public_context(self.root)
        source = next(e for e in frozen if e['path'].endswith('main.py'))
        original = source['text'].encode()
        self.assertEqual(source['sha256'], hashlib.sha256(original).hexdigest())
        self.write('products/services/demo/main.py', b'print("version two")\n')
        self.write('products/zz-late.txt', b'late product')
        self.advance()
        after = progress.fingerprint(self.root, {}, {})
        self.assertIn('products/zz-late.txt', progress.delta(before, after)['new_products'])
        self.assertEqual(source['text'].encode(), original)
        self.assertEqual(mail_agent.validate_public_context(frozen), frozen)
        newer = next(e for e in mail_agent.public_context(self.root) if e['path'].endswith('main.py'))
        self.assertNotEqual(newer['sha256'], source['sha256'])

    def test_catalog_identity_migration_does_not_count_unchanged_files_as_progress(self):
        current = progress.fingerprint(self.root, {}, {})
        # Previous versions persisted SHA256(body); the catalog persists Git
        # object IDs. Changed identity encoding alone cannot count as new work.
        previous = dict(products={name:hashlib.sha256((self.repo / name).read_bytes()).hexdigest()
                                  for name in current['products']}, missions={}, revenue_cents=0)
        change = progress.delta(previous,current)
        self.assertEqual(change['new_products'], [])
        self.assertEqual(change['new_product_count'], 0)
        self.assertEqual(change['new_research_count'], 0)
        self.assertFalse(change['productive'])
        self.assertEqual(change['rewritten_count'],len(current['products']))

    def test_sparse_controller_discovery_and_legacy_result_classification(self):
        from controller import Controller
        from treasury import Treasury
        from world import World
        task = dict(id='TASK-1234', type='TOOL', submitted_by='BUILDER',
                    created_at='2026-11-05T00:00:00Z', action='EXEC',
                    args=dict(argv=['true'], outputs=[]), description='fixture',
                    estimated_cost_cad=0, approved_by=None)
        raw = json.dumps(task).encode()
        self.write('queue/done/TASK-1234.json', raw)
        self.write('queue/done/TASK-1234.result.json', json.dumps(dict(
            status='DONE', output='public fallback', metadata=dict(id='TASK-1234',type='TOOL',action='STATUS'))).encode())
        self.advance()
        state = self.root / 'state'
        state.mkdir()
        (state / 'TASK-1234.json').write_text(json.dumps(dict(id='TASK-1234',
            hash=hashlib.sha256(raw).hexdigest(), result=dict(status='DONE',output='legacy success'))))
        world = World(state / 'world.sqlite3')
        world.bootstrap()
        bank = Treasury(state / 'bank.sqlite3')
        controller = Controller(self.root,world,bank,{})
        results,coverage,excluded = controller.recent_results()
        self.assertEqual(results[0]['output'], 'legacy success')
        self.assertFalse(results[0]['output_redacted'])
        self.assertEqual(len(coverage), 1)
        self.assertEqual(excluded, [])
        context = controller.context()
        self.assertLessEqual(len(context['source_products']), 100)
        self.assertIsNotNone(context['source_catalog']['next_cursor'])
        self.assertIn('omitted products are not absent', context['source_catalog']['discovery'])
        self.assertEqual(context['source_catalog']['revision'], self.git('rev-parse','HEAD'))


if __name__ == '__main__':
    unittest.main()
