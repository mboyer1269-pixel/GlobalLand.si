"""Broad agent tools with host-owned credentials and disposable product workspaces."""
import base64
import hashlib
import http.client
import ipaddress
import json
import os
import pathlib
import re
import shutil
import socket
import ssl
import subprocess
import urllib.parse
from supervisor import bounded_run, check_secrets, safe_path

TOOL_ACTIONS = {'EXEC', 'FETCH', 'WORLD', 'STATUS', 'SPEND', 'RECONCILE', 'PUBLISH_ACTOR', 'ACTOR_STATS', 'PUBLISH_SITE'}
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
    elif action=='PUBLISH_SITE':
        if 'site' not in args or set(args)-{'site','dry_run','online'}:raise ValueError('publish site requires a site')
        if any(not isinstance(args.get(k,False),bool) for k in ('dry_run','online')):raise ValueError('dry_run and online must be boolean')
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

def task_origin(root,task):
    """Host-known origin of a task: (turn, provider). The brain cannot choose it.

    Tasks from a think turn carry TASK-<turn seconds><slot>; the provider of that
    turn is read from the host's own controller record. Anything else (an inbox
    task pushed through GitHub, e.g. by Grok) is EXTERNAL."""
    match=re.fullmatch(r'TASK-([0-9]{10})([0-9]{2})',task.get('id',''))
    if match:
        record=pathlib.Path(root)/'state'/'controller'/('THINK-%d.json'%int(match.group(1)))
        if record.is_file():
            try:
                provider=json.loads(record.read_text()).get('provider')
                if provider in ('codex','claude','cursor'):return ('THINK-%d'%int(match.group(1)),provider)
            except ValueError:pass
    return ('EXTERNAL-'+task.get('id','?'),'EXTERNAL')


def capability_view(root, config):
    """Local prerequisites only; never infer working auth from a file or flag.

    Fixed messages deliberately exclude configuration values and credentials.
    No network call or credential read is needed to build this observation.
    """
    root = pathlib.Path(root)

    def private_token(service):
        path = root / 'credentials' / service / 'token'
        try:
            return (not any(p.is_symlink() for p in (root / 'credentials', path.parent, path))
                    and path.is_file() and not path.stat().st_mode & 0o077 and path.stat().st_size > 0)
        except OSError:
            return False

    def view(missing, constraints):
        return dict(state='NOT_CONFIGURED' if missing else 'CONFIGURED_UNVERIFIED',
                    missing=missing, constraints=constraints)

    image = config.get('executor_image')
    executor = config.get('executor_enabled') is True and isinstance(image, str) and bool(
        re.fullmatch(r'[A-Za-z0-9./:_-]+@sha256:[0-9a-f]{64}', image))
    result = {'EXEC': view([] if executor else ['enabled executor with pinned image'],
                           'no direct network; use FETCH for public HTTP(S); only installed image programs are available; publish declared products outputs')}
    for action in ('FETCH', 'WORLD', 'STATUS'):
        result[action] = dict(state='BUILT_IN', missing=[], constraints={
            'FETCH': 'public HTTP(S) GET only; no authenticated sessions; 1 MiB response limit; reachability unverified',
            'WORLD': 'live resident identity required; action owner must match submitted_by; economy and registration require DIRECTOR',
            'STATUS': 'observation only; configuration is not proof of connectivity or revenue'}[action])
    for service, actions in (('apify', ('PUBLISH_ACTOR', 'ACTOR_STATS')), ('cloudflare', ('PUBLISH_SITE',))):
        module = __import__('apify' if service == 'apify' else 'sites')
        try:
            configured = module.settings(config) is not None
        except (ValueError, TypeError):
            configured = False
        missing = ([] if configured else ['valid enabled ' + service + ' configuration'])
        if not private_token(service):
            missing.append('private ' + service + ' credential file with mode 0600')
        for action in actions:
            result[action] = view(list(missing), 'account access and remote service unverified; public publication may require an independent review')
    adapter = root / 'integrations' / 'finance'
    try:
        finance = (not (root / 'integrations').is_symlink() and not adapter.is_symlink()
                   and adapter.is_file() and not adapter.stat().st_mode & 0o022 and os.access(adapter, os.X_OK))
    except OSError:
        finance = False
    for action in ('SPEND', 'RECONCILE'):
        result[action] = view([] if finance else ['installed trusted executable finance adapter'],
                              'verified available CAD required for SPEND; adapter and receipts unverified; GLC is virtual')
    mail = config.get('agentmail') or {}
    configured_mail = (isinstance(mail, dict) and mail.get('enabled') is True
                       and isinstance(mail.get('inbox_id'), str) and bool(mail['inbox_id'])
                       and isinstance(mail.get('inbox_address'), str) and '@' in mail['inbox_address'])
    missing_mail = [] if configured_mail else ['enabled private AgentMail inbox configuration']
    if not private_token('agentmail'):
        missing_mail.append('private agentmail credential file with mode 0600')
    result['PRIVATE_MAIL'] = view(missing_mail,
        'separate private correspondence cycle receives and replies using the subscription brain; '
        'not a submit_action tool; no message bodies or customer details belong in public tasks; '
        'configuration does not prove receipt, delivery or a running mail schedule')
    fulfillment = mail.get('fulfillment') if isinstance(mail, dict) else None
    if isinstance(fulfillment, dict) and fulfillment.get('enabled') is True:
        missing_work = list(missing_mail)
        if not executor:
            missing_work.append('enabled executor with pinned image')
        for key, default, maximum in (('max_steps_per_cycle', 2, 4), ('max_steps_per_case', 8, 16)):
            value = fulfillment.get(key, default)
            if type(value) is not int or not 1 <= value <= maximum:
                missing_work.append('valid private work step limits')
                break
        result['PRIVATE_MAIL']['fulfillment'] = view(missing_work,
            'case-local offline EXEC, durable results and inline UTF-8 artifact replies; '
            'no public case data, new URL retrieval or incoming attachments; '
            'configured is not proof of execution or recipient delivery')
    else:
        result['PRIVATE_MAIL']['fulfillment'] = {'state': 'DISABLED'}
    mail_status = root / 'state/private/agentmail-status.json'
    try:
        if (configured_mail and not any(p.is_symlink() for p in (root/'state', mail_status.parent, mail_status))
                and mail_status.is_file() and mail_status.stat().st_size < 4096):
            observation = json.loads(mail_status.read_text())
            safe_observation = {k: v for k, v in observation.items()
                                if k in ('processed', 'accepted', 'ignored', 'unknown', 'failed', 'skipped', 'retry')
                                and type(v) is int and v >= 0}
            at = observation.get('observed_at')
            if isinstance(at, str) and re.fullmatch(r'[0-9T:+.Z-]{20,40}', at):
                safe_observation['observed_at'] = at
            result['PRIVATE_MAIL']['last_cycle'] = safe_observation
    except (OSError, ValueError, AttributeError):
        pass
    return result


