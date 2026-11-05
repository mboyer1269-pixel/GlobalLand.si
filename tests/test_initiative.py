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


def admission_record(number, *, phase='ACKED'):
    import initiative
    context=dict(archive_text='retained context '*128,record=number)
    prepared=dict(context=context,assessment={},coverage=[],excluded=[])
    return dict(schema=1,wake_id=initiative.digest(['archive-receipt',number]),trigger='think',
                target='DIRECTOR',turn='THINK-'+str(number),cause=dict(root_id='c'*64,parent_turn=None,depth=0),
                event_ids=[],events=[],parents=[],coverage=[],context_digest=initiative.digest(context),
                prepared=prepared,phase=phase,started_at=number,finished_at=number if phase=='ACKED' else None,
                reason='EXACT_COVERAGE' if phase=='ACKED' else 'PROVIDER_START')


def seed_admission_archive(store, count=1001):
    ids=[]
    with store._db() as db:
        for number in range(1,count+1):
            receipt=admission_record(number);store._save_admission(db,receipt);ids.append(receipt['wake_id'])
    return set(ids)


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
    def test_large_legacy_result_wakes_once_and_remains_current(self):
        store=self.store()
        ident,record=self.result(6543,output='123 tests passed')
        record['files']={'products/a.txt':'a'*600000,'products/b.txt':'b'*600000}
        (self.root/'state'/(ident+'.json')).write_text(json.dumps(record))
        store.recorded_result(ident,now=1000)
        store.reconcile(dict(missions=[]),now=1001)
        events=store.events(kind='QUEUED_RESULT')
        self.assertEqual(len(events),1)
        with store._db() as db:self.assertTrue(store._current(db,events[0]))
        from result_envelope import write_result_envelope
        write_result_envelope(self.root,record)
        store.reconcile(dict(missions=[]),now=1002)
        self.assertEqual(len(store.events(kind='QUEUED_RESULT')),1)

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

    def test_bootstrap_crash_preserves_activation_inventory(self):
        import initiative
        import sqlite3
        original_root=self.root
        for phase in ('after_file','after_schema','partial_baseline'):
            with self.subTest(phase=phase):
                self.root=original_root/phase;(self.root/'state/private/agentmail').mkdir(parents=True)
                for n in range(3):self.signal('historical-%d'%n)
                connect=sqlite3.connect;inserts=0
                class InterruptedConnection:
                    def __init__(inner,*args,**kwargs):
                        inner.connection=connect(*args,**kwargs)
                        if phase=='after_file':
                            inner.connection.close();raise KeyboardInterrupt('bootstrap after file')
                    def __getattr__(inner,name):return getattr(inner.connection,name)
                    def executescript(inner,sql):
                        result=inner.connection.executescript(sql)
                        if phase=='after_schema':raise KeyboardInterrupt('bootstrap after schema')
                        return result
                    def execute(inner,sql,*args):
                        nonlocal inserts
                        result=inner.connection.execute(sql,*args)
                        if phase=='after_schema' and sql.strip().startswith('CREATE TABLE processed'):
                            raise KeyboardInterrupt('bootstrap after schema')
                        if sql.startswith('INSERT OR IGNORE INTO baseline'):
                            inserts+=1
                            if phase=='partial_baseline' and inserts==2:
                                raise KeyboardInterrupt('bootstrap partial baseline')
                        return result
                with patch('initiative.sqlite3.connect',side_effect=InterruptedConnection):
                    with self.assertRaises(KeyboardInterrupt):self.store()
                self.assertTrue((self.root/'state/private/initiative.sqlite3').exists())
                self.assertFalse((self.root/'state/private/initiative.initialized').exists())
                key,_=self.signal('post-boundary-arrival')
                store=self.store();store.reconcile(dict(missions=[]),now=1000)
                self.assertEqual(len(store.events(status='BASELINED')),3)
                self.assertFalse(store.events(status='ACKED'))
                wake=store.claim('wake',now=1001,world_state='ACTIVE',bank_state='UNFUNDED')
                self.assertEqual([e['key'] for e in wake['events']],[key])
        self.root=original_root

    def seed_pending_results(self,store,count):
        # These are real source journals and the same canonical host insertion
        # used by committed-source callbacks; no validation/read path is faked.
        with store._db() as db:
            for n in range(count):
                _,source=self.result(20000+n)
                store._insert(db,'QUEUED_RESULT',source,1000)

    def test_claim_source_reads_are_bounded_before_batch_selection(self):
        self.config['initiative'].update(scan_page_size=2,batch_size=1)
        store=self.store();self.seed_pending_results(store,501)
        with patch.object(store,'_current',wraps=store._current) as current,patch.object(store,'_read',wraps=store._read) as read:
            wake=store.claim('wake',now=1001,world_state='ACTIVE',bank_state='UNFUNDED')
        self.assertEqual(len(wake['events']),1)
        self.assertLessEqual(current.call_count,2)
        self.assertLessEqual(read.call_count,2)

    def test_throttled_claim_does_not_read_pending_sources(self):
        self.config['initiative'].update(scan_page_size=2,batch_size=1)
        store=self.store()
        periodic=store.claim('think',now=1000,world_state='ACTIVE',bank_state='UNFUNDED')
        store.start(periodic['wake_id'],prepared=dict(context={},assessment={},coverage=[],excluded=[]),now=1000)
        self.seed_pending_results(store,501)
        with patch.object(store,'_current',wraps=store._current) as current,patch.object(store,'_read',wraps=store._read) as read:
            self.assertIsNone(store.claim('wake',now=1001,world_state='ACTIVE',bank_state='UNFUNDED'))
        self.assertEqual(current.call_count,0);self.assertEqual(read.call_count,0)

    def test_private_claim_does_not_read_director_backlog(self):
        self.config['initiative'].update(scan_page_size=2,batch_size=1)
        store=self.store();self.seed_pending_results(store,501)
        source=dict(inbox_id='inbox',message_id='retry',state='RETRY',attempts=1,retry_after=1000)
        key=hashlib.sha256(b'inbox\0retry').hexdigest()
        (self.root/'state/private/agentmail'/(key+'.json')).write_text(json.dumps(source))
        with store._db() as db:store._insert(db,'PRIVATE_RETRY_DUE',source,1000)
        with patch.object(store,'_current',wraps=store._current) as current,patch.object(store,'_read',wraps=store._read) as read:
            wake=store.claim('mail',now=1001,world_state='ACTIVE',bank_state='UNFUNDED')
        self.assertEqual(wake['target'],'PRIVATE_MAIL')
        self.assertEqual([e['key'] for e in wake['events']],[key])
        self.assertLessEqual(current.call_count,2);self.assertLessEqual(read.call_count,2)
        self.assertTrue(all('TASK-' not in str(call.args[0]) for call in read.call_args_list))

    def test_bounded_stale_candidates_make_durable_progress(self):
        self.config['initiative'].update(scan_page_size=2,batch_size=1)
        store=self.store();self.seed_pending_results(store,5)
        for n in range(4):(self.root/'state'/('TASK-%012d.json'%(20000+n))).unlink()
        wake=None
        for now in range(1001,1004):
            store=self.store()
            with patch.object(store,'_current',wraps=store._current) as current:
                wake=store.claim('wake',now=now,world_state='ACTIVE',bank_state='UNFUNDED')
            self.assertLessEqual(current.call_count,2)
            if wake:break
        self.assertIsNotNone(wake)
        self.assertEqual([e['key'] for e in wake['events']],['TASK-000000020004'])
        self.assertEqual(len(store.events(status='OBSOLETE')),4)

    def test_small_batches_fairly_admit_old_classes_across_restart(self):
        original_root=self.root
        for batch in (1,2):
            with self.subTest(batch=batch):
                self.root=original_root/str(batch);(self.root/'state/private/agentmail').mkdir(parents=True)
                self.config['initiative'].update(scan_page_size=2,batch_size=batch,director_spacing_seconds=1)
                store=self.store();self.seed_pending_results(store,3)
                mission=dict(mission_id='OLD-LEASE',status='RUNNING',agent_id='BUILDER',lease_token='private-lease',lease_expires_at=1000)
                with store._db() as db:store._insert(db,'LEASE_DUE',mission,1000)
                admitted=[]
                for turn in range(3):
                    store=self.store()
                    _,signal=self.signal('new-commercial-%d'%turn)
                    _,result=self.result(30000+turn)
                    with store._db() as db:
                        store._insert(db,'COMMERCIAL_SIGNAL',signal,1000+turn)
                        store._insert(db,'QUEUED_RESULT',result,1000+turn)
                    wake=store.claim('wake',now=1001+turn,world_state='ACTIVE',bank_state='UNFUNDED')
                    admitted.extend(e['kind'] for e in wake['events'])
                    coverage=[dict(kind=e['kind'],key=e['key'],version=e['version'],representation='STATUS_ONLY') for e in wake['events']]
                    store.start(wake['wake_id'],prepared=dict(context={},assessment={},coverage=coverage,excluded=[]),now=1001+turn)
                    directory=self.root/'state/controller';directory.mkdir(exist_ok=True)
                    (directory/(wake['turn']+'.json')).write_text(json.dumps(dict(published=True,lineage=wake['cause'],files={})))
                    store.finish(wake['wake_id'],turn=wake['turn'],now=1001+turn)
                self.assertIn('QUEUED_RESULT',admitted)
                self.assertIn('LEASE_DUE',admitted)
        self.root=original_root

    def test_recovery_does_not_deserialize_or_hash_terminal_archive(self):
        import initiative
        store=self.store();history=seed_admission_archive(store)
        with patch.object(store,'_receipt',wraps=store._receipt) as validate,patch('initiative.digest',wraps=initiative.digest) as hashed:
            self.assertEqual(store.recover(now=10000),[])
        self.assertEqual(validate.call_count,0);self.assertEqual(hashed.call_count,0)
        with store._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM admissions').fetchone()[0],1001)
        self.assertEqual(store.admission(next(iter(history)))['phase'],'ACKED')

    def test_claim_and_exact_turn_do_not_walk_terminal_history(self):
        import initiative
        store=self.store();seed_admission_archive(store)
        active=store.claim('think',now=10000,world_state='ACTIVE',bank_state='UNFUNDED')
        store.start(active['wake_id'],prepared=dict(context={},assessment={},coverage=[],excluded=[]),now=10000)
        with patch.object(store,'_receipt',wraps=store._receipt) as validate:
            self.assertEqual(store.turn_cause(active['turn']),active['cause'])
        self.assertEqual(validate.call_count,1)
        with patch.object(store,'_receipt',wraps=store._receipt) as validate,patch('initiative.digest',wraps=initiative.digest) as hashed:
            self.assertIsNone(store.turn_cause('THINK-1'))
            self.assertIsNone(store.turn_cause('THINK-9999999999'))
            self.assertIsNone(store.claim('wake',now=10001,world_state='ACTIVE',bank_state='UNFUNDED'))
        self.assertEqual(validate.call_count,0);self.assertEqual(hashed.call_count,0)

    def test_reopen_skips_full_integrity_scan_but_explicit_check_remains(self):
        import sqlite3
        store=self.store();seed_admission_archive(store)
        statements=[];connect=sqlite3.connect
        def traced(*args,**kwargs):
            db=connect(*args,**kwargs);db.set_trace_callback(statements.append);return db
        with patch('initiative.sqlite3.connect',side_effect=traced):self.store()
        self.assertFalse(any('quick_check' in sql.lower() or 'integrity_check' in sql.lower() for sql in statements))
        statements.clear()
        with patch('initiative.sqlite3.connect',side_effect=traced):store.check_integrity()
        self.assertTrue(any('quick_check' in sql.lower() or 'integrity_check' in sql.lower() for sql in statements))

    def test_active_recovery_pages_make_progress_across_restart(self):
        store=self.store();seed_admission_archive(store)
        self.config['initiative']['scan_page_size']=2
        active=[]
        with store._db() as db:
            for number in range(20000,20005):
                receipt=admission_record(number,phase='CLAIMED')
                receipt.update(started_at=None,context_digest=None,prepared=None)
                store._save_admission(db,receipt);active.append(receipt['wake_id'])
        seen=set()
        for now in range(30000,30003):
            store=self.store()
            with patch.object(store,'_receipt',wraps=store._receipt) as validate:
                page=store.recover(now=now)
            self.assertLessEqual(validate.call_count,2)
            self.assertLessEqual(len(page),2);seen.update(r['wake_id'] for r in page)
        self.assertEqual(seen,set(active))
        with store._db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM admissions').fetchone()[0],1006)

    def test_corrupt_active_context_and_explicit_archive_check_fail_closed(self):
        store=self.store();seed_admission_archive(store,3)
        bad=admission_record(20000,phase='STARTED');bad['context_digest']='0'*64
        with store._db() as db:store._save_admission(db,bad)
        with self.assertRaisesRegex(ValueError,'^Initiative storage unavailable$'):store.recover(now=30000)
        # Logical corruption in terminal history is checked deliberately rather
        # than reparsing every historical prompt during each idle probe.
        bad.update(phase='ACKED',finished_at=20000)
        with store._db() as db:store._save_admission(db,bad)
        self.assertEqual(store.recover(now=30001),[])
        with self.assertRaisesRegex(ValueError,'^Initiative storage unavailable$'):store.check_integrity()

    def test_actual_schema_and_storage_errors_still_fail_closed(self):
        store=self.store()
        with store._db() as db:store._put(db,'schema',2)
        with self.assertRaisesRegex(ValueError,'^Initiative storage unavailable$'):self.store()
        store.path.write_bytes(b'not a sqlite database')
        with self.assertRaisesRegex(ValueError,'^Initiative storage unavailable$'):self.store()


if __name__ == '__main__': unittest.main()
