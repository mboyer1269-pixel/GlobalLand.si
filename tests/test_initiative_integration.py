"""Fault injection at private effects, admission and publication boundaries."""
import copy
import hashlib
import inspect
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from test_initiative import Fixture, POSIX, seed_admission_archive


class Client:
    def __init__(self): self.messages={}; self.posts=0
    def add(self, mid, *, ignored=False):
        self.messages[mid]=dict(message_id=mid,inbox_id='inbox',labels=['received'],
            **{'from':'Robot <robot@example.test>' if ignored else 'Person <person@example.test>'},
            text='PRIVATE MESSAGE', **({'headers':{'Auto-Submitted':'auto-generated'}} if ignored else {}))
    def list_received(self):return [dict(message_id=mid) for mid in self.messages]
    def get_message(self,mid):return copy.deepcopy(self.messages[mid])
    def reply(self,*args,**kwargs):self.posts+=1;return dict(message_id='outbound',thread_id='thread')


class PrivateReceiptTests(Fixture):
    def box(self, client):
        from mail import Mailbox
        return Mailbox(self.root,self.config,client)

    def retry(self,mid, *, due=10):
        import initiative
        key=hashlib.sha256(('inbox\0'+mid).encode()).hexdigest()
        source=dict(inbox_id='inbox',message_id=mid,state='RETRY',attempts=1,retry_after=due)
        path=self.root/'state/private/agentmail'/(key+'.json')
        path.write_text(json.dumps(source))
        return key,initiative.source_revision('PRIVATE_RETRY_DUE',source)[1]

    def test_callback_contract_is_host_optional(self):
        from mail import Mailbox
        self.assertIn('on_processed',inspect.signature(Mailbox.cycle).parameters)

    def test_private_pass_receipts_match_selected_revisions(self):
        import initiative
        client=Client();self.config['agentmail']['max_messages_per_cycle']=3
        old={}
        for n in range(7):
            mid='old-%d'%n;client.add(mid,ignored=True);key,version=self.retry(mid);old[key]=version
        for n in range(4):client.add('fresh-%d'%n,ignored=True)
        store=initiative.Store(self.root,self.config);store.reconcile(dict(missions=[]),now=1000)
        wake=store.claim('wake',now=1001,world_state='ACTIVE',bank_state='UNFUNDED')
        self.assertEqual(wake['target'],'PRIVATE_MAIL')
        store.start(wake['wake_id'],prepared=None,now=1001);receipts=[]
        def processed(receipt):receipts.append(receipt);store.processed(wake['wake_id'],receipt)
        with patch('mail.time.time',return_value=1001):
            result=self.box(client).cycle(lambda _:self.fail('ignored mail must not invoke responder'),on_processed=processed)
        self.assertEqual(result['ignored'],3);self.assertEqual(len(receipts),3)
        self.assertTrue(any(r['before_version'] is None for r in receipts))
        consumed=[r for r in receipts if r['before_version'] is not None]
        self.assertTrue(consumed)
        self.assertTrue(all(old[r['key']]==r['before_version'] for r in consumed))
        store.finish(wake['wake_id'],turn=None,now=1002)
        self.assertEqual(len(store.events(status='ACKED')),len(consumed))
        self.assertEqual(len(store.events(status='PENDING')),7-len(consumed))
        self.assertEqual(client.posts,0)

    @unittest.skipUnless(POSIX,'private controller imports real POSIX supervisor')
    def test_processed_callback_failure_cannot_downgrade_accepted(self):
        client=Client();client.add('one');box=self.box(client)
        def fail(_):raise RuntimeError('callback crash')
        first=box.cycle(lambda _:dict(action='reply',text='answer'),on_processed=fail)
        self.assertEqual(first['accepted'],1)
        path=box._path('one');self.assertEqual(json.loads(path.read_text())['state'],'ACCEPTED')
        box.cycle(lambda _:self.fail('accepted effect cannot replay'),on_processed=fail)
        self.assertEqual(client.posts,1)
        self.assertEqual(json.loads(path.read_text())['state'],'ACCEPTED')

    @unittest.skipUnless(POSIX,'private controller imports real POSIX supervisor')
    def test_retry_successors_deferred_and_unsaved_attempts(self):
        import initiative
        client=Client();client.add('one');self.retry('one');box=self.box(client)
        receipts=[]
        with patch('mail.time.time',return_value=1000):
            box.cycle(lambda _:(_ for _ in ()).throw(ValueError('pre-send failure')),on_processed=receipts.append)
        self.assertEqual(len(receipts),1)
        self.assertEqual(receipts[0]['disposition'],'REPLACED')
        self.assertNotEqual(receipts[0]['before_version'],receipts[0]['after_version'])
        source=json.loads(box._path('one').read_text())
        self.assertEqual(source['retry_after'],1120)
        self.assertEqual(initiative.source_revision('PRIVATE_RETRY_DUE',source)[1],receipts[0]['after_version'])
        receipts.clear()
        class Deferred(ValueError):private_deferred=True;progressed=False
        with patch('mail.time.time',return_value=1200):
            box.cycle(lambda _:(_ for _ in ()).throw(Deferred()),on_processed=receipts.append)
        self.assertEqual(receipts,[])
        save=box._save
        def unsaved(path,data):
            if path.suffix=='.json':raise OSError('journal save failed')
            return save(path,data)
        with patch.object(box,'_save',side_effect=unsaved),patch('mail.time.time',return_value=1200):
            box.cycle(lambda _:dict(action='ignore',text=''),on_processed=receipts.append)
        self.assertEqual(receipts,[])

    def test_callback_loss_recovers_without_a_private_send(self):
        import initiative
        client=Client();client.add('one',ignored=True);key,version=self.retry('one')
        store=initiative.Store(self.root,self.config);store.reconcile(dict(missions=[]),now=1000)
        wake=store.claim('wake',now=1001,world_state='ACTIVE',bank_state='UNFUNDED')
        store.start(wake['wake_id'],prepared=None,now=1001)
        with patch('mail.time.time',return_value=1001):
            self.box(client).cycle(lambda _:self.fail('no responder'),on_processed=lambda _:(_ for _ in ()).throw(RuntimeError('lost callback')))
        self.assertEqual(store.recover(now=1002),[])
        self.assertEqual(len(store.events(status='ACKED')),1)
        self.assertEqual(client.posts,0)

    def test_held_sources_emit_no_receipt_or_consumption(self):
        client=Client();client.add('held',ignored=True);self.retry('held')
        client.messages['held']['labels'].append('agent-armor-held')
        receipts=[]
        with patch('mail.time.time',return_value=1000):
            result=self.box(client).cycle(lambda _:self.fail('held body must not reach responder'),on_processed=receipts.append)
        self.assertEqual(receipts,[]);self.assertEqual(result['processed'],0)
        self.assertEqual(self.box(client)._read(self.box(client)._path('held'))['state'],'RETRY')


