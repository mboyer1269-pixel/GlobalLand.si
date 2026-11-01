"""Broad agent tools with host-owned credentials and disposable product workspaces."""
import base64
import hashlib
import http.client
import ipaddress
import json
import pathlib
import re
import shutil
import socket
import ssl
import subprocess
import urllib.parse
from supervisor import bounded_run, check_secrets, safe_path

TOOL_ACTIONS = {'EXEC', 'FETCH', 'WORLD', 'STATUS', 'SPEND', 'RECONCILE', 'PUBLISH_ACTOR', 'ACTOR_STATS'}
_RULE_MODULES = ('tools.py', 'world.py', 'treasury.py', 'gateway.py', 'supervisor.py', 'decision_protocol.py', 'broker.py')
# 'Invalid ' + name / 'Unknown ' + key in world.py take code-defined names only.
_RULE_PATTERN = re.compile(r'(?:Invalid|Unknown) [A-Za-z_]{1,30}(?: [A-Za-z_]{1,30}){0,3}|HTTP [1-5][0-9][0-9]')
_RULES = None


def _rule_messages():
    """Messages written as string literals in the installed control code.

    Only these, or the closed patterns above, may be published: exception text
    built from external data could carry credentials or untrusted content."""
    global _RULES
    if _RULES is None:
        import ast
        found = set()
        for name in _RULE_MODULES:
            path = pathlib.Path(__file__).with_name(name)
            if not path.is_file():
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
                    arg = node.exc.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        found.add(arg.value)
        _RULES = frozenset(found)
    return _RULES


def rejection_reason(error):
    """Explain a refused tool request so agents can correct the next one."""
    detail = error.args[0] if len(error.args) == 1 and isinstance(error.args[0], str) else None
    safe = getattr(type(error), 'safe_message', False) is True
    if detail is not None and len(detail) <= 200 and (safe or detail in _rule_messages() or _RULE_PATTERN.fullmatch(detail)):
        try:
            check_secrets(detail.encode())
            return 'Tool request refused: ' + detail + '. See queue/PROTOCOL.md.'
        except ValueError:
            pass
    return 'Tool request refused (' + type(error).__name__ + '); detail withheld because it is not a fixed protocol rule. See queue/PROTOCOL.md.'


def product_path(name):
    safe_path(name)
    if not name.startswith('products/') or len(name)>240 or any(p.startswith('.') for p in name.split('/')):
        raise ValueError('outputs must be public products paths')
    return name

def validate_envelope(t):
    allowed={'id','type','submitted_by','created_at','action','args','description','estimated_cost_cad','approved_by'}
    if not isinstance(t,dict) or set(t)-allowed: raise ValueError('unknown envelope fields')
    if not isinstance(t.get('id'),str) or not re.fullmatch(r'TASK-[0-9]{4,12}',t['id']):raise ValueError('invalid task id')
    if t.get('type')!='TOOL' or t.get('action') not in TOOL_ACTIONS:raise ValueError('unknown tool')
    if not re.fullmatch(r'[A-Z0-9_-]{1,64}',t.get('submitted_by','')):raise ValueError('invalid agent')
    if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',t.get('created_at','')):raise ValueError('invalid timestamp')
    if type(t.get('estimated_cost_cad')) not in (int,float) or t['estimated_cost_cad']!=0:raise ValueError('tool envelope is free; paid amounts come from gateway quote')
    if t.get('approved_by') is not None:raise ValueError('no per-action approval labels')
    args=t.get('args')
    if not isinstance(args,dict):raise ValueError('tool arguments must be object')
    action=t['action']
    if action=='EXEC':
        if set(args)-{'argv','cwd','outputs','mission_id'}:raise ValueError('unknown exec argument')
        argv=args.get('argv')
        if not isinstance(argv,list) or not 1<=len(argv)<=128 or any(not isinstance(a,str) or len(a)>8192 or '\x00' in a for a in argv) or not argv[0]:raise ValueError('invalid argv')
        cwd=args.get('cwd','')
        if cwd:safe_path(cwd)
        outputs=args.get('outputs',[])
        if not isinstance(outputs,list) or len(outputs)>64:raise ValueError('output count limit')
        for name in outputs:product_path(name)
    elif action=='FETCH':
        if set(args)-{'url','output','encoding'}:raise ValueError('unknown fetch argument')
        if not isinstance(args.get('url'),str) or len(args['url'])>8192:raise ValueError('invalid URL')
        product_path(args.get('output',''))
        if args.get('encoding','utf-8') not in ('utf-8','base64'):raise ValueError('unsupported output encoding')
    elif action=='WORLD' and args.get('op')=='extinguish':raise ValueError('extinction is triggered by verified treasury state')
    elif action=='STATUS' and args:raise ValueError('status takes no arguments')
    elif action=='SPEND':
        if set(args)!={'request'} or not isinstance(args['request'],dict):raise ValueError('spend requires a gateway request')
    elif action=='PUBLISH_ACTOR':
        if not {'actor','title','description'}<=set(args) or set(args)-{'actor','title','description','public','events'}:raise ValueError('publish actor requires actor, title and description')
        if not isinstance(args.get('public',False),bool):raise ValueError('public must be boolean')
    elif action=='ACTOR_STATS':
        if set(args)!={'actor'}:raise ValueError('actor stats requires exactly an actor')
    elif action=='RECONCILE':
        if set(args)!={'operation_id'} or not re.fullmatch(r'TASK-[0-9]{4,12}',args.get('operation_id','')):raise ValueError('invalid operation')
    return t

