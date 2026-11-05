"""PUBLISH_SITE: static sites on Cloudflare Workers, against a fake API and a real Node run of the module."""
import base64
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import sites
import test_autonomous_integration as integration
from sites import Publisher, SiteError, load_site

INDEX = '<!doctype html><title>GlobalLand</title><h1>Chronique</h1><footer>Made by autonomous AI agents.</footer>'
PNG = base64.b64encode(bytes(range(256))).decode()
ACCOUNT = 'a' * 32
CONFIG = {'cloudflare': {'enabled': True, 'account_id': ACCOUNT}}


def write_site(work, name='chronicle', index=INDEX, extra=None):
    base = pathlib.Path(work) / 'products/sites' / name
    (base / 'img').mkdir(parents=True, exist_ok=True)
    (base / 'index.html').write_text(index)
    (base / 'style.css').write_text('body{font-family:sans-serif}')
    (base / 'img/logo.png.b64').write_text(PNG)
    (base / 'about/index.html').parent.mkdir(exist_ok=True)
    (base / 'about/index.html').write_text('<p>About — agents IA autonomes</p>')
    for rel, text in (extra or {}).items():
        (base / rel).write_text(text)
    return base


class FakeCloudflare:
    def __init__(self, serve=True):
        self.calls, self.scripts, self.enabled, self.serve = [], {}, {}, serve

    def __call__(self, method, path, body=None, content_type='application/json'):
        self.calls.append((method, path))
        if method == 'PUT' and '/workers/scripts/' in path:
            assert content_type.startswith('multipart/form-data; boundary=')
            self.scripts[path.rsplit('/', 1)[1]] = body
            return 200, {'success': True, 'result': {'id': path.rsplit('/', 1)[1]}}
        if method == 'POST' and path.endswith('/subdomain'):
            self.enabled[path.split('/')[-2]] = body['enabled']
            return 200, {'success': True, 'result': body}
        if method == 'GET' and path.endswith('/workers/subdomain'):
            return 200, {'success': True, 'result': {'subdomain': 'globalland-founder'}}
        return 404, None

    def fetch(self, url):
        return (200, INDEX.encode()) if self.serve else (200, b'old page')


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        write_site(self.root / 'work')
        self.fake = FakeCloudflare()

    def publisher(self, config=CONFIG, reviews=None, origin=('THINK-2', 'claude')):
        return Publisher(self.root, config, client=sites.Client('token-not-used', transport=self.fake), reviews=reviews,
                         origin=origin, fetch=self.fake.fetch, sleep=lambda s: None)

    def task(self, ident='TASK-179349120010', **args):
        return {'id': ident, 'submitted_by': 'ACQUISITION', 'action': 'PUBLISH_SITE', 'args': dict({'site': 'chronicle'}, **args)}

    def founder_review(self, digest):
        return [dict(reviewer='FOUNDER', subject='site:chronicle', digest=digest, verdict='APPROVE', at=1, seq=1,
                     host_turn='FOUNDER-1', host_provider='FOUNDER')]

    def test_source_rules(self):
        files, digest = load_site(self.root / 'work', 'chronicle')
        self.assertEqual(set(files), {'/index.html', '/style.css', '/img/logo.png', '/about/index.html'})
        self.assertEqual(files['/img/logo.png']['c'], 'image/png')
        self.assertEqual(base64.b64decode(files['/img/logo.png']['b']), bytes(range(256)))
        cases = {'no disclosure': dict(index='<h1>Shop</h1>'),
                 'secret': dict(extra={'config.js': 'const k = "ghp_' + 'y' * 30 + '"'}),
                 'bad base64': dict(extra={'x.png.b64': '***'}),
                 'binary as text': dict(extra={'x.bin': ''})}
        for label, kwargs in cases.items():
            with self.subTest(label):
                work = self.root / ('other-' + label.replace(' ', '-'))
                base = write_site(work, **kwargs)
                if label == 'binary as text':
                    (base / 'x.bin').write_bytes(b'\xff\xfe\x00')
                with self.assertRaises(ValueError):
                    load_site(work, 'chronicle')
        for bad in ('../etc', 'UPPER', 'a' * 41):
            with self.subTest(bad=bad), self.assertRaisesRegex(SiteError, 'Invalid site name'):
                load_site(self.root / 'work', bad)

    def catalog(self):
        seed = self.root / 'seed'
        (self.root / 'work').rename(seed)
        for args in (['init', str(seed)], ['-C', str(seed), 'add', '.'],
                     ['-C', str(seed), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                      'commit', '-m', 'site'], ['clone', '--bare', str(seed), str(self.root / 'source.git')]):
            subprocess.run(['git'] + args, check=True, capture_output=True, timeout=30)
        return seed

    def test_catalog_dry_run_without_work_preserves_digest_and_binary_content(self):
        expected = load_site(self.root / 'work', 'chronicle')
        self.catalog()
        result = Publisher(self.root, {}).publish(self.task(dry_run=True))
        self.assertEqual(result['review_digest'], expected[1])
        self.assertFalse((self.root / 'work').exists())

    def test_catalog_online_ignores_stale_work_and_keeps_review_gate(self):
        _, digest = load_site(self.root / 'work', 'chronicle')
        self.catalog()
        write_site(self.root / 'work', index='stale invalid source')
        with self.assertRaisesRegex(SiteError, 'review APPROVE'):
            self.publisher().publish(self.task())
        self.assertEqual(self.fake.calls, [])
        result = self.publisher(reviews=self.founder_review(digest)).publish(self.task())
        self.assertEqual(result['status'], 'ONLINE_VERIFIED')
        self.assertIn(b'logo.png', self.fake.scripts['globalland-chronicle'])
        self.assertEqual((self.root / 'work/products/sites/chronicle/index.html').read_text(), 'stale invalid source')

    def test_offline_ignores_unusable_catalog_and_absent_work(self):
        shutil.rmtree(self.root / 'work')
        (self.root / 'source.git').mkdir()
        result = self.publisher().publish(self.task(online=False))
        self.assertEqual(result['status'], 'OFFLINE')
        self.assertFalse(self.fake.enabled['globalland-chronicle'])

    def test_catalog_preserves_existing_encoded_asset_size_allowance(self):
        (self.root / 'work/products/sites/chronicle/img/logo.png.b64').write_bytes(base64.b64encode(b'\0' * 800_000))
        expected = load_site(self.root / 'work', 'chronicle')[1]
        self.catalog()
        self.assertEqual(Publisher(self.root, {}).publish(self.task(dry_run=True))['review_digest'], expected)

    def test_invalid_catalog_cannot_fall_back_to_valid_work(self):
        (self.root / 'source.git').mkdir()
        with self.assertRaisesRegex(SiteError, 'catalog unavailable or invalid'):
            self.publisher().publish(self.task(dry_run=True))
        self.assertEqual(self.fake.calls, [])

    def test_catalog_operation_files_are_cleaned_after_loading(self):
        self.catalog()
        operations, original = [], sites.load_site
        def observed(work, site):
            operations.append(pathlib.Path(work))
            return original(work, site)
        with patch('sites.load_site', side_effect=observed):
            Publisher(self.root, {}).publish(self.task(dry_run=True))
        self.assertTrue(operations)
        self.assertTrue(all(not path.exists() for path in operations))

    def test_unrelated_large_product_does_not_block_site_export(self):
        (self.root / 'work/products/unrelated.bin').write_bytes(b'z' * (17 * 1024 * 1024))
        self.catalog()
        self.assertEqual(Publisher(self.root, {}).publish(self.task(dry_run=True))['status'], 'DRY_RUN')

    def test_work_fixture_parent_symlink_cannot_escape_site_source(self):
        folder = self.root / 'work/products/sites'
        folder.rename(self.root / 'outside-sites')
        try:
            folder.symlink_to(self.root / 'outside-sites', target_is_directory=True)
        except OSError:
            self.skipTest('directory symlinks unavailable')
        with self.assertRaises(SiteError):
            Publisher(self.root, {}).publish(self.task(dry_run=True))

    def test_generated_worker_serves_the_site_in_node(self):
        files, _ = load_site(self.root / 'work', 'chronicle')
        module = self.root / 'worker.mjs'
        module.write_text(sites.build_module(files))
        probe = self.root / 'probe.mjs'
        probe.write_text("""
import worker from %s;
const out = {};
for (const [method, path] of [['GET','/'],['GET','/style.css'],['GET','/img/logo.png'],['GET','/about/'],['GET','/missing'],['POST','/'],['GET','/%%E0%%A4%%A']]) {
  const r = await worker.fetch(new Request('https://chronicle.example.workers.dev' + path, {method}));
  const buf = new Uint8Array(await r.arrayBuffer());
  out[method + ' ' + path] = {status: r.status, type: r.headers.get('content-type'), len: buf.length,
    first: buf[0], nosniff: r.headers.get('x-content-type-options'), text: new TextDecoder().decode(buf).slice(0, 60)};
}
console.log(JSON.stringify(out));
""" % json.dumps(module.as_uri()))
        result = json.loads(subprocess.run(['node', str(probe)], capture_output=True, text=True, check=True, timeout=30).stdout)
        self.assertEqual(result['GET /']['status'], 200)
        self.assertIn('Chronique', result['GET /']['text'])
        self.assertEqual(result['GET /']['nosniff'], 'nosniff')
        self.assertEqual(result['GET /style.css']['type'], 'text/css; charset=utf-8')
        self.assertEqual((result['GET /img/logo.png']['len'], result['GET /img/logo.png']['first']), (256, 0))
        self.assertIn('agents IA', result['GET /about/']['text'])
        self.assertEqual(result['GET /missing']['status'], 404)
        self.assertEqual(result['POST /']['status'], 405)
        self.assertEqual(result['GET /%E0%A4%A']['status'], 400)

    def test_dry_run_needs_no_account_and_returns_the_review_digest(self):
        result = Publisher(self.root, {}).publish(self.task(dry_run=True))
        self.assertEqual(result['status'], 'DRY_RUN')
        self.assertEqual(result['review_digest'], load_site(self.root / 'work', 'chronicle')[1])
        self.assertEqual(self.fake.calls, [])

    def test_going_online_needs_a_host_bound_review(self):
        _, digest = load_site(self.root / 'work', 'chronicle')
        same_brain = [dict(reviewer='AUDITOR', subject='site:chronicle', digest=digest, verdict='APPROVE', at=1, seq=1,
                           host_turn='THINK-1', host_provider='claude')]
        for reviews in ([], same_brain):
            with self.assertRaisesRegex(SiteError, 'review APPROVE'):
                self.publisher(reviews=reviews).publish(self.task())
        self.assertEqual(self.fake.calls, [])

    def test_deploy_verify_and_take_offline(self):
        _, digest = load_site(self.root / 'work', 'chronicle')
        result = self.publisher(reviews=self.founder_review(digest)).publish(self.task())
        self.assertEqual(result['status'], 'ONLINE_VERIFIED')
        self.assertEqual(result['url'], 'https://globalland-chronicle.globalland-founder.workers.dev/')
        self.assertEqual(Publisher.task_status(result), 'DONE')
        body = self.fake.scripts['globalland-chronicle']
        self.assertIn(b'"main_module": "worker.js"', body)
        self.assertIn(b'name="worker.js"; filename="worker.js"', body)
        self.assertTrue(self.fake.enabled['globalland-chronicle'])
        journal = list((self.root / 'state/sites').glob('chronicle-*.json'))
        self.assertEqual(json.loads(journal[0].read_text())['step'], 'DONE')
        offline = self.publisher(reviews=[]).publish(self.task('TASK-179349120011', online=False))
        self.assertEqual(offline['status'], 'OFFLINE')
        self.assertFalse(self.fake.enabled['globalland-chronicle'])
        self.assertTrue(all('/workers/scripts/globalland-' in p or p.endswith('/workers/subdomain') for _, p in self.fake.calls))

    def test_unverified_page_is_reported_not_claimed(self):
        self.fake.serve = False
        _, digest = load_site(self.root / 'work', 'chronicle')
        result = self.publisher(reviews=self.founder_review(digest)).publish(self.task())
        self.assertEqual((result['status'], Publisher.task_status(result)), ('ONLINE_UNVERIFIED', 'TIMEOUT'))

    def test_configuration_and_token_are_host_controlled(self):
        with self.assertRaisesRegex(SiteError, 'not enabled'):
            Publisher(self.root, {}).publish(self.task())
        with self.assertRaises(ValueError):
            sites.settings({'cloudflare': {'enabled': True, 'account_id': 'not-hex'}})
        with self.assertRaisesRegex(SiteError, 'No Cloudflare integration configured'):
            Publisher(self.root, {'cloudflare': dict(CONFIG['cloudflare'], require_review=False)}).publish(self.task())


