"""Host-only catalog views, with explicit filesystem support for offline fixtures.

An installed source.git always takes precedence over sparse work/. No generated
program receives this adapter or access to the private Git object database.
"""
import base64
import hashlib
import json
import pathlib

MAX_PAGE = 100
MAX_RANGE = 65536


def source_for(root, revision=None):
    root = pathlib.Path(root)
    if (root / 'source.git').exists() or (root / 'source.git').is_symlink():
        from public_source import PublicSource
        return PublicSource(root, revision=revision)
    return _FilesystemSource(root / 'work', revision)


def entries(source, prefix):
    if hasattr(source, 'iter_entries'):
        yield from source.iter_entries(prefix=prefix)
        return
    cursor = None
    while True:
        page = source.list(prefix=prefix, cursor=cursor, limit=MAX_PAGE)
        yield from page['entries']
        cursor = page['next_cursor']
        if cursor is None:
            return


def chunk_bytes(chunk):
    return (chunk['content'].encode('utf-8') if chunk['encoding'] == 'utf-8'
            else base64.b64decode(chunk['content'], validate=True))


def bounded_bytes(source, path, budget):
    """Read at most budget bytes; refuse larger files before assembling them."""
    offset, raw = 0, bytearray()
    while True:
        chunk = source.read(path, offset=offset, limit=min(MAX_RANGE, max(4, budget - offset)))
        if chunk['total_bytes'] > budget:
            raise ValueError('public source exceeds context budget')
        raw.extend(chunk_bytes(chunk))
        if chunk['next_offset'] >= chunk['total_bytes']:
            return bytes(raw)
        if chunk['next_offset'] <= offset:
            raise ValueError('public source read did not advance')
        offset = chunk['next_offset']


def _path(name, *, prefix=False):
    from supervisor import safe_path
    safe_path(name[:-1] if prefix and name.endswith('/') else name)
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError('unsafe public source path')
    return name


class _FilesystemSource:
    """Explicit offline-fixture adapter; filesystem versions are not Git commits."""
    def __init__(self, work, revision=None):
        self.work = work
        self.revision = revision

    def _file(self, name):
        _path(name)
        path = self.work / name
        if (any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()
                or path.stat().st_nlink != 1):
            raise ValueError('public source not found')
        return path

    def list(self, prefix='products/', cursor=None, limit=MAX_PAGE):
        _path(prefix, prefix=True)
        if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
            raise ValueError('invalid catalog page limit')
        rows = []
        if self.work.is_dir() and not self.work.is_symlink():
            for path in sorted(self.work.rglob('*')):
                name = path.relative_to(self.work).as_posix()
                if not name.startswith(prefix):
                    continue
                try:
                    path = self._file(name)
                    digest = hashlib.sha256()
                    with path.open('rb') as stream:
                        for chunk in iter(lambda: stream.read(MAX_RANGE), b''):
                            digest.update(chunk)
                    rows.append(dict(path=name, size=path.stat().st_size, oid=digest.hexdigest()))
                except (OSError, ValueError):
                    continue
        revision = 'filesystem:' + hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        if self.revision is not None and self.revision != revision:
            raise ValueError('filesystem catalog changed; restart discovery')
        start = 0
        if cursor is not None:
            try:
                token = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if token['revision'] != revision or token['prefix'] != prefix:
                    raise ValueError()
                start = token['offset']
                if type(start) is not int or start < 0 or start > len(rows):
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                raise ValueError('invalid filesystem catalog cursor') from None
        end = start + limit
        token = dict(revision=revision, prefix=prefix, offset=end)
        next_cursor = base64.urlsafe_b64encode(json.dumps(token).encode()).decode() if end < len(rows) else None
        return dict(revision=revision, entries=rows[start:end], next_cursor=next_cursor,
                    source_kind='filesystem_fixture')

    def read(self, path, offset=0, limit=MAX_RANGE):
        if (type(offset) is not int or offset < 0 or type(limit) is not int
                or not 1 <= limit <= MAX_RANGE):
            raise ValueError('invalid public source range')
        item = self._file(path)
        total = item.stat().st_size
        if offset > total:
            raise ValueError('public source offset outside file')
        with item.open('rb') as stream:
            stream.seek(offset)
            raw = stream.read(limit)
        content, encoding = None, 'utf-8'
        for cut in range(min(3, len(raw)) + 1):
            try:
                content = raw[:len(raw) - cut].decode('utf-8')
                if content or not raw:
                    raw = raw[:len(raw) - cut]
                    break
            except UnicodeError:
                continue
        if content is None or (not content and raw):
            content, encoding = base64.b64encode(raw).decode(), 'base64'
        return dict(revision=self.revision, path=path, offset=offset, content=content,
                    encoding=encoding, next_offset=offset + len(raw), total_bytes=total,
                    eof=offset + len(raw) >= total, source_kind='filesystem_fixture')
