"""Offline regression checks; fake Cloudflare and durable executor only."""
import contextlib
import importlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
from tools import validate_envelope

def load_repository_operation():
    """Exercise the operator code against this checkout, without path leakage.

    Production intentionally prepends its installed control path. Pin the real
    repository dependencies before executing it and restore sys.path afterward,
    so discovery cannot cache an older installed sites/review implementation.
    """
    scripts = HERE.parent / 'scripts'
    with patch.object(sys, 'path', list(sys.path)):
        sys.path.insert(0, str(scripts))
        for name in ('supervisor', 'sites', 'review', 'tools'):
            module = importlib.import_module(name)
            if pathlib.Path(module.__file__).resolve() != scripts / (name + '.py'):
                raise AssertionError('operator test dependency is outside repository: ' + name)
        spec = importlib.util.spec_from_file_location('contact_publish', HERE.parent / 'ops/publish_welfare_brief.py')
        operation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(operation)
    return operation


helper = load_repository_operation()


class FakeSupervisor:
    def __init__(self, root):
        self.root = root
        self.calls = []
        self.effects = 0
        self.result = {'status': 'DONE', 'output': json.dumps({'status': 'ONLINE_VERIFIED'})}
        self.journal_state = 'PUBLISHED'
        self.envelope_valid = False
        self.world = Mock()
        self.world.reviews.return_value = []
        self.bank = Mock()
        self.bank.snapshot.return_value = {'state': 'UNFUNDED'}

    def services(self):
        return self.world, self.bank, {'cloudflare': {'enabled': True}}

    def execute_tool(self, task, *args, **kwargs):
        self.calls.append(task.copy())
        path = self.root / 'state' / (task['id'] + '.json')
        if path.exists():
            return json.loads(path.read_text())['result']
        try:
            validate_envelope(task)
            self.envelope_valid = True
        except ValueError as error:
            result = {'status': 'REJECTED', 'output': str(error)}
        else:
            self.effects += 1
            result = self.result.copy()
        # As in Supervisor, a recovered result does not carry the extra pending field.
        stored = {k: v for k, v in result.items() if k != 'publication'}
        path.write_text(json.dumps({'state': self.journal_state, 'result': stored}))
        return result


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / 'state/private').mkdir(parents=True)
        self.app = FakeSupervisor(self.root)
        self.api = Mock()
        self.api.call.return_value = {'subdomain': 'global-land'}
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        values = {'ROOT': self.root, 'Supervisor': lambda: self.app,
                  'Client': lambda token: self.api,
                  'read_token': lambda root: 'FAKE-NOT-A-CREDENTIAL',
                  'load_site': lambda *args: ({'/index.html': {'t': 'example'}}, helper.DIGEST),
                  'settings': lambda config: {'account_id': 'a' * 32, 'require_review': True},
                  'authors': lambda *args: {'claude'},
                  'approved': lambda *args: True}
        self.stack.enter_context(patch.multiple(helper, **values))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def test_real_envelope_contract_is_satisfied(self):
        code = helper.main('publish')
        self.assertTrue(self.app.envelope_valid)
        self.assertEqual(code, 0)
        validate_envelope(self.app.calls[0])

    def test_reentry_reuses_durable_request_without_another_effect(self):
        with patch.object(helper.time, 'time', side_effect=[1793831500, 1793831560]):
            self.assertEqual(helper.main('publish'), 0)
            self.assertEqual(helper.main('publish'), 0)
        self.assertEqual(self.app.effects, 1)
        self.assertEqual(self.app.calls[0], self.app.calls[1])

    def test_nonverified_results_return_failure(self):
        for status, value in [('REJECTED', 'refused'), ('FAILED', 'failed'),
                              ('TIMEOUT', json.dumps({'status': 'ONLINE_UNVERIFIED'})),
                              ('DONE', json.dumps({'status': 'ONLINE_UNVERIFIED'}))]:
            with self.subTest(status=status, value=value):
                # Each subcase gets an isolated request/journal directory.
                with tempfile.TemporaryDirectory() as tmp:
                    root = pathlib.Path(tmp)
                    (root / 'state/private').mkdir(parents=True)
                    app = FakeSupervisor(root)
                    app.result = {'status': status, 'output': value}
                    with patch.multiple(helper, ROOT=root, Supervisor=lambda: app):
                        self.assertEqual(helper.main('publish'), 1)

    def test_pending_git_receipt_stays_pending_on_reentry(self):
        self.app.journal_state = 'COMPLETED'
        self.app.result['publication'] = 'PENDING'
        self.assertEqual(helper.main('publish'), 1)
        self.assertEqual(helper.main('publish'), 1)
        self.assertEqual(self.app.effects, 1)
        proof = json.loads((self.root / 'state/private/contact-site-publication.json').read_text())
        self.assertTrue(proof['public_receipt_pending'])
        record_path = self.root / 'state' / (self.app.calls[0]['id'] + '.json')
        record = json.loads(record_path.read_text())
        record['state'] = 'PUBLISHED'
        record_path.write_text(json.dumps(record))
        self.assertEqual(helper.main('publish'), 0)
        self.assertEqual(self.app.effects, 1)

    def test_both_authors_are_retained_and_review_is_not_fabricated(self):
        approval = Mock(return_value=False)
        with patch.object(helper, 'approved', approval):
            with self.assertRaisesRegex(ValueError, 'Independent review'):
                helper.main('publish')
        self.assertEqual(approval.call_args.args[-1], {'codex', 'claude'})
        self.assertFalse(self.app.calls)
        self.app.world.apply.assert_not_called()

    def test_existing_different_request_is_rejected(self):
        request_path = self.root / 'state/private' / ('contact-site-request-' + helper.DIGEST + '.json')
        request_path.write_text(json.dumps({'site': helper.SITE, 'digest': 'wrong', 'task': {}}))
        with self.assertRaises(ValueError):
            helper.main('publish')
        self.assertFalse(self.app.calls)


class ImportIsolationTests(unittest.TestCase):
    def test_full_suite_discovery_never_imports_installed_control(self):
        # Use a fresh process: the test runner's cached modules can conceal the
        # operator helper loading an older installed sites.py or review.py.
        script = r'''
import importlib.machinery
import pathlib
import sys
import unittest

installed = pathlib.Path('/opt/globalland/control')
class RejectInstalledControl:
    def find_spec(self, fullname, path=None, target=None):
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.origin and pathlib.Path(spec.origin).is_relative_to(installed):
            raise AssertionError('test discovery attempted installed control import: ' + fullname)
        return None
sys.meta_path.insert(0, RejectInstalledControl())
loader = unittest.TestLoader()
suite = loader.discover(sys.argv[1])
assert not loader.errors, '\n'.join(loader.errors)
assert str(installed) not in sys.path, 'operator import leaked installed control into sys.path'
for name, module in list(sys.modules.items()):
    origin = getattr(module, '__file__', None)
    assert not origin or not pathlib.Path(origin).is_relative_to(installed), name
scripts = pathlib.Path(sys.argv[1]).parent / 'scripts'
for name in ('supervisor', 'sites', 'review', 'tools'):
    assert pathlib.Path(sys.modules[name].__file__).resolve() == scripts / (name + '.py'), name
print('Isolated discovery: %d tests; installed control imports: 0' % suite.countTestCases())
'''
        result = subprocess.run([sys.executable, '-c', script, str(HERE)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('installed control imports: 0', result.stdout)


if __name__ == '__main__':
    unittest.main()
