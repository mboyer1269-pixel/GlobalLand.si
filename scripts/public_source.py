"""Bounded, host-only reads of immutable local public Git source.

No checkout, archive, network access or repository programs are used. A source
instance pins one commit, including across HEAD changes. Offsets are byte
offsets. Reads prefer UTF-8 and trim an incomplete final codepoint; binary data,
arbitrary offsets into codepoints and too-small limits use explicit base64.
"""
import base64
import contextlib
import hashlib
import json
import os
import pathlib
import re
import secrets
import shutil
import stat
import subprocess
import threading
import time

MAX_READ_BYTES = 65536
MAX_PAGE_ENTRIES = 1000
# Per-export metadata/work bound, not a retained-source or listing limit.
MAX_EXPORT_ENTRIES = 100000
OPERATION_TIMEOUT = 60
_OID = re.compile(r'[0-9a-f]{40}\Z')
_REGULAR = {'100644', '100755'}


class PublicSourceError(RuntimeError):
    def __init__(self, code, selected_bytes=None):
        self.code = code
        self.selected_bytes = selected_bytes
        super().__init__(code)


def validate_public_path(value, allow_empty=False):
    """Validate a literal public file or directory selector without Git syntax."""
    if not isinstance(value, str):
        raise PublicSourceError('source_path_invalid')
    try:
        if len(value.encode('utf-8')) > 4096:
            raise PublicSourceError('source_path_invalid')
    except UnicodeError as exc:
        raise PublicSourceError('source_path_invalid') from exc
    if not value and allow_empty:
        return value
    if (not value or value.startswith('/') or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(c in value for c in '\\:*?[]') or '\x00' in value):
        raise PublicSourceError('source_path_invalid')
    parts = (value[:-1] if value.endswith('/') else value).split('/')
    if any(p in {'', '.', '..'} or p.casefold() == '.git' for p in parts):
        raise PublicSourceError('source_path_invalid')
    return value


# Keep the concise internal spelling; consumers use the public validator above.
_path = validate_public_path


