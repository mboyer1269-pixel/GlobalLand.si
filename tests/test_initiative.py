"""Exact private source coverage and durable admission, without external services."""
import copy
import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
POSIX = importlib.util.find_spec('fcntl') is not None
CONFIG = dict(initiative=dict(enabled=True, debounce_seconds=0),
              agentmail=dict(enabled=True, inbox_id='inbox', inbox_address='city@example.test',
                             commercial=dict(enabled=True)),
              controller=dict(mode='subscriptions', providers=['claude'],
                              subscriptions_confirmed=True, extra_usage_disabled=True,
                              image='brain@sha256:' + '1' * 64))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name); self.config = copy.deepcopy(CONFIG)
        (self.root / 'state/private/agentmail').mkdir(parents=True)

    def signal(self, mid, **changes):
        observation = dict(category='PRICE_QUESTION', audience='ORDINARY', experiment_id=None,
                           evidence=dict(field='text', quote='PRIVATE QUOTE'), origin='INBOUND_UNVERIFIED',
                           attribution='UNATTRIBUTED', provider='claude', observed_at='2026-11-05T00:00:00Z')
        observation.update(changes)
        record = dict(inbox_id='inbox', message_id=mid, state='ACCEPTED', observation=observation)
        key = hashlib.sha256(('inbox\0' + mid).encode()).hexdigest()
        path = self.root / 'state/private/agentmail' / (key + '.json')
        path.write_text(json.dumps(record), encoding='utf-8')
        return key, record

    def result(self, n, action='EXEC', output='ok', shape='request'):
        ident = 'TASK-%012d' % n
        task = dict(id=ident, type='TOOL', submitted_by='BUILDER', action=action,
                    args=dict(argv=['node', '-p', '1'], outputs=[]))
        record = dict(id=ident, hash=hashlib.sha256(json.dumps(task).encode()).hexdigest(),
                      task='queue/inbox/' + ident + '.json', state='COMPLETED',
                      result=dict(status='DONE', output=output))
        if shape == 'request': record['request'] = task
        elif shape == 'task': record['task'] = task
        else:
            path = self.root / 'work/queue/inbox' / (ident + '.json')
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(task))
        (self.root / 'state' / (ident + '.json')).write_text(json.dumps(record), encoding='utf-8')
        return ident, record

    def controller(self):
        from controller import Controller
        class Snapshot:
            def snapshot(self): return dict(state='UNFUNDED', missions=[], agents=[])
        return Controller(self.root, Snapshot(), Snapshot(), self.config)