@unittest.skipUnless(POSIX,'supervisor requires real POSIX locking')
class SupervisorAdmissionTests(Fixture):
    def app(self):
        from supervisor import Supervisor
        from world import World
        from treasury import Treasury
        app=Supervisor(self.root);(self.root/'control').mkdir(exist_ok=True)
        (self.root/'control/config.json').write_text(json.dumps(self.config))
        world=World(self.root/'state/private/world.sqlite3');world.bootstrap()
        bank=Treasury(self.root/'state/private/treasury.sqlite3')
        return app,world,bank

    def test_idle_and_busy_wake_make_no_external_calls(self):
        from supervisor import main
        app,world,bank=self.app()
        with patch.object(app,'git',side_effect=AssertionError('idle Git')),patch('gateway.Gateway.sync',side_effect=AssertionError('idle finance')),patch('controller.Controller.plan',side_effect=AssertionError('idle provider')),patch('mail_agent.run_mail_cycle',side_effect=AssertionError('idle mailbox')):
            self.assertEqual(app.dispatch('wake',now=1000)['state'],'IDLE')
        import fcntl
        with (self.root/'state/supervisor.lock').open('a') as held:
            fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with patch('supervisor.ROOT',self.root),patch('supervisor.sys.argv',['supervisor.py','wake']),patch('supervisor.Supervisor',side_effect=AssertionError('busy initialization')):
                self.assertEqual(main()['state'],'BUSY')

    def test_idle_and_throttled_dispatch_ignore_completed_context_archive(self):
        import initiative
        import sqlite3
        app,_,_=self.app();store=initiative.Store(self.root,self.config)
        history=seed_admission_archive(store)
        statements=[];connect=sqlite3.connect;receipt=initiative.Store._receipt
        def traced(*args,**kwargs):
            db=connect(*args,**kwargs);db.set_trace_callback(statements.append);return db
        def checked(raw):
            self.assertFalse(json.loads(raw)['wake_id'] in history,'terminal archive was deserialized')
            return receipt(raw)
        with patch('initiative.sqlite3.connect',side_effect=traced),patch.object(initiative.Store,'_receipt',side_effect=checked),patch.object(app,'git',side_effect=AssertionError('idle network')):
            self.assertEqual(app.dispatch('wake',now=10000)['state'],'IDLE')
        active=store.claim('think',now=10000,world_state='ACTIVE',bank_state='UNFUNDED')
        store.start(active['wake_id'],prepared=dict(context={},assessment={},coverage=[],excluded=[]),now=10000)
        with patch('initiative.sqlite3.connect',side_effect=traced),patch.object(initiative.Store,'_receipt',side_effect=checked),patch.object(app,'git',side_effect=AssertionError('throttled network')):
            self.assertEqual(app.dispatch('wake',now=10001)['state'],'IDLE')
        self.assertFalse(any('quick_check' in sql.lower() or 'integrity_check' in sql.lower() for sql in statements))

    def test_periodic_and_wake_share_single_admission(self):
        import initiative
        app,world,bank=self.app();initiative.Store(self.root,self.config);self.signal('wake')
        calls=[]
        def cycle(mode,**kwargs):
            if mode!='think' or not kwargs.get('productive',True):return {}
            admission=kwargs['admission'];store=kwargs['store'];calls.append(mode)
            store.start(admission['wake_id'],prepared=dict(context={},assessment={},coverage=[],excluded=[]),now=1001)
            return {}
        with patch.object(app,'_cycle',side_effect=cycle):
            app.dispatch('wake',now=1001)
            app.dispatch('think',now=1001)
        self.assertEqual(calls,['think'])

    def test_broker_effect_before_decision_never_reinfers_wake(self):
        import initiative
        app,world,bank=self.app();store=initiative.Store(self.root,self.config);self.signal('wake')
        store.reconcile(world.snapshot(),now=1000)
        admission=store.claim('wake',now=1001,world_state='ACTIVE',bank_state='UNFUNDED')
        store.start(admission['wake_id'],prepared=dict(context={},assessment={},coverage=[],excluded=[]),now=1001)
        counter=self.root/'effect';counter.write_text('1')  # effect committed, no decision
        with patch.object(app,'_cycle',side_effect=AssertionError('uncertain inference replay')):
            self.assertEqual(app.dispatch('wake',now=2000)['state'],'IDLE')
        self.assertEqual(counter.read_text(),'1')
        self.assertEqual(store.admission(admission['wake_id'])['phase'],'INTERRUPTED')

    def test_legacy_callers_respect_both_stop_stores(self):
        app,world,bank=self.app()
        for state in ('HALTED','EXTINCT'):
            for where in ('world','bank'):
                for mode in ('mail','queue','think','wake'):
                    with self.subTest(state=state,where=where,mode=mode):
                        ws=dict(state=state if where=='world' else 'ACTIVE',missions=[])
                        bs=dict(state=state if where=='bank' else 'UNFUNDED')
                        with patch.object(world,'snapshot',return_value=ws),patch.object(bank,'snapshot',return_value=bs),patch.object(app,'services',return_value=(world,bank,self.config)),patch.object(app,'_cycle',return_value={}) as phase:
                            app.dispatch(mode,now=1000)
                            for call in phase.call_args_list:self.assertFalse(call.kwargs.get('productive',True))


