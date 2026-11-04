import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from scripts.mail import Client, Mailbox, MailError, MAX_RESPONSE


def message(mid='incoming', **extra):
    return dict(message_id=mid, inbox_id='city@example.test', labels=['received'],
                **{'from': 'Human <human@example.test>'}, text='Private question', **extra)


class Transport:
    def __init__(self, messages):
        self.messages = messages
        self.calls = []
        self.failure = None

    def __call__(self, method, url, headers, payload):
        self.calls.append((method, url, headers, payload))
        if self.failure:
            raise self.failure
        path = urlsplit(url).path
        if method == 'POST':
            return {'message_id': 'outbound', 'thread_id': 'thread'}
        if path.endswith('/messages'):
            return {'messages': copy.deepcopy(self.messages)}
        from urllib.parse import unquote
        mid = unquote(path.rsplit('/', 1)[-1])
        return copy.deepcopy(next(m for m in self.messages if m['message_id'] == mid))


class MailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        token = self.root / 'credentials/agentmail/token'
        token.parent.mkdir(parents=True)
        token.write_text('secret-test-token')
        token.chmod(0o600)
        self.config = {'agentmail': {'enabled': True, 'inbox_id': 'city@example.test',
                                     'inbox_address': 'city@example.test'}}
        self.transport = Transport([message()])
        self.client = Client(self.root, self.config, self.transport)
        self.box = Mailbox(self.root, self.config, self.client)

    def responder(self, msg):
        return {'action': 'reply', 'text': 'Private AI reply'}

    def records(self):
        return list((self.root / 'state/private/agentmail').glob('*.json'))

    def test_receive_reply_and_duplicate_cycle(self):
        result = self.box.cycle(self.responder)
        self.assertEqual(result['accepted'], 1)
        self.assertEqual(self.box.cycle(self.responder)['accepted'], 0)
        posts = [c for c in self.transport.calls if c[0] == 'POST']
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][3]['reply_all'], False)
        self.assertEqual(set(posts[0][3]), {'text', 'reply_all', 'headers'})
        self.assertIn('X-GlobalLand-Operation', posts[0][3]['headers'])
        self.assertEqual(posts[0][3]['headers']['Auto-Submitted'], 'auto-replied')
        self.assertEqual(self.box.status()['accepted'], 1)
        public = json.dumps([result, self.box.status()])
        for secret in ['human@', 'Private', 'incoming', 'city@', 'secret-test-token']:
            self.assertNotIn(secret, public)

    def test_started_is_durable_before_network_and_recovered_unknown(self):
        def crash(mid, text, operation):
            self.assertEqual(json.loads(self.records()[0].read_text())['state'], 'STARTED')
            raise KeyboardInterrupt()
        self.client.reply = crash
        with self.assertRaises(KeyboardInterrupt):
            self.box.cycle(self.responder)
        self.assertEqual(self.box.status()['unknown'], 1)
        restart = Mailbox(self.root, self.config, Client(self.root, self.config, self.transport))
        self.assertEqual(restart.cycle(self.responder)['accepted'], 0)
        self.assertEqual(json.loads(self.records()[0].read_text())['state'], 'UNKNOWN')
        self.assertFalse(any(c[0] == 'POST' for c in self.transport.calls))

    def test_uncertain_send_is_never_retried(self):
        self.client.reply = lambda *args: (_ for _ in ()).throw(TimeoutError('private token'))
        self.assertEqual(self.box.cycle(self.responder)['unknown'], 1)
        self.assertEqual(self.box.cycle(self.responder)['unknown'], 0)
        self.assertEqual(self.box.status()['unknown'], 1)

    def test_interrupted_responder_is_not_marked_success(self):
        def interrupted(msg):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.box.cycle(interrupted)
        self.assertEqual(self.box.status()['accepted'], 0)
        self.assertEqual(self.box.cycle(self.responder)['accepted'], 1)

    def test_failures_are_independent_and_do_not_starve_next_cycle(self):
        self.transport.messages = [message(str(i)) for i in range(5)]
        def bad(msg):
            if msg['message_id'] == '0':
                raise ValueError('private prose')
            return self.responder(msg)
        first = self.box.cycle(bad)
        self.assertEqual((first['failed'], first['accepted']), (1, 2))
        self.assertEqual(self.box.cycle(bad)['accepted'], 2)

    def test_transient_presend_failure_retries_after_backoff(self):
        with patch('scripts.mail.time.time', return_value=1000):
            self.assertEqual(self.box.cycle(lambda _: (_ for _ in ()).throw(ValueError('private')))['failed'], 1)
        record = json.loads(self.records()[0].read_text())
        self.assertEqual((record['state'], record['attempts'], record['retry_after']), ('RETRY', 1, 1060))
        self.assertEqual(self.box.status()['failed'], 1)
        self.transport.messages.append(message('new'))
        with patch('scripts.mail.time.time', return_value=1020):
            self.assertEqual(self.box.cycle(self.responder)['accepted'], 1)
        with patch('scripts.mail.time.time', return_value=1061):
            self.assertEqual(self.box.cycle(self.responder)['accepted'], 1)
        self.assertEqual(self.box.status()['failed'], 0)

    def test_repeated_presend_failure_increases_backoff(self):
        def fail(_):
            raise ValueError('private')
        with patch('scripts.mail.time.time', return_value=1000):
            self.box.cycle(fail)
        with patch('scripts.mail.time.time', return_value=1061):
            self.box.cycle(fail)
        record = json.loads(self.records()[0].read_text())
        self.assertEqual((record['attempts'], record['retry_after']), (2, 1181))

    def test_ignore_is_persistent(self):
        self.assertEqual(self.box.cycle(lambda _: {'action': 'ignore', 'text': ''})['ignored'], 1)
        self.assertEqual(self.box.cycle(self.responder)['accepted'], 0)

    def test_pending_vendor_scan_is_revisited_without_starving_other_mail(self):
        self.config['agentmail']['max_messages_per_cycle'] = 1
        self.box = Mailbox(self.root, self.config, self.client)
        self.transport.messages = [message('pending', agent_armor={'status': 'pending'}), message('ready')]
        self.assertEqual(self.box.cycle(self.responder)['accepted'], 1)
        self.transport.messages[0]['agent_armor']['status'] = 'complete'
        self.transport.messages[0]['agent_armor']['verdict'] = 'clear'
        self.assertEqual(self.box.cycle(self.responder)['accepted'], 1)

    def test_armor_held_then_released_is_revisited_without_terminal_ignore(self):
        self.config['agentmail']['max_messages_per_cycle'] = 1
        self.box = Mailbox(self.root, self.config, self.client)
        held = message('held', agent_armor={'status': 'complete', 'verdict': 'review'})
        held['labels'].append('agent-armor-held')
        self.transport.messages = [held, message('ready')]
        seen = []
        def respond(msg):
            seen.append(msg['message_id'])
            return self.responder(msg)
        first = self.box.cycle(respond)
        self.assertEqual((first['accepted'], first['skipped'], first['ignored']), (1, 1, 0))
        self.assertEqual(seen, ['ready'])
        self.assertFalse(self.box._path('held').exists())
        held['agent_armor']['manual_override'] = {
            'override_id': 'verified-release', 'released_at': '2026-11-04T12:00:00Z'}
        # Labels can lag release; wait for the held label to clear too.
        self.assertEqual(self.box.cycle(respond)['accepted'], 0)
        held['labels'].remove('agent-armor-held')
        self.assertEqual(self.box.cycle(respond)['accepted'], 1)
        self.assertEqual(seen, ['ready', 'held'])
        self.assertEqual(self.box.cycle(respond)['accepted'], 0)

    def test_armor_review_without_label_unavailable_and_malformed_defer(self):
        variants = [
            {'status': 'complete', 'verdict': 'review'},
            {'status': 'complete', 'verdict': 'review', 'manual_override': {}},
            {'status': 'complete', 'verdict': 'review', 'manual_override': True},
            {'status': 'unavailable', 'unavailable_reason': 'payload_too_large'},
            {'status': 'unavailable', 'unavailable_reason': 'deadline_exceeded'},
            {'status': 'complete'}, {}, 'malformed',
        ]
        seen = []
        for index, armor in enumerate(variants):
            with self.subTest(armor=armor):
                self.transport.messages = [message(str(index), agent_armor=armor)]
                result = self.box.cycle(lambda msg: seen.append(msg))
                self.assertEqual((result['processed'], result['skipped'], result['ignored']), (0, 1, 0))
                self.assertFalse(self.records())
        self.assertFalse(seen)
        self.assertFalse(any(c[0] == 'POST' for c in self.transport.calls))

    def test_armor_held_label_defers_even_without_scan_result(self):
        self.transport.messages[0]['labels'].append('agent-armor-held')
        result = self.box.cycle(self.responder)
        self.assertEqual((result['accepted'], result['skipped'], result['ignored']), (0, 1, 0))
        self.assertFalse(self.records())

    def test_concurrent_cycle_cannot_send_twice(self):
        nested = []
        def respond(msg):
            nested.append(Mailbox(self.root, self.config, self.client).cycle(self.responder))
            return self.responder(msg)
        self.assertEqual(self.box.cycle(respond)['accepted'], 1)
        self.assertEqual(nested[0]['failed'], 1)
        self.assertEqual(sum(c[0] == 'POST' for c in self.transport.calls), 1)

    def test_provider_evidence_is_allowlisted_and_private(self):
        class Responder:
            last_provider = 'cursor'
            def __call__(self, msg):
                return {'action': 'reply', 'text': 'AI response'}
        self.box.cycle(Responder())
        self.assertEqual(json.loads(self.records()[0].read_text())['provider'], 'cursor')
        self.assertNotIn('provider', self.box.status())

    def test_journal_write_failure_prevents_send(self):
        with patch.object(self.box, '_save', side_effect=OSError('private path')):
            self.assertEqual(self.box.cycle(self.responder)['failed'], 1)
        self.assertFalse(any(c[0] == 'POST' for c in self.transport.calls))

    def test_failure_after_api_acceptance_leaves_unknown_without_retry(self):
        original = self.box._save
        def save(path, record):
            if record['state'] == 'ACCEPTED':
                raise OSError('disk failure')
            return original(path, record)
        with patch.object(self.box, '_save', side_effect=save):
            self.assertEqual(self.box.cycle(self.responder)['unknown'], 1)
        self.assertEqual(self.box.cycle(self.responder)['accepted'], 0)
        self.assertEqual(sum(c[0] == 'POST' for c in self.transport.calls), 1)

    def test_injected_routing_and_actions_are_rejected(self):
        for extra in ({'to': 'other@example.test'}, {'commands': ['exec']}, {'action': 'send'}):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as tmp:
                box = Mailbox(tmp, self.config, self.client)
                result = box.cycle(lambda _: dict(self.responder({}), **extra))
                self.assertEqual(result['accepted'], 0)
                self.assertEqual(result['failed'], 1)
        self.assertFalse(any(c[0] == 'POST' for c in self.transport.calls))

    def test_responder_cannot_change_reply_target(self):
        def mutate(msg):
            msg['message_id'] = 'other'
            return self.responder(msg)
        self.box.cycle(mutate)
        self.assertTrue([c for c in self.transport.calls if c[0] == 'POST'][0][1].endswith('/incoming/reply'))

    def test_loop_filters(self):
        variants = [
            {'from': 'City <city@example.test>'}, {'labels': ['sent']},
            {'labels': ['received', 'spam']}, {'labels': ['received', 'blocked']},
            {'from': 'MAILER-DAEMON@example.test'}, {'from': 'postmaster@example.test'},
            {'headers': {'Auto-Submitted': 'auto-replied'}},
            {'headers': {'Precedence': 'bulk'}}, {'headers': {'Return-Path': '<>'}},
            {'headers': {'Content-Type': 'multipart/report; report-type=delivery-status'}},
            {'headers': {'X-GlobalLand-Operation': 'earlier-operation'}},
            {'reply_to': ['city@example.test']},
        ]
        self.transport.messages = [dict(message(str(i)), **v) for i, v in enumerate(variants)]
        while self.box.status()['ignored'] < len(variants):
            self.box.cycle(self.responder)
        self.assertFalse(any(c[0] == 'POST' for c in self.transport.calls))

    def test_disabled_does_not_read_token_or_call_network(self):
        config = {'agentmail': {'enabled': False}}
        box = Mailbox(self.root, config, self.client)
        self.assertFalse(box.cycle(self.responder)['enabled'])
        self.assertFalse(self.transport.calls)

    def test_pagination_and_encoded_opaque_ids(self):
        calls = []
        def pages(method, url, headers, payload):
            calls.append(url)
            query = parse_qs(urlsplit(url).query)
            self.assertEqual(query['labels'], ['received'])
            self.assertEqual(query['ascending'], ['true'])
            if 'page_token' not in query:
                return {'messages': [message('one')], 'next_page_token': 'opaque +/token'}
            self.assertEqual(query['page_token'], ['opaque +/token'])
            return {'messages': [message('two')]}
        client = Client(self.root, self.config, pages)
        self.assertEqual([m['message_id'] for m in client.list_received()], ['one', 'two'])
        self.transport.messages = [message('../../private?a#b')]
        self.box.cycle(self.responder)
        self.assertIn('..%2F..%2Fprivate%3Fa%23b', self.transport.calls[-1][1])
        self.assertEqual(len(self.records()[0].stem), 64)

    def test_page_loop_fails_safely(self):
        client = Client(self.root, self.config, lambda *a: {'messages': [], 'next_page_token': 'same'})
        with self.assertRaises(MailError):
            list(client.list_received())

    def test_private_journal_permissions(self):
        self.box.cycle(self.responder)
        if os.name == 'posix':
            self.assertEqual(self.records()[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.records()[0].parent.stat().st_mode & 0o777, 0o700)

    def test_corrupt_journal_is_not_overwritten_or_resent(self):
        self.box.cycle(self.responder)
        self.records()[0].write_text('{broken')
        self.transport.calls.clear()
        self.assertEqual(self.box.cycle(self.responder)['failed'], 1)
        self.assertFalse(any(c[0] == 'POST' for c in self.transport.calls))

    def test_errors_are_sanitized(self):
        self.transport.failure = RuntimeError('secret-test-token Private question')
        with self.assertRaises(MailError) as caught:
            self.client.get_message('incoming')
        self.assertNotIn('secret-test-token', str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_oversized_response_rejected(self):
        client = Client(self.root, self.config, lambda *a: {'text': 'x' * (MAX_RESPONSE + 1)})
        with self.assertRaises(MailError):
            client.get_message('incoming')

    def test_no_redirects_or_proxy_credentials(self):
        with patch('scripts.mail.urllib.request.build_opener') as build:
            build.return_value.open.side_effect = RuntimeError('private')
            client = Client(self.root, self.config)
            with self.assertRaises(MailError):
                client.get_message('incoming')
            handlers = build.call_args.args
            self.assertTrue(any(type(h).__name__ == 'NoRedirect' for h in handlers))
            self.assertTrue(any(getattr(h, 'proxies', None) == {} for h in handlers))

    def test_wrong_inbox_response_rejected(self):
        self.transport.messages[0]['inbox_id'] = 'other@example.test'
        self.assertEqual(self.box.cycle(self.responder)['failed'], 1)
        self.assertFalse(any(c[0] == 'POST' for c in self.transport.calls))


if __name__ == '__main__':
    unittest.main()
