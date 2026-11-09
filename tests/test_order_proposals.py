"""Offline administrative product ordering, using only fictional private cases."""
import copy
import hashlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import continuity
import order_context
import orders
import orders_admin


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.private = self.root / 'state/private'; self.private.mkdir(parents=True, mode=0o700)
        self.config = {'agentmail': {'enabled': True, 'inbox_id': 'inbox', 'inbox_address': 'city@example.test',
                                    'commercial': {'enabled': True, 'synthetic_senders': []}}}
        (self.root / 'control').mkdir()
        self.save_config()
        self.artifact = self.root / 'products/checklist.txt'
        self.artifact.parent.mkdir(); self.artifact.write_bytes(b'Reusable checklist.\n')
        self.demand = self.case('demand', 'Please offer your reusable checklist.')
        self.proposal = {
            'completion': self.demand, 'demand_excerpt': 'your reusable checklist',
            'terms': {'version': 1, 'product_id': 'checklist', 'product_version': '1.0',
                      'offer_version': 1, 'title': 'Reusable checklist',
                      'scope': 'One copy of the existing checklist.', 'exclusions': 'No custom work.',
                      'license': 'Single business internal use.', 'support': 'No ongoing support.',
                      'amount_cents': 1900, 'currency': 'CAD',
                      'delivery': {'mode': 'MANUAL_ARTIFACT', 'artifact_path': 'products/checklist.txt',
                                   'artifact_sha256': hashlib.sha256(self.artifact.read_bytes()).hexdigest()}}
        }

    def case(self, mid, text, **changes):
        message = dict(inbox_id='inbox', message_id=mid, thread_id='thread', labels=['received'],
                       to=['city@example.test'], text=text, extracted_text=text,
                       authentication_results={'dmarc': 'pass', 'dmarc_domain': 'example.test'},
                       **{'from': 'private-buyer@example.test'})
        message.update(changes)
        auth = continuity.authorize_message(message, self.config['agentmail'])
        data = dict(identity=['inbox', mid], incoming=message, state='READY', steps=[],
                    provider='claude', decision={'action': 'reply', 'text': 'Draft review only.'},
                    continuity=dict(version=1, state=auth['state'], binding=auth['binding'],
                                    route=auth['route'], guard=continuity.guard(message), history=[],
                                    manifest=continuity.empty_manifest()))
        continuity.seal(data)
        ref = continuity.completion(data)
        path = continuity.case_path(self.root, ref['case_key']); path.parent.mkdir(parents=True, mode=0o700)
        path.write_text(json.dumps(data)); path.chmod(0o600)
        return ref

    def save_config(self):
        path = self.root / 'control/config.json'; path.write_text(json.dumps(self.config)); path.chmod(0o600)

    def invoke(self, action, data, uid=0):
        request = self.private / 'request.json'; request.write_text(json.dumps(data)); request.chmod(0o600)
        with patch('sys.stdout', new_callable=io.StringIO) as stream:
            try:
                result = orders_admin.main([action, '--request', str(request)], root=self.root, euid=lambda: uid)
            except SystemExit:
                self.fail('Administrative proposal action is not implemented: ' + action)
        for secret in ('private-buyer', 'your reusable checklist', 'city@example.test'):
            self.assertNotIn(secret, stream.getvalue())
        return result

    def acceptance(self, created, **changes):
        data = dict(proposal_id=created['proposal_id'], order_id=created['order_id'],
                    terms_sha256=created['terms_sha256'],
                    completion=self.case('accept', 'I accept checklist version 1 at CAD 19.'),
                    acceptance_excerpt='I accept checklist version 1 at CAD 19.',
                    attestation='ADMIN_REVIEWED_EXACT_TERMS')
        data.update(changes)
        return data

    def route(self):
        self.invoke('route', dict(version=1, state='READY_FOR_INSTRUCTIONS', method='INTERAC', currency='CAD',
                                 recipient_email='city@example.test', account_alias='project',
                                 confirmed_at='2026-11-09T12:00:00Z', confirmation='FOUNDER_OBSERVED'))

    def test_product_demand_becomes_one_draft_and_no_treasury(self):
        first = self.invoke('propose', self.proposal)
        self.assertEqual(first['commercial_status'], 'DRAFT')
        self.assertEqual(self.invoke('propose', self.proposal)['order_id'], first['order_id'])
        self.assertEqual(orders.project(self.root)['orders_count'], 1)
        self.assertFalse((self.private / 'treasury.sqlite3').exists())
        incoming = continuity.load_ready(self.root, self.demand)['incoming']
        self.assertNotIn('payment_instructions', order_context.for_message(self.root, incoming, self.config)['orders'][0])

    def test_changed_terms_replay_refused_and_revision_distinct(self):
        created = self.invoke('propose', self.proposal)
        changed = copy.deepcopy(self.proposal); changed['terms']['amount_cents'] = 2000
        with self.assertRaises(ValueError): self.invoke('propose', changed)
        changed['terms']['offer_version'] = 2
        revised = self.invoke('propose', changed)
        self.assertNotEqual(revised['order_id'], created['order_id'])
        self.assertNotEqual(revised['terms_sha256'], created['terms_sha256'])

    def test_explicit_matching_acceptance_then_private_instructions(self):
        self.route(); created = self.invoke('propose', self.proposal)
        acceptance = self.acceptance(created)
        accepted = self.invoke('accept-proposal', acceptance)
        self.assertEqual(accepted['commercial_status'], 'ACCEPTED')
        self.assertEqual(self.invoke('accept-proposal', acceptance), accepted)
        target = self.private / 'instructions.json'
        exported = self.invoke('instructions', dict(proposal_id=created['proposal_id'], order_id=created['order_id'], output=str(target)))
        self.assertTrue(exported['prepared'])
        output = json.loads(target.read_text())
        self.assertEqual(output['payment_instructions']['reference'], created['order_id'])
        self.assertEqual(output['payment_instructions']['amount_cents'], 1900)
        self.assertEqual(output['payment_instructions']['recipient_email'], 'city@example.test')
        self.assertFalse((self.private / 'treasury.sqlite3').exists())
        if os.name == 'posix': self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_acceptance_requires_exact_terms_distinct_source_and_same_buyer(self):
        created = self.invoke('propose', self.proposal)
        request = self.acceptance(created)
        bad_cases = [dict(attestation='MODEL_ACCEPTED'), dict(terms_sha256='f' * 64),
                     dict(completion=self.demand, acceptance_excerpt='your reusable checklist'),
                     dict(acceptance_excerpt='not in original message'),
                     dict(completion=self.case('other', 'I accept.', **{'from': 'other@example.test'}), acceptance_excerpt='I accept.'),
                     dict(completion=self.case('thread2', 'I accept.', thread_id='other'), acceptance_excerpt='I accept.')]
        for change in bad_cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.invoke('accept-proposal', dict(request, **change))
        self.assertEqual(orders.OrderRegister(self.root).get_order(created['order_id'])['commercial_status'], 'DRAFT')

    def test_one_acceptance_message_cannot_accept_two_proposal_versions(self):
        first = self.invoke('propose', self.proposal)
        a = self.acceptance(first); self.invoke('accept-proposal', a)
        revised = copy.deepcopy(self.proposal); revised['terms']['offer_version'] = 2
        second = self.invoke('propose', revised)
        a.update(proposal_id=second['proposal_id'], order_id=second['order_id'], terms_sha256=second['terms_sha256'])
        with self.assertRaises(ValueError): self.invoke('accept-proposal', a)
        self.assertEqual(orders.OrderRegister(self.root).get_order(second['order_id'])['commercial_status'], 'DRAFT')

    def test_invalid_proposal_never_initializes_order_storage(self):
        for field, value in [('amount_cents', True), ('amount_cents', 1.5), ('amount_cents', 0),
                             ('amount_cents', 2**63), ('currency', 'cad'), ('offer_version', True),
                             ('version', 2), ('title', ''), ('scope', 'x' * 4097)]:
            bad = copy.deepcopy(self.proposal); bad['terms'][field] = value
            with self.subTest(field=field, value=str(value)[:30]), self.assertRaises(ValueError): self.invoke('propose', bad)
        for change in [dict(case_key='invented'), dict(demand_excerpt='not present'),
                       dict(completion=self.case('isolated', 'please', authentication_results={}))]:
            with self.subTest(change=change), self.assertRaises(ValueError): self.invoke('propose', dict(self.proposal, **change))
        self.assertFalse((self.private / 'orders.sqlite3').exists())

    def test_artifact_evidence_rejects_changed_missing_and_oversize(self):
        for content in (b'changed', b'\xff\xfe', b'x' * 16001):
            self.artifact.write_bytes(content)
            with self.assertRaises(ValueError): self.invoke('propose', self.proposal)
        self.artifact.unlink()
        with self.assertRaises((ValueError, OSError)): self.invoke('propose', self.proposal)
        self.assertFalse((self.private / 'orders.sqlite3').exists())

    def test_no_instructions_for_draft_unconfigured_claimed_or_foreign_order(self):
        created = self.invoke('propose', self.proposal)
        request = dict(proposal_id=created['proposal_id'], order_id=created['order_id'], output=str(self.private / 'instructions.json'))
        with self.assertRaises(ValueError): self.invoke('instructions', request)
        self.invoke('accept-proposal', self.acceptance(created))
        with self.assertRaises(ValueError): self.invoke('instructions', request)
        self.route()
        self.invoke('claim', dict(order_id=created['order_id'], source_id='unverified', amount_cents=1900, currency='CAD'))
        with self.assertRaises(ValueError): self.invoke('instructions', request)
        self.assertFalse(pathlib.Path(request['output']).exists())
        self.assertFalse((self.private / 'treasury.sqlite3').exists())

    def test_private_output_refuses_public_path_and_existing_file(self):
        self.route(); created = self.invoke('propose', self.proposal)
        self.invoke('accept-proposal', self.acceptance(created))
        target = self.private / 'existing.json'; target.write_text('preserve'); target.chmod(0o600)
        for path in (target, self.root / 'public.json', self.private / '../public.json'):
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                self.invoke('instructions', dict(proposal_id=created['proposal_id'], order_id=created['order_id'], output=str(path)))
        self.assertEqual(target.read_text(), 'preserve')

    def test_saved_source_tamper_and_unprivileged_import_fail_before_register(self):
        with self.assertRaises(ValueError): self.invoke('propose', self.proposal, uid=1000)
        path = continuity.case_path(self.root, self.demand['case_key'])
        data = json.loads(path.read_text()); data['incoming']['text'] = 'changed'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError): self.invoke('propose', self.proposal)
        self.assertFalse((self.private / 'orders.sqlite3').exists())

    def test_current_inbox_configuration_is_required_for_import_accept_and_export(self):
        self.config['agentmail']['inbox_id'] = 'retired'; self.save_config()
        with self.assertRaises(ValueError): self.invoke('propose', self.proposal)
        self.assertFalse((self.private / 'orders.sqlite3').exists())
        self.config['agentmail']['inbox_id'] = 'inbox'; self.save_config()
        self.route(); created = self.invoke('propose', self.proposal)
        acceptance = self.acceptance(created)
        self.config['agentmail']['inbox_address'] = 'new@example.test'; self.save_config()
        with self.assertRaises(ValueError): self.invoke('accept-proposal', acceptance)
        self.config['agentmail']['inbox_address'] = 'city@example.test'; self.save_config()
        self.invoke('accept-proposal', acceptance)
        self.config['agentmail']['enabled'] = False; self.save_config()
        with self.assertRaises(ValueError):
            self.invoke('instructions', dict(proposal_id=created['proposal_id'], order_id=created['order_id'], output=str(self.private / 'instructions.json')))

    def test_synthetic_automated_and_held_sources_cannot_be_real_orders(self):
        self.config['agentmail']['commercial']['synthetic_senders'] = ['private-buyer@example.test']; self.save_config()
        with self.assertRaises(ValueError): self.invoke('propose', self.proposal)
        self.config['agentmail']['commercial']['enabled'] = False; self.save_config()
        with self.assertRaises(ValueError): self.invoke('propose', self.proposal)
        self.config['agentmail']['commercial']['synthetic_senders'] = []; self.save_config()
        for index, changes in enumerate((dict(headers={'auto-submitted': 'auto-generated'}), dict(labels=['received', 'spam']),
                                         dict(labels=['received', 'agent-armor-held']))):
            source = self.case('notice' + str(index), 'your reusable checklist', **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.invoke('propose', dict(self.proposal, completion=source))
        self.assertFalse((self.private / 'orders.sqlite3').exists())

    def test_binary_product_and_exact_artifact_bound_are_supported(self):
        for content in (b'PK\x03\x04\xff\x00binary', b'x' * (1024 * 1024)):
            self.artifact.write_bytes(content)
            self.proposal['terms']['delivery']['artifact_sha256'] = hashlib.sha256(content).hexdigest()
            self.proposal['terms']['offer_version'] += 1
            self.assertEqual(self.invoke('propose', self.proposal)['commercial_status'], 'DRAFT')
        content = b'x' * (1024 * 1024 + 1); self.artifact.write_bytes(content)
        self.proposal['terms']['delivery']['artifact_sha256'] = hashlib.sha256(content).hexdigest()
        self.proposal['terms']['offer_version'] += 1
        with self.assertRaises(ValueError): self.invoke('propose', self.proposal)
        self.assertEqual(orders.project(self.root)['orders_count'], 2)

    def test_interrupted_snapshot_cleanup_does_not_poison_replay(self):
        # A process can stop immediately after publication but before cleanup.
        import order_proposals
        with patch('order_proposals.os.unlink', side_effect=OSError('interrupted cleanup')):
            try: self.invoke('propose', self.proposal)
            except OSError: pass
        result = self.invoke('propose', self.proposal)
        self.assertEqual(result['commercial_status'], 'DRAFT')
        self.assertEqual(orders.project(self.root)['orders_count'], 1)

    def test_creation_and_acceptance_replay_after_ledger_commit_interruption(self):
        original = orders.OrderRegister.create_order
        def interrupted(register, *args, **kwargs):
            original(register, *args, **kwargs)
            raise OSError('crashed after order commit')
        with patch.object(orders.OrderRegister, 'create_order', interrupted), self.assertRaises(OSError):
            self.invoke('propose', self.proposal)
        created = self.invoke('propose', self.proposal)
        original_accept = orders.OrderRegister.accept_order
        def interrupted_accept(register, *args, **kwargs):
            original_accept(register, *args, **kwargs)
            raise OSError('crashed after acceptance commit')
        request = self.acceptance(created)
        with patch.object(orders.OrderRegister, 'accept_order', interrupted_accept), self.assertRaises(OSError):
            self.invoke('accept-proposal', request)
        self.assertEqual(self.invoke('accept-proposal', request)['commercial_status'], 'ACCEPTED')
        self.assertEqual(orders.project(self.root)['orders_count'], 1)
        self.assertFalse((self.private / 'treasury.sqlite3').exists())

    def test_exact_order_export_survives_more_than_ten_newer_drafts(self):
        self.route(); first = self.invoke('propose', self.proposal)
        self.invoke('accept-proposal', self.acceptance(first))
        for version in range(2, 12):
            self.proposal['terms']['offer_version'] = version
            self.invoke('propose', self.proposal)
        result = self.invoke('instructions', dict(proposal_id=first['proposal_id'], order_id=first['order_id'], output=str(self.private / 'older-order.json')))
        self.assertTrue(result['prepared'])
        message = continuity.load_ready(self.root, self.demand)['incoming']
        self.assertEqual(len(order_context.for_message(self.root, message, self.config)['orders']), 10)
        message['from'] = 'someone-else@example.test'
        self.assertEqual(order_context.for_message(self.root, message, self.config, order_id=first['order_id'])['orders'], [])

    def test_fixture_proposal_reaches_founder_posting_once_and_cannot_request_payment_again(self):
        from treasury import Treasury
        self.route(); created = self.invoke('propose', self.proposal)
        self.invoke('accept-proposal', self.acceptance(created))
        request = dict(proposal_id=created['proposal_id'], order_id=created['order_id'], output=str(self.private / 'ready.json'))
        self.invoke('instructions', request)
        self.invoke('claim', dict(order_id=created['order_id'], source_id='fixture-claim', amount_cents=1900, currency='CAD'))
        self.assertFalse((self.private / 'treasury.sqlite3').exists())
        deposit = self.invoke('confirm', dict(account_alias='project', reference='fixture-reference', amount_cents=1900,
            currency='CAD', observed_at='2026-11-09T12:00:01Z', evidence_sha256='e' * 64,
            attestation='FOUNDER_OBSERVED_BANK_DEPOSIT'))
        self.invoke('allocate', dict(deposit_id=deposit['deposit_id'], order_id=created['order_id']))
        self.assertFalse((self.private / 'treasury.sqlite3').exists())
        for _ in range(2):
            self.invoke('post', dict(deposit_id=deposit['deposit_id'], attestation='FOUNDER_OBSERVED_BANK_DEPOSIT'))
        bank = Treasury(self.private / 'treasury.sqlite3').snapshot()
        self.assertEqual(bank['cash_cents'], 1900)
        self.assertEqual(bank['founder_attested_revenue_cents'], 1900)
        self.assertFalse(bank['funding_verified'])
        request['output'] = str(self.private / 'paid.json')
        with self.assertRaises(ValueError): self.invoke('instructions', request)
        self.assertFalse((self.private / 'paid.json').exists())

    def test_artifact_mutation_after_proposal_prevents_acceptance_and_export(self):
        self.route(); created = self.invoke('propose', self.proposal)
        acceptance = self.acceptance(created)
        self.artifact.write_bytes(b'changed product')
        with self.assertRaises(ValueError): self.invoke('accept-proposal', acceptance)
        self.artifact.write_bytes(b'Reusable checklist.\n')
        self.invoke('accept-proposal', acceptance)
        self.artifact.unlink()
        with self.assertRaises((ValueError, OSError)):
            self.invoke('instructions', dict(proposal_id=created['proposal_id'], order_id=created['order_id'], output=str(self.private / 'missing.json')))

    def test_swapped_order_and_symlink_or_public_evidence_are_refused(self):
        first = self.invoke('propose', self.proposal)
        other = copy.deepcopy(self.proposal); other['terms']['offer_version'] = 2
        second = self.invoke('propose', other)
        with self.assertRaises(ValueError):
            self.invoke('accept-proposal', self.acceptance(first, order_id=second['order_id']))
        source = continuity.case_path(self.root, self.demand['case_key'])
        if os.name == 'posix':
            source.chmod(0o644)
            with self.assertRaises(ValueError): self.invoke('propose', self.proposal)
            source.chmod(0o600)
        self.artifact.rename(self.artifact.with_suffix('.real'))
        self.artifact.symlink_to(self.artifact.with_suffix('.real'))
        with self.assertRaises(ValueError): self.invoke('propose', self.proposal)


if __name__ == '__main__': unittest.main()
