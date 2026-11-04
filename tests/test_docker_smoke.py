"""Real offline container smoke test. Enabled explicitly in CI/VPS, never calls a model."""
import os,pathlib,subprocess,tempfile,unittest,sys,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
@unittest.skipUnless(os.environ.get('GLOBALLAND_DOCKER_SMOKE')=='1','real Docker smoke requires explicit daemon access')
class DockerSmoke(unittest.TestCase):
 def test_private_case_executes_csv_program_and_replays_exact_reply(self):
  from private_work import PrivateResponder
  from unittest.mock import patch
  image=json.loads(subprocess.check_output(['docker','image','inspect','node:22-bookworm']))[0]['RepoDigests'][0]
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'control').mkdir();(root/'work/products').mkdir(parents=True)
   (root/'control/executor.js').write_bytes((pathlib.Path(__file__).resolve().parents[1]/'scripts/executor.js').read_bytes())
   (root/'work/products/other-customer.txt').write_text('must not be mounted')
   message={'inbox_id':'synthetic-inbox','message_id':'synthetic-csv','thread_id':'synthetic-thread','text':'amount\n2\n3\n'}
   config={'controller':{'providers':['claude']},'agentmail':{'fulfillment':{'enabled':True}},'executor_enabled':True,'executor_image':image}
   program="const fs=require('fs');if(fs.existsSync('/var/run/docker.sock')||fs.existsSync('products/other-customer.txt'))process.exit(9);const m=JSON.parse(fs.readFileSync('incoming.json','utf8'));const sum=m.text.trim().split('\\n').slice(1).reduce((n,v)=>n+Number(v),0);fs.writeFileSync('products/result.csv','sum\\n'+sum+'\\n');console.log('observed sum='+sum);"
   values=[{'summary':'Compute supplied CSV','actions':[{'agent':'BUILDER','action':'EXEC','args':{'argv':['node','-e',program],'outputs':['products/result.csv']}}]}, {'actions':[],'summary':json.dumps({'action':'reply','text':'Computed supplied CSV.','artifacts':['products/result.csv']})}]
   prompts=[]
   def plan(planner,provider,prompt):
    prompts.append(prompt)
    return values.pop(0)
   with patch('controller.Controller.plan',plan):reply=PrivateResponder(root,config)(message)
   self.assertIn('sum\n5\n',reply['text']);self.assertIn('observed sum=5',prompts[1]);self.assertIn('SHA256:',reply['text'])
   self.assertFalse((root/'work/products/result.csv').exists())
   with patch('controller.Controller.plan',side_effect=AssertionError('READY must replay')):self.assertEqual(PrivateResponder(root,config)(message),reply)
   self.assertFalse(list((root/'state/private/fulfillment').glob('*/TASK-*')))
 def test_arbitrary_program_produces_product_without_host_access(self):
  from world import World
  from treasury import Treasury
  from tools import Toolbox
  image=json.loads(subprocess.check_output(['docker','image','inspect','node:22-bookworm']))[0]['RepoDigests'][0]
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'work/products').mkdir(parents=True);(root/'control').mkdir();(root/'state').mkdir();(root/'oria.txt').write_text('running')
   (root/'control/executor.js').write_bytes((pathlib.Path(__file__).resolve().parents[1]/'scripts/executor.js').read_bytes())
   program="const fs=require('fs'); if(fs.existsSync('/var/run/docker.sock')||fs.existsSync('/opt/globalland/state'))process.exit(9); fs.writeFileSync('products/generated.txt','real sandbox product'); console.log('built');"
   (root/'work/products/build.js').write_text(program)
   world=World(root/'state/world.sqlite3');world.bootstrap();bank=Treasury(root/'state/bank.sqlite3')
   task={'id':'TASK-0999','type':'TOOL','submitted_by':'BUILDER','created_at':'2026-10-31T00:00:00Z','action':'EXEC','args':{'argv':['bash','-lc','node products/build.js'],'outputs':['products/generated.txt']},'estimated_cost_cad':0,'approved_by':None}
   result,files=Toolbox(root,world,bank,{'executor_enabled':True,'executor_image':image}).run(task)
   self.assertEqual(result['status'],'DONE',result);self.assertEqual(files['products/generated.txt'],'real sandbox product');self.assertEqual((root/'oria.txt').read_text(),'running');self.assertFalse((root/'work/products/generated.txt').exists())
if __name__=='__main__':unittest.main()
