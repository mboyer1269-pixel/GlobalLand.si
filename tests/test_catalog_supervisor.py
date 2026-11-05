"""Large public history must not halt a small independent job."""
import json
import os
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import test_publication_resilience as fixtures


class CatalogSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PublicationResilienceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.app = self.fixture.app
        self.seed = self.fixture.seed

    def large_history(self):
        directory = self.seed / 'products/archive'
        directory.mkdir(parents=True)
        for n in range(20):
            (directory / ('part-%02d.txt' % n)).write_bytes(bytes([65 + n]) * 950000)
        book = self.seed / 'agents/playbooks/example.md'
        book.parent.mkdir(parents=True)
        book.write_text('Optional strategic guide')

    def test_large_history_does_not_block_small_queue_job(self):
        self.large_history()
        self.fixture.enqueue(400, 'WORLD', dict(op='create_mission', mission_id='STILL-ACTIVE', goal='Choose useful work'))
        self.fixture.commit('large history and small task')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.app.cycle('queue')
        result = json.loads(self.app.git('show', 'HEAD:queue/done/TASK-0400.result.json'))
        self.assertEqual(result['status'], 'DONE')
        self.assertFalse((self.app.root / 'work/products/archive').exists())
        self.assertEqual((self.app.root / 'work/agents/playbooks/example.md').read_text(), 'Optional strategic guide')
        self.assertEqual(len(self.app.git('show', 'HEAD:products/archive/part-19.txt')), 950000)

    def test_oversized_optional_playbook_does_not_block_queue_or_hide_small_guide(self):
        import lessons
        directory = self.seed / 'agents/playbooks'
        directory.mkdir(parents=True)
        (directory / 'a-huge.md').write_bytes(b'a' * (5 * 1024 * 1024))
        (directory / 'z-useful.md').write_text('Keep learning from verified outcomes.')
        self.fixture.enqueue(430, 'WORLD', dict(op='create_mission', mission_id='GUIDE-INDEPENDENT', goal='Keep working'))
        self.fixture.commit('oversized optional guide')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.app.cycle('queue')
        result = json.loads(self.app.git('show', 'HEAD:queue/done/TASK-0430.result.json'))
        self.assertEqual(result['status'], 'DONE')
        books = lessons.playbooks(self.app.root / 'work')
        self.assertEqual(books['z-useful'], 'Keep learning from verified outcomes.')
        self.assertIn('omitted', books['_source_omissions'])
        self.assertIn('a-huge.md', books['_source_omissions'])
        self.assertEqual(len(self.app.git('show', 'HEAD:agents/playbooks/a-huge.md')), 5 * 1024 * 1024)

    def test_legacy_staging_ignores_regenerable_history_and_uses_refresh_revision(self):
        (self.seed / 'ledger.json').write_text('{"version":"old"}')
        history = self.seed / 'logs/transactions.log'
        history.parent.mkdir()
        history.write_bytes(b'h' * (2 * 1024 * 1024))
        self.fixture.commit('legacy state with large optional history')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.app.git('fetch', 'origin', 'main')
        self.app.git('update-ref', 'refs/heads/main', self.app.git('rev-parse', 'FETCH_HEAD').decode().strip())
        self.app.refresh_work()
        (self.seed / 'ledger.json').write_text('{"version":"new"}')
        self.fixture.commit('later ledger')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.app.git('fetch', 'origin', 'main')
        self.app.git('update-ref', 'refs/heads/main', self.app.git('rev-parse', 'FETCH_HEAD').decode().strip())
        self.app.stage_legacy_inputs()
        self.assertEqual((self.app.root / 'work/ledger.json').read_text(), '{"version":"old"}')
        self.assertFalse((self.app.root / 'work/logs/transactions.log').exists())

    def test_legacy_daily_worker_regenerates_log_without_importing_large_history(self):
        base = pathlib.Path(__file__).resolve().parents[1]
        (self.seed / 'ledger.json').write_bytes((base / 'tests/fixtures/genesis.json').read_bytes())
        history = self.seed / 'logs/transactions.log'
        history.parent.mkdir()
        history.write_bytes(b'h' * (2 * 1024 * 1024))
        self.fixture.commit('legacy ledger and retained generated log')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.app.cycle('queue')
        self.app.stage_legacy_inputs()
        work = self.app.root / 'work'
        self.assertFalse((work / 'logs/transactions.log').exists())
        result = json.loads(subprocess.check_output(['node', str(base / 'scripts/worker.js'),
                             'daily', '2026-11-05', str(work)], timeout=30))
        self.assertEqual(json.loads(result['ledger.json'])['last_tick_date'], '2026-11-05')
        self.assertIn('DAY_TICK', result['logs/transactions.log'])
        self.assertIn('UNFUNDED', result['bank/audits/audit-2026-11-05.md'])

    def test_legacy_audit_after_first_task_receives_current_private_treasury(self):
        base = pathlib.Path(__file__).resolve().parents[1]
        (self.seed / 'ledger.json').write_bytes((base / 'tests/fixtures/genesis.json').read_bytes())
        status = self.seed / 'bank/status.json'
        status.parent.mkdir()
        status.write_text('{"state":"FAKE_PUBLIC_FUNDING","available_cad":999999}')
        self.fixture.enqueue(440, 'STATUS', {})
        audit = self.fixture.enqueue(441, 'AUDIT', [])
        audit['type'] = 'SHELL'
        (self.seed / 'queue/inbox/TASK-0441.json').write_text(json.dumps(audit))
        self.fixture.commit('status followed by legacy audit')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        def worker(kind, rel):
            return json.loads(subprocess.check_output(['node', str(base / 'scripts/worker.js'),
                                kind, rel, str(self.app.root / 'work')], timeout=30))
        with patch.object(self.app, 'worker', side_effect=worker):
            self.app.cycle('queue')
        result = json.loads(self.app.git('show', 'HEAD:queue/done/TASK-0441.result.json'))
        self.assertEqual(result['status'], 'DONE')
        report = json.loads(result['output'].split('\n\n')[1])
        self.assertIsNotNone(report['verified_treasury'])
        self.assertEqual(report['verified_treasury']['state'], 'UNFUNDED')
        self.assertNotIn('FAKE_PUBLIC_FUNDING', result['output'])

    def test_exec_only_materializes_selected_inputs_from_pinned_git(self):
        self.large_history()
        selected = self.seed / 'products/input.csv'
        selected.write_text('value\n7\n')
        self.fixture.commit('selected input in large catalog')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.app.git('fetch', 'origin', 'main')
        self.app.git('update-ref', 'refs/heads/main', self.app.git('rev-parse', 'FETCH_HEAD').decode().strip())
        world, bank, _ = self.app.services()
        from tools import Toolbox
        task = self.fixture.enqueue(401, 'EXEC', dict(argv=['node', '-p', '7'],
                       inputs=['products/input.csv'], outputs=['products/output.txt']))
        observed = []
        def execute(command, **kwargs):
            directory = self.app.root / 'jobs/TASK-0401/workspace/input'
            self.assertEqual((directory / 'products/input.csv').read_text(), 'value\n7\n')
            self.assertFalse((directory / 'products/archive').exists())
            self.assertFalse((directory / '.git').exists())
            observed.append(True)
            return 0, json.dumps(dict(status='DONE', output='7', files={'products/output.txt': '7'})).encode()
        with patch('tools.bounded_run', side_effect=execute), patch('tools.subprocess.run', return_value=type('Done', (), {'returncode': 0})()):
            result, files = Toolbox(self.app.root, world, bank,
                    dict(executor_enabled=True, executor_image='node@sha256:' + '1' * 64)).run(task)
        self.assertEqual(result['status'], 'DONE')
        self.assertEqual(observed, [True])
        self.assertEqual(files['products/output.txt'], '7')
        receipt = json.loads(files['products/receipts/TASK-0401.json'])
        self.assertEqual(receipt['input_source']['revision'], self.app.git('rev-parse', 'HEAD').decode().strip())
        self.assertEqual(receipt['input_source']['total_bytes'], 8)
        self.assertEqual(receipt['input_source']['file_count'], 1)

    def test_pending_publication_is_not_default_catalog_until_push_succeeds(self):
        path = self.seed / 'products/value.txt'
        path.parent.mkdir()
        path.write_text('old')
        self.fixture.commit('old public value')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.app.cycle('queue')
        world, bank, config = self.app.services()
        task = self.fixture.enqueue(402, 'FETCH', dict(url='https://example.org/data', output='products/value.txt'))
        original_git = self.app.git
        def offline_push(*args, **kwargs):
            if args[0] == 'push': raise RuntimeError('fixture offline push')
            return original_git(*args, **kwargs)
        with patch.object(self.app, 'git', side_effect=offline_push), patch('tools.fetch_public', return_value=(b'new', 'https://example.org/data', 200)) as fetch:
            result = self.app.execute_tool(task, world, bank, config)
            replay = self.app.execute_tool(task, world, bank, config)
        self.assertEqual(fetch.call_count, 1)
        self.assertIn('PENDING', result['publication'])
        self.assertIn('PENDING', replay['publication'])
        from public_source import PublicSource
        self.assertEqual(PublicSource(self.app.root).read('products/value.txt')['content'], 'old')
        journal = self.app.root / 'state/TASK-0402.json'
        with patch('tools.fetch_public', side_effect=AssertionError('publication retry must not replay FETCH')):
            self.app.finish(journal, json.loads(journal.read_text()))
        self.assertEqual(PublicSource(self.app.root).read('products/value.txt')['content'], 'new')

    def test_oversized_legacy_selection_refuses_only_that_job(self):
        path = self.seed / 'products/huge.bin'
        path.parent.mkdir()
        with path.open('wb') as output:
            for _ in range(129): output.write(b'x' * 1024 * 1024)
        self.fixture.enqueue(410, 'EXEC', dict(argv=['node', '-p', '1'], outputs=[]))
        self.fixture.enqueue(411, 'EXEC', dict(argv=['node', '-p', '2'], inputs=[], outputs=[]))
        self.fixture.commit('large legacy input then empty selected input')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        control = self.app.root / 'control'
        control.mkdir()
        (control / 'config.json').write_text(json.dumps(dict(executor_enabled=True, executor_image='node@sha256:' + '1' * 64)))
        executed = []
        def execute(command, **kwargs):
            directory = self.app.root / 'jobs/TASK-0411/workspace/input'
            self.assertTrue(directory.is_dir())
            self.assertEqual(list(directory.iterdir()), [])
            executed.append(True)
            return 0, b'{"status":"DONE","output":"2","files":{}}'
        with patch('tools.bounded_run', side_effect=execute), patch('tools.subprocess.run', return_value=type('Done', (), {'returncode': 0})()):
            self.app.cycle('queue')
        failed = json.loads(self.app.git('show', 'HEAD:queue/failed/TASK-0410.result.json'))
        self.assertEqual(failed['status'], 'REJECTED')
        self.assertIn('select fewer files', failed['output'])
        self.assertEqual(executed, [True])
        self.assertFalse((self.app.root / 'jobs/TASK-0410').exists())


