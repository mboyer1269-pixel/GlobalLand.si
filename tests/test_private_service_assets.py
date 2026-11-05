"""Versioned public service bytes reach private sandboxes, never host imports."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from mail_agent import MAX_MESSAGE, public_context
from private_work import PrivateResponder

REPO = pathlib.Path(__file__).resolve().parents[1]


class ServiceAssetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.config = {'controller': {'providers': ['claude']},
                       'agentmail': {'fulfillment': {'enabled': True}},
                       'executor_enabled': True, 'executor_image': 'node@sha256:' + '1' * 64}
        self.message = dict(inbox_id='fixture-inbox', message_id='fixture-message', text='demo\r\né')

    def source(self, name='demo/program.js', raw=b'// synthetic source\r\n'):
        path = self.root / 'work/products/services' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def test_offered_diagnostic_source_is_complete_and_versioned_without_running_it(self):
        raw = (REPO / 'products/services/csv-text-diagnostic/diagnostic.py').read_bytes()
        self.source('csv-text-diagnostic/diagnostic.py', raw)
        entries = public_context(self.root)
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry['path'], 'products/services/csv-text-diagnostic/diagnostic.py')
        self.assertEqual(entry['text'].encode('utf-8'), raw)
        self.assertEqual(entry['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(entry['bytes'], len(raw))
        self.assertIs(entry['source_asset'], True)
        self.assertIs(entry['possibly_truncated'], False)

    def test_unsafe_or_incomplete_sources_are_omitted(self):
        self.source('demo/oversize.py', b'x' * (MAX_MESSAGE + 1))
        self.source('demo/binary.py', b'\xff')
        outside = self.root / 'outside.py'; outside.write_text('PRIVATE-OUTSIDE')
        self.source('demo/linked.py').unlink()
        (self.root / 'work/products/services/demo/linked.py').symlink_to(outside)
        os.link(outside, self.root / 'work/products/services/demo/hardlinked.js')
        self.source('demo/.hidden.py', b'PRIVATE-HIDDEN')
        self.assertEqual(public_context(self.root), [])

    def test_source_files_at_byte_limit_are_complete_and_total_context_is_bounded(self):
        self.source('demo/a.py', b'a' * MAX_MESSAGE)
        self.source('demo/b.js', b'b' * MAX_MESSAGE)
        self.source('demo/c.py', b'c')
        entries = public_context(self.root)
        self.assertEqual([entry['path'] for entry in entries],
                         ['products/services/demo/a.py', 'products/services/demo/b.js'])
        self.assertTrue(all(entry['bytes'] == MAX_MESSAGE and not entry['possibly_truncated'] for entry in entries))

    def test_frozen_source_executes_fixture_and_delivers_exact_produced_bytes(self):
        # This known synthetic program is the only source run by the process
        # seam. It proves byte flow, not Docker isolation or a live model/send.
        raw = (b"import json, pathlib\r\n"
               b"m=json.loads(pathlib.Path('incoming.json').read_text(encoding='utf-8'))\r\n"
               b"pathlib.Path('products/result.txt').write_bytes(m['text'].upper().encode('utf-8'))\r\n"
               b"print('observed fixture version one')\r\n")
        source = self.source('demo/program.py', raw=raw)
        # Freeze before a later responder resumes this still-working case.
        PrivateResponder(self.root, self.config)._open(self.message)
        source.write_text('raise RuntimeError("later version must not run")')
        name = 'products/services/demo/program.py'
        argv = ['python3', '-I', name]
        action = dict(summary='Run selected fixture', actions=[dict(agent='BUILDER', action='EXEC',
                      args=dict(argv=argv, outputs=['products/result.txt']))])
        prompts = []
        def plan(planner, provider, prompt):
            prompts.append(prompt)
            if len(prompts) == 1:
                self.assertIn(hashlib.sha256(raw).hexdigest(), prompt)
                self.assertNotIn('later version must not run', prompt)
                return action
            self.assertIn('observed fixture version one', prompt)
            self.assertNotIn('later version must not run', prompt)
            return dict(actions=[], summary=json.dumps(dict(action='reply', text='Computed fixture.',
                        artifacts=['products/result.txt'])))
        run = subprocess.run
        def sandbox(command, **kwargs):
            self.assertIn('none', command)
            mount = next(command[i+1] for i, item in enumerate(command[:-1])
                         if item == '--mount' and 'dst=/input,' in command[i+1])
            input_dir = pathlib.Path(mount.split(',dst=')[0].split('src=')[1])
            self.assertEqual((input_dir / name).read_bytes(), raw)
            request = input_dir.parent / 'request.json'
            workspace = input_dir.parent / 'fixture-execution'
            shutil.copytree(input_dir, workspace)
            args = json.loads(request.read_text())
            result = run(args['argv'], cwd=workspace, capture_output=True, check=True)
            files = {name: (workspace / name).read_bytes().decode('utf-8') for name in args['outputs']}
            return 0, json.dumps(dict(status='DONE', output=result.stdout.decode(), files=files)).encode()
        with (patch('controller.Controller.plan', plan), patch('private_work.bounded_run', sandbox),
              patch('private_work.subprocess.run') as cleanup):
            cleanup.return_value.returncode = 0
            reply = PrivateResponder(self.root, self.config)(self.message)
        expected = 'DEMO\r\nÉ'
        self.assertIn('--- BEGIN FILE ---\n' + expected + '\n--- END FILE ---', reply['text'])
        self.assertIn(hashlib.sha256(expected.encode()).hexdigest(), reply['text'])
        ledger = next((self.root / 'state/private/fulfillment').glob('*/case.json'))
        data = json.loads(ledger.read_text())
        self.assertEqual(data['steps'][0]['action']['args']['argv'], argv)
        self.assertEqual(data['steps'][0]['receipt']['input_service_sources'],
                         [dict(path=name, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))])
        self.assertEqual(data['steps'][0]['receipt']['files']['products/result.txt'], expected)
        with patch('controller.Controller.plan', side_effect=AssertionError('READY must replay')):
            self.assertEqual(PrivateResponder(self.root, self.config)(self.message), reply)
        data['steps'][0]['receipt']['input_service_sources'][0]['sha256'] = '0' * 64
        ledger.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            PrivateResponder(self.root, self.config)(self.message)

    def test_snapshot_corruption_is_refused_before_planning_or_execution(self):
        self.source()
        responder = PrivateResponder(self.root, self.config)
        path, data = responder._open(self.message)
        original = json.loads(path.read_text())
        for changes in ({'text': 'changed'}, {'path': 'products/../escape.py'},
                        {'possibly_truncated': True}, {'bytes': True}):
            data = json.loads(json.dumps(original))
            data['public_context']['entries'][0].update(changes)
            path.write_text(json.dumps(data))
            with self.subTest(changes=changes), patch('controller.Controller.plan', side_effect=AssertionError('corrupt snapshot')):
                with self.assertRaisesRegex(ValueError, '^Private work unavailable$'):
                    responder(self.message)

    def test_generated_artifacts_cannot_overwrite_selected_source_paths(self):
        self.source()
        for name in ('products/services/demo/program.js', 'products/services/demo'):
            action = dict(summary='Overwrite', actions=[dict(agent='BUILDER', action='EXEC',
                          args=dict(argv=['node', '-e', ''], outputs=[name]))])
            with self.subTest(name=name), patch('controller.Controller.plan', return_value=action), \
                    patch('private_work.bounded_run', side_effect=AssertionError('source overwrite')) as run:
                with self.assertRaises(ValueError):
                    PrivateResponder(self.root, self.config)(dict(self.message, message_id=name))
                run.assert_not_called()

    def test_legacy_working_and_ready_cases_keep_text_only_context_and_replay(self):
        self.source(raw=b'LEGACY-MUST-NOT-ACQUIRE-NEW-SOURCE')
        responder = PrivateResponder(self.root, self.config)
        path, data = responder._open(self.message)
        data.pop('public_context', None)
        path.write_text(json.dumps(data))
        def plan(planner, provider, prompt):
            self.assertNotIn('LEGACY-MUST-NOT-ACQUIRE-NEW-SOURCE', prompt)
            return dict(actions=[], summary=json.dumps(dict(action='reply', text='Legacy reply.', artifacts=[])))
        with patch('controller.Controller.plan', plan):
            reply = responder(self.message)
        self.assertNotIn('public_context', json.loads(path.read_text()))
        with patch('controller.Controller.plan', side_effect=AssertionError('legacy READY must replay')):
            self.assertEqual(responder(self.message), reply)


@unittest.skipUnless(os.environ.get('GLOBALLAND_DOCKER_SMOKE') == '1',
                     'real Docker smoke requires explicit daemon access')
class DockerServiceAssetTests(unittest.TestCase):
    setUp = ServiceAssetTests.setUp
    source = ServiceAssetTests.source

    def test_offered_diagnostic_runs_from_frozen_readonly_source_and_delivers_exact_json(self):
        image = json.loads(subprocess.check_output(['docker', 'image', 'inspect',
                           os.environ.get('GLOBALLAND_DOCKER_SMOKE_IMAGE', 'node:22-bookworm')]))[0]['RepoDigests'][0]
        self.config['executor_image'] = image
        (self.root / 'control').mkdir()
        (self.root / 'control/executor.js').write_bytes((REPO / 'scripts/executor.js').read_bytes())
        raw = (REPO / 'products/services/csv-text-diagnostic/diagnostic.py').read_bytes()
        source = self.source('csv-text-diagnostic/diagnostic.py', raw)
        self.message['text'] = 'Synthetic sample\n---CSV START---\nA,B\n1,2\n---CSV END---'
        selected = 'products/services/csv-text-diagnostic/diagnostic.py'
        wrapper = ("import hashlib,json,pathlib,subprocess; "
                   "source=pathlib.Path('/input/" + selected + "'); "
                   "print('source_sha256='+hashlib.sha256(source.read_bytes()).hexdigest()); "
                   "m=json.loads(pathlib.Path('incoming.json').read_text()); "
                   "result=subprocess.run(['python3','-I',str(source)],input=m['text'],text=True,capture_output=True,check=True); "
                   "pathlib.Path('products/diagnostic.json').write_bytes(result.stdout.encode('utf-8'))")
        turns = []
        def plan(planner, provider, prompt):
            turns.append(prompt)
            if len(turns) == 1:
                source.write_text('raise RuntimeError("new public version must not run")')
                return dict(summary='Run the frozen diagnostic inside EXEC', actions=[dict(agent='BUILDER',
                            action='EXEC', args=dict(argv=['python3', '-I', '-c', wrapper],
                                                    outputs=['products/diagnostic.json']))])
            self.assertIn('source_sha256=' + hashlib.sha256(raw).hexdigest(), prompt)
            return dict(actions=[], summary=json.dumps(dict(action='reply', text='Computed supplied synthetic sample.',
                        artifacts=['products/diagnostic.json'])))
        with patch('controller.Controller.plan', plan):
            reply = PrivateResponder(self.root, self.config)(self.message)
        expected = json.dumps(dict(status='CHECKED', structure_ok=True, dataRows=1, columns=2, errors=[],
                     not_checked=['amounts', 'dates', 'tax', 'currency', 'customer or account mappings',
                                  'semicolon/tab delimiters', 'encoding beyond UTF-8 text',
                                  'compatibility with Manager.io or any accounting platform']), indent=2) + '\n'
        ledger = next((self.root / 'state/private/fulfillment').glob('*/case.json'))
        data = json.loads(ledger.read_text())
        self.assertEqual(data['steps'][0]['receipt']['files']['products/diagnostic.json'], expected)
        self.assertEqual(data['steps'][0]['receipt']['input_service_sources'],
                         [dict(path=selected, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))])
        self.assertIn('--- BEGIN FILE ---\n' + expected + '\n--- END FILE ---', reply['text'])
        self.assertIn(hashlib.sha256(expected.encode()).hexdigest(), reply['text'])
        with patch('controller.Controller.plan', side_effect=AssertionError('READY must replay')):
            self.assertEqual(PrivateResponder(self.root, self.config)(self.message), reply)
        self.assertFalse(list((self.root / 'state/private/fulfillment').glob('*/TASK-*')))


if __name__ == '__main__':
    unittest.main()