class CoverageTests(Fixture):
    def test_source_contract_is_available(self):
        self.assertIsNotNone(importlib.util.find_spec('initiative'), 'missing initiative source revision contract')

    @unittest.skipUnless(POSIX, 'controller requires real POSIX locking')
    def test_frozen_context_ack_only_visible_revisions(self):
        import initiative
        import commercial
        controller = self.controller(); priority = []
        for n in range(23):
            _, record = self.result(n + 1000, output='é' * 2001)
            key, version = initiative.source_revision('QUEUED_RESULT', record)
            priority.append(dict(kind='QUEUED_RESULT', key=key, version=version))
        for n in range(2001):
            key, record = self.signal('message-%04d' % n)
            key, version = initiative.source_revision('COMMERCIAL_SIGNAL', record)
            priority.append(dict(kind='COMMERCIAL_SIGNAL', key=key, version=version))
        with patch('commercial.scan', wraps=commercial.scan) as scan:
            prepared = controller.prepare_context(priority=priority)
        self.assertEqual(scan.call_count, 1)
        self.assertEqual(set(prepared), {'context', 'assessment', 'coverage', 'excluded'})
        results = prepared['context']['latest_task_results']
        self.assertEqual(len(results), 20)
        self.assertEqual([v['task'] for v in results], [p['key'] for p in priority[:20]])
        self.assertTrue(all(len(v['output']) == 2000 and v['output_truncated'] for v in results))
        covered = prepared['coverage']
        self.assertEqual(sum(v['kind'] == 'QUEUED_RESULT' for v in covered), 20)
        self.assertEqual(sum(v['kind'] == 'COMMERCIAL_SIGNAL' for v in covered), 2000)
        self.assertEqual(prepared['context']['commercial_feedback']['state'], 'PARTIAL')
        frozen = copy.deepcopy(prepared)
        self.result(1000, output='changed'); self.signal('message-0000', category='REJECTION')
        self.assertEqual(prepared, frozen)
        old = {(v['kind'], v['key'], v['version']) for v in covered}
        remaining = [p for p in priority if (p['kind'], p['key'], p['version']) not in old]
        for n in range(50): self.result(9000 + n); self.signal('recent-%04d' % n)
        next_batch = controller.prepare_context(priority=remaining)
        new = {(v['kind'], v['key'], v['version']) for v in next_batch['coverage']}
        self.assertTrue(all((p['kind'], p['key'], p['version']) in new for p in remaining))
        public = json.dumps(prepared['context'])
        self.assertNotIn('PRIVATE QUOTE', public)
        self.assertNotIn(priority[23]['key'], public)

    @unittest.skipUnless(POSIX, 'controller requires real POSIX locking')
    def test_financial_legacy_shapes_are_status_only(self):
        for n, (action, shape) in enumerate((a, s) for a in ('SPEND', 'RECONCILE')
                                           for s in ('request', 'task', 'path')):
            ident, record = self.result(2000 + n, action=action, shape=shape,
                output='SECRET_FINANCE_OUTPUT receipt signature gateway cursor idempotency_key')
            request = record.get('request', record.get('task'))
            if isinstance(request, dict):
                request['args'] = dict(secret='SECRET_FINANCE_ARGUMENT')
                (self.root / 'state' / (ident + '.json')).write_text(json.dumps(record))
        prepared = self.controller().prepare_context()
        self.assertEqual(len(prepared['context']['latest_task_results']), 6)
        for row in prepared['context']['latest_task_results']:
            self.assertTrue(row['output_redacted']); self.assertEqual(row['status'], 'DONE')
        public = json.dumps(prepared['context'])
        for marker in ('SECRET_FINANCE', 'signature', 'idempotency_key', 'gateway cursor'):
            self.assertNotIn(marker, public)
        self.assertTrue(all(v['representation'] == 'STATUS_ONLY' for v in prepared['coverage']))

    @unittest.skipUnless(POSIX, 'controller requires real POSIX locking')
    def test_corrupt_sources_and_screening_are_explicit(self):
        self.result(3000, output='receipt PRIVATE_RESPONSE')
        _, broken = self.result(3001); broken['result']['status'] = 'INVENTED'
        (self.root / 'state/TASK-000000003001.json').write_text(json.dumps(broken))
        prepared = self.controller().prepare_context()
        self.assertEqual(len(prepared['context']['latest_task_results']), 1)
        self.assertTrue(prepared['context']['latest_task_results'][0]['output_redacted'])
        self.assertTrue(prepared['excluded'])
        self.assertNotIn('PRIVATE_RESPONSE', json.dumps(prepared['context']))


