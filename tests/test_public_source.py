"""Real Git acceptance tests for the host-only public source catalog."""
import base64
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from public_source import PublicSource, PublicSourceError, public_export_directory, validate_public_path


class PublicSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.repo = self.root / 'source.git'
        self.git('init', '--bare', str(self.repo), bare=False)
        self.git('config', 'user.name', 'Catalog Test')
        self.git('config', 'user.email', 'catalog@example.invalid')

    def git(self, *args, data=None, bare=True):
        argv = ['git'] + (['--git-dir', str(self.repo)] if bare else []) + list(args)
        return subprocess.run(argv, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True).stdout.strip()

    def commit(self, files, parent=None):
        self.git('read-tree', '--empty')
        for name, value in files.items():
            mode, content = value if isinstance(value, tuple) else ('100644', value)
            oid = (content if mode == '160000' else self.git('hash-object', '-w', '--stdin', data=content)).decode()
            self.git('update-index', '--add', '--cacheinfo', mode, oid, name)
        tree = self.git('write-tree').decode()
        args = ['commit-tree', tree] + (['-p', parent] if parent else [])
        revision = self.git(*args, data=b'catalog test\n').decode()
        self.git('update-ref', 'HEAD', revision)
        return revision

    def collect(self, source, prefix='products/', size=97):
        result, cursor = [], None
        while True:
            page = source.list(prefix, cursor, size)
            self.assertEqual(page['revision'], source.revision)
            result.extend(page['entries'])
            cursor = page['next_cursor']
            if cursor is None:
                return result

    def test_large_corpus_pagination_pin_history_and_selected_export(self):
        files = {'products/%04d.txt' % n: b'product' + b'x' * 40000 for n in range(629)}
        files['products/0629.txt'] = b'product'
        files['archive/huge.bin'] = b'x' * (21 * 1024 * 1024)
        files['products/demo/build.py'] = b'print("ok")\n'
        first = self.commit(files)
        source = PublicSource(self.root)
        page = source.list(limit=100)
        second = self.commit({'products/new.txt': b'new'}, first)
        entries = self.collect(source)
        self.assertEqual(len(entries), 631)
        self.assertEqual(len({e['path'] for e in entries}), 631)
        self.assertEqual([e['path'] for e in entries], sorted(e['path'] for e in entries))
        self.assertEqual(source.read('products/0629.txt')['content'], 'product')
        self.assertEqual(PublicSource(self.root, first).list(cursor=page['next_cursor'])['revision'], first)
        self.assertEqual(PublicSource(self.root).revision, second)
        with self.assertRaises(PublicSourceError):
            PublicSource(self.root).list(cursor=page['next_cursor'])
        out = self.root / 'job'
        manifest = source.export(['products/demo/'], out, 1024)
        self.assertEqual(manifest['total_bytes'], 12)
        self.assertEqual((out / 'products/demo/build.py').read_bytes(), b'print("ok")\n')
        self.assertEqual(self.git('rev-parse', first).decode(), first)

    def test_utf8_binary_and_arbitrary_offsets_are_lossless(self):
        raw = ('a' * 65535 + '🌍é' * 20000).encode()
        self.commit({'products/unicode.txt': raw, 'products/binary': b'\xff\x00\x80'})
        source, offset, pieces = PublicSource(self.root), 0, []
        while True:
            part = source.read('products/unicode.txt', offset)
            chunk = part['content'].encode() if part['encoding'] == 'utf-8' else base64.b64decode(part['content'])
            self.assertLessEqual(len(chunk), 65536)
            pieces.append(chunk)
            offset = part['next_offset']
            if part['eof']:
                break
        self.assertEqual(b''.join(pieces), raw)
        part = source.read('products/unicode.txt', 65536, 2)
        self.assertEqual(base64.b64decode(part['content']), raw[65536:65538])
        self.assertEqual(source.read('products/binary')['encoding'], 'base64')
        self.assertEqual(source.read('products/binary', 3)['next_offset'], 3)

    def test_preflight_budget_missing_size_modes_and_empty_inputs(self):
        initial = self.commit({'seed': b'seed'})
        self.commit({'products/a': b'a' * 10, 'products/b': b'b' * 10,
                     'huge': b'h' * (1048576 + 1), 'link': ('120000', b'/etc/passwd'),
                     'module': ('160000', initial.encode())}, initial)
        source = PublicSource(self.root)
        self.assertEqual(len(source.list()['entries']), 2)
        for inputs, budget in [(['products/'], 19), (['missing'], 100), (['huge'], 1048576),
                               (['link'], 100), (['module/'], 100), (None, 3000000)]:
            destination = self.root / 'must-not-exist'
            with self.subTest(inputs=inputs), self.assertRaises(PublicSourceError):
                source.export(inputs, destination, budget)
            self.assertFalse(destination.exists())
        source.export([], self.root / 'empty', 0)
        self.assertEqual(list((self.root / 'empty').iterdir()), [])
        source.export(['huge'], self.root / 'large', 1048577)
        self.assertEqual((self.root / 'large/huge').stat().st_size, 1048577)
        manifest = source.export(['products/a', 'products/'], self.root / 'safe', 20)
        self.assertEqual(manifest['total_bytes'], 20)
        self.assertEqual(len(manifest['entries']), 2)

    def test_untrusted_paths_revisions_cursors_and_destination_links(self):
        self.commit({'products/safe': b'ok', 'products/link': ('120000', b'/etc/passwd'),
                     'products/bad\nname': b'bad'})
        source = PublicSource(self.root)
        self.assertEqual([e['path'] for e in source.list()['entries']], ['products/safe'])
        for path in ['../secret', '/tmp/file', 'products/../safe', '.git/config',
                     'products/a\\b', 'products/*', 'products/:(glob)**', 'products/bad\nname']:
            with self.subTest(path=path), self.assertRaises(PublicSourceError):
                source.read(path)
        for revision in ['HEAD', 'HEAD:products/safe', '-' + 'a' * 40, 'a' * 39]:
            with self.assertRaises(PublicSourceError):
                PublicSource(self.root, revision)
        for cursor in ['{}', 'a' * 20000]:
            with self.assertRaises(PublicSourceError):
                source.list(cursor=cursor)
        if os.name != 'nt':
            outside = self.root / 'outside'
            outside.mkdir()
            (self.root / 'linked').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(PublicSourceError):
                source.export(['products/safe'], self.root / 'linked/job', 100)
            self.assertEqual(list(outside.iterdir()), [])

    def test_git_environment_and_repository_config_cannot_run_helpers(self):
        self.commit({'products/safe': b'ok'})
        self.git('config', 'core.fsmonitor', 'touch ' + str(self.root / 'ran'))
        old = os.environ.get('GIT_EXTERNAL_DIFF')
        os.environ['GIT_EXTERNAL_DIFF'] = 'touch ' + str(self.root / 'ran')
        try:
            self.assertEqual(PublicSource(self.root).read('products/safe')['content'], 'ok')
        finally:
            if old is None:
                os.environ.pop('GIT_EXTERNAL_DIFF', None)
            else:
                os.environ['GIT_EXTERNAL_DIFF'] = old
        self.assertFalse((self.root / 'ran').exists())

    def test_exports_public_modes_even_with_restrictive_host_umask(self):
        self.commit({'products/deep/file': b'public'})
        previous = os.umask(0o077)
        try:
            PublicSource(self.root).export(['products/'], self.root / 'job', 100)
        finally:
            os.umask(previous)
        for path in [self.root / 'job', self.root / 'job/products', self.root / 'job/products/deep']:
            self.assertEqual(path.stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.root / 'job/products/deep/file').stat().st_mode & 0o777, 0o644)

    def test_corrupt_blob_hash_fails_without_exposing_partial_destination(self):
        self.commit({'products/bad': b'abc', 'products/good': b'good'})
        source = PublicSource(self.root)
        entry = next(e for e in source.list()['entries'] if e['path'] == 'products/bad')
        loose = self.repo / 'objects' / entry['oid'][:2] / entry['oid'][2:]
        loose.chmod(0o644)
        loose.write_bytes(zlib.compress(b'blob 3\0xyz'))
        with self.assertRaises(PublicSourceError):
            source.export(['products/'], self.root / 'bad-job', 100)
        self.assertFalse((self.root / 'bad-job').exists())
        self.assertEqual(list(self.root.glob('.public-source-*')), [])
        source.export(['products/good'], self.root / 'good-job', 100)
        self.assertEqual((self.root / 'good-job/products/good').read_bytes(), b'good')

    @unittest.skipIf(os.name == 'nt', 'Linux resource accounting and public executor runtime')
    def test_streaming_real_git_memory_and_copy_benchmark(self):
        """Measure fresh reader processes, excluding fixture creation memory."""
        script = r'''
import json, pathlib, resource, sys, time, tracemalloc
from public_source import PublicSource
count = 0
def audit(event, args):
    global count
    if event == 'subprocess.Popen':
        count += 1
sys.addaudithook(audit)
tracemalloc.start()
start = time.monotonic()
source = PublicSource(sys.argv[1])
page = source.list()
part = source.read('products/large', 0, 65536)
manifest = source.export(['products/large', 'products/tiny'], pathlib.Path(sys.argv[1]) / 'job', int(sys.argv[2]) + 16)
status = dict(line.split(':', 1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
print(json.dumps(dict(corpus_bytes=int(sys.argv[2]), wall_seconds=time.monotonic()-start,
    processes=count, copied_files=len(manifest['entries']), copied_bytes=manifest['total_bytes'],
    python_peak_bytes=tracemalloc.get_traced_memory()[1],
    reader_peak_kib=int(status['VmHWM'].split()[0]),
    reader_ru_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    git_peak_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)))
'''
        results = []
        parent = None
        for mebibytes in (32, 256):
            blob = self.root / 'large-blob'
            with blob.open('wb') as stream:
                for _ in range(mebibytes):
                    stream.write(b'x' * (1024 * 1024))
            oid = self.git('hash-object', '-w', str(blob)).decode()
            blob.unlink()
            parent = self.commit({'products/tiny': b'small'}, parent)
            self.git('read-tree', parent)
            self.git('update-index', '--add', '--cacheinfo', '100644', oid, 'products/large')
            tree = self.git('write-tree').decode()
            parent = self.git('commit-tree', tree, '-p', parent, data=b'large benchmark\n').decode()
            self.git('update-ref', 'HEAD', parent)
            result = subprocess.run([sys.executable, '-c', script, str(self.root), str(mebibytes * 1024 * 1024)],
                                    env={**os.environ, 'PYTHONPATH': str(pathlib.Path(__file__).resolve().parents[1] / 'scripts')},
                                    check=True, capture_output=True, text=True)
            measured = json.loads(result.stdout)
            self.assertEqual(measured['copied_bytes'], mebibytes * 1024 * 1024 + 5)
            self.assertEqual(measured['copied_files'], 2)
            self.assertEqual(measured['processes'], 8)
            self.assertLess(measured['python_peak_bytes'], 2 * 1024 * 1024)
            self.assertLess(measured['reader_peak_kib'], 128 * 1024)
            self.assertLess(measured['git_peak_kib'], 128 * 1024)
            results.append(measured)
            shutil.rmtree(self.root / 'job')
        print('\nPublicSource real Git benchmark: ' + json.dumps(results, sort_keys=True))

    def test_default_revision_follows_confirmed_publication_ref(self):
        first = self.commit({'products/item': b'published'})
        self.git('update-ref', 'refs/globalland/published', first)
        second = self.commit({'products/item': b'pending'}, first)
        self.assertEqual(PublicSource(self.root).read('products/item')['content'], 'published')
        self.assertEqual(PublicSource(self.root, second).read('products/item')['content'], 'pending')
        self.git('update-ref', 'refs/globalland/published', second)
        self.assertEqual(PublicSource(self.root).read('products/item')['content'], 'pending')
        self.assertEqual(PublicSource(self.root, first).read('products/item')['content'], 'published')
        (self.repo / 'refs/globalland/published').write_text('malformed\n')
        with self.assertRaises(PublicSourceError):
            PublicSource(self.root)

    def test_unrelated_invalid_deep_or_non_utf8_paths_do_not_block_safe_inputs(self):
        deep = 'products/deep/' + ('d' * 120 + '/') * 80 + 'file'
        invalid_utf8 = 'products/nonutf8-' + chr(0xDCFF)
        self.commit({'products/safe': b'usable', deep: b'invalid path', invalid_utf8: b'invalid UTF8'})
        source = PublicSource(self.root)
        self.assertEqual([e['path'] for e in source.list()['entries']], ['products/safe'])
        source.export(['products/safe'], self.root / 'safe', 100)
        self.assertEqual((self.root / 'safe/products/safe').read_bytes(), b'usable')
        with self.assertRaises(PublicSourceError):
            source.export(['products/'], self.root / 'unsafe', 100)
        self.assertFalse((self.root / 'unsafe').exists())

    def test_limits_and_cursor_prefix_binding(self):
        self.commit({'products/a': b'a', 'products/b': b'b', 'other/a': b'a'})
        source = PublicSource(self.root)
        cursor = source.list(limit=1)['next_cursor']
        with self.assertRaises(PublicSourceError):
            source.list('other/', cursor)
        for offset, limit in [(-1, 1), (True, 1), (0, 0), (0, 65537), (2, 1)]:
            with self.subTest(offset=offset, limit=limit), self.assertRaises(PublicSourceError):
                source.read('products/a', offset, limit)

    def test_destination_parent_symlink_swap_cannot_redirect_or_leave_staging(self):
        parent=self.root/'parent';parent.mkdir()
        outside=self.root/'outside';outside.mkdir()
        relocated=self.root/'old-parent'
        with self.assertRaises(PublicSourceError):
            with public_export_directory(parent/'input') as staging:
                parent.rename(relocated)
                parent.symlink_to(outside,target_is_directory=True)
                (staging/'public').write_bytes(b'public')
        self.assertEqual(list(outside.iterdir()),[])
        self.assertEqual(list(relocated.iterdir()),[])

    def test_destination_changed_during_export_is_preserved_and_refused(self):
        destination=self.root/'input';destination.mkdir()
        with self.assertRaises(PublicSourceError):
            with public_export_directory(destination) as staging:
                (staging/'public').write_bytes(b'public')
                (destination/'concurrent').write_bytes(b'keep me')
        self.assertEqual((destination/'concurrent').read_bytes(),b'keep me')
        self.assertFalse((destination/'public').exists())
        self.assertEqual(list(self.root.glob('.public-source-*')),[])

    def test_public_path_validator_is_shared_and_rejects_repeated_slashes(self):
        self.assertEqual(validate_public_path('products/demo/'),'products/demo/')
        for path in ['products//','products/a//b',None,12]:
            with self.assertRaises(PublicSourceError):validate_public_path(path)

    def test_full_metadata_iterator_uses_one_process_for_ten_thousand_paths(self):
        script = r'''
import json, sys, time, tracemalloc
from public_source import PublicSource
source = PublicSource(sys.argv[1])
processes = 0
def audit(event, args):
    global processes
    if event == 'subprocess.Popen':
        processes += 1
sys.addaudithook(audit)
tracemalloc.start()
start = time.monotonic()
count, total, previous = 0, 0, ''
for entry in source.iter_entries('products/'):
    assert entry['path'] > previous
    previous = entry['path']
    count += 1
    total += entry['size']
print(json.dumps(dict(paths=count, selected_bytes=total, processes=processes,
    python_peak_bytes=tracemalloc.get_traced_memory()[1], wall_seconds=time.monotonic()-start)))
'''
        results = []
        for count in (1000, 10000):
            self.git('read-tree', '--empty')
            oid = self.git('hash-object', '-w', '--stdin', data=b'public').decode()
            rows = ''.join('100644 %s\tproducts/%05d.txt\0' % (oid, n) for n in range(count))
            rows += '120000 %s\tproducts/link\0' % oid
            self.git('update-index', '-z', '--index-info', data=rows.encode())
            tree = self.git('write-tree').decode()
            revision = self.git('commit-tree', tree, data=b'metadata benchmark\n').decode()
            self.git('update-ref', 'HEAD', revision)
            result = subprocess.run([sys.executable, '-c', script, str(self.root)],
                                    env={**os.environ, 'PYTHONPATH': str(pathlib.Path(__file__).resolve().parents[1] / 'scripts')},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            measured = json.loads(result.stdout)
            self.assertEqual(measured['paths'], count)
            self.assertEqual(measured['selected_bytes'], count * 6)
            self.assertEqual(measured['processes'], 1)
            self.assertLess(measured['python_peak_bytes'], 1024 * 1024)
            results.append(measured)
        print('\nPublicSource metadata benchmark: ' + json.dumps(results, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