def public_target(url,resolver=socket.getaddrinfo):
    p=urllib.parse.urlsplit(url)
    try:port=p.port or (443 if p.scheme=='https' else 80)
    except ValueError:raise ValueError('invalid port') from None
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or port not in (80,443):raise ValueError('public HTTP(S) URL required')
    addresses=resolver(p.hostname,port,type=socket.SOCK_STREAM)
    ips=[]
    for a in addresses:
        ip=ipaddress.ip_address(a[4][0])
        if not ip.is_global:raise ValueError('private/local/metadata destination refused')
        ips.append(str(ip))
    if not ips:raise ValueError('no public address')
    return p,port,ips[0]

def fetch_public(url,limit=1024*1024):
    """Pin the validated address on each redirect, preserving HTTPS hostname validation."""
    for _ in range(6):
        p,port,ip=public_target(url)
        conn=http.client.HTTPConnection(p.hostname,port,timeout=20)
        sock=socket.create_connection((ip,port),timeout=20)
        if p.scheme=='https':sock=ssl.create_default_context().wrap_socket(sock,server_hostname=p.hostname)
        conn.sock=sock
        try:
            target=urllib.parse.urlunsplit(('', '', p.path or '/',p.query,''))
            conn.request('GET',target,headers={'Host':p.netloc,'User-Agent':'GlobalLand/3 public research','Accept-Encoding':'identity'})
            response=conn.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:raise ValueError('redirect missing location')
                url=urllib.parse.urljoin(url,location);continue
            if response.status>=400:raise ValueError('HTTP '+str(response.status))
            raw=response.read(limit+1)
            if len(raw)>limit:raise ValueError('fetch size limit')
            check_secrets(raw)
            return raw,url,response.status
        finally:conn.close()
    raise ValueError('redirect limit')

def collect_outputs(root,names):
    result={};total=0
    for name in names:
        product_path(name);p=root
        for part in name.split('/'):
            p=p/part
            if p.is_symlink():raise ValueError('symlink output refused')
        if not p.is_file() or p.stat().st_nlink!=1:raise ValueError('regular independent output required')
        size=p.stat().st_size
        total+=size
        if size>1024*1024 or total>8*1024*1024:raise ValueError('artifact size limit')
        raw=p.read_bytes();check_secrets(raw)
        try:result[name]=raw.decode('utf-8')
        except UnicodeDecodeError:raise ValueError('binary output: encode as base64 text before publishing') from None
    return result

def sandbox_command(ident,workspace,image,args):
    if not re.fullmatch(r'TASK-[0-9]{4,12}',ident):raise ValueError('invalid task id')
    if not re.fullmatch(r'[A-Za-z0-9./:_-]+@sha256:[0-9a-f]{64}',image):raise ValueError('pinned image digest required')
    # workspace is a host-owned per-job directory with input/ and request.json.
    control=workspace.parent.parent.parent/'control'/'executor.js'
    return ['docker','run','--rm','--name','globalland-job-'+ident.lower(),'--network','none','--read-only','--user','65534:65534','--cap-drop','ALL','--security-opt','no-new-privileges:true','--memory','1g','--cpus','0.5','--pids-limit','128','--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--tmpfs','/workspace:rw,nosuid,size=256m,uid=65534,gid=65534','--mount',f'type=bind,src={workspace / "input"},dst=/input,readonly','--mount',f'type=bind,src={workspace / "request.json"},dst=/request.json,readonly','--mount',f'type=bind,src={control},dst=/executor.js,readonly','--workdir','/workspace',image,'node','/executor.js']