class AdmissionTests(Fixture):
    def store(self):
        import initiative
        return initiative.Store(self.root, self.config)

    def test_exact_settings_ranges_and_canonical_duplicate_suppression(self):
        import initiative
        self.assertFalse(initiative.settings({})['enabled'])
        for key, (low, high) in initiative.RANGES.items():
            for bad in (True, low - 1, high + 1, '1'):
                with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                    initiative.settings(dict(initiative={key: bad}))
        for bad in ('true', 1, None):
            with self.assertRaises(ValueError): initiative.settings(dict(initiative=dict(enabled=bad)))
        store = self.store(); key, record = self.signal('new')
        store.reconcile(dict(missions=[]), now=1000)
        store.reconcile(dict(missions=[]), now=1001)
        wake = store.claim('wake', now=1002, world_state='RUNNING', bank_state='UNFUNDED')
        self.assertEqual(len(wake['events']), 1)
        event = wake['events'][0]
        self.assertEqual(event['id'], initiative.digest([event['kind'], key, event['version']]))
        self.assertEqual(store.claim('wake', now=1003, world_state='RUNNING', bank_state='UNFUNDED')['wake_id'], wake['wake_id'])
        record['observation']['observed_at'] = '2026-11-05T01:00:00Z'
        self.assertEqual(initiative.source_revision('COMMERCIAL_SIGNAL', record)[1], event['version'])

    def test_scan_cursor_deletion_and_baseline_restart(self):
        import initiative
        self.config['initiative']['scan_page_size'] = 1
        for n in range(4): self.signal('historic-%d' % n)
        store = self.store(); store.reconcile(dict(missions=[]), now=100)
        paths = sorted((self.root / 'state/private/agentmail').glob('*.json'))
        paths[0].unlink()
        key, record = self.signal('arriving-after-activation')
        store = self.store()
        for now in range(101, 115): store.reconcile(dict(missions=[]), now=now)
        wake = store.claim('wake', now=120, world_state='RUNNING', bank_state='UNFUNDED')
        self.assertEqual([v['key'] for v in wake['events']], [key])
        # The already-discovered deleted identity remains durable dedupe evidence.
        self.assertEqual(len(store.events(status='BASELINED')), 4)
        self.assertFalse(store.events(status='ACKED'))

    def test_only_host_eligible_sources_and_lease_replacement(self):
        store = self.store()
        for n, changes in enumerate((dict(origin='SYNTHETIC'), dict(origin='AUTOMATED'),
                                    dict(category='UNKNOWN', evidence=None), dict(audience='AUTOMATED'))):
            self.signal('excluded-%d' % n, **changes)
        key, _ = self.signal('useful')
        for n, (action, origin) in enumerate((('STATUS', 'queued'), ('EXEC', 'broker'), ('EXEC', 'queued'))):
            _, r = self.result(4000 + n, action=action); r['origin'] = origin
            (self.root / 'state' / (r['id'] + '.json')).write_text(json.dumps(r))
        mission = dict(mission_id='MISSION', status='RUNNING', agent_id='BUILDER',
                       lease_token='private-lease', lease_expires_at=1400)
        world = dict(missions=[mission], agents=[dict(agent_id='BUILDER', status='ACTIVE')])
        store.reconcile(world, now=1000)
        store.reconcile(world, now=1500)
        self.assertEqual(len(store.events(kind='COMMERCIAL_SIGNAL')), 1)
        self.assertEqual(len(store.events(kind='QUEUED_RESULT')), 1)
        self.assertEqual(len(store.events(kind='LEASE_DUE')), 1)
        old = store.events(kind='LEASE_DUE')[0]
        mission.update(lease_token='replacement', lease_expires_at=1800)
        store.reconcile(world, now=1501)
        self.assertEqual(store.event(old['id'])['status'], 'OBSOLETE')

    def test_chain_depth_survives_restart_and_periodic_consumes_backlog(self):
        import initiative
        store = self.store(); self.signal('root')
        store.reconcile(dict(missions=[]), now=1000)
        wake = store.claim('wake', now=1001, world_state='RUNNING', bank_state='UNFUNDED')
        self.assertEqual(wake['cause']['depth'], 1)
        prepared = dict(context={}, assessment={}, coverage=[dict(v, representation='AGGREGATE_COUNTER')
                        for v in (dict(kind=e['kind'], key=e['key'], version=e['version']) for e in wake['events'])], excluded=[])
        store.start(wake['wake_id'], prepared=prepared, now=1002)
        task = dict(id='TASK-000000005000', type='TOOL', action='EXEC', args=dict(argv=['node'], outputs=[]))
        store.bind_task(task, turn=wake['turn'], cause=wake['cause'], origin='queued')
        _, record = self.result(5000)
        record['request'] = task
        (self.root / 'state' / (record['id'] + '.json')).write_text(json.dumps(record))
        store = self.store(); store.recover(now=1400); store.reconcile(dict(missions=[]), now=1401)
        self.assertIsNone(store.claim('wake', now=1500, world_state='RUNNING', bank_state='UNFUNDED'))
        periodic = store.claim('think', now=1500, world_state='RUNNING', bank_state='UNFUNDED')
        self.assertTrue(periodic['events']); self.assertEqual(periodic['cause']['depth'], 0)
        self.assertTrue(any(e['cause']['depth'] == 1 for e in periodic['events']))

    def test_started_uncertainty_and_spacing_survive_restart_and_clock_rollback(self):
        store = self.store(); self.signal('first')
        store.reconcile(dict(missions=[]), now=1000)
        wake = store.claim('wake', now=1001, world_state='RUNNING', bank_state='UNFUNDED')
        store.start(wake['wake_id'], prepared=dict(context={}, assessment={}, coverage=[], excluded=[]), now=1002)
        store = self.store(); self.assertEqual(store.recover(now=1003), [])
        self.assertEqual(store.admission(wake['wake_id'])['phase'], 'INTERRUPTED')
        for now in (100, 1004, 1301):
            self.assertIsNone(store.claim('think', now=now, world_state='RUNNING', bank_state='UNFUNDED'))
        self.assertIsNotNone(store.claim('think', now=1302, world_state='RUNNING', bank_state='UNFUNDED'))

    def test_both_store_stop_guards_and_permanent_extinction(self):
        for stopped in ('HALTED', 'EXTINCT'):
            with self.subTest(stopped=stopped):
                store = self.store()
                self.assertIsNone(store.claim('think', now=1000, world_state=stopped, bank_state='UNFUNDED'))
                self.assertIsNone(store.claim('mail', now=1000, world_state='RUNNING', bank_state=stopped))
        self.assertIsNone(self.store().claim('think', now=2000, world_state='RUNNING', bank_state='UNFUNDED'))

    def test_claim_effect_before_receipt_keeps_lineage(self):
        from world import World
        store = self.store()
        world = World(self.root / 'state/private/world.sqlite3', clock=lambda: 1000); world.bootstrap()
        world.apply('mission',dict(op='create_mission',mission_id='CAUSAL',goal='Useful work'))
        task=dict(id='TASK-000000006000',type='TOOL',action='WORLD',args=dict(op='claim_mission',mission_id='CAUSAL',agent_id='BUILDER',lease_seconds=300))
        cause=dict(root_id='a'*64,parent_turn='THINK-1000',depth=1)
        store.bind_task(task,turn='THINK-1000',cause=cause,origin='broker')
        result=world.apply(task['id'],task['args'],actor='BUILDER')
        self.assertEqual(world.operation_result(task['id']),result)
        self.assertIsNone(world.operation_result('absent'))
        # Crash before any supervisor result journal: the exact WORLD receipt is
        # the sole evidence connecting this new lease to its admitted cause.
        store=self.store();store.reconcile(world.snapshot(),now=1001)
        event=next(e for e in store.events(kind='LEASE_DUE') if e['key']=='CAUSAL')
        self.assertEqual(event['cause'],cause)

    def test_decision_and_push_before_ack_recover_exact_frozen_coverage(self):
        store=self.store();self.signal('visible');self.signal('not-in-prompt')
        store.reconcile(dict(missions=[]),now=1000)
        wake=store.claim('wake',now=1001,world_state='ACTIVE',bank_state='UNFUNDED')
        event=wake['events'][0]
        coverage=[dict(kind=event['kind'],key=event['key'],version=event['version'],representation='AGGREGATE_COUNTER')]
        store.start(wake['wake_id'],prepared=dict(context={'safe':1},assessment={},coverage=coverage,excluded=[]),now=1001)
        directory=self.root/'state/controller';directory.mkdir()
        path=directory/(wake['turn']+'.json')
        saved=dict(published=False,lineage=wake['cause'],files={},decision=dict(summary='No action',actions=[]))
        path.write_text(json.dumps(saved))
        recovered=self.store().recover(now=1002)
        self.assertEqual(len(recovered),1);self.assertEqual(recovered[0]['turn'],wake['turn'])
        self.assertEqual(recovered[0]['phase'],'DECISION_READY')
        store.finish(wake['wake_id'],turn='THINK-999',now=1002)
        self.assertEqual(store.events(status='ACKED'),[])
        saved['published']=True;path.write_text(json.dumps(saved))
        # A crash after push but before ACK is repaired locally, once, with no
        # publication or inference call and without acknowledging omitted input.
        self.assertEqual(self.store().recover(now=1003),[])
        self.assertEqual([e['id'] for e in store.events(status='ACKED')],[event['id']])
        self.assertEqual(len(store.events(status='PENDING')),1)

    def test_missing_or_ineligible_sources_cannot_repeat_invisible_turns(self):
        store=self.store();key,_=self.signal('deleted')
        store.reconcile(dict(missions=[]),now=1000)
        (self.root/'state/private/agentmail'/(key+'.json')).unlink()
        self.assertIsNone(store.claim('wake',now=1001,world_state='ACTIVE',bank_state='UNFUNDED'))
        self.assertEqual(len(store.events(status='OBSOLETE')),1)

    def test_configured_higher_chain_depth_preserves_parent(self):
        self.config['initiative']['max_chain_depth']=3
        store=self.store();task=dict(id='TASK-000000007000',type='TOOL',action='EXEC',args={})
        cause=dict(root_id='b'*64,parent_turn='THINK-900',depth=2)
        store.bind_task(task,turn='THINK-900',cause=cause,origin='queued')
        self.result(7000)
        store.reconcile(dict(missions=[]),now=1000)
        wake=self.store().claim('wake',now=1001,world_state='ACTIVE',bank_state='UNFUNDED')
        self.assertEqual(wake['cause']['depth'],3)
        self.assertEqual(wake['cause']['root_id'],cause['root_id'])
        self.assertEqual(wake['parents'],[cause])

    def test_source_commit_before_insert_and_storage_loss_fail_closed(self):
        import initiative
        store=self.store();self.signal('committed-source')
        original=store._insert
        with patch.object(store,'_insert',side_effect=RuntimeError('crash before insertion')):
            with self.assertRaises(RuntimeError):store.reconcile(dict(missions=[]),now=1000)
        self.assertEqual(store.events(),[])
        store=self.store();store.reconcile(dict(missions=[]),now=1001)
        self.assertEqual(len(store.events()),1)
        store.path.unlink()
        with self.assertRaisesRegex(ValueError,'^Initiative storage unavailable$'):self.store()

    def test_existing_world_float_leases_and_valid_mission_ids_are_preserved(self):
        from world import World
        world=World(self.root/'state/private/world.sqlite3',clock=lambda:1000.25);world.bootstrap()
        world.apply('create',dict(op='create_mission',mission_id='VALID.MISSION:1',goal='Work'))
        world.apply('claim',dict(op='claim_mission',mission_id='VALID.MISSION:1',agent_id='BUILDER',lease_seconds=600))
        store=self.store();store.reconcile(world.snapshot(),now=1001)
        event=next(e for e in store.events(kind='LEASE_DUE') if e['key']=='VALID.MISSION:1')
        self.assertEqual(event['not_before'],1301)
        self.assertEqual(type(event['not_before']),int)

    def test_retry_source_validation_matches_mailbox_attempts(self):
        import initiative
        source=dict(inbox_id='inbox',message_id='retry',state='RETRY',attempts=0,retry_after=1000)
        with self.assertRaisesRegex(ValueError,'Invalid initiative source'):
            initiative.source_revision('PRIVATE_RETRY_DUE',source)

    def test_reserved_turn_cannot_collide_with_legacy_published_decision(self):
        directory=self.root/'state/controller';directory.mkdir()
        (directory/'THINK-1000.json').write_text(json.dumps(dict(published=True,files={})))
        store=self.store();self.signal('new-source');store.reconcile(dict(missions=[]),now=1000)
        wake=store.claim('wake',now=1000,world_state='ACTIVE',bank_state='UNFUNDED')
        self.assertEqual(wake['turn'],'THINK-1001')


if __name__ == '__main__': unittest.main()
