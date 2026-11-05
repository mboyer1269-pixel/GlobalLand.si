"""Host-side tool broker for one think turn.

The brain container holds subscription credentials but no GlobalLand
capability. It reaches this broker through a Unix socket bind-mounted at
/broker, via the stdio MCP server globalland_mcp.js. Every request is
validated here, budgeted, and journaled before any effect. Effects reuse the
supervisor's durable task path, so a broker action is executed, recorded and
published exactly like a queued task, under a stable TASK identifier.

Financial actions (SPEND, RECONCILE) stay on the queue path for now.
"""
import datetime
import hashlib
import json
import os
import pathlib
import re
import socket
import threading

from supervisor import check_secrets

OPS = ('world_status', 'list_products', 'read_product', 'recent_results', 'submit_action')
EFFECT_ACTIONS = ('EXEC', 'FETCH', 'WORLD', 'STATUS', 'PUBLISH_ACTOR', 'ACTOR_STATS', 'PUBLISH_SITE')
MAX_REQUEST = 256 * 1024
MAX_RESPONSE = 1024 * 1024
MAX_READ = 64 * 1024
FIRST_ACTION_SLOT = 10  # 00-04 stay reserved for the turn's final decision.
BROKER_PROVIDERS = ('claude', 'codex')


class BrokerError(ValueError):
    """A refused request whose message is a fixed rule, safe to return."""


def limits(config):
    """Validated broker settings from controller config; disabled by default."""
    c = config.get('broker') or {}
    if not isinstance(c, dict) or c.get('enabled') is not True:
        return None
    def bounded(key, default, low, high):
        value = c.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError('invalid broker configuration')
        return value
    providers = c.get('providers', ['claude'])
    # Codex reaches the broker through -c mcp_servers overrides; opt-in until
    # the installed Codex CLI is proven to accept them (INSTALL.md).
    if (not isinstance(providers, list) or not providers or len(set(providers)) != len(providers)
            or any(p not in BROKER_PROVIDERS for p in providers)):
        raise ValueError('invalid broker configuration')
    return dict(max_calls=bounded('max_calls', 40, 1, 200),
                max_actions=bounded('max_actions', 20, 1, 100 - FIRST_ACTION_SLOT),
                turn_timeout_seconds=bounded('turn_timeout_seconds', 900, 60, 3600),
                max_turns=bounded('max_turns', 40, 2, 200),
                providers=list(providers))