def _directory_fd(path, create=False):
    """Open an absolute directory through no-follow component descriptors."""
    path = pathlib.Path(os.path.abspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        for component in path.parts[1:]:
            try:
                child = os.open(component, flags, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, mode=0o755, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextlib.contextmanager
def public_export_directory(destination, forbidden=()):
    """Build public inputs privately, then install through one anchored rename.

    The Linux host runtime provides dir_fd and no-follow opens. Destination
    parents and the staging directory stay bound to descriptors throughout;
    replacing a checked ancestor with a symlink cannot redirect writes.
    """
    destination = pathlib.Path(os.path.abspath(destination))
    for source in forbidden:
        source = pathlib.Path(source).resolve()
        if destination == source or source in destination.parents or destination in source.parents:
            raise PublicSourceError('source_destination_invalid')
    parent_fd, staging_fd, staging_name = None, None, None
    installed = False
    try:
        # Existing components are validated before any directory is created.
        for part in (destination, *destination.parents):
            if part.is_symlink():
                raise PublicSourceError('source_destination_invalid')
        parent_fd = _directory_fd(destination.parent, create=True)
        try:
            previous = os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            previous = None
        if previous is not None:
            if not stat.S_ISDIR(previous.st_mode):
                raise PublicSourceError('source_destination_invalid')
            current_fd = os.open(destination.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                 dir_fd=parent_fd)
            try:
                with os.scandir(current_fd) as items:
                    if next(items, None) is not None:
                        raise PublicSourceError('source_destination_not_empty')
            finally:
                os.close(current_fd)
        candidate = '.public-source-' + secrets.token_hex(16)
        os.mkdir(candidate, mode=0o700, dir_fd=parent_fd)
        staging_name = candidate
        staging_fd = os.open(staging_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                             dir_fd=parent_fd)
        staging = pathlib.Path('/proc/self/fd') / str(staging_fd)
        yield staging
        for current, _, _ in os.walk(staging):
            pathlib.Path(current).chmod(0o755)
        # Refuse an ancestor/destination swap, even though anchored operations
        # already prevent a symlink from redirecting the bytes elsewhere.
        check_fd = _directory_fd(destination.parent)
        try:
            checked, anchored = os.fstat(check_fd), os.fstat(parent_fd)
            if (checked.st_dev, checked.st_ino) != (anchored.st_dev, anchored.st_ino):
                raise PublicSourceError('source_destination_changed')
        finally:
            os.close(check_fd)
        try:
            current = os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            current = None
        if ((current is None) != (previous is None) or (current is not None and
                (not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) !=
                 (previous.st_dev, previous.st_ino)))):
            raise PublicSourceError('source_destination_changed')
        os.replace(staging_name, destination.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        installed = True
    except OSError as exc:
        raise PublicSourceError('source_export_failed') from exc
    finally:
        if staging_fd is not None:
            os.close(staging_fd)
        if staging_name is not None and not installed:
            shutil.rmtree(staging_name, dir_fd=parent_fd, ignore_errors=True)
        if parent_fd is not None:
            os.close(parent_fd)


def _integer(value, low, high, code):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise PublicSourceError(code)
    return value


class PublicSource:
    MAX_READ_BYTES = MAX_READ_BYTES

    def __init__(self, root, revision=None):
        self.root = pathlib.Path(root).absolute()
        self.repo = self.root / 'source.git'
        if self.repo.is_symlink() or not self.repo.is_dir():
            raise PublicSourceError('source_repository_missing')
        self.repo = self.repo.resolve()
        if revision is not None and (not isinstance(revision, str) or not _OID.fullmatch(revision)):
            raise PublicSourceError('source_revision_invalid')
        deadline = self._deadline()
        requested = revision
        if requested is None:
            # A failed publication can leave a newer local HEAD. The supervisor
            # advances this exact ref only after confirmed synchronization/push.
            with self._process(['show-ref', '--verify', '--quiet', 'refs/globalland/published'], deadline) as proc:
                status = proc.wait()
                if status not in {0, 1}:
                    raise PublicSourceError('source_revision_invalid')
                if status == 1 and os.path.lexists(self.repo / 'refs/globalland/published'):
                    raise PublicSourceError('source_revision_invalid')
            requested = 'refs/globalland/published' if status == 0 else 'HEAD'
        raw = self._small(['rev-parse', '--verify', requested + '^{commit}'], deadline, 64)
        self.revision = raw.strip().decode('ascii')
        if not _OID.fullmatch(self.revision) or (revision and revision != self.revision):
            raise PublicSourceError('source_revision_invalid')

    @staticmethod
    def _deadline():
        return time.monotonic() + OPERATION_TIMEOUT

    @contextlib.contextmanager
    def _process(self, args, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PublicSourceError('source_timeout')
        # Discard inherited GIT_*, auth, SSH and user Git configuration. Git's
        # local object readers do not invoke hooks, filters or checkout helpers.
        env = {k: os.environ[k] for k in ('PATH', 'SYSTEMROOT', 'WINDIR') if k in os.environ}
        env.update({'LC_ALL': 'C', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_SYSTEM': os.devnull,
                    'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_COUNT': '0',
                    'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_NO_LAZY_FETCH': '1',
                    'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0',
                    'GIT_PROTOCOL_FROM_USER': '0'})
        argv = ['git', '--no-pager', '--literal-pathspecs', '--git-dir=' + str(self.repo),
                '-c', 'core.hooksPath=' + os.devnull, '-c', 'core.fsmonitor=false',
                '-c', 'credential.helper=', '-c', 'protocol.allow=never',
                '-c', 'protocol.file.allow=never', '-c', 'extensions.partialClone='] + args
        expired = threading.Event()
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, env=env)
        except OSError as exc:
            raise PublicSourceError('source_git_unavailable') from exc

        def terminate():
            expired.set()
            try:
                proc.kill()
            except OSError:
                pass

        timer = threading.Timer(remaining, terminate)
        timer.daemon = True
        timer.start()
        try:
            yield proc
            if expired.is_set():
                raise PublicSourceError('source_timeout')
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.kill()
            proc.stdout.close()
            proc.wait()

    def _small(self, args, deadline, bound):
        with self._process(args, deadline) as proc:
            raw = proc.stdout.read(bound + 1)
            if len(raw) > bound:
                raise PublicSourceError('source_git_output_invalid')
            if proc.wait() != 0:
                raise PublicSourceError('source_git_failed')
            return raw

    def _tree(self, prefix, deadline):
        # Tree records contain decimal size, object ID, mode and a literal NUL
        # terminated path. Stream records; never buffer the entire tree.
        args = ['ls-tree', '-r', '-l', '-z', '--full-tree', self.revision]
        if prefix:
            args += ['--', prefix]
        with self._process(args, deadline) as proc:
            pending = b''
            while True:
                block = proc.stdout.read(65536)
                if not block:
                    break
                records = block.split(b'\0')
                for index, fragment in enumerate(records):
                    # Invalid very long paths must not exhaust memory or block
                    # safe unrelated selections. Their retained prefix is enough
                    # to reject any selected directory (selectors <=4096 bytes).
                    pending = (pending + fragment)[:8192]
                    if index == len(records) - 1:
                        break
                    record, pending = pending, b''
                    if time.monotonic() >= deadline:
                        raise PublicSourceError('source_timeout')
                    try:
                        metadata, raw_path = record.split(b'\t', 1)
                        mode, kind, oid, size = metadata.split()
                        path = raw_path.decode('utf-8', errors='surrogateescape')
                        entry = {'path': path, 'size': int(size) if size != b'-' else 0,
                                 'oid': oid.decode('ascii')}
                        if not _OID.fullmatch(entry['oid']):
                            raise ValueError()
                    except (ValueError, UnicodeError) as exc:
                        raise PublicSourceError('source_tree_record_invalid') from exc
                    yield mode.decode('ascii'), kind.decode('ascii'), entry
            if pending or proc.wait() != 0:
                raise PublicSourceError('source_git_failed')

    @staticmethod
    def _eligible(mode, kind, entry):
        try:
            _path(entry['path'])
        except PublicSourceError:
            return False
        return mode in _REGULAR and kind == 'blob' and entry['size'] >= 0

    def iter_entries(self, prefix=''):
        """Stream all eligible metadata once, for host consumers of a full view.

        This is distinct from bounded public discovery pages: full comparisons
        must not repeatedly scan the tree from its beginning for every page.
        Closing an unfinished iterator also closes its Git child process.
        """
        prefix = _path(prefix, allow_empty=True)
        stream = self._tree(prefix, self._deadline())
        try:
            for mode, kind, entry in stream:
                if self._eligible(mode, kind, entry):
                    yield entry
        finally:
            stream.close()

    def list(self, prefix='products/', cursor=None, limit=100):
        prefix = _path(prefix, allow_empty=True)
        _integer(limit, 1, MAX_PAGE_ENTRIES, 'source_limit_invalid')
        after = ''
        if cursor is not None:
            if not isinstance(cursor, str) or len(cursor) > 16384:
                raise PublicSourceError('source_cursor_invalid')
            try:
                decoded = base64.b64decode(cursor.encode('ascii'), altchars=b'-_', validate=True)
                state = json.loads(decoded)
                if (not isinstance(state, list) or len(state) != 3 or state[:2] != [self.revision, prefix]
                        or not isinstance(state[2], str)):
                    raise ValueError()
                after = _path(state[2])
                if prefix and not (after == prefix or after.startswith(prefix.rstrip('/') + '/')):
                    raise ValueError()
            except (ValueError, UnicodeError, TypeError, PublicSourceError) as exc:
                raise PublicSourceError('source_cursor_invalid') from exc
        entries = []
        stream = self._tree(prefix, self._deadline())
        try:
            for mode, kind, entry in stream:
                if entry['path'] > after and self._eligible(mode, kind, entry):
                    entries.append(entry)
                    if len(entries) > limit:
                        break
        finally:
            stream.close()
        more = len(entries) > limit
        entries = entries[:limit]
        cursor = None
        if more:
            cursor = base64.urlsafe_b64encode(json.dumps(
                [self.revision, prefix, entries[-1]['path']], separators=(',', ':')).encode()).decode()
        return {'revision': self.revision, 'entries': entries, 'next_cursor': cursor}

    def _entry(self, path, deadline):
        path = _path(path)
        stream = self._tree(path, deadline)
        try:
            for mode, kind, entry in stream:
                if entry['path'] == path:
                    if not self._eligible(mode, kind, entry):
                        raise PublicSourceError('source_mode_invalid')
                    return entry
        finally:
            stream.close()
        raise PublicSourceError('source_path_missing')

    def read(self, path, offset=0, limit=MAX_READ_BYTES):
        _path(path)
        _integer(offset, 0, 2**63 - 1, 'source_offset_invalid')
        _integer(limit, 1, MAX_READ_BYTES, 'source_limit_invalid')
        deadline = self._deadline()
        entry = self._entry(path, deadline)
        if offset > entry['size']:
            raise PublicSourceError('source_offset_invalid')
        with self._process(['cat-file', 'blob', entry['oid']], deadline) as proc:
            remaining = offset
            while remaining:
                block = proc.stdout.read(min(65536, remaining))
                if not block:
                    raise PublicSourceError('source_blob_invalid')
                remaining -= len(block)
            raw = proc.stdout.read(min(limit, entry['size'] - offset))
            if len(raw) != min(limit, entry['size'] - offset):
                raise PublicSourceError('source_blob_invalid')
        encoding = 'utf-8'
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            if exc.reason == 'unexpected end of data' and exc.start > 0:
                raw = raw[:exc.start]
                content = raw.decode('utf-8')
            else:
                encoding = 'base64'
                content = base64.b64encode(raw).decode('ascii')
        next_offset = offset + len(raw)
        return {'revision': self.revision, 'path': path, 'oid': entry['oid'], 'offset': offset,
                'content': content, 'encoding': encoding, 'total_bytes': entry['size'],
                'next_offset': next_offset, 'eof': next_offset >= entry['size']}

    def export(self, inputs, destination, budget):
        _integer(budget, 0, 2**63 - 1, 'source_budget_invalid')
        if inputs is not None and (not isinstance(inputs, (list, tuple)) or len(inputs) > 10000):
            raise PublicSourceError('source_inputs_invalid')
        selectors = None if inputs is None else list(dict.fromkeys(_path(p) for p in inputs))
        selector_set = set(selectors or [])
        deadline = self._deadline()
        entries, found, selected_bytes = [], set(), 0
        # One full metadata walk keeps argv and process counts independent of
        # selected path count. Bodies are read only after every preflight passes.
        if selectors != []:
            for mode, kind, entry in self._tree('', deadline):
                path = entry['path']
                ancestors = [path[:i + 1] for i, c in enumerate(path) if c == '/']
                matches = selector_set.intersection([path, path + '/', *ancestors])
                if selectors is not None and not matches:
                    continue
                # A directory-looking selector can also name an invalid gitlink.
                found.update(matches)
                if not self._eligible(mode, kind, entry):
                    raise PublicSourceError('source_mode_invalid')
                selected_bytes += entry['size']
                if selected_bytes > budget:
                    raise PublicSourceError('source_budget_exceeded', selected_bytes)
                if len(entries) >= MAX_EXPORT_ENTRIES:
                    raise PublicSourceError('source_export_entries_exceeded', selected_bytes)
                entries.append(entry)
            if selectors is not None and set(selectors) != found:
                raise PublicSourceError('source_path_missing')
        with public_export_directory(destination, forbidden=[self.repo]) as staging:
            for entry in entries:
                target = staging / entry['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha1(b'blob ' + str(entry['size']).encode() + b'\0')
                copied = 0
                with target.open('xb') as output, self._process(
                        ['cat-file', 'blob', entry['oid']], deadline) as proc:
                    while True:
                        chunk = proc.stdout.read(min(65536, entry['size'] - copied + 1))
                        if not chunk:
                            break
                        copied += len(chunk)
                        if copied > entry['size']:
                            raise PublicSourceError('source_blob_invalid')
                        digest.update(chunk)
                        output.write(chunk)
                    if proc.wait() != 0 or copied != entry['size'] or digest.hexdigest() != entry['oid']:
                        raise PublicSourceError('source_blob_invalid')
                target.chmod(0o644)
        return {'revision': self.revision, 'entries': entries, 'total_bytes': selected_bytes}