@unittest.skipUnless(os.environ.get('GLOBALLAND_DOCKER_SMOKE') == '1', 'real Docker requires explicit daemon access')
class CatalogExecutionSmoke(unittest.TestCase):
    setUp = CatalogSupervisorTests.setUp
    large_history = CatalogSupervisorTests.large_history

    def test_selected_git_input_runs_in_offline_container_with_large_history(self):
        self.large_history()
        (self.seed / 'products/input.csv').write_text('value\n7\n')
        self.fixture.commit('selected Docker input')
        self.fixture.git('-C', str(self.seed), 'push', 'origin', 'main')
        self.app.cycle('queue')
        image = json.loads(subprocess.check_output(['docker', 'image', 'inspect',
                           os.environ.get('GLOBALLAND_DOCKER_SMOKE_IMAGE', 'node:22-bookworm')]))[0]['RepoDigests'][0]
        control = self.app.root / 'control'
        control.mkdir(exist_ok=True)
        (control / 'executor.js').write_bytes((pathlib.Path(__file__).resolve().parents[1] / 'scripts/executor.js').read_bytes())
        task = self.fixture.enqueue(420, 'EXEC', dict(argv=['node', '-e',
            "const fs=require('fs'); if(fs.existsSync('products/archive')||fs.existsSync('/var/run/docker.sock')||fs.existsSync('/input/.git'))process.exit(9); const n=Number(fs.readFileSync('products/input.csv','utf8').trim().split('\\n')[1]); fs.writeFileSync('products/answer.txt',String(n)+'\\n');"],
            inputs=['products/input.csv'], outputs=['products/answer.txt']))
        world, bank, _ = self.app.services()
        from tools import Toolbox
        result, files = Toolbox(self.app.root, world, bank, dict(executor_enabled=True, executor_image=image)).run(task)
        self.assertEqual(result['status'], 'DONE')
        self.assertEqual(files['products/answer.txt'], '7\n')
        self.assertFalse((self.app.root / 'jobs/TASK-0420').exists())


if __name__ == '__main__':
    unittest.main()
