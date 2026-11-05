"""Bounded host-only task feedback, separate from publication artifact blobs.

Legacy journals are projected with a bounded streaming scan. Only selected
top-level fields are retained; product contents never enter the feedback view.
"""
import hashlib
import json
import os
import pathlib
import re
import stat
import tempfile

MAX_ENVELOPE = 64 * 1024
MAX_FIELD = 1024 * 1024
MAX_LEGACY = 64 * 1024 * 1024
TASK = re.compile(r'TASK-[0-9]{4,12}')
HEX = re.compile(r'[0-9a-f]{64}')
FIELDS = {'id', 'hash', 'input_sha256', 'origin', 'state', 'metadata', 'request', 'task', 'result'}
TERMINAL = ('DONE', 'FAILED', 'REJECTED', 'TIMEOUT', 'INTERRUPTED')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


class ResultSource(dict):
    """A private, validated projection; public JSON cannot supply its revision."""
    def copy(self):
        return ResultSource(self)


def _safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Invalid result source')
    if path.exists():
        info = path.stat()
        if (not (stat.S_ISDIR(info.st_mode) or (stat.S_ISREG(info.st_mode) and info.st_nlink == 1))
                or (hasattr(os, 'geteuid') and info.st_uid != os.geteuid())):
            raise ValueError('Invalid result source')


def _screened(result):
    from supervisor import check_secrets
    screened = dict(result)
    if isinstance(screened.get('artifacts'), list):
        screened['artifacts'] = [p for p in screened['artifacts'] if not (
            isinstance(p, str) and re.fullmatch(r'products/receipts/TASK-[0-9]{4,12}\.json', p))]
    if re.search(r'receipt|credential|auth\.json|access_token|refresh_token|idempotency|gateway',
                 json.dumps(screened), re.I):
        return True
    try:
        check_secrets(str(result.get('output', '')).encode())
    except ValueError:
        return True
    return False


def _classification(value):
    if not isinstance(value, dict):
        return None
    return {k: v if isinstance(v, str) and len(v) <= 256 else None
            for k, v in value.items() if k in ('id', 'type', 'action', 'origin', 'input_sha256')}


def envelope(record):
    ident, input_hash, result = record.get('id'), record.get('hash'), record.get('result')
    if (not isinstance(ident, str) or not TASK.fullmatch(ident)
            or not isinstance(input_hash, str) or not HEX.fullmatch(input_hash)
            or not isinstance(result, dict) or result.get('status') not in TERMINAL):
        raise ValueError('Invalid result source')
    output = str(result.get('output', ''))
    value = dict(schema='globalland.result.v1', id=ident, hash=input_hash,
                 origin=record.get('origin'), state=record.get('state'),
                 source_version=hashlib.sha256(_canonical([input_hash, result]).encode()).hexdigest(),
                 result=dict(status=result['status'], output=output[:2000]),
                 output_redacted=_screened(result), output_truncated=len(output) > 2000)
    for field in ('metadata', 'request', 'task'):
        if field in record:
            value[field] = _classification(record[field]) if isinstance(record[field], dict) else (
                record[field][:256] if field == 'task' and isinstance(record[field], str) else None)
    if len(_canonical(value).encode()) > MAX_ENVELOPE:
        raise ValueError('Invalid result source')
    return value


def _identity(path):
    info=path.stat()
    return [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns]


