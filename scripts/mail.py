"""Private AgentMail receive/reply gateway. No mail content goes to public state.

The API accepting a reply is recorded as ACCEPTED, never as delivery. A send
whose outcome is uncertain remains UNKNOWN and is never retried automatically.
Pre-send failures retry with persisted exponential backoff so transient failures
can recover while later mail progresses. The supervisor owns scheduling.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from email.utils import getaddresses


API = 'https://api.agentmail.to/v0'
MAX_RESPONSE = 2 * 1024 * 1024
MAX_TEXT = 32000
STATES = {'STARTED', 'UNKNOWN', 'ACCEPTED', 'IGNORED', 'FAILED', 'RETRY'}


class MailError(ValueError):
    """Only fixed, public-safe error messages may leave this module."""
    safe_message = True


def settings(config):
    value = config.get('agentmail') or {}
    if not isinstance(value, dict):
        raise MailError('Invalid mail configuration')
    if value.get('enabled') is not True:
        return None
    inbox = value.get('inbox_id')
    address = value.get('inbox_address')
    limit = value.get('max_messages_per_cycle', 3)
    if (not isinstance(inbox, str) or not inbox or len(inbox) > 512
            or any(ord(c) < 32 for c in inbox)
            or not isinstance(address, str)
            or not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+', address)
            or type(limit) is not int or not 1 <= limit <= 100):
        raise MailError('Invalid mail configuration')
    return dict(inbox_id=inbox, inbox_address=address.lower(), max_messages_per_cycle=limit)


def _opaque(value):
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise MailError('Invalid mail identifier')
    if value in {'.', '..'}:
        return '%2E' * len(value)
    return urllib.parse.quote(value, safe='')


def _read_token(root):
    path = Path(root) / 'credentials/agentmail/token'
    try:
        if any(p.is_symlink() for p in (path, path.parent, path.parent.parent)):
            raise MailError('Mail credential unavailable')
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode) or mode & 0o077:
            raise MailError('Mail credential must be owner-only')
        with path.open('r', encoding='utf-8') as stream:
            token = stream.read(1025).strip()
        if not token or len(token) > 1024 or any(c.isspace() for c in token):
            raise MailError('Invalid mail credential')
        return token
    except MailError:
        raise
    except Exception:
        raise MailError('Mail credential unavailable') from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    """Fixed-origin client. A test transport takes (method, url, headers, payload).

    The transport returns decoded JSON. It is a trusted test seam, never model
    input. Production reads the token only on the host and disables proxy/redirect
    forwarding. Responses and errors are bounded and errors discard remote text.
    """
    def __init__(self, root, config, transport=None):
        self.root = Path(root)
        self.settings = settings(config)
        self.transport = transport

    def _request(self, method, suffix='', payload=None, query=None):
        if self.settings is None:
            raise MailError('Mail is disabled')
        url = API + '/inboxes/' + _opaque(self.settings['inbox_id']) + '/messages' + suffix
        if query:
            url += '?' + urllib.parse.urlencode(query)
        try:
            headers = {'Authorization': 'Bearer ' + _read_token(self.root),
                       'Content-Type': 'application/json', 'Accept': 'application/json'}
            if self.transport is not None:
                result = self.transport(method, url, headers, payload)
                raw = json.dumps(result, ensure_ascii=False).encode('utf-8')
            else:
                body = None if payload is None else json.dumps(payload).encode('utf-8')
                request = urllib.request.Request(url, data=body, method=method, headers=headers)
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
                with opener.open(request, timeout=30) as response:
                    if not 200 <= response.status < 300:
                        raise MailError('Mail API request failed')
                    raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise MailError('Mail API response too large')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise MailError('Invalid mail API response')
            return result
        except MailError:
            raise
        except Exception:
            raise MailError('Mail API request failed') from None

    def list_received(self):
        """Walk every received page oldest first; callers may stop lazily."""
        token, seen = None, set()
        while True:
            query = {'labels': 'received', 'ascending': 'true', 'limit': 100}
            if token:
                query['page_token'] = token
            page = self._request('GET', query=query)
            messages = page.get('messages')
            if not isinstance(messages, list) or any(not isinstance(m, dict) for m in messages):
                raise MailError('Invalid mail API response')
            yield from messages
            token = page.get('next_page_token')
            if token is None or token == '':
                return
            if not isinstance(token, str) or len(token) > 8192 or token in seen:
                raise MailError('Invalid mail pagination')
            seen.add(token)

    def get_message(self, message_id):
        result = self._request('GET', '/' + _opaque(message_id))
        if (result.get('message_id') != message_id
                or result.get('inbox_id') != self.settings['inbox_id']):
            raise MailError('Mail identity mismatch')
        return result

    def reply(self, message_id, text, operation_id):
        if (not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT
                or not isinstance(operation_id, str)
                or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', operation_id)):
            raise MailError('Invalid mail reply')
        result = self._request('POST', '/' + _opaque(message_id) + '/reply', {
            'text': text, 'reply_all': False,
            'headers': {'X-GlobalLand-Operation': operation_id, 'Auto-Submitted': 'auto-replied'},
        })
        _opaque(result.get('message_id'))
        return result


def _addresses(value):
    values = value if isinstance(value, list) else [value]
    if not all(isinstance(v, str) for v in values):
        return []
    return [address.lower() for _, address in getaddresses(values) if address]


def _armor_deferred(message):
    """Polling also sees held mail; wait for a clear result or verified release.

    AgentMail documents unavailable scans as requiring the same review as a
    review verdict. Held labels may lag either verdict or release, so check both.
    This gateway never releases mail or changes provider security settings.
    """
    labels = message.get('labels')
    if isinstance(labels, list) and 'agent-armor-held' in labels:
        return True
    armor = message.get('agent_armor')
    if armor is None:
        return False  # Mail received without Agent Armor has no result field.
    if not isinstance(armor, dict) or armor.get('status') != 'complete':
        return True
    if armor.get('verdict') == 'clear':
        return False
    override = armor.get('manual_override')
    released = (isinstance(override, dict)
                and all(isinstance(override.get(k), str) and override[k].strip()
                        for k in ('override_id', 'released_at')))
    return not (armor.get('verdict') == 'review' and released)


def _should_ignore(message, own_address):
    labels = message.get('labels')
    if not isinstance(labels, list) or not all(isinstance(v, str) for v in labels):
        return True
    labels = {v.lower() for v in labels}
    if 'received' not in labels or labels & {'sent', 'spam', 'blocked', 'bounced', 'rejected', 'junk', 'unauthenticated', 'trash'}:
        return True
    headers = message.get('headers') or {}
    if not isinstance(headers, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                for k, v in headers.items()):
        return True
    headers = {k.lower(): v.strip().lower() for k, v in headers.items()}
    sender = _addresses(message.get('from', ''))
    targets = _addresses(message.get('reply_to', [])) or sender
    if not sender or not targets or own_address in sender + targets:
        return True
    if any(a.split('@')[0] in {'mailer-daemon', 'postmaster', 'noreply', 'no-reply', 'donotreply'}
           for a in sender + targets):
        return True
    if headers.get('auto-submitted', 'no') != 'no':
        return True
    if (headers.get('precedence') in {'bulk', 'junk', 'list'}
            or headers.get('return-path') == '<>'
            or 'x-globalland-operation' in headers
            or 'x-autoreply' in headers or 'x-autorespond' in headers
            or 'list-id' in headers
            or 'report-type=delivery-status' in headers.get('content-type', '')
            or 'report-type=disposition-notification' in headers.get('content-type', '')):
        return True
    subject = str(message.get('subject', '')).lower().strip()
    if subject.startswith(('automatic reply:', 'auto-reply:', 'out of office:',
                           'undeliverable:', 'delivery status notification')):
        return True
    return False


class Mailbox:
    def __init__(self, root, config, client=None):
        self.root = Path(root)
        self.settings = settings(config)
        self.client = client if client is not None else Client(root, config)
        self.directory = self.root / 'state/private/agentmail'

    def _prepare(self):
        for path in (self.root / 'state', self.root / 'state/private', self.directory):
            if path.is_symlink():
                raise MailError('Unsafe mail journal directory')
            path.mkdir(mode=0o700, exist_ok=True)
        os.chmod(self.root / 'state/private', 0o700)
        os.chmod(self.directory, 0o700)

    def _path(self, mid):
        _opaque(mid)
        key = self.settings['inbox_id'] + '\0' + mid
        return self.directory / (hashlib.sha256(key.encode('utf-8')).hexdigest() + '.json')

    def _read(self, path):
        if path.is_symlink():
            raise MailError('Unsafe mail journal record')
        if not path.exists():
            return None
        try:
            if path.stat().st_size > MAX_RESPONSE:
                raise ValueError()
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('state') not in STATES:
                raise ValueError()
            if data['state'] == 'RETRY' and (type(data.get('attempts')) is not int
                    or data['attempts'] < 1 or type(data.get('retry_after')) is not int
                    or data['retry_after'] < 0):
                raise ValueError()
            return data
        except Exception:
            raise MailError('Invalid mail journal record') from None

    def _save(self, path, data):
        if path.is_symlink():
            raise MailError('Unsafe mail journal record')
        fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=self.directory)
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            if os.name == 'posix':
                directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @contextlib.contextmanager
    def _lock(self):
        self._prepare()
        path = self.directory / '.lock'
        if path.is_symlink():
            raise MailError('Unsafe mail journal lock')
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == 'posix':
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b'0')
                os.lseek(fd, 0, 0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except Exception:
            os.close(fd)
            raise MailError('Mail cycle already running') from None
        try:
            yield
        finally:
            os.close(fd)

    def status(self):
        result = dict(enabled=self.settings is not None, accepted=0, ignored=0, unknown=0, failed=0)
        if not self.settings or not self.directory.exists():
            return result
        if any(p.is_symlink() for p in (self.root / 'state', self.directory.parent, self.directory)):
            result['failed'] = 1
            return result
        for path in self.directory.glob('*.json'):
            try:
                record = self._read(path)
                state = record['state']
                key = {'STARTED': 'unknown', 'RETRY': 'failed'}.get(state, state.lower())
                result[key] += 1
            except Exception:
                result['failed'] += 1
        return result

    def cycle(self, responder):
        result = dict(enabled=self.settings is not None, processed=0, accepted=0,
                      ignored=0, unknown=0, failed=0, skipped=0)
        if not self.settings:
            return result
        try:
            with self._lock():
                # Recover even if a STARTED message has since left the received list.
                for path in self.directory.glob('*.json'):
                    try:
                        record = self._read(path)
                        if record['state'] == 'STARTED':
                            record['state'] = 'UNKNOWN'
                            self._save(path, record)
                            result['unknown'] += 1
                    except MailError:
                        pass  # Corrupt records remain immutable; handled per-message.
                retries = []
                for item in self.client.list_received():
                    mid = item.get('message_id')
                    try:
                        path = self._path(mid)
                        previous = self._read(path)
                        if previous is not None and (previous['state'] != 'RETRY'
                                or previous['retry_after'] > time.time()):
                            result['skipped'] += 1
                            continue
                        if previous is not None:
                            # Fresh messages get a turn before due retries, even
                            # when polling runs more slowly than retry backoff.
                            retries.append((mid, path, previous))
                            continue
                    except Exception:
                        result['failed'] += 1
                        continue
                    result['processed'] += 1
                    self._process(mid, path, responder, result, previous)
                    if result['processed'] >= self.settings['max_messages_per_cycle']:
                        break
                if result['processed'] < self.settings['max_messages_per_cycle']:
                    for mid, path, previous in retries:
                        result['processed'] += 1
                        self._process(mid, path, responder, result, previous)
                        if result['processed'] >= self.settings['max_messages_per_cycle']:
                            break
        except Exception:
            result['failed'] += 1
        return result

    def _process(self, mid, path, responder, result, previous=None):
        record = {'message_id': mid, 'inbox_id': self.settings['inbox_id']}
        started = False
        try:
            message = self.client.get_message(mid)
            if (message.get('message_id') != mid
                    or message.get('inbox_id') != self.settings['inbox_id']):
                raise MailError('Mail identity mismatch')
            if _armor_deferred(message):
                # Revisit after the scan or a provider-side human release. Never
                # give held content to the responder or create a terminal record.
                result['processed'] -= 1
                result['skipped'] += 1
                return
            if _should_ignore(message, self.settings['inbox_address']):
                decision = {'action': 'ignore', 'text': ''}
            else:
                decision = responder(message)
                provider = getattr(responder, 'last_provider', None)
                if provider in ('codex', 'claude', 'cursor'):
                    record['provider'] = provider
            if (not isinstance(decision, dict) or set(decision) != {'action', 'text'}
                    or decision['action'] not in {'reply', 'ignore'}
                    or not isinstance(decision['text'], str)
                    or len(decision['text']) > MAX_TEXT):
                raise MailError('Invalid mail decision')
            if decision['action'] == 'ignore':
                record['state'] = 'IGNORED'
                self._save(path, record)
                result['ignored'] += 1
                return
            if not decision['text'].strip():
                raise MailError('Empty mail reply')
            record.update(state='STARTED', operation_id='gl-' + uuid.uuid4().hex)
            self._save(path, record)
            started = True
            response = self.client.reply(mid, decision['text'], record['operation_id'])
            _opaque(response.get('message_id'))
            record.update(state='ACCEPTED', outbound_message_id=response['message_id'])
            self._save(path, record)
            result['accepted'] += 1
        except Exception as error:
            if not started and getattr(type(error), 'private_deferred', False) is True:
                result['processed'] -= 1
                result['skipped'] += 1
                if getattr(error, 'progressed', True):
                    # A partial computation is neither sent nor terminally
                    # ignored. Delay it while other cases use the shared budget.
                    record.update(state='RETRY', attempts=(previous or {}).get('attempts', 0) + 1,
                                  retry_after=int(time.time()) + 600)
                    try:
                        self._save(path, record)
                    except Exception:
                        result['failed'] += 1
                return
            record['state'] = 'UNKNOWN' if started else 'RETRY'
            if not started:
                attempts = (previous or {}).get('attempts', 0) + 1
                record.update(attempts=attempts,
                              retry_after=int(time.time()) + min(60 * 2 ** min(attempts - 1, 6), 3600))
            # If persistence fails, leave STARTED in place and never report success.
            try:
                self._save(path, record)
            except Exception:
                pass
            result['unknown' if started else 'failed'] += 1
