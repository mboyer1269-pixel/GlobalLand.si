import unittest,tempfile,pathlib,sys,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
class ControllerTests(unittest.TestCase):
 def test_missing_configuration_never_claims_thinking(self):
  from controller import Controller
  with tempfile.TemporaryDirectory() as d:
   c=Controller(pathlib.Path(d),None,None,{})
   self.assertEqual(c.readiness()['state'],'WAITING_CONTROLLER')
 def test_subscription_commands_never_include_api_auth_or_worker_mounts(self):
  from controller import brain_command
  root=pathlib.Path('/opt/globalland');image='globalland-brain@sha256:'+'a'*64
  for provider in ['codex','claude']:
   argv=brain_command(root,image,provider)
   text=' '.join(argv);self.assertNotIn('API_KEY',text);self.assertNotIn('/state',text);self.assertNotIn('/ssh',text);self.assertNotIn('/work:',text)
   self.assertIn('--read-only',argv)
  self.assertIn('forced_login_method="chatgpt"',brain_command(root,image,'codex'))
  self.assertIn('--safe-mode',brain_command(root,image,'claude'))
 def test_decisions_create_only_validated_tasks_and_durable_outbox(self):
  from controller import Controller
  from world import World
  from treasury import Treasury
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'state').mkdir();w=World(root/'state/world.sqlite3');w.bootstrap();b=Treasury(root/'state/bank.sqlite3')
   class Fake(Controller):
    calls=0
    def plan(self,provider,prompt):
     self.calls+=1
     return {'summary':'Build global tool','actions':[{'agent':'BUILDER','action':'EXEC','args':{'argv':['node','-p','123'],'outputs':[]}}]}
   c=Fake(root,w,b,{'controller':{'mode':'subscriptions','providers':['codex'],'subscriptions_confirmed':True,'extra_usage_disabled':True,'image':'brain@sha256:'+'1'*64}})
   turn,files=c.tick(now=1800000000);self.assertEqual(len(files),1);task=json.loads(next(iter(files.values())));self.assertEqual(task['action'],'EXEC')
   self.assertEqual(c.tick(now=1800000000),(turn,files));self.assertEqual(c.calls,1)
   b2=Treasury(root/'state/bank2.sqlite3',verifier=lambda r:True);b2.confirm_funding({'provider':'test','account':'world','event_id':'fund','amount_cents':5000,'currency':'CAD','kind':'FUNDING','settled':True});b2.reserve('x',5000,'hash');b2.mark_submitted('x');b2.settle('x',{'provider':'test','account':'world','event_id':'spend','amount_cents':5000,'currency':'CAD','kind':'SPEND','settled':True})
   c.mark_published(turn)
   c.treasury=b2
   with self.assertRaisesRegex(ValueError,'stopped'):c.tick(now=1800000300)
if __name__=='__main__':unittest.main()

class ControllerIsolationTests(unittest.TestCase):
 def test_configured_is_not_auth_verified(self):
  from controller import Controller
  c=Controller('/tmp/example',None,None,{'controller':{'mode':'subscriptions','providers':['codex'],'subscriptions_confirmed':True,'extra_usage_disabled':True,'image':'brain@sha256:'+'a'*64}})
  r=c.readiness();self.assertTrue(r['configured']);self.assertFalse(r['verified']);self.assertEqual(r['state'],'WAITING_SUBSCRIPTION_AUTH')
 def test_unsupported_restrictions_stop_before_auth_or_inference(self):
  from controller import Controller
  from unittest.mock import patch
  c=Controller('/tmp/example',None,None,{'controller':{'mode':'subscriptions','providers':['claude'],'subscriptions_confirmed':True,'extra_usage_disabled':True,'image':'brain@sha256:'+'a'*64}})
  with patch('controller.bounded_run',return_value=(0,b'--tools')) as run,patch('controller.cleanup_brain'):
   with self.assertRaisesRegex(ValueError,'unsupported'):c.check_provider('claude')
   self.assertEqual(run.call_count,1)
 def test_claude_requires_structured_output_not_text_result(self):
  from controller import Controller
  from unittest.mock import patch
  c=Controller('/tmp/example',None,None,{'controller':{'image':'brain@sha256:'+'a'*64}})
  with patch.object(c,'check_provider'),patch('controller.bounded_run',return_value=(0,b'{"result":"success"}')),patch('controller.cleanup_brain'):
   with self.assertRaisesRegex(ValueError,'structured output'):c.plan('claude','test')
 def test_invalid_actions_never_enter_outbox(self):
  from controller import validate_decision
  for value in ({'summary':'x','actions':[],'extra':True},{'summary':'x','actions':[{'agent':'lower','action':'EXEC','args':{}}]}):
   with self.assertRaises(ValueError):validate_decision(value)

