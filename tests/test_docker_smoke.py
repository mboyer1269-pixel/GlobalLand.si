"""Real offline container smoke test. Enabled explicitly in CI/VPS, never calls a model."""
import os,pathlib,subprocess,tempfile,unittest,sys,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
@unittest.skipUnless(os.environ.get('GLOBALLAND_DOCKER_SMOKE')=='1','real Docker smoke requires explicit daemon access')
class DockerSmoke(unittest.TestCase):
 def test_private_continuity_a_b_c_files_receipts_and_exact_replay(self):
  from private_work import PrivateResponder
  from mail import Mailbox
  from test_continuity import message,finish,CONFIG
  import copy,hashlib
  from unittest.mock import patch
  image=json.loads(subprocess.check_output(['docker','image','inspect',os.environ.get('GLOBALLAND_DOCKER_SMOKE_IMAGE','node:22-bookworm')]))[0]['RepoDigests'][0]
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'control').mkdir();(root/'work/products').mkdir(parents=True)
   (root/'control/executor.js').write_bytes((pathlib.Path(__file__).resolve().parents[1]/'scripts/executor.js').read_bytes())
   (root/'work/products/other-customer.txt').write_text('UNRELATED-CUSTOMER')
   config=copy.deepcopy(CONFIG);config.update(executor_enabled=True,executor_image=image)
   config['agentmail']['max_messages_per_cycle']=1
   akey=hashlib.sha256(b'inbox\0A').hexdigest();ahash=hashlib.sha256(b'sum\n5\n').hexdigest()
   messages=[message('A',text='amount\n2\n3\n')];sent=[]
   class Client:
    def list_received(self):return messages
    def get_message(self,mid):return copy.deepcopy(next(m for m in messages if m['message_id']==mid))
    def reply(self,mid,text,operation,*,route=None):sent.append((mid,text,route));return dict(message_id='out-'+mid,thread_id='opaque-thread')
   client=Client()
   common="const fs=require('fs');if(fs.existsSync('/var/run/docker.sock')||fs.existsSync('products/other-customer.txt'))process.exit(9);"
   programs={
    'A':common+"fs.writeFileSync('products/A.csv','sum\\n5\\n');console.log('PRIVATE-RECEIPT-A');",
    'B':common+"const crypto=require('crypto');const p='history/"+akey+"/products/A.csv';const a=fs.readFileSync(p);if(crypto.createHash('sha256').update(a).digest('hex')!=='"+ahash+"')process.exit(8);const h=JSON.parse(fs.readFileSync('history.json','utf8'));if(!h.untrusted_history.some(x=>x.receipts.some(r=>r.output.includes('PRIVATE-RECEIPT-A'))))process.exit(7);fs.writeFileSync('products/B.csv','sum\\n9\\n');console.log('corrected historical sum=9');",
    'C':common+"const h=JSON.parse(fs.readFileSync('history.json','utf8'));if(fs.existsSync('history')||h.untrusted_history.length||h.manifest.files.length||h.manifest.text_cases.length)process.exit(6);fs.writeFileSync('products/C.csv','isolated');console.log('isolated');"}
   prompts={}
   def plan(planner,provider,prompt):
    data=json.loads(prompt[prompt.index('{"private_case"'):]);case=data['private_case'];mid=case['identity'][1]
    prompts.setdefault(mid,[]).append(prompt)
    if mid=='B':self.assertIn('PRIVATE-RECEIPT-A',prompt);self.assertIn(ahash,prompt)
    if mid=='C':
     # C's own program tests generic emptiness, without receiving A's private
     # key or marker. Check host context separately before injecting that program
     # and retain whole-prompt checks on subsequent receipt turns as well.
     self.assertEqual(case['continuity']['history'],[]);self.assertIsNone(case['continuity']['binding'])
     self.assertEqual(data['private_history']['untrusted_history'],[])
     self.assertEqual(data['private_history']['manifest']['files'],[])
     self.assertEqual(data['private_history']['manifest']['text_cases'],[])
     self.assertNotIn('PRIVATE-RECEIPT-A',prompt);self.assertNotIn(akey,prompt);self.assertNotIn(ahash,prompt)
    if not case['steps']:return {'summary':'Compute current correction','actions':[{'agent':'BUILDER','action':'EXEC','args':{'argv':['node','-e',programs[mid]],'outputs':['products/'+mid+'.csv']}}]}
    self.assertEqual(case['steps'][-1]['receipt']['status'],'DONE')
    return finish('Computed current case.',artifacts=['products/'+mid+'.csv'])
   with patch('controller.Controller.plan',plan):
    self.assertEqual(Mailbox(root,config,client).cycle(PrivateResponder(root,config))['accepted'],1)
    messages.append(message('B',in_reply_to='out-A',text='Please add 4.',extracted_text='Please add 4.'))
    self.assertEqual(Mailbox(root,config,client).cycle(PrivateResponder(root,config))['accepted'],1)
    messages.append(message('C',in_reply_to='out-A',text='My separate task.',**{'from':'Other@example.test'}))
    self.assertEqual(Mailbox(root,config,client).cycle(PrivateResponder(root,config))['accepted'],1)
   self.assertIn('sum\n9\n',sent[1][1]);self.assertEqual(sent[1][2]['to'],['Alice+tag@example.test'])
   with patch('controller.Controller.plan',side_effect=AssertionError('no replay')):
    self.assertEqual(PrivateResponder(root,config)(messages[1])['text'],sent[1][1])
    Mailbox(root,config,client).cycle(PrivateResponder(root,config))
   self.assertEqual(len(sent),3);self.assertFalse(list((root/'state/private/fulfillment').glob('*/TASK-*')))
 def test_private_case_executes_csv_program_and_replays_exact_reply(self):
  from private_work import PrivateResponder
  from unittest.mock import patch
  image=json.loads(subprocess.check_output(['docker','image','inspect',os.environ.get('GLOBALLAND_DOCKER_SMOKE_IMAGE','node:22-bookworm')]))[0]['RepoDigests'][0]
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
  image=json.loads(subprocess.check_output(['docker','image','inspect',os.environ.get('GLOBALLAND_DOCKER_SMOKE_IMAGE','node:22-bookworm')]))[0]['RepoDigests'][0]
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
