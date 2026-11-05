#!/usr/bin/env python3
"""Installed control plane. Never run the mutable repository copy from cron."""
import base64, datetime, fcntl, hashlib, io, json, os, pathlib, re, subprocess, sys, tarfile, tempfile, time
ROOT=pathlib.Path('/opt/globalland')
SECRET=re.compile(rb'(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{10,}|(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:API_KEY|TOKEN|PASSWORD)\s*[=:]\s*[^\s#]{8,}',re.I)
FAILURE_KINDS=('TimeoutError','FileNotFoundError','PermissionError','ValueError','OSError','RuntimeError','Exception')
FAILURE_DEFAULTS={'TimeoutError':'provider_timeout','FileNotFoundError':'runtime_dependency_missing','PermissionError':'runtime_permission_denied','ValueError':'provider_or_decision_validation_failed','OSError':'runtime_io_failure','RuntimeError':'runtime_failure','Exception':'unexpected_planner_failure'}
FAILURE_MESSAGES={'invalid subscription structured output':'invalid_provider_structured_output','invalid controller decision':'invalid_controller_decision','invalid controller action':'invalid_controller_action','secret pattern detected; publication blocked':'secret_detected','unsafe path':'invalid_task_path','outputs must be public products paths':'invalid_task_path','all configured subscription providers failed':'all_subscription_providers_failed','Cannot verify brain container cleanup':'container_cleanup_unverified'}
FAILURE_MESSAGES.update({'configured brain image missing':'brain_image_missing','brain image inspection failed':'brain_image_inspection_failed'})
FAILURE_CODES=frozenset(FAILURE_DEFAULTS.values())|frozenset(FAILURE_MESSAGES.values())
def failure_details(error):
 # Exception strings can contain credentials: expose fixed codes only.
 kind=next((t.__name__ for t in (TimeoutError,FileNotFoundError,PermissionError,ValueError,OSError,RuntimeError) if isinstance(error,t)),'Exception')
 detail=error.args[0] if len(error.args)==1 and isinstance(error.args[0],str) else None
 return {'exception_type':kind,'reason':FAILURE_MESSAGES.get(detail,FAILURE_DEFAULTS[kind])}
def bounded_run(args,env,input=None,limit=20*1024*1024,timeout=120,merge_stderr=False,stderr_limit=65536):
 """Bound all I/O under one deadline; callers own external-container cleanup."""
 import selectors,time
 with subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env) as proc:
  try:
   out=bytearray();err_size=0;offset=0;payload=input or b'';deadline=time.monotonic()+timeout
   with selectors.DefaultSelector() as selector:
    for stream in (proc.stdout,proc.stderr,proc.stdin):os.set_blocking(stream.fileno(),False)
    selector.register(proc.stdout,selectors.EVENT_READ,'out');selector.register(proc.stderr,selectors.EVENT_READ,'err')
    if payload:selector.register(proc.stdin,selectors.EVENT_WRITE,'in')
    else:proc.stdin.close()
    while selector.get_map():
     remaining=deadline-time.monotonic()
     if remaining<=0:raise TimeoutError('command timed out')
     for key,_ in selector.select(min(remaining,1)):
      if key.data=='in':
       try:offset+=os.write(key.fd,payload[offset:offset+65536])
       except BrokenPipeError:offset=len(payload)
       if offset>=len(payload):selector.unregister(key.fileobj);key.fileobj.close()
       continue
      data=os.read(key.fd,65536)
      if not data:selector.unregister(key.fileobj);continue
      if key.data=='out' or merge_stderr:
       if len(out)+len(data)>limit:raise ValueError('command output limit exceeded')
       out.extend(data)
      if key.data=='err':
       err_size+=len(data)
       if err_size>stderr_limit:raise ValueError('command error output limit exceeded')
   return proc.wait(timeout=max(0.1,deadline-time.monotonic())),bytes(out)
  except BaseException:
   proc.kill();proc.wait();raise
def strict_json(raw):
 def pairs(items):
  value={}
  for k,v in items:
   if k in value:raise ValueError('duplicate JSON key')
   value[k]=v
  return value
 return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('non-finite JSON')))