@unittest.skipUnless(POSIX,'local Git supervisor integration needs POSIX')
class InstalledEventIntegration(unittest.TestCase):
    def setUp(self):
        import test_autonomous_integration as fixtures
        fixtures.AutonomousIntegration.setUp(self)
        from test_initiative import CONFIG
        import initiative
        self.config=copy.deepcopy(CONFIG)
        (self.install/'control/config.json').write_text(json.dumps(self.config))
        self.store=initiative.Store(self.install,self.config)
        directory=self.install/'state/private/agentmail';directory.mkdir(exist_ok=True)
        observation=dict(category='PRICE_QUESTION',audience='ORDINARY',experiment_id=None,
            evidence=dict(field='text',quote='PRIVATE QUOTE'),origin='INBOUND_UNVERIFIED',
            attribution='UNATTRIBUTED',provider='claude',observed_at='2026-11-05T00:00:00Z')
        key=hashlib.sha256(b'inbox\0source').hexdigest()
        (directory/(key+'.json')).write_text(json.dumps(dict(state='ACCEPTED',inbox_id='inbox',message_id='source',observation=observation)))

    def run(self,args=None,result=None):
        if not isinstance(args,list):return super().run(args if args is not None else result)
        import subprocess
        return subprocess.run(args,check=True,capture_output=True).stdout

    def git(self,*args):return self.run(['git','-C',str(self.seed),'-c','user.name=Test','-c','user.email=test@local',*args])

    def test_enabled_wake_publishes_runs_queue_and_does_not_feedback(self):
        from controller import Controller
        calls=[]
        def plan(planner,provider,prompt):
            calls.append(prompt)
            return dict(summary='Observed an unverified inquiry; create useful work.',actions=[
                dict(agent='DIRECTOR',action='WORLD',args=dict(op='create_mission',mission_id='FROM-EVENT',goal='Make useful work'))])
        with patch.object(Controller,'plan',plan):report=self.app.dispatch('wake',now=1800000000)
        self.assertEqual(report['target'],'DIRECTOR');self.assertEqual(len(calls),1)
        world,_,_=self.app.services()
        self.assertTrue(any(m['mission_id']=='FROM-EVENT' for m in world.snapshot()['missions']))
        admission=self.store.admission(report['wake_id'])
        self.assertEqual(admission['phase'],'ACKED')
        self.assertEqual(len(self.store.events(status='ACKED')),1)
        result=self.store.events(kind='QUEUED_RESULT')[0]
        self.assertEqual(result['cause']['depth'],1)
        self.assertEqual(result['cause']['root_id'],admission['cause']['root_id'])
        with patch.object(self.app,'git',side_effect=AssertionError('depth-limited idle Git')),patch.object(Controller,'plan',side_effect=AssertionError('feedback inference')):
            self.assertEqual(self.app.dispatch('wake',now=1800000400)['state'],'IDLE')
        self.assertNotIn('PRIVATE QUOTE',calls[0])

    def test_real_broker_effect_before_decision_is_never_reinferred(self):
        from controller import Controller
        effects=[]
        def interrupted(planner,provider,prompt):
            task=dict(id='TASK-180000000099',type='TOOL',submitted_by='DIRECTOR',
                      created_at='2027-01-15T08:00:00Z',action='WORLD',args=dict(op='create_mission',mission_id='BROKER-EFFECT',goal='Committed effect'),estimated_cost_cad=0,approved_by=None)
            effects.append(planner.executor(task));raise KeyboardInterrupt()
        with patch.object(Controller,'plan',interrupted):
            with self.assertRaises(KeyboardInterrupt):self.app.dispatch('wake',now=1800000000)
        self.assertEqual(len(effects),1)
        with patch.object(Controller,'plan',side_effect=AssertionError('uncertain turn replay')),patch.object(self.app,'git',side_effect=AssertionError('idle publication')):
            self.assertEqual(self.app.dispatch('wake',now=1800000400)['state'],'IDLE')
        admissions=[e for e in self.store.events() if e['kind']=='COMMERCIAL_SIGNAL']
        self.assertTrue(admissions[0]['periodic_only'])

    def test_disabled_new_ordinary_feedback_survives_without_finance_output(self):
        import test_autonomous_integration as fixtures
        from controller import Controller
        self.config['initiative']['enabled']=False
        (self.install/'control/config.json').write_text(json.dumps(self.config))
        ordinary=fixtures.AutonomousIntegration.submit(self,9200,'FETCH',dict(url='https://example.test',output='products/proof.txt'))
        financial=fixtures.AutonomousIntegration.submit(self,9201,'SPEND',dict(request=dict(purpose='request is private')))
        def tool(box,task):
            output='ordinary safe result' if task['action']=='FETCH' else 'FINANCE_OUTPUT_PRIVATE_SENTINEL'
            return dict(status='DONE',output=output),{}
        with patch('tools.Toolbox.run',tool):self.app.cycle('queue')
        world,bank,config=self.app.services()
        results=Controller(self.install,world,bank,config).context()['latest_task_results']
        by_id={r['task']:r for r in results}
        self.assertEqual(by_id[ordinary]['output'],'ordinary safe result')
        self.assertFalse(by_id[ordinary]['output_redacted'])
        self.assertEqual(by_id[financial]['output'],'[output redacted]')
        self.assertTrue(by_id[financial]['output_redacted'])
        self.assertNotIn('FINANCE_OUTPUT_PRIVATE_SENTINEL',json.dumps(results))
        for ident,action in ((ordinary,'FETCH'),(financial,'SPEND')):
            saved=json.loads((self.install/'state'/(ident+'.json')).read_text())
            self.assertEqual(saved['metadata'],dict(type='TOOL',action=action))

    def test_controller_broker_reads_exact_active_turn_without_archive_work(self):
        import initiative
        import sqlite3
        from controller import Controller
        history=seed_admission_archive(self.store)
        receipt=initiative.Store._receipt;statements=[];connect=sqlite3.connect;effects=[]
        def checked(raw):
            self.assertFalse(json.loads(raw)['wake_id'] in history,'broker loaded terminal archive')
            return receipt(raw)
        def traced(*args,**kwargs):
            db=connect(*args,**kwargs);db.set_trace_callback(statements.append);return db
        def plan(planner,provider,prompt):
            task=dict(id='TASK-180000000099',type='TOOL',submitted_by='DIRECTOR',created_at='2027-01-15T08:00:00Z',
                      action='WORLD',args=dict(op='create_mission',mission_id='EXACT-ACTIVE-TURN',goal='Useful effect'),estimated_cost_cad=0,approved_by=None)
            effects.append(planner.executor(task));return dict(summary='Committed useful work.',actions=[])
        with patch('initiative.sqlite3.connect',side_effect=traced),patch.object(initiative.Store,'_receipt',side_effect=checked),patch.object(Controller,'plan',plan):
            result=self.app.dispatch('wake',now=1800000000)
        self.assertEqual(result['state'],'COMPLETED');self.assertEqual(len(effects),1)
        self.assertEqual(effects[0]['status'],'DONE')
        self.assertFalse(any('quick_check' in sql.lower() or 'integrity_check' in sql.lower() for sql in statements))
        self.assertEqual(self.store.task_cause('TASK-180000000099')['parent_turn'],'THINK-1800000000')


if __name__=='__main__':unittest.main()
