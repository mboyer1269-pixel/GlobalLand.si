"""Host-authorized private conversation lineage; synthetic fixtures only."""
import copy
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

CONFIG = {'agentmail': {'enabled': True, 'inbox_id': 'inbox', 'inbox_address': 'city@example.test',
          'continuity': {'enabled': True}}, 'controller': {'providers': ['claude']}}


def message(mid='A', **changes):
    result = dict(inbox_id='inbox', message_id=mid, thread_id='opaque-thread',
                  to=['City <city@EXAMPLE.TEST>'], labels=['received'],
                  authentication_results={'dmarc': 'pass', 'dmarc_domain': 'EXAMPLE.TEST'},
                  text='PRIVATE-HISTORY price?', extracted_text='price?',
                  **{'from': 'Alice <Alice+tag@Example.Test>'})
    result.update(changes)
    return result


def finish(text='A private answer.', artifacts=None):
    return dict(actions=[], summary=json.dumps(dict(action='reply', text=text, artifacts=artifacts or [])))


class ContinuityPureTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('continuity'), 'private continuity implementation missing')
        import continuity
        return continuity

    def test_strict_metadata_gate_preserves_local_parts_and_optional_lists(self):
        c = self.module()
        bound = c.authorize_message(message(), CONFIG['agentmail'])
        self.assertEqual(bound['state'], 'ELIGIBLE')
        self.assertEqual(bound['binding']['peer'], 'Alice+tag@example.test')
        self.assertEqual(bound['route'], dict(to=['Alice+tag@example.test'], cc=[], bcc=[], reply_all=False))
        for changes in [dict(authentication_results={}), dict(authentication_results={'dkim': 'pass'}),
                        dict(authentication_results={'dmarc': 'pass', 'dmarc_domain': 'other.test'}),
                        dict(reply_to=['other@example.test']), dict(cc=['other@example.test']),
                        dict(bcc=None), dict(to=['city@example.test', 'extra@example.test']),
                        {'from': 'a@example.test, b@example.test'}, {'from': 'bad <a@example.test> trailing'},
                        dict(thread_id=''), dict(headers={'Authentication-Results': 'dmarc=pass'}, authentication_results=None)]:
            with self.subTest(changes=changes):
                self.assertEqual(c.authorize_message(message(**changes), CONFIG['agentmail'])['state'], 'ISOLATED')
        lower = c.authorize_message(message(**{'from': 'alice+tag@example.test'}), CONFIG['agentmail'])
        self.assertNotEqual(bound['binding'], lower['binding'])

    def test_default_disabled_and_invalid_config_never_enables_history(self):
        c = self.module()
        self.assertFalse(c.enabled({}))
        for value in ({'enabled': 'true'}, {'enabled': 1}, {'enabled': True, 'extra': True}, []):
            self.assertFalse(c.enabled({'agentmail': {'continuity': value}}))

    def test_digest_seals_semantics_but_not_derived_transport_metadata(self):
        c = self.module()
        data = dict(identity=['inbox', 'A'], state='READY', incoming=message(), continuity={'version': 1},
                    steps=[], decision={'action': 'reply', 'text': 'Ready'}, provider='claude')
        digest = c.ready_digest(data)
        self.assertEqual(digest, c.ready_digest(dict(data, ready_digest='ignored', index_repaired=True)))
        changed = copy.deepcopy(data); changed['incoming']['text'] += 'changed'
        self.assertNotEqual(digest, c.ready_digest(changed))
        changed = copy.deepcopy(data); changed['decision']['text'] += 'changed'
        self.assertNotEqual(digest, c.ready_digest(changed))

    def test_linked_commercial_source_uses_only_current_extracted_text(self):
        c = self.module()
        data = dict(incoming={'text': 'quoted old price?', 'extracted_text': 'Thanks.'},
                    continuity={'history': [{'case_key': 'a' * 64}]})
        self.assertEqual(c.observation_message(data), {'extracted_text': 'Thanks.'})
        data['incoming']['extracted_text'] = ' '
        self.assertEqual(c.observation_message(data), {})

    def test_self_reference_duplicate_refs_and_invalid_versions_are_rejected(self):
        c = self.module(); key = 'a' * 64
        desc = dict(version=1, state='ELIGIBLE', binding=dict(inbox_id='inbox', thread_id='thread', peer='a@example.test'),
                    route=dict(to=['a@example.test'], cc=[], bcc=[], reply_all=False), guard='f' * 64,
                    history=[], manifest=c.empty_manifest())
        for change in [dict(version=True), dict(manifest={}), dict(history=[dict(case_key=key, ready_digest='b' * 64, outbound_id='out')]),
                       dict(history=[dict(case_key='b' * 64, ready_digest='c' * 64, outbound_id='out')] * 2)]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                c.validate_descriptor(dict(desc, **change), key)


class ContinuityIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name); self.config = copy.deepcopy(CONFIG)
        self.messages = []; self.sent = []
        owner = self
        class Client:
            def list_received(self): return owner.messages
            def get_message(self, mid): return copy.deepcopy(next(m for m in owner.messages if m['message_id'] == mid))
            def reply(self, mid, text, operation, *, route=None):
                owner.sent.append((mid, text, route)); return dict(message_id='out-' + mid, thread_id='opaque-thread')
        self.client = Client()

    def box(self):
        from mail import Mailbox
        return Mailbox(self.root, self.config, self.client)

    def key(self, mid): return hashlib.sha256(('inbox\0' + mid).encode()).hexdigest()

    def case(self, mid):
        return self.root / 'state/private/fulfillment' / self.key(mid) / 'case.json'

    def tool_free(self):
        from mail_agent import MailResponder
        return MailResponder(self.root, self.config)

    def reply(self, text): return dict(actions=[], summary=json.dumps(dict(action='reply', text=text)))

    def test_tool_free_commercial_off_a_b_c_isolation_and_accepted_replay(self):
        import continuity
        self.messages = [message()]
        with patch('controller.Controller.plan', return_value=self.reply('PRIVATE-ANSWER-A')):
            self.assertEqual(self.box().cycle(self.tool_free())['accepted'], 1)
        self.assertTrue(self.case('A').is_file())
        self.messages += [message('B', in_reply_to='out-A'),
                          message('C', in_reply_to='out-A', **{'from': 'Other@example.test'})]
        seen = []
        def plan(planner, provider, prompt):
            seen.append(prompt)
            self.assertNotIn('EXEC is the only', planner.tool_guide)
            self.assertNotIn('PUBLISH_SITE:', planner.tool_guide)
            return self.reply('A useful answer')
        with patch('controller.Controller.plan', plan): self.box().cycle(self.tool_free())
        self.assertIn('PRIVATE-ANSWER-A', seen[0])
        self.assertNotIn('PRIVATE-ANSWER-A', seen[1])
        self.assertNotIn(self.key('A'), seen[1])
        self.assertEqual(self.sent[1][2], dict(to=['Alice+tag@example.test'], cc=[], bcc=[], reply_all=False))
        with patch('controller.Controller.plan', side_effect=AssertionError('no replay model')):
            self.box().cycle(self.tool_free())
        self.assertEqual(len(self.sent), 3)

    def test_ready_retry_route_change_never_sends_and_isolated_never_upgrades(self):
        import continuity
        self.messages = [message()]
        box = self.box(); save = box._save
        def fail_started(path, data):
            if data.get('state') == 'STARTED': raise OSError('interrupted before send')
            save(path, data)
        with patch.object(box, '_save', fail_started), patch('controller.Controller.plan', return_value=self.reply('PRIVATE-READY')):
            box.cycle(self.tool_free())
        self.assertEqual(self.sent, [])
        self.messages[0]['from'] = 'Other@example.test'
        with patch('mail.time.time', return_value=10**12), patch('controller.Controller.plan', side_effect=AssertionError('do not replan')):
            self.box().cycle(self.tool_free())
        self.assertEqual(self.sent, [])

    def test_index_failure_after_accepted_is_repaired_without_resend(self):
        import continuity
        self.messages = [message()]
        with patch('continuity.record_accepted', side_effect=OSError('index failure')), \
             patch('controller.Controller.plan', return_value=self.reply('durable')):
            self.assertEqual(self.box().cycle(self.tool_free())['accepted'], 1)
        journal = self.root / 'state/private/agentmail' / (self.key('A') + '.json')
        self.assertEqual(json.loads(journal.read_text())['state'], 'ACCEPTED')
        with patch('controller.Controller.plan', side_effect=AssertionError('no replay')):
            self.box().cycle(self.tool_free())
        self.assertEqual(len(self.sent), 1)
        self.messages += [message('B', in_reply_to='out-A')]
        def plan(planner, provider, prompt):
            self.assertIn('durable', prompt); return self.reply('continued')
        with patch('controller.Controller.plan', plan): self.box().cycle(self.tool_free())

    def seed_a(self):
        self.messages = [message()]
        with patch('controller.Controller.plan', return_value=self.reply('PRIVATE-ANSWER-A')):
            self.assertEqual(self.box().cycle(self.tool_free())['accepted'], 1)

    def test_frozen_working_history_fails_closed_then_ready_survives_ancestor_loss(self):
        self.seed_a(); self.messages.append(message('B', in_reply_to='out-A'))
        with patch('controller.Controller.plan', side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt): self.box().cycle(self.tool_free())
        frozen = json.loads(self.case('B').read_text())['continuity']
        original = self.case('A').read_text(); self.case('A').write_text('{corrupt')
        with patch('controller.Controller.plan', side_effect=AssertionError('cannot change frozen input')):
            self.assertEqual(self.box().cycle(self.tool_free())['failed'], 1)
        self.case('A').write_text(original)
        self.config['agentmail']['continuity']['enabled'] = False
        box = self.box(); save = box._save
        def fail_started(path, data):
            if data.get('state') == 'STARTED': raise OSError('pre-send failure')
            save(path, data)
        with patch('mail.time.time', return_value=10**12), patch.object(box, '_save', fail_started), \
             patch('controller.Controller.plan', return_value=self.reply('PRIVATE-READY-B')):
            box.cycle(self.tool_free())
        self.assertEqual(json.loads(self.case('B').read_text())['continuity'], frozen)
        self.case('A').unlink()
        with patch('mail.time.time', return_value=10**12 + 10000), patch('controller.Controller.plan', side_effect=AssertionError('READY replay only')):
            self.assertEqual(self.box().cycle(self.tool_free())['accepted'], 1)
        self.assertEqual(self.sent[-1][0], 'B')

    def test_ready_guard_changes_and_isolated_retry_never_upgrade(self):
        import continuity
        original_root = self.root
        for field, value in [('reply_to', ['other@example.test']), ('to', ['other@example.test']),
                             ('thread_id', 'changed'), ('authentication_results', {})]:
            with self.subTest(field=field):
                self.root = original_root / field; self.root.mkdir(); self.sent = []
                mid = 'guard-' + field; self.messages = [message(mid)]
                box = self.box(); save = box._save
                def fail(path, data):
                    if data.get('state') == 'STARTED': raise OSError('before send')
                    save(path, data)
                with patch.object(box, '_save', fail), patch('controller.Controller.plan', return_value=self.reply('PRIVATE-READY')):
                    box.cycle(self.tool_free())
                count = len(self.sent); self.messages[0][field] = value
                with patch('mail.time.time', return_value=10**12), patch('controller.Controller.plan', side_effect=AssertionError('no replan')):
                    self.box().cycle(self.tool_free())
                self.assertEqual(len(self.sent), count)
        self.root = original_root
        isolated = message('isolated', authentication_results={})
        from private_work import PrivateResponder
        responder = PrivateResponder(self.root, self.config)
        with patch('controller.Controller.plan', side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt): responder(isolated)
        frozen = json.loads(self.case('isolated').read_text())['continuity']
        self.assertEqual(frozen['state'], 'ISOLATED')
        with self.assertRaises(ValueError): continuity.prepare(self.root, message('isolated'), self.config)
        self.assertEqual(json.loads(self.case('isolated').read_text())['continuity'], frozen)

    def test_forged_index_changed_ready_and_conflicting_outbound_ids_fail_closed(self):
        import continuity
        self.seed_a()
        index = continuity.link_path(self.root, 'inbox', 'out-A')
        value = json.loads(index.read_text()); value['ready_digest'] = '0' * 64; index.write_text(json.dumps(value))
        self.messages.append(message('B', in_reply_to='out-A'))
        def plan(planner, provider, prompt):
            self.assertNotIn('PRIVATE-ANSWER-A', prompt); return self.reply('isolated')
        with patch('controller.Controller.plan', plan): self.box().cycle(self.tool_free())
        # Repair cannot bless a mismatched/forged link.
        self.assertNotIn('binding', json.loads(index.read_text()))
        # An independently eligible reply with a conflicting outbound identifier
        # makes the derived target unusable for every subsequent lookup.
        self.messages.append(message('D'))
        def duplicate(mid, text, operation, *, route=None):
            self.sent.append((mid, text, route)); return dict(message_id='out-A', thread_id='opaque-thread')
        with patch.object(self.client, 'reply', duplicate), patch('controller.Controller.plan', return_value=self.reply('PRIVATE-D')):
            self.box().cycle(self.tool_free())
        self.assertTrue(json.loads(index.read_text())['conflict'])
        self.messages.append(message('E', in_reply_to='out-A'))
        with patch('controller.Controller.plan', plan): self.box().cycle(self.tool_free())

    def test_response_thread_mismatch_is_unknown_and_not_retried(self):
        self.messages = [message()]
        def wrong(mid, text, operation, *, route=None):
            self.sent.append((mid, text, route)); return dict(message_id='out-A', thread_id='wrong')
        with patch.object(self.client, 'reply', wrong), patch('controller.Controller.plan', return_value=self.reply('answer')):
            self.assertEqual(self.box().cycle(self.tool_free())['unknown'], 1)
        with patch('controller.Controller.plan', side_effect=AssertionError('no uncertain repeat')):
            self.box().cycle(self.tool_free())
        self.assertEqual(len(self.sent), 1)
        self.assertFalse((self.root / 'state/private/reply-links').exists())

    def test_linked_quoted_full_text_is_not_new_commercial_evidence(self):
        self.config['agentmail']['commercial'] = {'enabled': True}
        self.seed_a(); self.messages.append(message('B', in_reply_to='out-A', text='quoted: PRIVATE-HISTORY price?', extracted_text='Thanks.'))
        response = self.reply('A useful response')
        response['summary'] = json.dumps(dict(action='reply', text='A useful response', observation=dict(
            category='PRICE_QUESTION', audience='ORDINARY', experiment_id=None,
            evidence={'field': 'text', 'quote': 'PRIVATE-HISTORY price?'})))
        with patch('controller.Controller.plan', return_value=response): self.box().cycle(self.tool_free())
        self.assertEqual(json.loads(self.case('B').read_text())['observation']['category'], 'UNKNOWN')
        import commercial
        self.assertNotIn('PRIVATE-HISTORY', json.dumps(commercial.project(self.root, self.config)))

    def test_history_window_is_bounded_nonrecursive_and_whole_unicode_text_is_omitted(self):
        import continuity
        self.messages = [message('0', text='界' * 40000)]
        with patch('controller.Controller.plan', return_value=self.reply('R' * 12000)):
            self.assertEqual(self.box().cycle(self.tool_free())['accepted'], 1)
        self.messages.append(message('1', in_reply_to='out-0', text='follow-up'))
        with patch('controller.Controller.plan', return_value=self.reply('continued')):
            self.assertEqual(self.box().cycle(self.tool_free())['accepted'], 1)
        first = json.loads(self.case('1').read_text())
        self.assertEqual(first['continuity']['manifest']['omitted_text'], 1)
        self.assertEqual(first['continuity']['manifest']['text_cases'], [])
        for n in range(2, 11):
            self.messages.append(message(str(n), in_reply_to='out-' + str(n-1), text='follow-up'))
            with patch('controller.Controller.plan', return_value=self.reply('continued')):
                self.assertEqual(self.box().cycle(self.tool_free())['accepted'], 1)
        data = json.loads(self.case('10').read_text()); refs = data['continuity']['history']
        self.assertEqual(len(refs), 8)
        self.assertEqual([ref['case_key'] for ref in refs], [self.key(str(n)) for n in range(2, 10)])
        self.assertTrue(data['continuity']['manifest']['ancestors_omitted'])
        self.assertTrue(all(set(ref) == {'case_key', 'ready_digest', 'outbound_id'} for ref in refs))

    def test_changed_ready_and_unsafe_derived_index_never_authorize_history(self):
        import continuity
        self.seed_a()
        data = json.loads(self.case('A').read_text()); ref = continuity.completion(data)
        data['decision']['text'] = 'ALTERED-PRIVATE-ANSWER'; self.case('A').write_text(json.dumps(data))
        with self.assertRaises(ValueError): continuity.load_ready(self.root, ref)
        self.messages.append(message('B', in_reply_to='out-A'))
        def plan(planner, provider, prompt):
            self.assertNotIn('ALTERED-PRIVATE-ANSWER', prompt); return self.reply('isolated')
        with patch('controller.Controller.plan', plan): self.box().cycle(self.tool_free())
        index = continuity.link_path(self.root, 'inbox', 'out-A'); index.unlink()
        outside = self.root / 'outside.json'; outside.write_text('{"private":"DO-NOT-READ"}')
        index.symlink_to(outside)
        with self.assertRaises(ValueError): continuity.validate_link(self.root, dict(inbox_id='inbox', thread_id='opaque-thread', peer='Alice+tag@example.test'), 'out-A')

    def test_historical_files_use_whole_byte_bounded_items_and_current_artifact_ownership(self):
        import continuity
        from private_work import PrivateResponder
        contents = '界' * 8000
        digest = hashlib.sha256(contents.encode('utf-8')).hexdigest()
        receipt = dict(status='DONE', output='Computed privately.', files={'products/out.csv': contents}, sha256={'products/out.csv': digest})
        action = dict(summary='Compute', actions=[dict(agent='BUILDER', action='EXEC',
                      args=dict(argv=['node', '-e', 'unused fixture seam'], outputs=['products/out.csv']))])
        for n in range(3):
            mid = 'file-' + str(n)
            self.messages.append(message(mid, **({'in_reply_to': 'out-file-' + str(n-1)} if n else {})))
            with patch('controller.Controller.plan', side_effect=[action, finish(artifacts=['products/out.csv'])]), \
                 patch('private_work.PrivateResponder._execute', return_value=receipt):
                self.assertEqual(self.box().cycle(PrivateResponder(self.root, self.config))['accepted'], 1)
        followup = message('files-followup', in_reply_to='out-file-2')
        desc = continuity.prepare(self.root, followup, self.config)
        data = dict(identity=['inbox', 'files-followup'], continuity=desc, steps=[])
        view, files = continuity.materialize_history(self.root, data)
        self.assertEqual(view['manifest']['omitted_files'], 1)
        self.assertEqual(sum(len(v.encode('utf-8')) for v in files.values()), 48000)
        self.assertEqual(len(files), 2)
        self.assertTrue(all(v == contents for v in files.values()))
        self.assertTrue(all(f['sha256'] == digest and f['bytes'] == 24000 for f in view['manifest']['files']))
        self.assertEqual((view, files), continuity.materialize_history(self.root, data))
        with self.assertRaises(ValueError):
            PrivateResponder(self.root, self.config)._final(finish(artifacts=[next(iter(files))]), {'steps': []})

    def test_actual_client_serializes_only_the_pinned_host_route(self):
        from mail import Client
        token = self.root / 'credentials/agentmail/token'; token.parent.mkdir(parents=True)
        token.write_text('synthetic-token'); token.chmod(0o600)
        calls = []
        def transport(method, url, headers, payload):
            calls.append(payload); return dict(message_id='out-A', thread_id='opaque-thread')
        client = Client(self.root, self.config, transport)
        route = dict(to=['Alice+tag@example.test'], cc=[], bcc=[], reply_all=False)
        client.reply('A', 'A private reply', 'gl-fixture', route=route)
        self.assertEqual({k: calls[0][k] for k in route}, route)
        with self.assertRaises(ValueError): client.reply('A', 'reply', 'gl-fixture', route=dict(route, reply_all=0))


if __name__ == '__main__': unittest.main()
