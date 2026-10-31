import unittest, tempfile, pathlib, sys, json, subprocess, os
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
class SupervisorTests(unittest.TestCase):
 def test_safe_paths_and_secrets(self):
  import supervisor as s
  for p in ['../x','.git/config','a/.git/hooks/x','/etc/passwd','queue/../x']:
   with self.assertRaises(ValueError): s.safe_path(p)
  self.assertEqual(s.safe_path('queue/inbox/TASK-0001.json'),'queue/inbox/TASK-0001.json')
  for raw in [b'sk-'+b'x'*30,b'-----BEGIN OPENSSH PRIVATE KEY-----',b'ghp_'+b'x'*40]:
   with self.assertRaises(ValueError): s.check_secrets(raw)
 def test_atomic_journal_and_recovery_no_reexecution(self):
  import supervisor as s
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'TASK-0001.json';s.atomic_json(p,{'state':'RUNNING','hash':'abc','files':{}})
   r=s.recover(p);self.assertEqual(r['state'],'INTERRUPTED');self.assertEqual(s.recover(p),r)
 def test_archive_rejects_symlink_git_and_traversal(self):
  import supervisor as s,tarfile,io
  for name,kind in [('products/link',tarfile.SYMTYPE),('../escape',tarfile.REGTYPE),('.git/config',tarfile.REGTYPE)]:
   b=io.BytesIO()
   with tarfile.open(fileobj=b,mode='w') as t:
    i=tarfile.TarInfo(name);i.type=kind;i.linkname='/tmp/escape';t.addfile(i)
   with tempfile.TemporaryDirectory() as d:
    with self.assertRaises(ValueError):s.extract_archive(b.getvalue(),pathlib.Path(d))
 def test_publication_allowlist_and_symlinks(self):
  import supervisor as s
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'ledger.json').write_text('{}');self.assertEqual(s.read_artifact(root,'ledger.json'),b'{}')
   with self.assertRaises(ValueError):s.read_artifact(root,'scripts/audit.js')
   (root/'logs').symlink_to('/tmp',target_is_directory=True)
   with self.assertRaises(ValueError):s.read_artifact(root,'logs/transactions.log')
 def test_push_failure_retries_before_pull(self):
  import supervisor as s
  calls=[]
  def git(*args):
   calls.append(args)
   if args[0]=='push':raise RuntimeError('offline')
  with self.assertRaises(RuntimeError):s.sync(git)
  self.assertEqual(calls,[('push','origin','HEAD:main')])
 def test_real_git_publication_retry(self):
  import supervisor as s
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);remote=root/'remote.git';repo=root/'repo'
   subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
   subprocess.run(['git','clone',str(remote),str(repo)],check=True,capture_output=True)
   def g(*a):return subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@local',*a],check=True,capture_output=True).stdout
   g('checkout','-b','main');(repo/'a').write_text('a');g('add','a');g('commit','-m','init');g('push','-u','origin','main')
   (repo/'a').write_text('b');g('add','a');g('commit','-m','pending');s.sync(g)
   self.assertEqual(g('rev-parse','HEAD'),g('rev-parse','origin/main'))
 def test_full_cycle_real_git_worker_recovery_and_duplicate(self):
  import supervisor as s
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);remote=root/'remote.git';seed=root/'seed';install=root/'install';install.mkdir();(install/'state').mkdir()
   subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
   subprocess.run(['git','init','-b','main',str(seed)],check=True,capture_output=True)
   def g(*args):return subprocess.run(['git','-C',str(seed),'-c','user.name=Test','-c','user.email=test@local',*args],check=True,capture_output=True).stdout
   base=pathlib.Path(__file__).resolve().parents[1]
   for name in ['ledger.json','queue/inbox/TASK-0001.json']:
    p=seed/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((base/name).read_bytes())
   g('add','.');g('commit','-m','seed');g('remote','add','origin',str(remote));g('push','origin','main')
   subprocess.run(['git','clone','--bare',str(remote),str(install/'source.git')],check=True,capture_output=True)
   subprocess.run(['git','--git-dir='+str(install/'source.git'),'symbolic-ref','HEAD','refs/heads/main'],check=True)
   class Local(s.Supervisor):
    executions=0
    def git(self,*args,**kwargs):
     if args[0]=='push' and getattr(self,'fail_next',False):
      self.fail_next=False;raise RuntimeError('simulated push failure')
     return super().git(*args,**kwargs)
    def worker(self,kind,rel=''):
     self.executions+=1
     r=subprocess.run(['node',str(base/'scripts/worker.js'),kind,rel,str(install/'work')],check=True,capture_output=True)
     return json.loads(r.stdout)
   app=Local(install);app.fail_next=True
   with self.assertRaisesRegex(RuntimeError,'simulated push failure'):app.cycle('queue')
   self.assertEqual(app.executions,1)
   self.assertEqual(json.loads((install/'state/TASK-0001.json').read_text())['state'],'COMPLETED')
   app.cycle('queue');self.assertEqual(app.executions,1)
   app.cycle('queue');self.assertEqual(app.executions,1)
   result=app.git('show','HEAD:queue/done/TASK-0001.result.json');self.assertEqual(json.loads(result)['status'],'DONE')
   app.cycle('daily');app.cycle('daily');self.assertEqual(app.executions,2)
   ledger=json.loads(app.git('show','HEAD:ledger.json'));self.assertEqual(ledger['grace_period_days_remaining'],6)
   self.assertEqual(len(ledger['transactions']),2)
   self.assertFalse((install/'work/.git').exists())
   g('pull','--ff-only','origin','main');(seed/'queue/inbox').mkdir(parents=True,exist_ok=True);(seed/'queue/inbox/TASK-0001.json').write_text('{"replay":true}')
   g('add','.');g('commit','-m','replay');g('push','origin','main')
   with self.assertRaisesRegex(ValueError,'ID reused'):app.cycle('queue')
   self.assertEqual(app.executions,2)
 def test_interrupted_daily_requires_explicit_operator_review(self):
  import supervisor as s
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'state').mkdir()
   p=root/'state/DAILY-2026-10-30.json';s.atomic_json(p,{'state':'RUNNING','id':'DAILY-2026-10-30','task':None,'files':{},'hash':'abc'})
   with self.assertRaisesRegex(RuntimeError,'Interrupted daily audit'):s.Supervisor(root).cycle('queue')
   self.assertEqual(s.recover(p)['state'],'INTERRUPTED')
 def test_git_capture_bounded_before_archive_parsing(self):
  import supervisor as s
  with self.assertRaisesRegex(ValueError,'output limit'):
   s.bounded_run([sys.executable,'-c','import sys;sys.stdout.write("x"*200000)'],env=os.environ,limit=100000)
  code,out=s.bounded_run([sys.executable,'-c','print("ok")'],env=os.environ,limit=100000)
  self.assertEqual((code,out),(0,b'ok\n'))
if __name__=='__main__':unittest.main()