class Broker:
    def __init__(self, directory, turn_seconds, handlers, max_calls=40, max_actions=20):
        self.directory = pathlib.Path(directory)
        self.turn_seconds = int(turn_seconds)
        if not 0 <= self.turn_seconds <= 9999999999:
            raise ValueError('turn timestamp outside task ID range')
        missing = {'world_status', 'list_products', 'read_product', 'recent_results', 'execute'} - set(handlers)
        if missing:
            raise ValueError('broker handlers missing')
        self.handlers = handlers
        self.max_calls = max_calls
        self.max_actions = min(max_actions, 100 - FIRST_ACTION_SLOT)
        self.calls = 0
        self.actions = 0
        self.lock = threading.Lock()
        self.server = None
        self.thread = None
        self.stopping = threading.Event()

    @property
    def socket_path(self):
        return self.directory / 'broker.sock'

    @property
    def journal_path(self):
        return self.directory / 'calls.jsonl'

    # Lifecycle -------------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        # The brain container user must traverse the mounted directory and
        # connect; it cannot list it. The journal stays owner-readable only.
        os.chmod(self.directory, 0o711)
        # A later provider attempt in the same turn continues the budget and
        # the identifier sequence: a TASK slot is never reused.
        if self.journal_path.exists():
            for line in self.journal_path.read_text().splitlines():
                entry = json.loads(line)
                self.calls = max(self.calls, entry.get('n', 0))
                if 'task' in entry:
                    self.actions += 1
        if self.socket_path.exists() or self.socket_path.is_symlink():
            self.socket_path.unlink()
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o666)
        self.server.listen(4)
        self.server.settimeout(0.5)
        self.thread = threading.Thread(target=self._serve, name='globalland-broker', daemon=True)
        self.thread.start()

    def stop(self):
        """Refuse new calls, then wait for an in-flight action to finish.

        An action already started must complete its durable record and
        publication before the turn publishes: the supervisor never runs two
        Git publications at once."""
        self.stopping.set()
        with self.lock:
            pass
        if self.thread:
            self.thread.join()
        if self.server:
            self.server.close()
        if self.socket_path.exists():
            self.socket_path.unlink()

    def _serve(self):
        while not self.stopping.is_set():
            try:
                conn, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                conn.settimeout(30)
                try:
                    self._connection(conn)
                except (OSError, socket.timeout):
                    continue

    def _connection(self, conn):
        buffer = b''
        while not self.stopping.is_set():
            chunk = conn.recv(65536)
            if not chunk:
                return
            buffer += chunk
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                conn.sendall(self._encode(self.request(line)))
            if len(buffer) > MAX_REQUEST:
                conn.sendall(self._encode(self._refused('request too large')))
                return

    @staticmethod
    def _encode(response):
        raw = json.dumps(response, ensure_ascii=False, allow_nan=False).encode()
        if len(raw) > MAX_RESPONSE:
            raw = json.dumps({'ok': False, 'error': 'response too large; narrow the request'}).encode()
        return raw + b'\n'

    @staticmethod
    def _refused(reason):
        return {'ok': False, 'error': reason}

    # Requests --------------------------------------------------------------

    def request(self, line):
        """Handle one JSON line. Serialized: one effect at a time per turn."""
        with self.lock:
            if self.stopping.is_set():
                return self._refused('turn ended; return the final decision')
            if len(line) > MAX_REQUEST:
                return self._refused('request too large')
            try:
                value = json.loads(line.decode('utf-8'))
            except (ValueError, UnicodeError):
                return self._refused('request must be one JSON object per line')
            if not isinstance(value, dict) or set(value) - {'op', 'args'} or value.get('op') not in OPS:
                return self._refused('unknown broker operation; use one of ' + ', '.join(OPS))
            args = value.get('args', {})
            if args is None:
                args = {}
            if not isinstance(args, dict):
                return self._refused('broker arguments must be an object')
            if self.calls >= self.max_calls:
                return self._refused('call budget exhausted for this turn; return the final decision')
            self.calls += 1
            # Every counted call is journaled first, so a retry in the same turn
            # restores the exact budget, refused calls included.
            self._journal(dict(op=value['op'], args_sha256=self._digest(args)))
            try:
                return {'ok': True, 'result': self._dispatch(value['op'], args)}
            except BrokerError as error:
                return self._refused(str(error))
            except (ValueError, UnicodeError) as error:
                from tools import rejection_reason
                return self._refused(rejection_reason(error))
            except Exception as error:
                return self._refused('internal broker failure (' + type(error).__name__ + '); no automatic retry')

    def _dispatch(self, op, args):
        if op != 'submit_action':
            if op == 'world_status':
                if (set(args)-{'collection','page'} or ('page' in args and 'collection' not in args)
                        or ('collection' in args and (not isinstance(args['collection'],str)
                            or not re.fullmatch(r'[a-z][a-z_]{0,63}',args['collection'])))
                        or ('page' in args and (type(args['page']) is not int or args['page']<0))):
                    raise BrokerError('world_status accepts a collection and nonnegative page')
                return self.handlers[op](**args)
            if op != 'read_product' and args:
                raise BrokerError(op + ' takes no arguments')
            if op == 'read_product':
                if set(args) != {'path'} or not isinstance(args['path'], str):
                    raise BrokerError('read_product requires exactly a path')
                return self.handlers['read_product'](args['path'])
            return self.handlers[op]()
        if set(args) != {'agent', 'action', 'args'}:
            raise BrokerError('submit_action requires agent, action and args')
        if args['action'] not in EFFECT_ACTIONS:
            raise BrokerError('submit_action accepts ' + ', '.join(EFFECT_ACTIONS) + '; SPEND and RECONCILE use the final decision')
        if self.actions >= self.max_actions:
            raise BrokerError('action budget exhausted for this turn; return the final decision')
        from decision_protocol import normalize_model_action
        from tools import validate_envelope
        action = normalize_model_action(dict(args))
        ident = 'TASK-%010d%02d' % (self.turn_seconds, FIRST_ACTION_SLOT + self.actions)
        created = datetime.datetime.fromtimestamp(self.turn_seconds, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        task = dict(id=ident, type='TOOL', submitted_by=action['agent'], created_at=created,
                    action=action['action'], args=action['args'],
                    description='Broker action during ' + 'THINK-' + str(self.turn_seconds),
                    estimated_cost_cad=0, approved_by=None)
        validate_envelope(task)
        check_secrets(json.dumps(task).encode())
        # The slot is consumed even if execution fails: an identifier is never reused.
        self.actions += 1
        self._journal(dict(op=op, task=task))  # the effect record precedes execution
        result = self.handlers['execute'](task)
        if not isinstance(result, dict) or not isinstance(result.get('status'), str):
            raise BrokerError('executor returned no result')
        output = str(result.get('output', ''))
        response=dict(task_id=ident, status=result['status'], output=output[:8000],
                      artifacts=result.get('artifacts', []))
        # Publication is host-derived transport state. Never forward arbitrary
        # exception text; the effect stays recorded and must not be resubmitted.
        publication=result.get('publication')
        if isinstance(publication,str) and publication.startswith('PENDING'):
            response.update(publication='PENDING: effect recorded; publication retried next cycle. Do not resubmit.',
                            artifacts_visible=False)
        return response

    @staticmethod
    def _digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def _journal(self, entry):
        entry = dict(entry, n=self.calls, at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        fd = os.open(self.journal_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n').encode())
            os.fsync(fd)
        finally:
            os.close(fd)


def read_handlers(root, world, treasury, context):
    """Read-only views over the exported public tree and private snapshots."""
    work = pathlib.Path(root) / 'work'

    def world_status(collection=None,page=0):
        if hasattr(world,'public_page'):
            snapshot=world.public_page(collection,page)
        elif collection is not None:
            raise BrokerError('world pagination unavailable')
        else:snapshot=world.snapshot()
        value = {'world': snapshot, 'bank': treasury.snapshot()}
        # Share the planner's capability observation without exposing config.
        value['capabilities'] = context().get('capabilities', {})
        return value

    def list_products():
        base = work / 'products'
        if not base.exists():
            return []
        return [str(p.relative_to(work)) for p in sorted(base.rglob('*'))
                if p.is_file() and not p.is_symlink() and 'receipts' not in p.parts][:500]

    def read_product(name):
        from tools import product_path
        product_path(name)
        path = work
        for part in name.split('/'):
            path = path / part
            if path.is_symlink():
                raise BrokerError('symlinked product refused')
        if not path.is_file():
            raise BrokerError('product not found')
        raw = path.read_bytes()
        truncated = len(raw) > MAX_READ
        raw = raw[:MAX_READ]
        check_secrets(raw)
        text = None
        # A cut at MAX_READ may split one UTF-8 character (at most 3 bytes).
        for cut in range(4 if truncated else 1):
            try:
                text = raw[:len(raw) - cut].decode('utf-8')
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise BrokerError('binary product; publish a base64 text version to read it')
        return {'path': name, 'content': text, 'truncated': truncated}

    def recent_results():
        return context()['latest_task_results']

    return dict(world_status=world_status, list_products=list_products,
                read_product=read_product, recent_results=recent_results)