class AuditRegressionTests(SiteTests):
    """Findings of the independent code review (2026-11-01)."""

    def receipt(self, task, provider, path='products/sites/chronicle/index.html'):
        seconds = int(task[5:15])
        (self.root / 'state/controller').mkdir(parents=True, exist_ok=True)
        (self.root / ('state/controller/THINK-%d.json' % seconds)).write_text(json.dumps({'provider': provider}))
        receipts = self.root / 'work/products/receipts'
        receipts.mkdir(parents=True, exist_ok=True)
        (receipts / (task + '.json')).write_text(json.dumps({'task': task, 'outputs': {path: 'x'}}))

    def review(self, digest, provider, turn):
        return [dict(reviewer='AUDITOR', subject='site:chronicle', digest=digest, verdict='APPROVE', at=1, seq=1,
                     host_turn=turn, host_provider=provider)]

    def test_offline_switch_works_even_when_the_source_is_gone(self):
        import shutil
        shutil.rmtree(self.root / 'work/products/sites/chronicle')
        result = self.publisher(reviews=[]).publish(self.task(online=False))
        self.assertEqual(result['status'], 'OFFLINE')

    def test_reviewer_must_be_independent_of_the_content_authors(self):
        _, digest = load_site(self.root / 'work', 'chronicle')
        self.receipt('TASK-179349000010', 'claude')  # claude wrote the site
        # claude approves in another turn, codex publishes: claude reviewed its own work.
        with self.assertRaisesRegex(SiteError, 'review APPROVE'):
            self.publisher(reviews=self.review(digest, 'claude', 'THINK-1793490500'), origin=('THINK-1793491000', 'codex')).publish(self.task())
        # codex approves, claude (the author) publishes in another turn: independent second key.
        ok = self.publisher(reviews=self.review(digest, 'codex', 'THINK-1793490500'), origin=('THINK-1793491000', 'claude')).publish(self.task())
        self.assertEqual(ok['status'], 'ONLINE_VERIFIED')

    def test_catalog_receipts_keep_content_authors_when_work_is_absent(self):
        _, digest = load_site(self.root / 'work', 'chronicle')
        self.receipt('TASK-179349000010', 'claude')
        self.catalog()
        from review import authors
        self.assertEqual(authors(self.root, 'products/sites/chronicle'), {'claude'})
        with self.assertRaisesRegex(SiteError, 'review APPROVE'):
            self.publisher(reviews=self.review(digest, 'claude', 'THINK-1793490500'),
                           origin=('THINK-1793491000', 'codex')).publish(self.task())
        self.assertEqual(self.fake.calls, [])

    def test_pending_private_receipt_cannot_erase_content_authors(self):
        _, digest = load_site(self.root / 'work', 'chronicle')
        self.receipt('TASK-179349000010', 'claude')
        receipt_path = self.root / 'work/products/receipts/TASK-179349000010.json'
        record = {'id': 'TASK-179349000010', 'state': 'COMPLETED', 'files': {
            'products/receipts/TASK-179349000010.json': receipt_path.read_text()}}
        (self.root / 'state/TASK-179349000010.json').write_text(json.dumps(record))
        receipt_path.unlink()
        self.catalog()
        from review import authors
        self.assertEqual(authors(self.root, 'products/sites/chronicle'), {'claude'})
        with self.assertRaisesRegex(SiteError, 'review APPROVE'):
            self.publisher(reviews=self.review(digest, 'claude', 'THINK-1793490500'),
                           origin=('THINK-1793491000', 'codex')).publish(self.task())
        self.assertEqual(self.fake.calls, [])

    def test_malformed_catalog_receipt_fails_closed_but_offline_still_works(self):
        _, digest = load_site(self.root / 'work', 'chronicle')
        self.receipt('TASK-179349000010', 'claude')
        (self.root / 'work/products/receipts/TASK-179349000010.json').write_text('{')
        self.catalog()
        with self.assertRaisesRegex(ValueError, 'provenance unavailable or invalid'):
            self.publisher(reviews=self.founder_review(digest)).publish(self.task())
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(self.publisher().publish(self.task(online=False))['status'], 'OFFLINE')

    def test_published_journal_payload_is_skipped_with_identity_checked_sidecar(self):
        from result_envelope import write_result_envelope
        from review import authors, MAX_JOURNAL
        self.receipt('TASK-179349000010', 'claude')
        self.catalog()
        record = {'id': 'TASK-179349000010', 'hash': 'a' * 64, 'state': 'PUBLISHED',
                  'result': {'status': 'DONE', 'output': ''}}
        path = self.root / 'state/TASK-179349000010.json'
        with path.open('w') as stream:
            stream.write(json.dumps(record)[:-1] + ',"retained_artifact":"')
            for _ in range(MAX_JOURNAL // (1024 * 1024) + 1):
                stream.write('x' * (1024 * 1024))
            stream.write('"}')
        write_result_envelope(self.root, record)
        self.assertEqual(authors(self.root, 'products/sites/chronicle'), {'claude'})

    def test_hidden_files_and_receipts_are_never_published(self):
        base = self.root / 'work/products/sites/chronicle'
        (base / 'receipts').mkdir()
        (base / 'receipts/2026-10.txt').write_text('private receipt')
        (base / '.env').write_text('X=1')
        files, _ = load_site(self.root / 'work', 'chronicle')
        self.assertFalse(any('receipt' in name or '.env' in name for name in files))

    def test_oversized_file_is_refused(self):
        (self.root / 'work/products/sites/chronicle/huge.txt').write_bytes(b'a' * 1_600_000)
        with self.assertRaisesRegex(SiteError, 'too large'):
            load_site(self.root / 'work', 'chronicle')

    def test_founder_cli_can_approve_a_site(self):
        import review_admin
        from world import World
        world = World(self.root / 'w.sqlite3'); world.bootstrap()
        _, digest = load_site(self.root / 'work', 'chronicle')
        review = review_admin.approve(world, 'chronicle', digest, kind='site')
        self.assertEqual(review['subject'], 'site:chronicle')
        ok = self.publisher(reviews=world.reviews()).publish(self.task())
        self.assertEqual(ok['status'], 'ONLINE_VERIFIED')


class PublishSiteQueueIntegration(unittest.TestCase):
    setUp = integration.AutonomousIntegration.setUp
    git = integration.AutonomousIntegration.git
    submit = integration.AutonomousIntegration.submit

    def run(self, args=None, result=None):
        if isinstance(args, list):
            return subprocess.run(args, check=True, capture_output=True).stdout
        return super().run(args if args is not None else result)

    def test_dry_run_through_the_queue_returns_the_digest(self):
        write_site(self.seed)
        self.git('add', '.'); self.git('commit', '-m', 'site'); self.git('push', 'origin', 'main')
        self.submit(140, 'PUBLISH_SITE', {'site': 'chronicle', 'dry_run': True})
        self.app.cycle('queue')
        result = json.loads(self.run(['git', '--git-dir=' + str(self.remote), 'show', 'main:queue/done/TASK-0140.result.json']))
        self.assertEqual(json.loads(result['output'])['status'], 'DRY_RUN')
        self.submit(141, 'PUBLISH_SITE', {'site': 'chronicle'})
        self.app.cycle('queue')
        refused = json.loads(self.run(['git', '--git-dir=' + str(self.remote), 'show', 'main:queue/failed/TASK-0141.result.json']))
        self.assertIn('Cloudflare integration not enabled by the founder', refused['output'])


if __name__ == '__main__':
    unittest.main()