def check_secrets(raw):
 if SECRET.search(raw):raise ValueError('secret pattern detected; publication blocked')
def safe_path(name):
 if not isinstance(name,str) or not name or name.startswith('/') or '\\' in name or any(p in ('','.','..','.git') for p in name.split('/')):raise ValueError('unsafe path')
 return name
PROJECTIONS=('bank/status.json','world/status.json','world/controller.json','world/blockers.json')
def allowed(name):
 return name in ('ledger.json','logs/transactions.log',*PROJECTIONS) or (name.startswith('products/') and not any(p.startswith('.') for p in name.split('/'))) or bool(re.fullmatch(r'bank/audits/audit-\d{4}-\d\d-\d\d\.md|queue/(?:done|failed)/TASK-[0-9]{4,12}\.result\.json',name))
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
 def services(self):
  from world import World
  from treasury import Treasury
  from gateway import Gateway
  private=self.state/'private';private.mkdir(parents=True,exist_ok=True,mode=0o700)
  world=World(private/'world.sqlite3');world.bootstrap()
  bank=Treasury(private/'treasury.sqlite3');bank.verifier=Gateway(self.root,bank).verify
  config_path=self.control/'config.json'
  config=json.loads(config_path.read_text()) if config_path.exists() else {}
  return world,bank,config
 def projections(self,world,bank,config,planner=None):
  from controller import Controller
  planner=planner or Controller(self.root,world,bank,config)
  status=planner.projection()
  import progress
  snapshot=world.snapshot()
  import payouts
  return {'bank/status.json':json.dumps(dict(bank.snapshot(),receivables=payouts.receivables(self.root)),indent=2)+'\n','world/status.json':json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n','world/controller.json':json.dumps(status,indent=2)+'\n','world/blockers.json':json.dumps(progress.board(self.root,snapshot),ensure_ascii=False,indent=2)+'\n'}
 def prepare_publication(self,record):
  # Reapply a durable outbox on non-overlapping upstream changes; never rerun work.
  self.git('fetch','origin','main')
  local=self.git('rev-parse','HEAD').decode().strip();remote=self.git('rev-parse','FETCH_HEAD').decode().strip()
  base=record.get('base_sha')
  if base and remote!=base:
   for name,text in record['files'].items():
    if name in PROJECTIONS:continue
    def content(ref):
     try:return self.git('show',ref+':'+name)
     except RuntimeError:return None
    before,current=content(base),content(remote)
    if before!=current and current!=text.encode():raise RuntimeError('Concurrent publication conflict: '+name)
  if local==remote:return
  try:self.git('merge-base','--is-ancestor',local,remote)
  except RuntimeError:
   try:self.git('merge-base','--is-ancestor',remote,local)
   except RuntimeError:
    base=record.get('base_sha')
    if not base:raise RuntimeError('Divergent legacy publication; operator reconciliation required')
    for name,text in record['files'].items():
     if name in PROJECTIONS:continue
     def blob(ref):
      try:return self.git('show',ref+':'+name)
      except RuntimeError:return None
     old,new=blob(base),blob(remote)
     if old!=new and new!=text.encode():raise RuntimeError('Concurrent publication conflict: '+name)
    self.git('update-ref','refs/globalland/pending/'+local,local)
    self.git('update-ref','refs/heads/main',remote,local)
  else:self.git('update-ref','refs/heads/main',remote,local)
  task=record.get('task')
  if task:
   try:current=self.git('show','HEAD:'+task)
   except RuntimeError:current=None
   if current is not None and hashlib.sha256(current).hexdigest()!=record['hash']:raise RuntimeError('Inbox changed while task was executing')
 def publish(self,record):
  self.prepare_publication(record)
  files=record['files'];task=record.get('task');result=record.get('result')
  if result:
   location='done' if result['status']=='DONE' else 'failed';request={'request':record['request']} if record.get('origin')=='broker' else {}
   files={**files,f"queue/{location}/{record['id']}.result.json":json.dumps({**result,**request,'id':record['id'],'input_sha256':record['hash']},ensure_ascii=False,indent=2)+'\n'}
  for name,text in files.items():
   if not (allowed(safe_path(name)) or (record['id'].startswith('THINK-') and re.fullmatch(r'queue/inbox/TASK-[0-9]{4,12}\.json',name))) or not isinstance(text,str) or len(text.encode())>1024*1024:raise ValueError('invalid publication')
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
  self.publish(r)
  if r['id'].startswith('THINK-'):
   from controller import Controller
   Controller(self.root,None,None,{}).mark_published(r['id'])
  r['state']='PUBLISHED';atomic_json(p,r)
 def execute_tool(self,task,world,bank,config,origin=None):
  """Run one broker action through the same durable journal as queued tasks.

  The record is written before execution; an existing record is never rerun."""
  from tools import Toolbox,rejection_reason
  ident=task['id'];raw=(json.dumps(task,ensure_ascii=False,sort_keys=True)+'\n').encode();check_secrets(raw)
  digest=hashlib.sha256(raw).hexdigest();p=self.state/(ident+'.json')
  if p.exists():
   r=recover(p)
   if r['hash']!=digest:raise ValueError('task ID reused with different bytes')
   return r.get('result') or {'status':'INTERRUPTED','output':'No recorded result; no automatic retry.'}
  if world.snapshot()['state'] in ('HALTED','EXTINCT') or bank.snapshot()['state'] in ('HALTED','EXTINCT'):
   return {'status':'REJECTED','output':'GlobalLand is stopped'}
  from initiative import Store,settings
  store=Store(self.root,config) if settings(config)['enabled'] else None
  if store:
   turn=origin[0] if isinstance(origin,tuple) and len(origin)==2 else None
   cause=store.turn_cause(turn)
   if cause is None:raise ValueError('Broker admission lineage unavailable')
   store.bind_task(task,turn=turn,cause=cause,origin='broker')
   store.bind_input(task['id'],digest)
  r={'id':ident,'hash':digest,'task':None,'origin':'broker','request':task,'state':'RUNNING','files':{},'base_sha':self.git('rev-parse','HEAD').decode().strip()};atomic_json(p,r)
  try:
   try:result,generated=Toolbox(self.root,world,bank,config).run(task,origin=origin)
   except (ValueError,UnicodeError) as error:result,generated={'status':'REJECTED','output':rejection_reason(error)},{}
   if not {'status','output'}<=set(result):raise ValueError('invalid tool result')
   # Projections are published once by the turn itself, not per action.
   r['result']=result;r['files'].update(generated);r['state']='COMPLETED'
  except Exception:
   r['state']='INTERRUPTED';r['result']={'status':'INTERRUPTED','output':'Broker action failed; inspect host journal. No automatic retry.'}
  atomic_json(p,r)
  result=dict(r['result'])
  try:
   self.finish(p,r)
  except Exception:
   # The effect already happened and is durably recorded; the next cycle
   # publishes it. Say so, so the brain does not resubmit the same work.
   result['publication']='PENDING: effect recorded; publication retried next cycle. Do not resubmit.'
  else:
   # Later actions in this turn see the published files without a full re-extract.
   self.write_work(r['files'])
  return result
 def write_work(self,files):
  work=self.root/'work'
  for name,text in files.items():
   if not allowed(safe_path(name)):continue
   path=work
   for part in name.split('/'):
    path=path/part
    if path.is_symlink():raise ValueError('symlink in work tree')
   path.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
   path.write_text(text);path.chmod(0o644)
 def refresh_work(self):
  import shutil
  work=self.root/'work'
  if work.exists():shutil.rmtree(work)
  work.mkdir(mode=0o755)
  extract_archive(self.git('archive','--format=tar','HEAD'),work)
 def cleanup_abandoned_job(self,ident):
  import shutil
  if not re.fullmatch(r'TASK-[0-9]{4,12}',ident):return
  job=self.root/'jobs'/ident
  if not job.exists():return
  env={'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'}
  name='globalland-job-'+ident.lower()
  code,out=bounded_run(['docker','ps','-aq','--filter','name=^/'+name+'$'],env=env,limit=4096,timeout=30)
  if code:raise RuntimeError('Cannot reconcile abandoned GlobalLand container; Docker unavailable')
  if out.strip():
   code,_=bounded_run(['docker','rm','-f',name],env=env,limit=4096,timeout=30)
   if code:raise RuntimeError('Cannot stop abandoned GlobalLand container')
  shutil.rmtree(job)
 def cycle(self,mode):
  """Compatibility entry; native CLI dispatch already holds this same lock."""
  self.state.mkdir(parents=True,exist_ok=True)
  with (self.state/'supervisor.lock').open('a') as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX | (fcntl.LOCK_NB if mode=='wake' else 0))
   except BlockingIOError:return {'state':'BUSY'}
   return self.dispatch(mode)
 def dispatch(self,mode,*,now=None):
  """Local admission under supervisor.lock, before any cycle network work."""
  if mode not in ('wake','think','mail','queue','daily'):raise ValueError('invalid supervisor mode')
  seconds=int(time.time() if now is None else now)
  world,bank,config=self.services()
  from initiative import Store,settings
  policy=settings(config)
  ws,bs=world.snapshot()['state'],bank.snapshot()['state']
  stopped=ws in ('HALTED','EXTINCT') or bs in ('HALTED','EXTINCT')
  if not policy['enabled']:
   if mode=='wake':return {'state':'DISABLED'}
   self._cycle(mode,now=seconds,productive=not stopped)
   return {'state':'DEFERRED' if stopped else 'COMPLETED'}
  store=Store(self.root,config)
  stopped=stopped or store.suppressed()
  resumable=store.recover(now=seconds)
  store.reconcile(world.snapshot(),now=seconds)
  if stopped:
   store.claim('wake',now=seconds,world_state=ws,bank_state=bs)
   if mode!='wake':self._cycle(mode,store=store,now=seconds,productive=False)
   return {'state':'SUPPRESSED_EXTINCT' if store.suppressed() else 'DEFERRED'}
  if mode in ('queue','daily'):
   self._cycle(mode,store=store,now=seconds)
   return {'state':'COMPLETED'}
  target=None if mode=='wake' else ('DIRECTOR' if mode=='think' else 'PRIVATE_MAIL')
  admission=next((r for r in resumable if target is None or r['target']==target),None)
  if admission is None:admission=store.claim(mode,now=seconds,world_state=ws,bank_state=bs)
  if admission is None:
   # Periodic think retains orphan decision/publication recovery and queue work.
   # Idle wake does absolutely no cycle network/recovery work.
   if mode=='think':
    self._cycle('think',store=store,now=seconds,productive=False)
    self._cycle('queue',store=store,now=seconds)
   return {'state':'IDLE'}
  lane='think' if admission['target']=='DIRECTOR' else 'mail'
  self._cycle(lane,store=store,admission=admission,now=seconds,
              productive=admission['phase']=='CLAIMED')
  if lane=='think':self._cycle('queue',store=store,now=seconds)
  store.reconcile(world.snapshot(),now=seconds)
  return {'state':'COMPLETED','wake_id':admission['wake_id'],'target':admission['target']}
 def _cycle(self,mode,*,store=None,admission=None,now=None,productive=True):
  self.state.mkdir(parents=True,exist_ok=True)
  # First finish every local terminal journal, then retry local Git commits and fetch.
  for p in sorted(self.state.glob('*.json')):
   r=recover(p)
   self.cleanup_abandoned_job(r.get('id',p.stem))
   if r['state']=='INTERRUPTED' and not r.get('task') and r.get('origin')!='broker':raise RuntimeError('Interrupted daily audit: operator review required; restore from journal backup or acknowledge after reconciliation')
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
  world,bank,config=self.services()
  if (self.root/'integrations/finance').is_file() and bank.snapshot()['state']!='EXTINCT':
   from gateway import Gateway
   try:Gateway(self.root,bank).sync()
   except Exception:
    print('Account synchronization incomplete; inspect private integration. Unverified receipts are not credited.',file=sys.stderr)
  if bank.snapshot()['state']=='EXTINCT':
   world.apply('bank-extinction',{'op':'extinguish','reason':'Verified owned GlobalLand capital exhausted'})
   atomic_json(self.state/'private'/'EXTINCT.json',{'terminal':True,'reason':bank.snapshot()['extinction_reason']})
   self.publish({'id':'EXTINCTION','files':self.projections(world,bank,config),'base_sha':self.git('rev-parse','HEAD').decode().strip()})
   return
  for name,text in self.projections(world,bank,config).items():
   target=work/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text);target.chmod(0o644)
  if mode=='mail':
   # Private correspondence never enters task journals, WORLD or Git output.
   if not productive or bank.snapshot()['state'] in ('HALTED','EXTINCT') or world.snapshot()['state'] in ('HALTED','EXTINCT'):return
   from mail_agent import run_mail_cycle
   if admission:store.start(admission['wake_id'],prepared=None,now=now)
   try:
    if admission:run_mail_cycle(self.root,config,on_processed=lambda receipt:store.processed(admission['wake_id'],receipt))
    else:run_mail_cycle(self.root,config)
   except Exception:raise RuntimeError('Private mail cycle failed; inspect private mail status') from None
   if admission:store.finish(admission['wake_id'],turn=None,now=now)
   return
  if mode=='think':
   from controller import Controller
   planner=Controller(self.root,world,bank,config)
   planner.executor=lambda task:self.execute_tool(task,world,bank,config,origin=('THINK-%d'%planner.turn_seconds,getattr(planner,'current_provider',None) or 'unknown'))
   pending=any(json.loads(p.read_text()).get('published') is not True for p in (self.state/'controller').glob('THINK-*.json'))
   if not pending and (not productive or bank.snapshot()['state'] in ('HALTED','EXTINCT') or world.snapshot()['state'] in ('HALTED','EXTINCT')):return
   if not planner.readiness().get('configured'):
    self.publish({'id':'READINESS','files':self.projections(world,bank,config),'base_sha':self.git('rev-parse','HEAD').decode().strip()});return
   try:
    if admission:
     planner.initiative_lineage=admission['cause']
     prepared=(admission.get('prepared') if admission['phase']=='DECISION_READY' else
               planner.prepare_context(priority=admission['events']))
     turn,files=planner.tick(int(admission['turn'].split('-')[1]),prepared=prepared,
                            before_plan=lambda:store.start(admission['wake_id'],prepared=prepared,now=now))
    else:turn,files=planner.tick()
   except Exception as error:
    message='Controller planning failed; inspect state/private/controller-failure.json'
    try:
     details=failure_details(error)
     private=self.state/'private';private.mkdir(parents=True,exist_ok=True,mode=0o700)
     atomic_json(private/'controller-failure.json',{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':'planner.tick','providers':[p for p in config.get('controller',{}).get('providers',[]) if p in ('codex','claude','cursor')],**details})
     files=self.projections(world,bank,config);status=json.loads(files['world/controller.json'])
     status.update(state='CONTROLLER_BLOCKED',reason=message+'; no API fallback',reason_code=details['reason'],exception_type=details['exception_type'])
     files['world/controller.json']=json.dumps(status)+'\n'
     self.publish({'id':'READINESS','files':files,'base_sha':self.git('rev-parse','HEAD').decode().strip()})
    except Exception:
     raise RuntimeError(message+'; blocked-state reporting incomplete') from None
    raise RuntimeError(message) from None
   p=self.state/(turn+'.json')
   r={'id':turn,'hash':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),'task':None,'state':'COMPLETED','files':{**files,**self.projections(world,bank,config,planner)},'base_sha':self.git('rev-parse','HEAD').decode().strip()}
   atomic_json(p,r);self.finish(p,r)
   if admission:store.finish(admission['wake_id'],turn=turn,now=now)
   return
  if not productive or bank.snapshot()['state'] in ('HALTED','EXTINCT') or world.snapshot()['state'] in ('HALTED','EXTINCT'):return
  if mode=='daily':jobs=[('DAILY-'+datetime.datetime.now(datetime.timezone.utc).date().isoformat(),None)]
  else:
   jobs=[]
   for f in sorted((work/'queue/inbox').glob('*.json')):
    if not re.fullmatch(r'TASK-[0-9]{4,12}\.json',f.name):raise ValueError('invalid inbox filename; operator review required')
    jobs.append((f.stem,'queue/inbox/'+f.name))
  for ident,rel in jobs:
   if bank.snapshot()['state'] in ('HALTED','EXTINCT') or world.snapshot()['state'] in ('HALTED','EXTINCT'):break
   if rel and not (work/rel).exists():continue
   raw=(work/rel).read_bytes() if rel else ident.encode();check_secrets(raw);digest=hashlib.sha256(raw).hexdigest();p=self.state/(ident+'.json')
   if p.exists():
    r=recover(p)
    if r['hash']!=digest:raise ValueError('task ID reused with different bytes')
    if rel:raise ValueError('published task replayed; operator review required')
    continue
   r={'id':ident,'hash':digest,'task':rel,'state':'RUNNING','files':{},'base_sha':self.git('rev-parse','HEAD').decode().strip()}
   try:
    generated={}
    try:task_data=strict_json(raw) if rel else None
    except (ValueError,UnicodeError):task_data={'type':'TOOL'}
    if task_data and task_data.get('type')=='TOOL':
     from tools import Toolbox,TOOL_ACTIONS
     action=task_data.get('action')
     if isinstance(action,str) and action in TOOL_ACTIONS:
      # Keep ordinary next-turn feedback usable with initiative disabled too.
      # Only the validated action/type are retained, never request arguments.
      r['metadata']={'type':'TOOL','action':action}
     if store:
      from initiative import digest as initiative_digest
      cause=store.task_cause(ident) or {'root_id':initiative_digest(['external-task',ident,digest]),'parent_turn':None,'depth':0}
      store.bind_task(task_data,turn=None,cause=cause,origin='external')
      store.bind_input(ident,digest)
     atomic_json(p,r)  # Claim intent and journal precede every productive effect.
     try:result,generated=Toolbox(self.root,world,bank,config).run(task_data)
     except (ValueError,UnicodeError) as error:
      from tools import rejection_reason
      result={'status':'REJECTED','output':rejection_reason(error)}
    else:
     atomic_json(p,r)
     if not rel:world.apply('cycle-'+ident[6:],{'op':'cycle','cycle_id':ident[6:]})
     result=self.worker('task' if rel else 'daily',rel or ident[6:])
    if rel:
     if not {'status','output'}<=set(result) or result['status'] not in ('DONE','REJECTED','FAILED','TIMEOUT'):raise ValueError('invalid worker result')
     r['result']=result
     r['files'].update(generated)
    else:
     expected={'ledger.json','logs/transactions.log',f"bank/audits/audit-{ident[6:]}.md"}
     if set(result)!=expected:raise ValueError('unexpected daily artifacts')
     r['files']=result
    r['files'].update(self.projections(world,bank,config))
    r['state']='COMPLETED'
   except Exception:
    r['state']='INTERRUPTED'
    if rel:r['result']={'status':'INTERRUPTED','output':'Worker failed; inspect host journal. No automatic retry.'}
    else:atomic_json(p,r);raise
   atomic_json(p,r)
   if store and rel:store.recorded_result(ident,now=int(time.time() if now is None else now))
   self.finish(p,r)
   self.refresh_work()
def main():
 if len(sys.argv)!=2 or sys.argv[1] not in ('queue','daily','think','mail','wake','status'):raise ValueError('usage: supervisor.py queue|daily|think|mail|wake|status')
 ROOT.joinpath('state').mkdir(parents=True,exist_ok=True)
 with open(ROOT/'state/supervisor.lock','a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX | (fcntl.LOCK_NB if sys.argv[1]=='wake' else 0))
  except BlockingIOError:return {'state':'BUSY'}
  app=Supervisor()
  if sys.argv[1]=='status':
   w,b,c=app.services();print(json.dumps({'bank':b.snapshot(),'world':w.snapshot(),'controller_config':c.get('controller',{}).get('mode','external_grok')},indent=2))
  else:return app.dispatch(sys.argv[1])
if __name__=='__main__':
 try:main()
 except Exception as e:print('GlobalLand stopped: '+str(e),file=sys.stderr);sys.exit(1)
