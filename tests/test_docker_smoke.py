"""Real offline container smoke test. Enabled explicitly in CI/VPS, never calls a model."""
import os,pathlib,subprocess,tempfile,unittest,sys,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
@unittest.skipUnless(os.environ.get('GLOBALLAND_DOCKER_SMOKE')=='1','real Docker smoke requires explicit daemon access')
class DockerSmoke(unittest.TestCase):
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
