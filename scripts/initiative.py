"""Host-only source identities and durable scheduling receipts. No external effects."""
import hashlib
import json
import pathlib
import re
import contextlib
import os
import sqlite3
import stat
import math
import time
import tempfile

HEX = re.compile(r'[0-9a-f]{64}')
TASK = re.compile(r'TASK-[0-9]{4,12}')
MISSION = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}')
TERMINAL = ('DONE', 'FAILED', 'REJECTED', 'TIMEOUT', 'INTERRUPTED')
KINDS = dict(COMMERCIAL_SIGNAL='DIRECTOR', QUEUED_RESULT='DIRECTOR',
             PRIVATE_RETRY_DUE='PRIVATE_MAIL', LEASE_DUE='DIRECTOR')
DEFAULTS = dict(enabled=False, debounce_seconds=60, director_spacing_seconds=300,
                mail_spacing_seconds=300, max_chain_depth=1, batch_size=64,
                scan_page_size=200, lease_notice_seconds=300)
RANGES = dict(debounce_seconds=(0, 3600), director_spacing_seconds=(1, 3600),
              mail_spacing_seconds=(1, 3600), max_chain_depth=(0, 8),
              batch_size=(1, 200), scan_page_size=(1, 2000), lease_notice_seconds=(0, 3600))
PHASES = ('CLAIMED','STARTED','DECISION_READY','ACKED','INTERRUPTED','OBSOLETE','SUPPRESSED_EXTINCT')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def settings(config):
    value = config.get('initiative', {})
    if (not isinstance(value, dict) or set(value) - set(DEFAULTS)
            or type(value.get('enabled', False)) is not bool):
        raise ValueError('Invalid initiative configuration')
    result = dict(DEFAULTS, **value)
    for key, (low, high) in RANGES.items():
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError('Invalid initiative configuration')
    return result


def _time(value):
    if type(value) is not int or value < 0: raise ValueError('Invalid initiative source')
    return value


def source_revision(kind, source):
    """Only validated values, never paths/mtime/publication state, define revisions."""
    if kind not in KINDS or not isinstance(source, dict):
        raise ValueError('Invalid initiative source')
    if kind in ('COMMERCIAL_SIGNAL', 'PRIVATE_RETRY_DUE'):
        inbox, mid = source.get('inbox_id'), source.get('message_id')
        if any(not isinstance(v, str) or not 1 <= len(v) <= 2048 for v in (inbox, mid)):
            raise ValueError('Invalid initiative source')
        key = hashlib.sha256((inbox + '\0' + mid).encode()).hexdigest()
        if kind == 'COMMERCIAL_SIGNAL':
            import commercial
            observation = source.get('observation')
            if (source.get('state') not in ('ACCEPTED', 'IGNORED', 'FAILED', 'RETRY')
                    or not commercial._valid_observation(observation)
                    or not commercial._interpreted(observation)):
                raise ValueError('Invalid initiative source')
            version = digest({k: v for k, v in observation.items() if k != 'observed_at'})
        else:
            if source.get('state') != 'RETRY': raise ValueError('Invalid initiative source')
            attempts = _time(source.get('attempts')); due = _time(source.get('retry_after'))
            if attempts < 1:raise ValueError('Invalid initiative source')
            version = digest(dict(state='RETRY', attempts=attempts, retry_after=due))
    elif kind == 'QUEUED_RESULT':
        key = source.get('id')
        request = source.get('request')
        if not isinstance(request, dict): request = source.get('task')
        if not isinstance(request, dict): request = source.get('metadata', {})
        result = source.get('result', source)
        input_hash = source.get('hash', source.get('input_sha256'))
        if (not isinstance(key, str) or not TASK.fullmatch(key)
                or not isinstance(input_hash, str) or not HEX.fullmatch(input_hash)
                or not isinstance(result, dict) or result.get('status') not in TERMINAL):
            raise ValueError('Invalid initiative source')
        version = digest([input_hash, result])
    else:
        key = source.get('mission_id')
        lease = dict(agent_id=source.get('agent_id'), token=source.get('lease_token'),
                     expires_at=source.get('lease_expires_at'))
        if (not isinstance(key, str) or not MISSION.fullmatch(key) or source.get('status') != 'RUNNING'
                or not isinstance(lease, dict) or not isinstance(lease.get('agent_id'), str)
                or not MISSION.fullmatch(lease['agent_id']) or not isinstance(lease.get('token'), str)
                or not 1 <= len(lease['token']) <= 256):
            raise ValueError('Invalid initiative source')
        expiry = lease.get('expires_at')
        # WORLD's existing clock stores fractional seconds. Preserve that exact
        # revision; only scheduling timestamps are rounded up to UTC seconds.
        if type(expiry) not in (int,float) or not math.isfinite(expiry) or expiry<0:
            raise ValueError('Invalid initiative source')
        version = digest([key, lease['agent_id'], lease['token'], expiry])
    return key, version


