#!/usr/bin/env python3
"""Installed control plane. Never run the mutable repository copy from cron."""
import base64, datetime, fcntl, hashlib, io, json, os, pathlib, re, subprocess, sys, tarfile, tempfile
ROOT=pathlib.Path('/opt/globalland')
SECRET=re.compile(rb'sk-[A-Za-z0-9_-]{10,}|(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:API_KEY|TOKEN|PASSWORD)\s*[=:]\s*[^\s#]{8,}',re.I)
def bounded_run(args,env,input=None,limit=20*1024*1024):
 """Read incrementally: archive size checks must not first exhaust host RAM."""
 import selectors, time
 with subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env) as proc:
  try:
   if input:proc.stdin.write(input)
   proc.stdin.close()
   out=bytearray();err_size=0;deadline=time.monotonic()+120
   with selectors.DefaultSelector() as selector:
    selector.register(proc.stdout,selectors.EVENT_READ,'out');selector.register(proc.stderr,selectors.EVENT_READ,'err')
    while selector.get_map():
     remaining=deadline-time.monotonic()
     if remaining<=0:raise TimeoutError('command timed out')
     for key,_ in selector.select(min(remaining,1)):
      data=key.fileobj.read1(65536)
      if not data:selector.unregister(key.fileobj);continue
      if key.data=='out':
       if len(out)+len(data)>limit:raise ValueError('command output limit exceeded')
       out.extend(data)
      else:
       err_size+=len(data)
       if err_size>65536:raise ValueError('command error output limit exceeded')
   return proc.wait(timeout=max(0.1,deadline-time.monotonic())),bytes(out)
  except BaseException:
   proc.kill();proc.wait();raise
def check_secrets(raw):
 if SECRET.search(raw):raise ValueError('secret pattern detected; publication blocked')
def safe_path(name):
 if not isinstance(name,str) or not name or name.startswith('/') or '\\' in name or any(p in ('','.','..','.git') for p in name.split('/')):raise ValueError('unsafe path')
 return name
def allowed(name):
 return name in ('ledger.json','logs/transactions.log') or bool(re.fullmatch(r'bank/audits/audit-\d{4}-\d\d-\d\d\.md|queue/(?:done|failed)/TASK-[0-9]{4,12}\.result\.json',name))
def read_artifact(root,name):
 if not allowed(safe_path(name)):raise ValueError('publication outside allowlist')
 p=root
 for part in name.split('/'):
  p=p/part
  if p.is_symlink():raise ValueError('symlink artifact')
 raw=p.read_bytes()
 if len(raw)>1024*1024:raise ValueError('oversized artifact')
 check_secrets(raw);return raw
def atomic_json(p,value):
 p.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.journal-')
 try:
  with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
  fd=os.open(p.parent,os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def recover(p):
 r=json.loads(p.read_text())
 if r['state']=='RUNNING':
  r['state']='INTERRUPTED';r['result']={'status':'INTERRUPTED','output':'Execution interrupted; no automatic retry.'};atomic_json(p,r)
 return r
def extract_archive(raw,dest):
 total=0
 with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
  members=archive.getmembers()
  for m in members:
   safe_path(m.name.rstrip('/'))
   if not(m.isdir() or m.isreg()):raise ValueError('archive links/special files refused')
   total+=m.size
   if m.size>1024*1024 or total>16*1024*1024:raise ValueError('archive size limit')
  for m in members:
   p=dest/m.name
   if m.isdir():p.mkdir(parents=True,exist_ok=True)
   else:
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.extractfile(m).read());p.chmod(0o644)
  dest.chmod(0o755)
  for p in dest.rglob('*'):
   if p.is_dir():p.chmod(0o755)
def sync(git):
 # Retry pending publication even with an empty inbox. Never rebase generated state.
 git('push','origin','HEAD:main')
 git('fetch','origin','main')
 old=git('rev-parse','HEAD').decode().strip();new=git('rev-parse','FETCH_HEAD').decode().strip()
 if old!=new:
  git('merge-base','--is-ancestor',old,new)
  git('update-ref','refs/heads/main',new,old)
