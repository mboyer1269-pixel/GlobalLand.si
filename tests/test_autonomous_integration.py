import json,pathlib,subprocess,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from supervisor import Supervisor
BASE=pathlib.Path(__file__).resolve().parents[1]
class AutonomousIntegration(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name);self.remote=self.root/'remote.git';self.seed=self.root/'seed';self.install=self.root/'install';self.install.mkdir();(self.install/'state').mkdir();(self.install/'control').mkdir()
  self.run(['git','init','--bare',str(self.remote)]);self.run(['git','init','-b','main',str(self.seed)])
  (self.seed/'ledger.json').write_bytes((BASE/'tests/fixtures/genesis.json').read_bytes());(self.seed/'queue/inbox').mkdir(parents=True)
  (self.seed/'queue/inbox/.gitkeep').write_text('');self.git('add','.');self.git('commit','-m','seed');self.git('remote','add','origin',str(self.remote));self.git('push','origin','main');self.run(['git','clone','--bare',str(self.remote),str(self.install/'source.git')]);self.run(['git','--git-dir='+str(self.install/'source.git'),'symbolic-ref','HEAD','refs/heads/main'])
  self.app=Supervisor(self.install)
 def run(self,args=None,result=None):
  if args is None or not isinstance(args,list):return super().run(args if args is not None else result)
  return subprocess.run(args,check=True,capture_output=True).stdout
 def git(self,*args):return self.run(['git','-C',str(self.seed),'-c','user.name=Test','-c','user.email=test@local',*args])
 def submit(self,number,action,args):
  ident='TASK-'+str(number).zfill(4);task={'id':ident,'type':'TOOL','submitted_by':'DIRECTOR','created_at':'2026-10-31T00:00:00Z','action':action,'args':args,'estimated_cost_cad':0,'approved_by':None};self.git('pull','--ff-only','origin','main');(self.seed/'queue/inbox').mkdir(exist_ok=True,parents=True);(self.seed/'queue/inbox'/(ident+'.json')).write_text(json.dumps(task));self.git('add','.');self.git('commit','-m','submit');self.git('push','origin','main');return ident
 def test_world_tools_products_and_private_bank(self):
  self.submit(100,'WORLD',{'op':'create_mission','mission_id':'GLOBAL-PRODUCT','goal':'Sell an Internet tool globally'})
  self.app.cycle('queue')
  state=json.loads(self.app.git('show','HEAD:world/status.json'));self.assertTrue(any(m['mission_id']=='GLOBAL-PRODUCT' for m in state['missions']))
  bank=json.loads(self.app.git('show','HEAD:bank/status.json'));self.assertEqual(bank['state'],'UNFUNDED');self.assertFalse(bank['funding_verified'])
  self.submit(101,'FETCH',{'url':'https://example.com/','output':'products/research.txt'})
  with patch('tools.fetch_public',return_value=(b'public source','https://example.com/',200)):self.app.cycle('queue')
  self.assertEqual(self.app.git('show','HEAD:products/research.txt'),b'public source')
  self.submit(102,'SPEND',{'request':{'purchase':'tool'}});self.app.cycle('queue')
  self.assertEqual(json.loads(self.app.git('show','HEAD:queue/failed/TASK-0102.result.json'))['status'],'REJECTED')
  self.assertNotIn(b'sqlite',self.app.git('ls-tree','-r','--name-only','HEAD'))
 def test_verified_death_stops_world_and_preserves_oria(self):
  w,b,c=self.app.services();b.verifier=lambda _:True
  b.confirm_funding({'provider':'test','account':'world','event_id':'fund','amount_cents':5000,'currency':'CAD','kind':'FUNDING','settled':True});b.reserve('end',5000,'hash');b.mark_submitted('end');b.settle('end',{'provider':'test','account':'world','event_id':'spend','amount_cents':5000,'currency':'CAD','kind':'SPEND','settled':True})
  oria=self.root/'oria.txt';oria.write_text('running')
  self.app.cycle('queue');self.assertEqual(oria.read_text(),'running');self.assertEqual(w.snapshot()['state'],'EXTINCT');self.assertTrue((self.install/'state/private/EXTINCT.json').exists())
 def test_controller_orphan_outbox_is_published_then_acknowledged(self):
  from controller import Controller
  config={'controller':{'mode':'subscriptions','providers':['codex'],'subscriptions_confirmed':True,'extra_usage_disabled':True,'image':'brain@sha256:'+'1'*64}}
  (self.install/'control/config.json').write_text(json.dumps(config));w,b,c=self.app.services()
  class Fake(Controller):
   def plan(self,provider,prompt):return {'summary':'Start work','actions':[{'agent':'DIRECTOR','action':'WORLD','args':{'op':'create_mission','mission_id':'FROM-BRAIN','goal':'Earn global revenue'}}]}
  turn,files=Fake(self.install,w,b,config).tick(now=1800000000)
  with patch('controller.Controller',Fake):self.app.cycle('think')
  outbox=json.loads((self.install/'state/controller'/(turn+'.json')).read_text());self.assertTrue(outbox['published'])
  self.app.cycle('queue');self.assertTrue(any(m['mission_id']=='FROM-BRAIN' for m in w.snapshot()['missions']))
 def test_concurrent_fastforward_product_edit_is_not_overwritten(self):
  (self.seed/'products').mkdir();(self.seed/'products/shared.txt').write_text('base')
  self.git('add','.');self.git('commit','-m','base product');self.git('push','origin','main');self.app.cycle('queue')
  base=self.app.git('rev-parse','HEAD').decode().strip()
  (self.seed/'products/shared.txt').write_text('upstream edit');self.git('add','.');self.git('commit','-m','concurrent');self.git('push','origin','main')
  with self.assertRaisesRegex(RuntimeError,'Concurrent publication conflict'):
   self.app.publish({'id':'TASK-0200','base_sha':base,'files':{'products/shared.txt':'stale overwrite'}})
  self.assertEqual(subprocess.check_output(['git','--git-dir='+str(self.remote),'show','main:products/shared.txt']),b'upstream edit')
 def test_same_batch_exec_consumes_preceding_fetch_artifact(self):
  from tools import Toolbox
  original=Toolbox.run
  self.submit(201,'FETCH',{'url':'https://example.com/','output':'products/data.txt'})
  self.submit(202,'EXEC',{'argv':['node','-p','123'],'outputs':[]})
  def run(box,task):
   if task['action']=='EXEC':
    self.assertEqual((box.root/'work/products/data.txt').read_text(),'fresh research')
    return {'status':'DONE','output':'consumed'},{}
   return original(box,task)
  with patch('tools.fetch_public',return_value=(b'fresh research','https://example.com/',200)),patch('tools.Toolbox.run',run):self.app.cycle('queue')
  self.assertEqual(json.loads(self.app.git('show','HEAD:queue/done/TASK-0202.result.json'))['output'],'consumed')
 def test_wire_decision_becomes_durable_tasks_and_real_git_results(self):
  from controller import Controller
  config={'controller':{'mode':'subscriptions','providers':['codex'],'subscriptions_confirmed':True,'extra_usage_disabled':True,'image':'brain@sha256:'+'1'*64}}
  (self.install/'control/config.json').write_text(json.dumps(config))
  wire={'summary':'Start evidence-backed work','actions':[
   {'agent':'DIRECTOR','action':'WORLD','args':{'op':'create_mission','mission_id':'WIRE-PRODUCT','goal':'Build a useful global product','agent_id':None,'parent_id':None,'priority':None}},
   {'agent':'RESEARCHER','action':'FETCH','args':{'url':'https://example.com/','output':'products/proof.txt','encoding':'utf-8'}}]}
  def auth(controller,provider):controller.verified[provider]=True
  with patch.object(Controller,'check_provider',auth),patch('controller.run_brain',return_value=(0,json.dumps(wire).encode())):
   self.app.cycle('think')
  tracked=self.app.git('ls-tree','-r','--name-only','HEAD').decode().splitlines()
  tasks=[p for p in tracked if p.startswith('queue/inbox/TASK-')]
  self.assertEqual(len(tasks),2)
  for task in tasks:
   value=json.loads(self.app.git('show','HEAD:'+task));self.assertIsInstance(value['args'],dict);self.assertNotIn('args_json',value)
  with patch('tools.fetch_public',return_value=(b'public fixture evidence','https://example.com/',200)):self.app.cycle('queue')
  self.assertEqual(self.app.git('show','HEAD:products/proof.txt'),b'public fixture evidence')
  for task in tasks:
   name=pathlib.PurePosixPath(task).stem
   self.assertEqual(json.loads(self.app.git('show','HEAD:queue/done/'+name+'.result.json'))['status'],'DONE')
  w,b,_=self.app.services();self.assertTrue(any(m['mission_id']=='WIRE-PRODUCT' for m in w.snapshot()['missions']))
  self.assertEqual(b.snapshot()['state'],'UNFUNDED')
  outboxes=list((self.install/'state/controller').glob('THINK-*.json'));self.assertEqual(len(outboxes),1)
  self.assertTrue(json.loads(outboxes[0].read_text())['published'])
if __name__=='__main__':unittest.main()