class ControllerRecoveryTests(unittest.TestCase):
 def test_bounded_world_context_prioritizes_hidden_due_leases_and_only_covers_visible_ones(self):
  from world import World
  from controller import Controller
  from initiative import source_revision
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'state').mkdir();world=World(root/'state/world.sqlite3');world.bootstrap()
   for n in range(30):
    world.apply('create-'+str(n),dict(op='create_mission',mission_id='DUE-'+str(n),goal='x'*10000),actor='DIRECTOR')
    world.apply('claim-'+str(n),dict(op='claim_mission',mission_id='DUE-'+str(n),agent_id='BUILDER',lease_seconds=600),actor='BUILDER')
   class Bank:
    def snapshot(self):return dict(state='UNFUNDED')
   hidden=world.snapshot()['missions'][-1]
   key,version=source_revision('LEASE_DUE',hidden)
   prepared=Controller(root,world,Bank(),{}).prepare_context(priority=[dict(kind='LEASE_DUE',key=key,version=version)])
   visible=prepared['context']['world']
   self.assertLessEqual(len(json.dumps(visible,ensure_ascii=False).encode()),192*1024)
   self.assertTrue(visible['projection']['truncated'])
   self.assertIn(key,{m['mission_id'] for m in visible['missions']})
   represented={source_revision('LEASE_DUE',m) for m in visible['missions'] if m.get('status')=='RUNNING'}
   covered={(c['key'],c['version']) for c in prepared['coverage'] if c['kind']=='LEASE_DUE'}
   self.assertEqual(covered,represented)
   self.assertLess(len(covered),30)
 def test_large_legacy_journal_keeps_classified_feedback_without_loading_blobs(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'state').mkdir();(root/'work/queue/done').mkdir(parents=True)
   ident='TASK-180000000000'
   record=dict(id=ident,hash='a'*64,state='PUBLISHED',origin='queued',
    metadata=dict(type='TOOL',action='EXEC'),result=dict(status='DONE',output='123 tests passed'),
    files={'products/a.txt':'a'*600000,'products/b.txt':'b'*600000})
   journal=root/'state'/(ident+'.json');journal.write_text(json.dumps(record))
   (root/'work/queue/done'/(ident+'.result.json')).write_text(json.dumps(record['result']))
   original=pathlib.Path.read_bytes
   def bounded_read(path):
    self.assertNotEqual(path,journal,'large artifact journal must be streamed')
    return original(path)
   with patch.object(pathlib.Path,'read_bytes',bounded_read):
    results,coverage,_=self.controller(root).recent_results()
   self.assertEqual(len(results),1)
   self.assertEqual(results[0]['output'],'123 tests passed')
   self.assertFalse(results[0]['output_redacted'])
   self.assertEqual(len(coverage),1)
 def controller(self,root):
  from controller import Controller
  class Snapshot:
   def snapshot(self):return {'state':'UNFUNDED'}
  class Fake(Controller):
   calls=0
   def plan(self,provider,prompt):
    self.calls+=1;return {'summary':'status','actions':[{'agent':'DIRECTOR','action':'STATUS','args':{}}]}
  return Fake(root,Snapshot(),Snapshot(),{'controller':{'mode':'subscriptions','providers':['claude'],'subscriptions_confirmed':True,'extra_usage_disabled':True,'image':'brain@sha256:'+'a'*64}})
 def test_unacknowledged_old_turn_replays_then_ack_allows_new(self):
  with tempfile.TemporaryDirectory() as d:
   c=self.controller(pathlib.Path(d));first=c.tick(1800000000)
   self.assertEqual(c.tick(1800000300),first);self.assertEqual(c.calls,1)
   c.mark_published(first[0]);self.assertNotEqual(c.tick(1800000300)[0],first[0]);self.assertEqual(c.calls,2)
 def test_context_handles_actual_journal_path_and_deduplicates(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);c=self.controller(root);(root/'state').mkdir();(root/'work/queue/done').mkdir(parents=True)
   task={'id':'TASK-180000000000','type':'TOOL','submitted_by':'BUILDER','created_at':'2026-11-05T00:00:00Z','action':'EXEC','args':{'argv':['node','-p','1'],'outputs':[]},'estimated_cost_cad':0,'approved_by':None}
   raw=json.dumps(task).encode()
   import hashlib
   record={'task':'queue/inbox/TASK-180000000000.json','hash':hashlib.sha256(raw).hexdigest(),'result':{'status':'DONE','output':'real journal result'}}
   (root/'work/queue/inbox').mkdir(parents=True)
   (root/'work/queue/inbox/TASK-180000000000.json').write_bytes(raw)
   (root/'state/TASK-180000000000.json').write_text(json.dumps(record))
   (root/'work/queue/done/TASK-180000000000.result.json').write_text(json.dumps(record['result']))
   for i in range(25):
    (root/f'state/TASK-1800000001{i:02d}.json').write_text(json.dumps({'task':'queue/inbox/x','result':{'output':'receipt secret'}}))
   results=c.context()['latest_task_results'];self.assertEqual(len(results),1);self.assertEqual(results[0]['output'],'real journal result')
 def test_recheck_invalidates_previous_ready(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   c=self.controller(pathlib.Path(d));c.verified['claude']=True
   with patch('controller.bounded_run',return_value=(1,b'')),patch('controller.cleanup_brain'):
    with self.assertRaises(ValueError):c.check_provider('claude')
   self.assertFalse(c.readiness()['verified'])
 def test_timeout_cleans_exact_unique_container(self):
  from unittest.mock import patch
  from controller import brain_command,run_brain
  image='brain@sha256:'+'a'*64
  a=brain_command('/tmp/a',image,'claude');b=brain_command('/tmp/a',image,'claude')
  self.assertNotEqual(a[a.index('--name')+1],b[b.index('--name')+1])
  with patch('controller.bounded_run',side_effect=TimeoutError),patch('controller.cleanup_brain') as cleanup:
   with self.assertRaises(TimeoutError):run_brain(a)
   cleanup.assert_called_once_with(a[a.index('--name')+1])
 def test_output_limit_and_cancel_also_clean_exact_container(self):
  from unittest.mock import patch
  from controller import brain_command,run_brain
  for failure in (ValueError('command output limit exceeded'),KeyboardInterrupt()):
   argv=brain_command('/tmp/a','brain@sha256:'+'a'*64,'codex')
   with patch('controller.bounded_run',side_effect=failure),patch('controller.cleanup_brain') as cleanup:
    with self.assertRaises(type(failure)):run_brain(argv)
    cleanup.assert_called_once_with(argv[argv.index('--name')+1])
 def test_plan_failure_invalidates_previous_auth(self):
  from unittest.mock import patch
  from controller import Controller
  with tempfile.TemporaryDirectory() as d:
   c=self.controller(pathlib.Path(d));c.verified['claude']=True
   with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(1,b'')):
    with self.assertRaises(ValueError):Controller.plan(c,'claude','prompt')
   self.assertFalse(c.readiness()['verified'])