class Supervisor:
 def __init__(self,root=ROOT):self.root=root;self.source=root/'source.git';self.state=root/'state';self.control=root/'control'
 def git(self,*args,input=None,env=None):
  e={**os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0','GIT_ATTR_NOSYSTEM':'1', 'GIT_SSH_COMMAND':f'ssh -i {self.root}/ssh/deploy_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile={self.root}/ssh/known_hosts'}
  # Do not inherit Git index/config overrides from a caller.
  for k in list(e):
   if k.startswith('GIT_') and k not in ('GIT_CONFIG_NOSYSTEM','GIT_CONFIG_GLOBAL','GIT_TERMINAL_PROMPT','GIT_ATTR_NOSYSTEM','GIT_SSH_COMMAND'):del e[k]
  if env:e.update(env)
  code,out=bounded_run(['git','--git-dir='+str(self.source),'-c','core.hooksPath=/dev/null','-c','core.attributesFile=/dev/null',*args],input=input,env=e)
  if code:raise RuntimeError('git '+args[0]+' failed; inspect privately, no retry of task')
  return out
 def publish(self,record):
  files=record['files'];task=record.get('task');result=record.get('result')
  if result:
   location='done' if result['status']=='DONE' else 'failed';files={**files,f"queue/{location}/{record['id']}.result.json":json.dumps({**result,'id':record['id'],'input_sha256':record['hash']},ensure_ascii=False,indent=2)+'\n'}
  for name,text in files.items():
   if not allowed(safe_path(name)) or not isinstance(text,str) or len(text.encode())>1024*1024:raise ValueError('invalid publication')
   check_secrets(text.encode())
  with tempfile.TemporaryDirectory(dir=self.state) as d:
   env={'GIT_INDEX_FILE':str(pathlib.Path(d)/'index')};parent=self.git('rev-parse','HEAD').decode().strip();self.git('read-tree',parent,env=env)
   for name,text in files.items():
    blob=self.git('hash-object','-w','--stdin',input=text.encode()).decode().strip();self.git('update-index','--add','--cacheinfo','100644',blob,name,env=env)
   if task:self.git('update-index','--index-info',input=('0 '+'0'*40+'\t'+safe_path(task)+'\n').encode(),env=env)
   tree=self.git('write-tree',env=env).decode().strip()
   if tree!=self.git('rev-parse','HEAD^{tree}').decode().strip():
    identity={'GIT_AUTHOR_NAME':'globalland-supervisor','GIT_AUTHOR_EMAIL':'supervisor@globalland.local','GIT_COMMITTER_NAME':'globalland-supervisor','GIT_COMMITTER_EMAIL':'supervisor@globalland.local'}
    commit=self.git('commit-tree',tree,'-p',parent,input=('ops: durable '+record['id']+'\n').encode(),env=identity).decode().strip();self.git('update-ref','refs/heads/main',commit,parent)
  self.git('push','origin','HEAD:main')
 def worker(self,kind,rel=''):
  # Compose and worker code come only from control/, installed by the administrator.
  r=subprocess.run(['docker','compose','-f',str(self.control/'compose.yml'),'--project-directory',str(self.root),'run','--rm','-T','core','node','/control/worker.js',kind,rel],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
  if r.returncode:raise RuntimeError('worker failed')
  if len(r.stdout)>1024*1024:raise ValueError('worker output too large')
  check_secrets(r.stdout);return json.loads(r.stdout)
 def finish(self,p,r):
  self.publish(r);r['state']='PUBLISHED';atomic_json(p,r)
 def cycle(self,mode):
  self.state.mkdir(parents=True,exist_ok=True)
  # First finish every local terminal journal, then retry local Git commits and fetch.
  for p in sorted(self.state.glob('*.json')):
   r=recover(p)
   if r['state']=='INTERRUPTED' and not r.get('task'):raise RuntimeError('Interrupted daily audit: operator review required; restore from journal backup or acknowledge after reconciliation')
   if r['state']!='PUBLISHED':self.finish(p,r)
  # A fetch-only first step permits upstream fast-forwards without a rejected push.
  self.git('fetch','origin','main')
  head=self.git('rev-parse','HEAD').decode().strip();remote=self.git('rev-parse','FETCH_HEAD').decode().strip()
  if head!=remote:
   try:self.git('merge-base','--is-ancestor',head,remote)
   except RuntimeError:sync(self.git)  # local commits or divergence: preserve, push or stop
   else:self.git('update-ref','refs/heads/main',remote,head)
  work=self.root/'work'
  # work is administrator-owned; containers see it read-only and cannot leave links.
  import shutil
  if work.exists():shutil.rmtree(work)
  work.mkdir(mode=0o755)
  extract_archive(self.git('archive','--format=tar','HEAD'),work)
  if mode=='daily':jobs=[('DAILY-'+datetime.datetime.now(datetime.timezone.utc).date().isoformat(),None)]
  else:
   jobs=[]
   for f in sorted((work/'queue/inbox').glob('*.json')):
    if not re.fullmatch(r'TASK-[0-9]{4,12}\.json',f.name):raise ValueError('invalid inbox filename; operator review required')
    jobs.append((f.stem,'queue/inbox/'+f.name))
  for ident,rel in jobs:
   raw=(work/rel).read_bytes() if rel else ident.encode();check_secrets(raw);digest=hashlib.sha256(raw).hexdigest();p=self.state/(ident+'.json')
   if p.exists():
    r=recover(p)
    if r['hash']!=digest:raise ValueError('task ID reused with different bytes')
    if rel:raise ValueError('published task replayed; operator review required')
    continue
   r={'id':ident,'hash':digest,'task':rel,'state':'RUNNING','files':{}};atomic_json(p,r)
   try:
    result=self.worker('task' if rel else 'daily',rel or ident[6:])
    if rel:
     if set(result)!= {'status','output'} or result['status'] not in ('DONE','REJECTED'):raise ValueError('invalid worker result')
     r['result']=result
    else:
     expected={'ledger.json','logs/transactions.log',f"bank/audits/audit-{ident[6:]}.md"}
     if set(result)!=expected:raise ValueError('unexpected daily artifacts')
     r['files']=result
    r['state']='COMPLETED'
   except Exception:
    r['state']='INTERRUPTED'
    if rel:r['result']={'status':'INTERRUPTED','output':'Worker failed; inspect host journal. No automatic retry.'}
    else:atomic_json(p,r);raise
   atomic_json(p,r);self.finish(p,r)
def main():
 if len(sys.argv)!=2 or sys.argv[1] not in ('queue','daily'):raise ValueError('usage: supervisor.py queue|daily')
 ROOT.joinpath('state').mkdir(parents=True,exist_ok=True)
 with open(ROOT/'state/supervisor.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);Supervisor().cycle(sys.argv[1])
if __name__=='__main__':
 try:main()
 except Exception as e:print('GlobalLand stopped: '+str(e),file=sys.stderr);sys.exit(1)
