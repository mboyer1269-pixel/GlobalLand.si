"""Private work behavior: real journals, external planner/executor seams only."""
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from private_work import PrivateResponder, PrivateDeferred
from mail import Mailbox
from mail_agent import run_mail_cycle


def finish(text='Computed from the supplied CSV.', artifacts=None):
    return {'actions': [], 'summary': json.dumps(dict(action='reply', text=text,
                                                     artifacts=artifacts or []))}


def execute(name='products/result.csv'):
    return {'summary': 'Compute', 'actions': [{'agent': 'BUILDER', 'action': 'EXEC',
            'args': {'argv': ['node', '-e', 'compute'], 'outputs': [name]}}]}


class PrivateWorkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.config = {'agentmail': {'fulfillment': {'enabled': True}},
                       'controller': {'providers': ['claude']}, 'executor_enabled': True,
                       'executor_image': 'node@sha256:' + '1' * 64}
        self.message = {'inbox_id': 'private-inbox', 'message_id': 'private-message',
                        'thread_id': 'private-thread', 'text': 'a,b\n2,3\n'}

    def responder(self):
        return PrivateResponder(self.root, self.config)

    def ledger(self):
        return next((self.root / 'state/private/fulfillment').glob('*/case.json'))

    def sandbox(self, command, **kwargs):
        self.assertIn('--network', command)
        self.assertIn('none', command)
        mounts = [command[i+1] for i, x in enumerate(command[:-1]) if x == '--mount']
        self.assertEqual(len(mounts), 3)
        self.assertTrue(any(str(self.root / 'control/executor.js') in m for m in mounts))
        input_dir = pathlib.Path(next(m.split(',dst=')[0].split('src=')[1] for m in mounts if 'dst=/input,' in m))
        self.assertEqual(json.loads((input_dir / 'incoming.json').read_text()), self.message)
        self.assertFalse((input_dir / 'other-private.txt').exists())
        self.assertFalse((input_dir / 'products/public-secret.txt').exists())
        return 0, b'{"status":"DONE","output":"sum=5","files":{"products/result.csv":"sum\\n5\\n"}}'

    def test_program_receipt_feedback_exact_file_delivery_and_ready_replay(self):
        product = self.root / 'work/products/public-secret.txt'
        product.parent.mkdir(parents=True)
        product.write_text('OTHER-WORK-SECRET')
        turns = []
        def plan(planner, provider, prompt):
            turns.append(prompt)
            if len(turns) == 1:
                return execute()
            self.assertIn('sum=5', prompt)
            self.assertIn('sum\\n5\\n', prompt)
            return finish(artifacts=['products/result.csv'])
        with patch('controller.Controller.plan', plan), patch('private_work.bounded_run', self.sandbox), patch('private_work.subprocess.run') as cleanup:
            cleanup.return_value.returncode = 0
            first = self.responder()(self.message)
        self.assertIn('sum\n5\n', first['text'])
        self.assertIn(hashlib.sha256(b'sum\n5\n').hexdigest(), first['text'])
        self.assertIn('AI', first['text'])
        data = json.loads(self.ledger().read_text())
        self.assertEqual(data['state'], 'READY')
        self.assertEqual(data['steps'][0]['provider'], 'claude')
        with patch('controller.Controller.plan', side_effect=AssertionError('must replay')):
            self.assertEqual(self.responder()(dict(self.message, text='changed remote body')), first)
        self.assertFalse((self.root / 'state/controller').exists())
        self.assertFalse((self.root / 'jobs').exists())
        if os.name == 'posix':
            self.assertEqual(self.ledger().stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.ledger().parent.stat().st_mode & 0o777, 0o700)

    def test_computed_result_survives_crash_before_final_planning(self):
        with patch('controller.Controller.plan', side_effect=[execute(), KeyboardInterrupt()]), patch('private_work.bounded_run', self.sandbox), patch('private_work.subprocess.run') as cleanup:
            cleanup.return_value.returncode = 0
            with self.assertRaises(KeyboardInterrupt):
                self.responder()(self.message)
        with patch('controller.Controller.plan', return_value=finish(artifacts=['products/result.csv'])), patch('private_work.bounded_run', side_effect=AssertionError('no rerun')):
            self.assertIn('sum\n5\n', self.responder()(self.message)['text'])

    def test_uncertain_execution_is_never_rerun_or_delivered_as_success(self):
        with patch('controller.Controller.plan', return_value=execute()), patch('private_work.bounded_run', side_effect=KeyboardInterrupt()), patch('private_work.subprocess.run') as cleanup:
            cleanup.return_value.returncode = 0
            with self.assertRaises(KeyboardInterrupt):
                self.responder()(self.message)
        def plan(planner, provider, prompt):
            self.assertIn('UNKNOWN', prompt)
            return finish('The previous computation has an uncertain outcome.')
        with patch('controller.Controller.plan', plan), patch('private_work.bounded_run', side_effect=AssertionError('no rerun')):
            self.assertIn('uncertain', self.responder()(self.message)['text'])

    def test_invented_cross_case_and_traversal_artifacts_are_rejected(self):
        for name in ['products/invented.csv', '../other/case.json', '/etc/passwd', 'products/../case.json']:
            with self.subTest(name=name), patch('controller.Controller.plan', return_value=finish(artifacts=[name])):
                with self.assertRaisesRegex(ValueError, '^Private work unavailable$'):
                    self.responder()(self.message)

    def test_unsafe_exec_and_public_actions_cannot_reach_executor(self):
        values = [execute('../case.json'), execute('products/../../secret'),
                  {'summary': '', 'actions': [{'action': 'PUBLISH_SITE', 'args': {'site': 'x'}}]},
                  {'summary': '', 'actions': [{'action': 'EXEC', 'args': {'argv': ['node'], 'outputs': [], 'cwd': '../other'}}]}]
        for index, value in enumerate(values):
            with self.subTest(value=value), patch('controller.Controller.plan', return_value=value), patch('private_work.bounded_run', side_effect=AssertionError('unsafe exec')):
                with self.assertRaises(ValueError):
                    self.responder()(dict(self.message, message_id=str(index)))

    def test_public_exec_input_selectors_cannot_replace_frozen_private_inputs(self):
        # Global EXEC selectors address mutable public source; this private
        # route must keep its case snapshot, even for an explicit empty list.
        for index, selector in enumerate(([], ['products/services/demo/'], None)):
            decision = execute()
            decision['actions'][0]['args']['inputs'] = selector
            with self.subTest(selector=selector), patch('controller.Controller.plan', return_value=decision), patch('private_work.bounded_run') as run:
                with self.assertRaisesRegex(ValueError,'^Private work unavailable$'):
                    self.responder()(dict(self.message,message_id='selector-'+str(index)))
                run.assert_not_called()

    def test_nullable_provider_inputs_normalize_to_the_private_frozen_default(self):
        from decision_protocol import normalize_model_action
        from private_work import _exec_args
        action = execute()['actions'][0]
        action['args']['inputs'] = None
        normalized = normalize_model_action(action)
        self.assertNotIn('inputs', normalized['args'])
        self.assertEqual(_exec_args(normalized),normalized['args'])

    def test_corrupt_or_symlinked_case_does_not_read_external_data(self):
        with patch('controller.Controller.plan', return_value=finish()):
            self.responder()(self.message)
        ledger = self.ledger()
        ledger.write_text('{broken')
        with self.assertRaisesRegex(ValueError, '^Private work unavailable$'):
            self.responder()(self.message)
        ledger.unlink()
        outside = self.root / 'outside'; outside.write_text('PRIVATE-OUTSIDE')
        ledger.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, '^Private work unavailable$'):
            self.responder()(self.message)
        self.assertEqual(outside.read_text(), 'PRIVATE-OUTSIDE')

    def test_execution_is_case_local_and_defers_at_bounded_work(self):
        self.config['agentmail']['fulfillment']['max_steps_per_cycle'] = 1
        with patch('controller.Controller.plan', return_value=execute()), patch('private_work.bounded_run', self.sandbox), patch('private_work.subprocess.run') as cleanup:
            cleanup.return_value.returncode = 0
            with self.assertRaises(PrivateDeferred):
                self.responder()(self.message)
        other = dict(self.message, message_id='other', text='OTHER CASE')
        def plan(planner, provider, prompt):
            self.assertNotIn('sum=5', prompt)
            self.assertNotIn('private-message', prompt)
            return finish('Other case')
        with patch('controller.Controller.plan', plan):
            self.assertEqual(self.responder()(other)['action'], 'reply')

    def test_recipient_injection_is_rejected(self):
        value = finish(); value['summary'] = json.dumps(dict(action='reply', text='x', artifacts=[], to='other@example.test'))
        with patch('controller.Controller.plan', return_value=value):
            with self.assertRaises(ValueError):
                self.responder()(self.message)

    def test_completed_receipt_tampering_is_not_delivered(self):
        with patch('controller.Controller.plan', side_effect=[execute(), KeyboardInterrupt()]), patch('private_work.bounded_run', self.sandbox), patch('private_work.subprocess.run') as cleanup:
            cleanup.return_value.returncode = 0
            with self.assertRaises(KeyboardInterrupt):
                self.responder()(self.message)
        data = json.loads(self.ledger().read_text())
        data['steps'][0]['receipt']['files']['products/result.csv'] = 'tampered'
        self.ledger().write_text(json.dumps(data))
        with patch('controller.Controller.plan', return_value=finish(artifacts=['products/result.csv'])):
            with self.assertRaisesRegex(ValueError, '^Private work unavailable$'):
                self.responder()(self.message)

    def test_shared_budget_bounds_all_provider_attempts_and_timeout(self):
        self.config['controller']['providers'] = ['claude', 'codex', 'cursor']
        self.config['controller']['timeout_seconds'] = 900
        calls = []
        def plan(planner, provider, prompt):
            calls.append((provider, planner.config.get('timeout_seconds')))
            raise ValueError('PRIVATE-ERROR')
        responder = self.responder()
        with patch('controller.Controller.plan', plan):
            with self.assertRaisesRegex(ValueError, '^Private work unavailable$'):
                responder(self.message)
            with self.assertRaises(PrivateDeferred):
                responder(dict(self.message, message_id='later'))
        self.assertEqual(len(calls), 2)
        self.assertEqual([timeout for _, timeout in calls], [120, 120])

    def test_pending_work_waits_for_available_shared_budget_then_executes_once(self):
        import private_work
        save = private_work._save
        def crash_before_start(path, data):
            if data['steps'] and data['steps'][-1]['state'] == 'STARTED':
                raise KeyboardInterrupt()
            save(path, data)
        with patch('controller.Controller.plan', return_value=execute()), patch('private_work._save', crash_before_start):
            with self.assertRaises(KeyboardInterrupt):
                self.responder()(self.message)
        self.assertEqual(json.loads(self.ledger().read_text())['steps'][0]['state'], 'PENDING')
        responder = self.responder(); responder.budget = 0
        with patch('private_work.bounded_run', side_effect=AssertionError('budget exhausted')):
            with self.assertRaises(PrivateDeferred):
                responder(self.message)
        with patch('controller.Controller.plan', return_value=finish(artifacts=['products/result.csv'])), patch('private_work.bounded_run', self.sandbox), patch('private_work.subprocess.run') as cleanup:
            cleanup.return_value.returncode = 0
            self.assertIn('sum\n5\n', self.responder()(self.message)['text'])

    def test_crash_after_computation_before_receipt_persistence_becomes_unknown(self):
        import private_work
        save = private_work._save
        def crash_receipt(path, data):
            if data['steps'] and data['steps'][-1]['state'] == 'COMPLETE':
                raise KeyboardInterrupt()
            save(path, data)
        with patch('controller.Controller.plan', return_value=execute()), patch('private_work.bounded_run', self.sandbox), patch('private_work.subprocess.run') as cleanup, patch('private_work._save', crash_receipt):
            cleanup.return_value.returncode = 0
            with self.assertRaises(KeyboardInterrupt):
                self.responder()(self.message)
        self.assertEqual(json.loads(self.ledger().read_text())['steps'][0]['state'], 'STARTED')
        with patch('controller.Controller.plan', return_value=finish('Computation outcome uncertain.')), patch('private_work.bounded_run', side_effect=AssertionError('no rerun')):
            self.assertIn('uncertain', self.responder()(self.message)['text'])

    def test_model_cannot_repeat_an_already_recorded_successful_program(self):
        self.config['agentmail']['fulfillment']['max_steps_per_cycle'] = 1
        with patch('controller.Controller.plan', return_value=execute()), patch('private_work.bounded_run', self.sandbox), patch('private_work.subprocess.run') as cleanup:
            cleanup.return_value.returncode = 0
            with self.assertRaises(PrivateDeferred):
                self.responder()(self.message)
        with patch('controller.Controller.plan', return_value=execute()), patch('private_work.bounded_run', side_effect=AssertionError('duplicate program')):
            with self.assertRaisesRegex(ValueError, '^Private work unavailable$'):
                self.responder()(self.message)

    def test_unverified_cleanup_withholds_artifacts(self):
        def final(planner, provider, prompt):
            self.assertIn('UNKNOWN', prompt)
            return finish('The sandbox outcome is uncertain.')
        with patch('controller.Controller.plan', side_effect=[execute(), finish(artifacts=['products/result.csv'])]), patch('private_work.bounded_run', self.sandbox), patch('private_work.subprocess.run', side_effect=OSError('private')):
            with self.assertRaises(ValueError):
                self.responder()(self.message)
        with patch('controller.Controller.plan', final):
            self.assertIn('uncertain', self.responder()(self.message)['text'])

    def test_symlinked_case_parent_is_rejected(self):
        outside = self.root / 'outside'; outside.mkdir()
        private = self.root / 'state/private'; private.mkdir(parents=True)
        (private / 'fulfillment').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, '^Private work unavailable$'):
            self.responder()(self.message)
        self.assertEqual(list(outside.iterdir()), [])

    def test_deferred_old_case_does_not_starve_new_mail_at_any_poll_cadence(self):
        config = {'agentmail': {'enabled': True, 'inbox_id': 'private-inbox',
                               'inbox_address': 'city@example.test', 'max_messages_per_cycle': 1}}
        incoming = [dict(self.message, labels=['received'], **{'from': 'human@example.test'}),
                    dict(self.message, message_id='later', labels=['received'], **{'from': 'other@example.test'})]
        class Client:
            def list_received(self): return incoming
            def get_message(self, mid): return next(m for m in incoming if m['message_id'] == mid)
            def reply(self, *args): return {'message_id': 'sent'}
        box = Mailbox(self.root, config, Client())
        seen = []
        def respond(msg):
            seen.append(msg['message_id'])
            if msg['message_id'] == 'private-message':
                raise PrivateDeferred()
            return {'action': 'reply', 'text': 'Later response'}
        first = box.cycle(respond)
        self.assertEqual((first['accepted'], first['ignored'], first['processed']), (1, 0, 1))
        self.assertEqual(box.status()['accepted'], 1)
        self.assertEqual(seen, ['private-message', 'later'])

    def test_ready_presend_failure_reuses_reply_without_replanning(self):
        config = {'agentmail': {'enabled': True, 'inbox_id': 'private-inbox',
                               'inbox_address': 'city@example.test'}}
        incoming = dict(self.message, labels=['received'], **{'from': 'human@example.test'})
        class Client:
            def list_received(self): return [incoming]
            def get_message(self, mid): return incoming
            def reply(self, *args): return {'message_id': 'sent'}
        box = Mailbox(self.root, config, Client())
        save = box._save
        def fail_before_send(path, data):
            if data['state'] == 'STARTED':
                raise OSError('private path')
            save(path, data)
        with patch('controller.Controller.plan', return_value=finish('Durable reply')), patch.object(box, '_save', fail_before_send):
            self.assertEqual(box.cycle(self.responder())['failed'], 1)
        self.assertEqual(json.loads(self.ledger().read_text())['state'], 'READY')
        with patch('mail.time.time', return_value=10**12), patch('controller.Controller.plan', side_effect=AssertionError('must replay')):
            self.assertEqual(box.cycle(self.responder())['accepted'], 1)

    def test_exhausted_budget_bounds_body_fetches_and_case_creation(self):
        config = {'agentmail': {'enabled': True, 'inbox_id': 'private-inbox',
                               'inbox_address': 'city@example.test', 'max_messages_per_cycle': 1}}
        incoming = [dict(self.message, message_id=str(i), labels=['received'],
                         **{'from': 'human@example.test'}) for i in range(200)]
        fetched = []
        class Client:
            def list_received(self): return incoming
            def get_message(self, mid): fetched.append(mid); return incoming[int(mid)]
        box = Mailbox(self.root, config, Client())
        def defer(msg): raise PrivateDeferred(False)
        result = box.cycle(defer)
        self.assertEqual(len(fetched), 2)
        self.assertEqual((result['accepted'], result['ignored']), (0, 0))
        box.cycle(defer)
        self.assertEqual(fetched, ['0', '1', '2', '3'])

    def test_due_ready_retry_gets_turn_despite_fresh_arrivals_and_scan_failure(self):
        config = {'agentmail': {'enabled': True, 'inbox_id': 'private-inbox',
                               'inbox_address': 'city@example.test', 'max_messages_per_cycle': 1}}
        incoming = [dict(self.message, labels=['received'], **{'from': 'human@example.test'})]
        sent = []
        class Client:
            broken = False
            def list_received(self):
                if self.broken: raise ValueError('private provider error')
                return incoming
            def get_message(self, mid): return next(m for m in incoming if m['message_id'] == mid)
            def reply(self, mid, *args): sent.append(mid); return {'message_id': 'sent'}
        client = Client(); box = Mailbox(self.root, config, client)
        def fail(_): raise ValueError('pre-send failure')
        box.cycle(fail)
        incoming.append(dict(incoming[0], message_id='new-arrival'))
        with patch('mail.time.time', return_value=10**12):
            box.cycle(lambda _: {'action': 'reply', 'text': 'Durable reply'})
        self.assertEqual(sent, ['private-message'])
        # Another retry remains serviceable even if fresh metadata listing fails.
        box.cycle(fail)
        client.broken = True
        with patch('mail.time.time', return_value=10**12):
            box.cycle(lambda _: {'action': 'reply', 'text': 'Durable reply'})
        self.assertEqual(sent, ['private-message', 'new-arrival'])

    def test_provider_metadata_scan_is_bounded_and_checkpointed(self):
        from mail import Client
        from urllib.parse import parse_qs, urlsplit
        config = {'agentmail': {'enabled': True, 'inbox_id': 'private-inbox',
                               'inbox_address': 'city@example.test', 'max_messages_per_cycle': 1}}
        token = self.root / 'credentials/agentmail/token'; token.parent.mkdir(parents=True)
        token.write_text('fixture-token'); token.chmod(0o600)
        pages = []
        def transport(method, url, headers, payload):
            query = parse_qs(urlsplit(url).query)
            if not query:
                mid = urlsplit(url).path.rsplit('/', 1)[-1]
                return dict(self.message, message_id=mid, labels=['received'], **{'from': 'human@example.test'})
            number = int(query.get('page_token', ['0'])[0]); pages.append(number)
            if number > 8:
                raise ValueError('fixture page bound exceeded')
            return {'messages': [dict(self.message, message_id=str(number))], 'next_page_token': str(number+1)}
        def defer(_): raise PrivateDeferred(False)
        box = Mailbox(self.root, config, Client(self.root, config, transport))
        box.cycle(defer)
        self.assertEqual(pages, [0, 1])
        box.cycle(defer)
        self.assertEqual(pages, [0, 1, 2, 3])

    def test_pending_page_batch_drains_before_scanning_past_held_messages(self):
        from mail import Client
        from urllib.parse import parse_qs, urlsplit
        config = {'agentmail': {'enabled': True, 'inbox_id': 'private-inbox',
                               'inbox_address': 'city@example.test', 'max_messages_per_cycle': 1}}
        token = self.root / 'credentials/agentmail/token'; token.parent.mkdir(parents=True)
        token.write_text('fixture-token'); token.chmod(0o600)
        pages, sent = [], []
        def incoming(mid):
            armor = {'status': 'pending'} if int(mid) % 3 < 2 else {'status': 'complete', 'verdict': 'clear'}
            return dict(self.message, message_id=mid, labels=['received'], agent_armor=armor,
                        **{'from': 'human@example.test'})
        def transport(method, url, headers, payload):
            query = parse_qs(urlsplit(url).query)
            if method == 'POST':
                sent.append(urlsplit(url).path.split('/')[-2]); return {'message_id': 'sent'}
            if not query:
                return incoming(urlsplit(url).path.rsplit('/', 1)[-1])
            number = int(query.get('page_token', ['0'])[0]); pages.append(number)
            return {'messages': [incoming(str(number*3+i)) for i in range(3)],
                    'next_page_token': str(number+1) if number < 2 else None}
        box = Mailbox(self.root, config, Client(self.root, config, transport))
        respond = lambda _: {'action': 'reply', 'text': 'Useful result'}
        self.assertEqual(box.cycle(respond)['accepted'], 0)
        self.assertEqual(box.cycle(respond)['accepted'], 1)
        self.assertEqual(pages, [0, 1])
        self.assertEqual(sent, ['2'])
        self.assertEqual(box.cycle(respond)['accepted'], 0)
        self.assertEqual(box.cycle(respond)['accepted'], 1)
        self.assertEqual(sent, ['2', '5'])

    def test_completed_page_survives_later_failure_and_stale_cursor_resets(self):
        from mail import Client
        from urllib.parse import parse_qs, urlsplit
        config = {'agentmail': {'enabled': True, 'inbox_id': 'private-inbox',
                               'inbox_address': 'city@example.test', 'max_messages_per_cycle': 1}}
        token = self.root / 'credentials/agentmail/token'; token.parent.mkdir(parents=True)
        token.write_text('fixture-token'); token.chmod(0o600)
        pages = []
        def transport(method, url, headers, payload):
            number = int(parse_qs(urlsplit(url).query).get('page_token', ['0'])[0]); pages.append(number)
            if number == 1: raise OSError('fixture page failure')
            return {'messages': [], 'next_page_token': '1'}
        box = Mailbox(self.root, config, Client(self.root, config, transport))
        box.cycle(lambda _: None)
        self.assertEqual(json.loads((box.directory / '.schedule').read_text())['page_token'], '1')
        box.cycle(lambda _: None)
        self.assertIsNone(json.loads((box.directory / '.schedule').read_text())['page_token'])
        self.assertEqual(pages, [0, 1, 1])

    def test_enabled_cycle_selects_private_responder_and_legacy_stays_tool_free(self):
        config = dict(self.config, agentmail=dict(enabled=True, fulfillment={'enabled': True}))
        observed = []
        def cycle(box, responder):
            observed.append(type(responder).__name__)
            return dict(processed=1, accepted=1, unsafe='PRIVATE CONTENT')
        # Exercise selection/status with the real Mailbox constructor settings.
        config['agentmail'].update(inbox_id='private-inbox', inbox_address='city@example.test')
        with patch('mail.Mailbox.cycle', cycle):
            run_mail_cycle(self.root, config)
            config['agentmail']['fulfillment']['enabled'] = False
            run_mail_cycle(self.root, config)
        self.assertEqual(observed, ['PrivateResponder', 'MailResponder'])
        public = (self.root / 'state/private/agentmail-status.json').read_text()
        self.assertNotIn('PRIVATE', public)


if __name__ == '__main__':
    unittest.main()