class Store:
    """SQLite authority for host scheduling, not model/runtime memory.

    Callers hold supervisor.lock. Transactions also make reservations/rate
    accounting atomic; configuration credentials never enter the database.
    """
    def __init__(self, root, config):
        self.root = pathlib.Path(root)
        self.policy = settings(config)
        self.config = config  # used only for current-inbox/source validation
        self.directory = self.root / 'state/private'
        self.path = self.directory / 'initiative.sqlite3'
        self.anchor = self.directory / 'initiative.initialized'
        self.bootstrap = self.directory / 'initiative.bootstrap.json'
        self._safe(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self._safe(self.path); self._safe(self.anchor);self._safe(self.bootstrap)
        existed = self.path.exists()
        if self.anchor.exists() and not existed: raise ValueError('Initiative storage unavailable')
        try:
            # This immutable census is durable before creating the database.
            # An aborted schema/baseline transaction must reuse this boundary,
            # never classify subsequent arrivals as historical on restart.
            inventory=self._bootstrap_inventory() if not existed else None
            with self._db() as db:
                tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                if not tables and not self.anchor.exists():
                    inventory=self._bootstrap_inventory() if inventory is None else inventory
                    schema='''
                        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                        CREATE TABLE baseline (kind TEXT, key TEXT, version TEXT,
                            PRIMARY KEY(kind,key,version));
                        CREATE TABLE events (id TEXT PRIMARY KEY, kind TEXT, key TEXT, version TEXT,
                            data TEXT NOT NULL, status TEXT NOT NULL, reservation TEXT,
                            periodic INTEGER NOT NULL DEFAULT 0);
                        CREATE TABLE admissions (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                        CREATE TABLE bindings (id TEXT PRIMARY KEY, input_hash TEXT NOT NULL,
                            data TEXT NOT NULL);
                        CREATE TABLE leases (version TEXT PRIMARY KEY, cause TEXT NOT NULL);
                        CREATE TABLE claim_intents (id TEXT PRIMARY KEY, mission TEXT NOT NULL,
                            pending INTEGER NOT NULL);
                        CREATE INDEX pending_claims ON claim_intents(pending,id);
                        CREATE INDEX mission_claims ON claim_intents(mission,pending);
                        CREATE TABLE processed (wake_id TEXT, key TEXT, version TEXT, data TEXT NOT NULL,
                            PRIMARY KEY(wake_id,key,version));
                    '''
                    # executescript implicitly commits an open transaction.
                    # Individual DDL keeps schema, baseline and completion atomic.
                    for statement in schema.split(';'):
                        if statement.strip():db.execute(statement)
                    for kind,key,version in inventory:
                        db.execute('INSERT OR IGNORE INTO baseline VALUES (?,?,?)',(kind,key,version))
                    self._put(db, 'schema', 1)
                if 'meta' not in tables and tables:raise ValueError('Initiative storage unavailable')
                if self._get(db, 'schema') != 1 or db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('Initiative storage unavailable')
                db.execute("CREATE INDEX IF NOT EXISTS pending_kind_due ON events(status,kind,json_extract(data,'$.not_before'))")
            if not self.anchor.exists():
                fd = os.open(self.anchor, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try: os.write(fd, b'1\n'); os.fsync(fd)
                finally: os.close(fd)
                if os.name != 'nt':
                    fd = os.open(self.directory, os.O_DIRECTORY)
                    try: os.fsync(fd)
                    finally: os.close(fd)
        except (sqlite3.Error, OSError, TypeError, KeyError, json.JSONDecodeError):
            raise ValueError('Initiative storage unavailable') from None

    def _bootstrap_inventory(self):
        if self.bootstrap.exists():
            record=self._read(self.bootstrap,64*1024*1024)
            if set(record)!={'schema','sources'} or type(record['schema']) is not int or record['schema']!=1 or not isinstance(record['sources'],list):
                raise ValueError('Initiative storage unavailable')
            for item in record['sources']:
                if (not isinstance(item,list) or len(item)!=3 or item[0] not in ('COMMERCIAL_SIGNAL','QUEUED_RESULT')
                        or not isinstance(item[1],str) or not (TASK if item[0]=='QUEUED_RESULT' else HEX).fullmatch(item[1])
                        or not isinstance(item[2],str) or not HEX.fullmatch(item[2])):
                    raise ValueError('Initiative storage unavailable')
            return record['sources']
        sources=[]
        for family in ('mail','tasks'):
            for path in self._paths(family):
                for kind,source in self._sources(family,path,None):
                    if kind in ('COMMERCIAL_SIGNAL','QUEUED_RESULT'):
                        key,version=source_revision(kind,source);sources.append([kind,key,version])
        fd,temporary=tempfile.mkstemp(prefix='.initiative-bootstrap-',dir=self.directory)
        try:
            os.chmod(temporary,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                stream.write(canonical(dict(schema=1,sources=sources)))
                stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.bootstrap)
            if os.name!='nt':
                directory=os.open(self.directory,os.O_DIRECTORY)
                try:os.fsync(directory)
                finally:os.close(directory)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)
        return sources

    @staticmethod
    def _safe(path):
        for item in (path, *path.parents):
            if item.is_symlink(): raise ValueError('Initiative storage unavailable')
        if path.exists():
            info = path.stat()
            if not (stat.S_ISDIR(info.st_mode) or (stat.S_ISREG(info.st_mode) and info.st_nlink == 1)):
                raise ValueError('Initiative storage unavailable')
            if hasattr(os, 'geteuid') and info.st_uid != os.geteuid():
                raise ValueError('Initiative storage unavailable')

    @contextlib.contextmanager
    def _db(self):
        for suffix in ('', '-journal', '-wal', '-shm'): self._safe(pathlib.Path(str(self.path)+suffix))
        db = sqlite3.connect(self.path, timeout=5)
        try:
            self.path.chmod(0o600)
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except sqlite3.Error:
            db.rollback()
            raise ValueError('Initiative storage unavailable') from None
        except BaseException:
            db.rollback(); raise
        finally:
            db.close()
            for suffix in ('', '-journal', '-wal', '-shm'):
                path = pathlib.Path(str(self.path)+suffix)
                if path.exists(): self._safe(path); path.chmod(0o600)

    @staticmethod
    def _get(db, key, default=None):
        row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def _put(db, key, value):
        db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key,canonical(value)))

    def _paths(self, family):
        directory = self.root / ('state/private/agentmail' if family == 'mail' else 'state')
        self._safe(directory)
        return sorted(directory.glob('*.json' if family == 'mail' else 'TASK-*.json'),key=lambda p:p.name)

    def _read(self, path, limit=1024*1024):
        self._safe(path)
        if not path.is_file() or path.stat().st_size > limit: raise ValueError('Invalid initiative source')
        raw = path.read_bytes()
        if len(raw)>limit: raise ValueError('Invalid initiative source')
        from_json = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(from_json,dict): raise ValueError('Invalid initiative source')
        return from_json

    def _sources(self, family, path, db):
        try:
            source = self._read(path,128*1024 if family=='mail' else 1024*1024)
            if family == 'mail':
                if (self.config.get('agentmail') or {}).get('enabled') is not True:return []
                if source.get('inbox_id') != (self.config.get('agentmail') or {}).get('inbox_id'): return []
                output=[]
                for kind in ('COMMERCIAL_SIGNAL','PRIVATE_RETRY_DUE'):
                    if kind=='COMMERCIAL_SIGNAL':
                        import commercial
                        if commercial.settings(self.config)['state']!='ENABLED':continue
                    try:key,_=source_revision(kind,source)
                    except ValueError:continue
                    if path.name==key+'.json':output.append((kind,source))
                return output
            ident=path.stem
            if not TASK.fullmatch(ident) or source.get('origin')=='broker':return []
            source=dict(source,id=ident)
            binding=db.execute('SELECT data FROM bindings WHERE id=?',(ident,)).fetchone() if db is not None else None
            metadata=json.loads(binding[0]) if binding else source.get('request',source.get('task'))
            if not isinstance(metadata,dict):metadata=source.get('metadata',{})
            if metadata.get('input_sha256',source.get('hash'))!=source.get('hash'):return []
            if (metadata.get('origin')=='broker' or metadata.get('type')!='TOOL'
                    or metadata.get('action') not in ('EXEC','FETCH','WORLD','SPEND','RECONCILE','PUBLISH_ACTOR','ACTOR_STATS','PUBLISH_SITE')):return []
            source['metadata']=metadata
            source_revision('QUEUED_RESULT',source)
            return [('QUEUED_RESULT',source)]
        except (OSError,ValueError,TypeError,KeyError):return []

    @staticmethod
    def _cause(value):
        if (not isinstance(value,dict) or set(value)!={'root_id','parent_turn','depth'}
                or not isinstance(value['root_id'],str) or not HEX.fullmatch(value['root_id'])
                or (value['parent_turn'] is not None and (not isinstance(value['parent_turn'],str)
                    or not re.fullmatch(r'THINK-[0-9]{1,10}',value['parent_turn'])))
                or type(value['depth']) is not int or not 0<=value['depth']<=8):
            raise ValueError('Invalid initiative cause')
        return dict(value)

    def _insert(self, db, kind, source, now):
        key,version=source_revision(kind,source); ident=digest([kind,key,version])
        due=source['retry_after'] if kind=='PRIVATE_RETRY_DUE' else (
            max(now,math.ceil(source['lease_expires_at']-self.policy['lease_notice_seconds'])) if kind=='LEASE_DUE'
            else now+self.policy['debounce_seconds'])
        baseline=db.execute('SELECT 1 FROM baseline WHERE kind=? AND key=? AND version=?',(kind,key,version)).fetchone()
        cause=dict(root_id=digest(['baseline']),parent_turn=None,depth=0) if baseline else dict(root_id=ident,parent_turn=None,depth=0)
        if kind=='QUEUED_RESULT':
            binding=db.execute('SELECT data FROM bindings WHERE id=?',(key,)).fetchone()
            if binding:cause=json.loads(binding[0])['cause']
        elif kind=='LEASE_DUE':
            row=db.execute('SELECT cause FROM leases WHERE version=?',(version,)).fetchone()
            cause=json.loads(row[0]) if row else dict(root_id=digest(['baseline']),parent_turn=None,depth=0)
        event=dict(schema=1,id=ident,kind=kind,key=key,version=version,target=KINDS[kind],
                   observed_at=now,not_before=due,cause=self._cause(cause))
        db.execute('INSERT OR IGNORE INTO events(id,kind,key,version,data,status) VALUES (?,?,?,?,?,?)',
                   (ident,kind,key,version,canonical(event),'BASELINED' if baseline else 'PENDING'))
        db.execute("UPDATE events SET status='OBSOLETE',reservation=NULL WHERE kind=? AND key=? AND version!=? AND status='PENDING'",(kind,key,version))

    @classmethod
    def _event(cls, value):
        try:
            if isinstance(value,str):value=json.loads(value)
            if (not isinstance(value,dict) or set(value)!={'schema','id','kind','key','version','target','observed_at','not_before','cause'}
                    or type(value['schema']) is not int or value['schema']!=1 or value['kind'] not in KINDS
                    or value['target']!=KINDS[value['kind']] or not isinstance(value['key'],str)
                    or not isinstance(value['version'],str) or not HEX.fullmatch(value['version'])):raise ValueError()
            pattern=TASK if value['kind']=='QUEUED_RESULT' else MISSION if value['kind']=='LEASE_DUE' else HEX
            if not pattern.fullmatch(value['key']) or value['id']!=digest([value['kind'],value['key'],value['version']]):raise ValueError()
            _time(value['observed_at']);_time(value['not_before']);cls._cause(value['cause'])
            return value
        except (ValueError,TypeError,KeyError):raise ValueError('Initiative storage unavailable') from None

    @classmethod
    def _receipt(cls, raw):
        try:
            value=json.loads(raw)
            if (not isinstance(value,dict) or value.get('schema')!=1
                    or value.get('phase') not in PHASES or value.get('trigger') not in ('wake','think','mail')
                    or value.get('target') not in ('DIRECTOR','PRIVATE_MAIL')
                    or not isinstance(value.get('wake_id'),str) or not HEX.fullmatch(value['wake_id'])
                    or not isinstance(value.get('events'),list) or len(value['events'])>200
                    or not isinstance(value.get('event_ids'),list)):raise ValueError()
            if value['target']=='DIRECTOR':
                if not isinstance(value.get('turn'),str) or not re.fullmatch(r'THINK-[0-9]{1,10}',value['turn']):raise ValueError()
            elif value.get('turn') is not None:raise ValueError()
            cls._cause(value['cause'])
            events=[cls._event(e) for e in value['events']]
            if not set(value['event_ids'])<={e['id'] for e in events}:raise ValueError()
            if value.get('started_at') is not None:_time(value['started_at'])
            if value.get('finished_at') is not None:_time(value['finished_at'])
            if value.get('prepared') is not None and value.get('context_digest')!=digest(value['prepared']['context']):raise ValueError()
            return value
        except (ValueError,TypeError,KeyError):raise ValueError('Initiative storage unavailable') from None

    def _repair_claims(self, db):
        from world import World
        path=self.root/'state/private/world.sqlite3'
        if not path.exists(): return
        self._safe(path)
        world=World(path)
        cursor=self._get(db,'cursor:claims','')
        query='SELECT b.data FROM bindings b JOIN claim_intents c ON b.id=c.id WHERE c.pending=1 AND c.id>? ORDER BY c.id LIMIT ?'
        rows=db.execute(query,(cursor,self.policy['scan_page_size'])).fetchall()
        if not rows:rows=db.execute(query,('',self.policy['scan_page_size'])).fetchall()
        for (raw,) in rows:
            binding=json.loads(raw)
            result=world.operation_result(binding['id'])
            if result is not None:
                try:_,version=source_revision('LEASE_DUE',result)
                except ValueError:raise ValueError('Initiative lineage mismatch') from None
                if result['mission_id']!=binding['claim_intent']['mission_id']:raise ValueError('Initiative lineage mismatch')
                db.execute('INSERT OR IGNORE INTO leases VALUES (?,?)',(version,canonical(binding['cause'])))
            # Under supervisor.lock there is no concurrently executing effect.
            # A future queued task re-arms this intent via bind_input immediately
            # before its first execution, even if its decision was prepared early.
            db.execute('UPDATE claim_intents SET pending=0 WHERE id=?',(binding['id'],))
        self._put(db,'cursor:claims',json.loads(rows[-1][0])['id'] if rows else '')

    def reconcile(self, world, *, now):
        _time(now)
        if not self.policy['enabled']:return
        with self._db() as db:
            self._repair_claims(db)
            for family in ('mail','tasks'):
                paths=self._paths(family);cursor=self._get(db,'cursor:'+family,'')
                page=[p for p in paths if p.name>cursor][:self.policy['scan_page_size']]
                if not page:page=paths[:self.policy['scan_page_size']]
                for path in page:
                    sources=self._sources(family,path,db)
                    for kind,source in sources:self._insert(db,kind,source,now)
                    if family=='mail':self._obsolete_private(db,path,sources)
                self._put(db,'cursor:'+family,page[-1].name if page else '')
            live=[]
            active={a.get('agent_id') for a in world.get('agents',[]) if a.get('status')=='ACTIVE'}
            for mission in world.get('missions',[]):
                try:
                    _,version=source_revision('LEASE_DUE',mission)
                    if 'agents' in world and mission['agent_id'] not in active:continue
                    known=db.execute('SELECT 1 FROM leases WHERE version=?',(version,)).fetchone()
                    pending=db.execute('SELECT 1 FROM claim_intents WHERE mission=? AND pending=1 LIMIT 1',(mission['mission_id'],)).fetchone()
                    if pending and not known:
                        # Never invent baseline ancestry while the exact committed
                        # operation is waiting for its bounded recovery page.
                        live.append(version);continue
                    self._insert(db,'LEASE_DUE',mission,now);live.append(version)
                except ValueError:continue
            for ident,version in db.execute("SELECT id,version FROM events WHERE kind='LEASE_DUE' AND status IN ('PENDING','RESERVED')"):
                if version not in live:db.execute("UPDATE events SET status='OBSOLETE',reservation=NULL WHERE id=?",(ident,))

    def _obsolete_private(self, db, path, sources):
        try:
            record=self._read(path,128*1024)
            if record.get('inbox_id')!=(self.config.get('agentmail') or {}).get('inbox_id'):return
            key=hashlib.sha256((record['inbox_id']+'\0'+record['message_id']).encode()).hexdigest()
            if path.name!=key+'.json':return
            if record.get('state') not in ('RETRY','ACCEPTED','IGNORED','FAILED','UNKNOWN'):return
            successor=next((source_revision(k,s)[1] for k,s in sources if k=='PRIVATE_RETRY_DUE'),None)
            for ident,version in db.execute("SELECT id,version FROM events WHERE kind='PRIVATE_RETRY_DUE' AND key=? AND status IN ('PENDING','RESERVED')",(key,)):
                if version!=successor:
                    db.execute("UPDATE events SET status='OBSOLETE',reservation=NULL WHERE id=?",(ident,))
        except (ValueError,OSError,TypeError,KeyError):return

    def events(self, *, status=None,kind=None):
        with self._db() as db:
            rows=db.execute('SELECT data,status,periodic FROM events ORDER BY rowid').fetchall()
        return [dict(self._event(data),status=state,periodic_only=bool(periodic)) for data,state,periodic in rows
                if (status is None or state==status) and (kind is None or self._event(data)['kind']==kind)]

    def event(self, ident):
        return next((e for e in self.events() if e['id']==ident),None)

    def admission(self, ident):
        with self._db() as db:
            row=db.execute('SELECT data FROM admissions WHERE id=?',(ident,)).fetchone()
            return self._receipt(row[0]) if row else None

    @staticmethod
    def _save_admission(db, receipt):
        db.execute('INSERT OR REPLACE INTO admissions VALUES (?,?)',(receipt['wake_id'],canonical(receipt)))

    def claim(self, mode, *, now,world_state,bank_state):
        _time(now)
        if mode not in ('wake','think','mail'):raise ValueError('Invalid initiative mode')
        if not self.policy['enabled']:return None
        with self._db() as db:
            if 'EXTINCT' in (world_state,bank_state):
                self._put(db,'extinct',True)
                db.execute("UPDATE events SET status='SUPPRESSED_EXTINCT',reservation=NULL WHERE status IN ('PENDING','RESERVED')")
                for (raw,) in db.execute('SELECT data FROM admissions'):
                    r=self._receipt(raw)
                    if r['phase'] in ('CLAIMED','STARTED'):
                        r.update(phase='SUPPRESSED_EXTINCT',reason='EXTINCT',finished_at=now);self._save_admission(db,r)
            if self._get(db,'extinct',False) or 'HALTED' in (world_state,bank_state):return None
            requested=None if mode=='wake' else ('DIRECTOR' if mode=='think' else 'PRIVATE_MAIL')
            for (raw,) in db.execute('SELECT data FROM admissions ORDER BY rowid'):
                r=self._receipt(raw)
                if r['phase']=='CLAIMED' and (requested is None or r['target']==requested):return r
            # A pending old decision must be recovered before admitting a new turn.
            if requested!='PRIVATE_MAIL':
                for p in (self.root/'state/controller').glob('THINK-*.json'):
                    if self._read(p).get('published') is not True:return None
            def ready(target):
                spacing=self.policy['director_spacing_seconds' if target=='DIRECTOR' else 'mail_spacing_seconds']
                at=self._get(db,'started:'+target)
                return at is None or now>=at+spacing
            if mode=='wake':
                lanes=['PRIVATE_MAIL','DIRECTOR'] if self._get(db,'last_lane')=='DIRECTOR' else ['DIRECTOR','PRIVATE_MAIL']
                target=next((lane for lane in lanes if ready(lane) and any(
                    self._candidate(db,kind,now,mode,()) is not None for kind in KINDS if KINDS[kind]==lane)),None)
                if target is None:return None
            else:
                target=requested
                if not ready(target):return None
            # A wake probes one eligible lane only. Spacing is checked before
            # opening any candidate source, including unrelated target backlogs.
            self._put(db,'last_lane',target)
            kinds=[kind for kind in KINDS if KINDS[kind]==target]
            last=self._get(db,'last_kind:'+target)
            if last in kinds:
                offset=kinds.index(last)+1;kinds=kinds[offset:]+kinds[:offset]
            selected=[];validated=0
            while validated<self.policy['scan_page_size'] and len(selected)<self.policy['batch_size']:
                excluded=[e['id'] for e in selected]
                candidate=None
                for kind in kinds:
                    candidate=self._candidate(db,kind,now,mode,excluded)
                    if candidate is not None:break
                if candidate is None:break
                validated+=1
                # Rotate even after an obsolete candidate, so small scan pages
                # and interrupted/empty probes cannot starve another class.
                self._put(db,'last_kind:'+target,kind)
                offset=kinds.index(kind)+1;kinds=kinds[offset:]+kinds[:offset]
                if self._current(db,candidate):selected.append(candidate)
                else:db.execute("UPDATE events SET status='OBSOLETE',reservation=NULL WHERE id=?",(candidate['id'],))
            if mode=='wake' and not selected:return None
            prior=max((int(p.stem.split('-')[1]) for p in (self.root/'state/controller').glob('THINK-*.json')
                       if re.fullmatch(r'THINK-[0-9]{1,10}',p.stem)),default=-1)
            seconds=max(now,self._get(db,'last_turn',-1)+1,prior+1)
            if seconds>9999999999:raise ValueError('Initiative turn range exhausted')
            self._put(db,'last_turn',seconds)
            turn='THINK-'+str(seconds) if target=='DIRECTOR' else None
            seq=self._get(db,'sequence',0)+1;self._put(db,'sequence',seq)
            ident=digest(['admission',seq,seconds,target])
            cause=dict(root_id=digest(['scheduled',ident]),parent_turn=None,depth=0)
            if mode=='wake' and target=='DIRECTOR':
                oldest=min(selected,key=lambda e:(e['observed_at'],e['id']))
                cause=dict(root_id=oldest['cause']['root_id'],parent_turn=oldest['cause']['parent_turn'],
                           depth=max(e['cause']['depth'] for e in selected)+1)
            receipt=dict(schema=1,wake_id=ident,trigger=mode,target=target,turn=turn,cause=cause,
                         event_ids=[e['id'] for e in selected],events=selected,parents=[e['cause'] for e in selected],
                         coverage=[],context_digest=None,phase='CLAIMED',started_at=None,finished_at=None,reason='RESERVED')
            self._save_admission(db,receipt)
            for e in selected:db.execute("UPDATE events SET status='RESERVED',reservation=? WHERE id=?",(ident,e['id']))
            self._put(db,'last_lane',target)
            return receipt

    def _candidate(self,db,kind,now,mode,excluded):
        # Only bounded host ledger rows are materialized. The due-expression
        # index supplies oldest due revisions without opening source files.
        query="SELECT data FROM events WHERE status='PENDING' AND kind=? AND json_extract(data,'$.not_before')<=?"
        args=[kind,now]
        if mode=='wake':
            query+=' AND periodic=0'
            if KINDS[kind]=='DIRECTOR':
                query+=" AND json_extract(data,'$.cause.depth')<?";args.append(self.policy['max_chain_depth'])
        if excluded:
            query+=' AND id NOT IN ('+','.join('?' for _ in excluded)+')';args.extend(excluded)
        query+=" ORDER BY json_extract(data,'$.not_before'),rowid LIMIT 1"
        row=db.execute(query,args).fetchone()
        if not row:return None
        event=self._event(row[0])
        if event['kind']!=kind:raise ValueError('Initiative storage unavailable')
        return event

    def _current(self,db,event):
        if event['kind']=='LEASE_DUE':return True  # validated by reconcile's exact world snapshot
        family='tasks' if event['kind']=='QUEUED_RESULT' else 'mail'
        directory=self.root/('state' if family=='tasks' else 'state/private/agentmail')
        path=directory/(event['key']+'.json')
        return any(kind==event['kind'] and source_revision(kind,source)==(event['key'],event['version'])
                   for kind,source in self._sources(family,path,db))

    def start(self, wake_id, *, prepared,now):
        _time(now)
        with self._db() as db:
            row=db.execute('SELECT data FROM admissions WHERE id=?',(wake_id,)).fetchone()
            if not row:raise ValueError('Unknown initiative admission')
            r=self._receipt(row[0])
            if r['phase']!='CLAIMED':raise ValueError('Initiative admission already started')
            if r['target']=='DIRECTOR':
                if not isinstance(prepared,dict) or set(prepared)!={'context','assessment','coverage','excluded'}:
                    raise ValueError('Invalid prepared initiative context')
                coverage=prepared['coverage'];visible={(c['kind'],c['key'],c['version']) for c in coverage}
                ineligible={(c['kind'],c['key']) for c in prepared['excluded']
                            if c.get('reason') in ('INVALID_RESULT','INVALID_SOURCE','INVALID_COMMERCIAL_OBSERVATION')}
                bound=[]
                for e in r['events']:
                    if (e['kind'],e['key'],e['version']) in visible:bound.append(e['id'])
                    else:
                        disposition='OBSOLETE' if (e['kind'],e['key']) in ineligible else 'PENDING'
                        db.execute('UPDATE events SET status=?,reservation=NULL WHERE id=? AND reservation=?',(disposition,e['id'],wake_id))
                r.update(selected_event_ids=r['event_ids'],event_ids=bound,coverage=coverage,
                         context_digest=digest(prepared['context']),prepared=prepared,excluded=prepared['excluded'])
            r.update(phase='STARTED',started_at=now,reason='PROVIDER_START' if r['target']=='DIRECTOR' else 'PRIVATE_PASS_START')
            self._put(db,'started:'+r['target'],max(now,self._get(db,'started:'+r['target'],0)))
            self._save_admission(db,r)

    def bind_task(self, task, *, turn,cause,origin):
        if origin not in ('queued','broker','external'):raise ValueError('Invalid initiative origin')
        # Scheduling metadata validates identity/action only. Toolbox retains
        # complete envelope/argument authorization before any actual effect.
        if (not isinstance(task,dict) or not isinstance(task.get('id'),str)
                or not TASK.fullmatch(task['id']) or task.get('type')!='TOOL'
                or task.get('action') not in ('EXEC','FETCH','WORLD','STATUS','SPEND','RECONCILE','PUBLISH_ACTOR','ACTOR_STATS','PUBLISH_SITE')
                or not isinstance(task.get('args'),dict)):
            raise ValueError('Invalid initiative task binding')
        cause=self._cause(cause)
        if turn is not None:
            if not re.fullmatch(r'THINK-[0-9]{1,10}',turn):raise ValueError('Invalid initiative turn')
            cause=dict(cause,parent_turn=turn)
        # Match the supervisor's canonical broker input; queued byte hashes may
        # differ in whitespace and are attached separately before execution.
        input_hash=digest(task)
        value=dict(id=task['id'],type=task['type'],action=task.get('action'),origin=origin,cause=cause,turn=turn)
        if task.get('action')=='WORLD' and task.get('args',{}).get('op')=='claim_mission':
            value['claim_intent']=dict(mission_id=task['args']['mission_id'])
        with self._db() as db:
            old=db.execute('SELECT input_hash,data FROM bindings WHERE id=?',(task['id'],)).fetchone()
            if old:
                if old[0]!=input_hash:raise ValueError('Initiative task identity reused')
                return  # Never replace host lineage with later/external context.
            db.execute('INSERT INTO bindings VALUES (?,?,?)',(task['id'],input_hash,canonical(value)))
            if value.get('claim_intent'):
                db.execute('INSERT INTO claim_intents VALUES (?,?,1)',(task['id'],value['claim_intent']['mission_id']))

    def task_cause(self, task_id):
        with self._db() as db:
            row=db.execute('SELECT data FROM bindings WHERE id=?',(task_id,)).fetchone()
            return json.loads(row[0])['cause'] if row else None

    def bind_input(self, task_id, input_hash):
        if not isinstance(input_hash,str) or not HEX.fullmatch(input_hash):raise ValueError('Invalid initiative input hash')
        with self._db() as db:
            row=db.execute('SELECT data FROM bindings WHERE id=?',(task_id,)).fetchone()
            if not row:raise ValueError('Missing initiative task binding')
            value=json.loads(row[0])
            if value.get('input_sha256',input_hash)!=input_hash:raise ValueError('Initiative input identity reused')
            value['input_sha256']=input_hash
            db.execute('UPDATE bindings SET data=? WHERE id=?',(canonical(value),task_id))
            db.execute('UPDATE claim_intents SET pending=1 WHERE id=?',(task_id,))

    def turn_cause(self, turn):
        with self._db() as db:
            for (raw,) in db.execute('SELECT data FROM admissions'):
                receipt=self._receipt(raw)
                if receipt['turn']==turn and receipt['phase'] in ('STARTED','DECISION_READY'):
                    return receipt['cause']
        return None

    def suppressed(self):
        with self._db() as db:return self._get(db,'extinct',False) is True

    def recorded_result(self, task_id, *, now):
        """Host callback after its own task journal commit; repair uses same IDs."""
        _time(now)
        if not isinstance(task_id,str) or not TASK.fullmatch(task_id):raise ValueError('Invalid initiative task')
        with self._db() as db:
            for kind,source in self._sources('tasks',self.root/'state'/(task_id+'.json'),db):
                self._insert(db,kind,source,now)

    def processed(self, wake_id,receipt):
        fields={'key','before_version','after_version','after_state','disposition'}
        if (not isinstance(receipt,dict) or set(receipt)!=fields
                or not isinstance(receipt['key'],str) or not HEX.fullmatch(receipt['key'])
                or any(v is not None and (not isinstance(v,str) or not HEX.fullmatch(v))
                       for v in (receipt['before_version'],receipt['after_version']))
                or receipt['after_state'] not in ('RETRY','ACCEPTED','IGNORED','FAILED','UNKNOWN')
                or receipt['disposition'] not in ('CONSUMED','REPLACED','OBSOLETE')):
            raise ValueError('Invalid private processing receipt')
        with self._db() as db:
            row=db.execute('SELECT data FROM admissions WHERE id=?',(wake_id,)).fetchone()
            if not row:raise ValueError('Unknown initiative admission')
            r=self._receipt(row[0])
            if r['target']!='PRIVATE_MAIL' or r['phase']!='STARTED':raise ValueError('Invalid private admission')
            # Receipt values alone cannot acknowledge a revision: verify the
            # committed source and successor independently using its fixed key.
            path=self.root/'state/private/agentmail'/(receipt['key']+'.json')
            record=self._read(path,128*1024)
            inbox,mid=record.get('inbox_id'),record.get('message_id')
            if (not isinstance(inbox,str) or not isinstance(mid,str)
                    or inbox!=(self.config.get('agentmail') or {}).get('inbox_id')
                    or hashlib.sha256((inbox+'\0'+mid).encode()).hexdigest()!=receipt['key']):
                raise ValueError('Private receipt mismatch')
            if record.get('state')!=receipt['after_state']:raise ValueError('Private receipt mismatch')
            current=None
            if record['state']=='RETRY':current=source_revision('PRIVATE_RETRY_DUE',record)[1]
            if current!=receipt['after_version']:raise ValueError('Private receipt mismatch')
            for e in r['events']:
                if e['key']==receipt['key'] and e['version']==receipt['before_version']:
                    db.execute('INSERT OR REPLACE INTO processed VALUES (?,?,?,?)',
                               (wake_id,e['key'],e['version'],canonical(receipt)))
            for kind,source in self._sources('mail',path,db):
                self._insert(db,kind,source,int(time.time()))

    def finish(self, wake_id, *, turn,now):
        _time(now)
        with self._db() as db:
            row=db.execute('SELECT data FROM admissions WHERE id=?',(wake_id,)).fetchone()
            if not row:raise ValueError('Unknown initiative admission')
            r=self._receipt(row[0])
            if r['phase']=='ACKED':return
            if r['phase'] not in ('STARTED','DECISION_READY'):raise ValueError('Unstarted initiative admission')
            if r['target']=='DIRECTOR':
                if turn!=r['turn']:return  # A returned older decision covers no newly claimed input.
                saved=self._read(self.root/'state/controller'/(turn+'.json'))
                if saved.get('published') is not True:return
                if saved.get('lineage')!=r['cause']:raise ValueError('Initiative decision lineage mismatch')
                ids=r['event_ids']
            else:
                ids=[]
                for e in r['events']:
                    receipt=db.execute('SELECT 1 FROM processed WHERE wake_id=? AND key=? AND version=?',(wake_id,e['key'],e['version'])).fetchone()
                    if receipt:ids.append(e['id'])
            for ident in ids:db.execute("UPDATE events SET status='ACKED',reservation=NULL WHERE id=? AND reservation=?",(ident,wake_id))
            db.execute("UPDATE events SET status='PENDING',reservation=NULL WHERE reservation=? AND status='RESERVED'",(wake_id,))
            r.update(phase='ACKED',finished_at=now,reason='EXACT_COVERAGE' if r['target']=='DIRECTOR' else 'PRIVATE_RECEIPTS')
            self._save_admission(db,r)

    def recover(self, *, now):
        _time(now);resume=[];private=[];published=[]
        with self._db() as db:
            self._repair_claims(db)
            for (raw,) in db.execute('SELECT data FROM admissions ORDER BY rowid').fetchall():
                r=self._receipt(raw)
                if r['phase']=='CLAIMED':resume.append(r);continue
                if r['phase'] not in ('STARTED','DECISION_READY'):continue
                if r['target']=='PRIVATE_MAIL':private.append(r);continue
                path=self.root/'state/controller'/(r['turn']+'.json')
                if path.exists():
                    saved=self._read(path)
                    if saved.get('lineage')!=r['cause']:raise ValueError('Initiative decision lineage mismatch')
                    r.update(phase='DECISION_READY',reason='PUBLICATION_RECOVERY');self._save_admission(db,r)
                    if saved.get('published') is True:published.append(r)
                    else:resume.append(r)
                else:
                    r.update(phase='INTERRUPTED',finished_at=now,reason='UNCERTAIN_PROVIDER_EFFECTS')
                    self._save_admission(db,r)
                    # Includes released sources: uncertainty must not expedite a
                    # new causal root merely because the window was incomplete.
                    for ident in r.get('selected_event_ids',r['event_ids']):
                        db.execute("UPDATE events SET status='PENDING',reservation=NULL,periodic=1 WHERE id=? AND status IN ('PENDING','RESERVED')",(ident,))
        for r in published:self.finish(r['wake_id'],turn=r['turn'],now=now)
        for r in private:
            # Recover callback loss solely from durable source successors.
            for e in r['events']:
                try:
                    source=self._read(self.root/'state/private/agentmail'/(e['key']+'.json'),128*1024)
                    current=source_revision('PRIVATE_RETRY_DUE',source)[1] if source.get('state')=='RETRY' else None
                    if source.get('state') in ('RETRY','ACCEPTED','IGNORED','FAILED','UNKNOWN') and current!=e['version']:
                        self.processed(r['wake_id'],dict(key=e['key'],before_version=e['version'],after_version=current,
                            after_state=source['state'],disposition='REPLACED' if current else 'CONSUMED'))
                except (ValueError,OSError):continue
            self.finish(r['wake_id'],turn=None,now=now)
        return resume