class Toolbox:
    def __init__(self,root,world,treasury,config=None):
        self.root=pathlib.Path(root);self.world=world;self.treasury=treasury;self.config=config or {}
    def run(self,task):
        validate_envelope(task)
        if self.treasury.snapshot()['state'] in ('EXTINCT','HALTED'):raise ValueError('GlobalLand is stopped')
        action,args=task['action'],task['args'];files={}
        if action=='EXEC':
            if self.config.get('executor_enabled') is not True:raise ValueError('executor not configured; install v3 control/image')
            job=self.root/'jobs'/task['id'];workspace=job/'workspace'
            if job.exists():raise ValueError('workspace exists after uncertain execution; use a new task ID')
            workspace.mkdir(parents=True,mode=0o755)
            shutil.copytree(self.root/'work',workspace/'input')
            (workspace/'request.json').write_text(json.dumps(args));(workspace/'request.json').chmod(0o644)
            command=sandbox_command(task['id'],workspace,self.config['executor_image'],args)
            try:
                code,output=bounded_run(command,env={'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'},limit=10*1024*1024)
                check_secrets(output)
                if code:return {'status':'FAILED','output':'Sandbox failed; no files published.'},{}
                value=json.loads(output)
                if not isinstance(value,dict) or value.get('status') not in ('DONE','FAILED','TIMEOUT') or not isinstance(value.get('files'),dict):raise ValueError('invalid sandbox response')
                if value['status']!='DONE':return {'status':value['status'],'output':str(value.get('output',''))[:8000]},{}
                files=value['files']
                if set(files)!=set(args.get('outputs',[])):raise ValueError('unexpected artifact set')
                total=0
                for name,text in files.items():
                    product_path(name)
                    if not isinstance(text,str):raise ValueError('invalid artifact')
                    raw=text.encode();total+=len(raw)
                    if len(raw)>1024*1024 or total>8*1024*1024:raise ValueError('artifact size limit')
                    check_secrets(raw)
                provenance={'task':task['id'],'outputs':{n:hashlib.sha256(v.encode()).hexdigest() for n,v in files.items()}}
                files['products/receipts/'+task['id']+'.json']=json.dumps(provenance,indent=2)+'\n'
                result={'status':'DONE','output':str(value.get('output',''))[:8000],'artifacts':list(files)}
            finally:
                name='globalland-job-'+task['id'].lower()
                removed=subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
                absent=removed.returncode==0
                if not absent:
                    listing=subprocess.run(['docker','ps','-aq','--filter','name=^/'+name+'$'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=30)
                    absent=listing.returncode==0 and not listing.stdout.strip()
                if absent:shutil.rmtree(job,ignore_errors=True)
            return result,files
        if action=='FETCH':
            raw,url,status=fetch_public(args['url'])
            text=base64.b64encode(raw).decode() if args.get('encoding')=='base64' else raw.decode('utf-8')
            files[args['output']]=text
            return {'status':'DONE','output':json.dumps({'source':url,'http_status':status,'sha256':hashlib.sha256(raw).hexdigest(),'artifact':args['output']})},files
        if action=='WORLD':
            value=self.world.apply(task['id'],args)
            return {'status':'DONE','output':json.dumps(value,ensure_ascii=False)},{}
        if action=='STATUS':return {'status':'DONE','output':json.dumps({'world':self.world.snapshot(),'bank':self.treasury.snapshot()},ensure_ascii=False)},{}
        if action in ('PUBLISH_ACTOR','ACTOR_STATS'):
            from apify import Publisher
            publisher=Publisher(self.root,self.config,reviews=self.world.reviews() if hasattr(self.world,'reviews') else [])
            if action=='ACTOR_STATS':return {'status':'DONE','output':json.dumps(publisher.stats(task),ensure_ascii=False)},{}
            result=publisher.publish(task)
            return {'status':Publisher.task_status(result),'output':json.dumps(result,ensure_ascii=False)[:8000]},{}
        from gateway import Gateway
        gateway=Gateway(self.root,self.treasury)
        result=gateway.spend(task) if action=='SPEND' else gateway.reconcile(args['operation_id'])
        return {'status':'DONE','output':json.dumps(result)},{}