def write_result_envelope(root, record, *, source_identity=None):
    """Call after terminal journal commits; ignore non-task/nonterminal records."""
    if (not isinstance(record.get('id'), str) or not TASK.fullmatch(record['id'])
            or not isinstance(record.get('hash'), str) or not HEX.fullmatch(record['hash'])
            or not isinstance(record.get('result'), dict)
            or record['result'].get('status') not in TERMINAL):
        return
    value = envelope(record)
    journal=pathlib.Path(root)/'state'/(value['id']+'.json')
    _safe(journal)
    current=_identity(journal) if journal.exists() else None
    if source_identity is not None and current!=source_identity:
        raise ValueError('Invalid result source')
    value['journal_identity']=current
    path = pathlib.Path(root) / 'state/results' / (value['id'] + '.json')
    _safe(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, temporary = tempfile.mkstemp(prefix='.result-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            stream.write(_canonical(value) + '\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != 'nt':
            directory = os.open(path.parent, os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def result_paths(root):
    state = pathlib.Path(root) / 'state'
    paths = {p.name: p for p in (state / 'results').glob('TASK-*.json')}
    paths.update({p.name: p for p in state.glob('TASK-*.json')})
    return sorted(paths.values(), key=lambda p: p.name)


def _legacy_projection(path):
    """Scan at most MAX_LEGACY bytes, retaining at most MAX_FIELD per field."""
    if path.stat().st_size > MAX_LEGACY:
        raise ValueError('Invalid result source')
    def characters(stream):
        total = 0
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk: return
            total += len(chunk.encode())
            if total > MAX_LEGACY: raise ValueError('Invalid result source')
            yield from chunk
    def nonspace(chars):
        for c in chars:
            if not c.isspace(): return c
        raise ValueError('Invalid result source')
    result = {}; seen = set()
    with path.open(encoding='utf-8') as stream:
        chars = iter(characters(stream))
        if nonspace(chars) != '{': raise ValueError('Invalid result source')
        first = nonspace(chars)
        if first == '}': return result
        while True:
            if first != '"': raise ValueError('Invalid result source')
            key_text = '"'; escaped = False
            for c in chars:
                key_text += c
                if len(key_text) > 256: raise ValueError('Invalid result source')
                if c == '"' and not escaped: break
                escaped = c == '\\' and not escaped
            key = json.loads(key_text)
            if key in seen: raise ValueError('Invalid result source')
            seen.add(key)
            if len(seen) > 64: raise ValueError('Invalid result source')
            if nonspace(chars) != ':': raise ValueError('Invalid result source')
            keep = key in FIELDS; value = []; size = 0; stack = []; quoted = escaped = False
            for c in chars:
                if not quoted and not stack and c in ',}': break
                if keep:
                    size += len(c.encode())
                    if size > MAX_FIELD: raise ValueError('Invalid result source')
                    value.append(c)
                if quoted:
                    if c == '"' and not escaped: quoted = False
                    escaped = c == '\\' and not escaped
                elif c == '"': quoted = True
                elif c in '[{':
                    stack.append(c)
                    if len(stack) > 128: raise ValueError('Invalid result source')
                elif c in ']}':
                    if not stack or stack.pop() != ('[' if c == ']' else '{'):
                        raise ValueError('Invalid result source')
            else: raise ValueError('Invalid result source')
            if keep: result[key] = json.loads(''.join(value), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if c == '}': break
            first = nonspace(chars)
        if any(not c.isspace() for c in chars): raise ValueError('Invalid result source')
    return result


def read_result(root, path):
    """Prefer a trusted sidecar, projecting a bounded legacy journal as fallback."""
    path = pathlib.Path(path); _safe(path)
    ident = path.stem
    if not TASK.fullmatch(ident): raise ValueError('Invalid result source')
    compact = pathlib.Path(root) / 'state/results' / (ident + '.json')
    source_identity=_identity(path) if path!=compact and path.exists() else None
    value=None
    try:
        _safe(compact)
        if compact.exists() and (path == compact or not path.exists()
                                or compact.stat().st_mtime_ns >= path.stat().st_mtime_ns):
            if compact.stat().st_size > MAX_ENVELOPE: raise ValueError('Invalid result source')
            from supervisor import strict_json
            with compact.open('rb') as stream:raw=stream.read(MAX_ENVELOPE+1)
            if len(raw)>MAX_ENVELOPE:raise ValueError('Invalid result source')
            value = strict_json(raw)
            if (not isinstance(value, dict) or value.get('schema') != 'globalland.result.v1'
                    or value.get('id') != ident or not isinstance(value.get('hash'), str)
                    or not HEX.fullmatch(value['hash']) or not isinstance(value.get('source_version'), str)
                    or not HEX.fullmatch(value['source_version']) or not isinstance(value.get('result'), dict)
                    or value['result'].get('status') not in TERMINAL
                    or type(value.get('output_redacted')) is not bool
                    or type(value.get('output_truncated')) is not bool):
                raise ValueError('Invalid result source')
            if source_identity is not None and value.get('journal_identity',source_identity)!=source_identity:
                value=None
    except (OSError,ValueError):
        # A derived cache never outranks the authoritative private journal.
        # Unsafe entries are not followed or overwritten by the backfill.
        # With no safe host journal, refusal still suppresses public fallback.
        if source_identity is None:raise
        value=None
    if value is None:
        record = _legacy_projection(path)
        if record.get('id', ident) != ident: raise ValueError('Invalid result source')
        record['id'] = ident
        if source_identity is None or _identity(path)!=source_identity:
            raise ValueError('Invalid result source')
        if not isinstance(record.get('hash'),str) or not HEX.fullmatch(record['hash']):
            # Historical host observations can still provide classified,
            # screened status/output. They cannot assert an input identity or
            # create initiative coverage without their original input hash.
            return record
        value = envelope(record)
        try:
            # Cache only a stable original journal. The retained fingerprint
            # invalidates the cache even if a newer journal preserves mtime or
            # races the atomic sidecar write. Cache failure loses no evidence.
            write_result_envelope(root,record,source_identity=source_identity)
        except (OSError,ValueError):
            pass
    if source_identity is not None and _identity(path)!=source_identity:
        raise ValueError('Invalid result source')
    return ResultSource(value)