class Toolbox:
    def __init__(self,root,world,treasury,config=None):
        self.root=pathlib.Path(root);self.world=world;self.treasury=treasury;self.config=config or {}
    def run(self,task,origin=None):
        validate_envelope(task)
        origin=origin or task_origin(self.root,task)
        if self.treasury.snapshot()['state'] in ('EXTINCT','HALTED'):raise ValueError('GlobalLand is stopped')
        action,args=task['action'],task['args'];files={}
        if action != 'STATUS':self.world.require_active(task['submitted_by'])
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
            if any(isinstance(k,str) and k.startswith('host_') for k in args):raise ValueError('host fields are reserved')
            if args.get('op')=='review':
                # Reviewer provenance is set by the host, never by the brain.
                args=dict(args,host_turn=origin[0],host_provider=origin[1])
            value=self.world.apply(task['id'],args,actor=task['submitted_by'])
            return {'status':'DONE','output':json.dumps(value,ensure_ascii=False)},{}
        if action=='STATUS':return {'status':'DONE','output':json.dumps({'world':self.world.snapshot(),'bank':self.treasury.snapshot(),'capabilities':capability_view(self.root,self.config)},ensure_ascii=False)},{}
        if action=='PUBLISH_SITE':
            from sites import Publisher as SitePublisher
            result=SitePublisher(self.root,self.config,reviews=self.world.reviews() if hasattr(self.world,'reviews') else [],origin=origin).publish(task)
            return {'status':SitePublisher.task_status(result),'output':json.dumps(result,ensure_ascii=False)[:8000]},{}
        if action in ('PUBLISH_ACTOR','ACTOR_STATS'):
            from apify import Publisher
            publisher=Publisher(self.root,self.config,reviews=self.world.reviews() if hasattr(self.world,'reviews') else [],origin=origin)
            if action=='ACTOR_STATS':return {'status':'DONE','output':json.dumps(publisher.stats(task),ensure_ascii=False)},{}
            result=publisher.publish(task)
            return {'status':Publisher.task_status(result),'output':json.dumps(result,ensure_ascii=False)[:8000]},{}
        from gateway import Gateway
        gateway=Gateway(self.root,self.treasury)
        result=gateway.spend(task) if action=='SPEND' else gateway.reconcile(args['operation_id'])
        return {'status':'DONE','output':json.dumps(result)},{}
