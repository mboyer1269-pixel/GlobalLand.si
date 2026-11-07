"""Private AgentMail receive/reply gateway. No mail content goes to public state.

The API accepting a reply is recorded as ACCEPTED, never as delivery. A send
whose outcome is uncertain remains UNKNOWN and is never retried automatically.
Pre-send failures retry with persisted exponential backoff so transient failures
can recover while later mail progresses. The supervisor owns scheduling.
"""
import contextlib
import hashlib
import itertools
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

    def list_received(self, *, page_token=None, max_pages=None, checkpoint=None):
        """Walk received metadata; bounded callers persist opaque continuation."""
        token, seen, pages = page_token, set(), 0
        while True:
            query = {'labels': 'received', 'ascending': 'true', 'limit': 100}
            if token:
                query['page_token'] = token
            try:
                page = self._request('GET', query=query)
            except MailError:
                if token is not None and pages == 0 and checkpoint is not None:
                    checkpoint(None)  # Stale provider cursors cannot wedge polling.
                raise
            messages = page.get('messages')
            if not isinstance(messages, list) or len(messages) > 100 or any(not isinstance(m, dict) for m in messages):
                raise MailError('Invalid mail API response')
            yield from messages
            token = page.get('next_page_token')
            if token is not None and token != '' and (not isinstance(token, str) or len(token) > 8192 or token in seen):
                if checkpoint is not None:
                    checkpoint(None)
                raise MailError('Invalid mail pagination')
            if checkpoint is not None:
                checkpoint(token or None)
            pages += 1
            if not token or (max_pages is not None and pages >= max_pages):
                return
            seen.add(token)

    def get_message(self, message_id):
        result = self._request('GET', '/' + _opaque(message_id))
        if (result.get('message_id') != message_id
                or result.get('inbox_id') != self.settings['inbox_id']):
            raise MailError('Mail identity mismatch')
        return result

    def reply(self, message_id, text, operation_id, *, route=None):
        if (not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT
                or not isinstance(operation_id, str)
                or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', operation_id)):
            raise MailError('Invalid mail reply')
        payload = {
            'text': text, 'reply_all': False,
            'headers': {'X-GlobalLand-Operation': operation_id, 'Auto-Submitted': 'auto-replied'},
        }
        if route is not None:
            import continuity
            if (not isinstance(route, dict) or set(route) != {'to', 'cc', 'bcc', 'reply_all'}
                    or not isinstance(route['to'], list) or len(route['to']) != 1
                    or route['reply_all'] is not False
                    or route != dict(to=[continuity.address(route['to'][0])], cc=[], bcc=[], reply_all=False)):
                raise MailError('Invalid mail route')
            payload.update(route)
        result = self._request('POST', '/' + _opaque(message_id) + '/reply', payload)
        _opaque(result.get('message_id'))
        return result


def _addresses(value):
    values = value if isinstance(value, list) else [value]
    if not all(isinstance(v, str) for v in values):
        return []
    return [address.lower() for _, address in getaddresses(values) if address]


def _financial_notice(message):
    """Protective routing hold only: sender domains never authenticate a deposit.

    Fixed provider roots cover registration and payment notices, including
    catch@payments.interac.ca and notifications@o.wealthsimple.com. Match an
    exact DNS root or its dot-delimited subdomains, not lookalike suffixes.
    Provider reference: help.wealthsimple.com/hc/en-ca/articles/5984295977243
    No body/subject keywords: ordinary customers may discuss payment freely.
    """
    roots = ('wealthsimple.com', 'interac.ca', 'interac.com')
    for address in _addresses(message.get('from', '')) + _addresses(message.get('reply_to', [])):
        domain = address.rsplit('@', 1)[-1].rstrip('.')
        if any(domain == root or domain.endswith('.' + root) for root in roots):
            return True
    return False


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
        self.config = config
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
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise MailError('Unsafe mail journal record')
        if not path.exists():
            return None
        try:
            if not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > MAX_RESPONSE:
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
        if (any(p.is_symlink() for p in (path, *path.parents))
                or (path.exists() and (not path.is_file() or path.stat().st_nlink != 1))):
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

    def _schedule(self):
        path = self.directory / '.schedule'
        if path.is_symlink():
            raise MailError('Unsafe mail schedule')
        if not path.exists():
            return dict(state='SCHEDULE', next_category='new', new_cursor=None,
                        retry_cursor=None, page_token=None, pending_new=[])
        try:
            if not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > 4 * MAX_RESPONSE:
                raise ValueError()
            value = json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(value, dict) or set(value) != {'state', 'next_category', 'new_cursor', 'retry_cursor', 'page_token', 'pending_new'}
                    or value['state'] != 'SCHEDULE' or value['next_category'] not in ('new', 'retry')
                    or any(value[k] is not None and (not isinstance(value[k], str)
                        or not re.fullmatch(r'[0-9a-f]{64}', value[k])) for k in ('new_cursor', 'retry_cursor'))
                    or (value['page_token'] is not None and (not isinstance(value['page_token'], str)
                        or not value['page_token'] or len(value['page_token']) > 8192))
                    or not isinstance(value['pending_new'], list) or len(value['pending_new']) > 200
                    or any(not isinstance(mid, str) or not mid or len(mid) > 2048 for mid in value['pending_new'])):
                raise ValueError()
            return value
        except Exception:
            raise MailError('Invalid mail schedule') from None

    @staticmethod
    def _rotate(candidates, cursor):
        for index, (_, path, _) in enumerate(candidates):
            if path.stem == cursor:
                return candidates[index+1:] + candidates[:index+1]
        return candidates

    def cycle(self, responder, *, on_processed=None):
        result = dict(enabled=self.settings is not None, processed=0, accepted=0,
                      ignored=0, unknown=0, failed=0, skipped=0)
        if not self.settings:
            return result
        try:
            with self._lock():
                schedule = self._schedule()
                retries = []
                # Recover even if a STARTED message has since left the received list.
                for path in self.directory.glob('*.json'):
                    try:
                        record = self._read(path)
                        if (record['state'] == 'ACCEPTED' and record.get('completion')
                                and record.get('inbox_id') == self.settings['inbox_id']
                                and self._path(record.get('message_id')) == path):
                            try:
                                import continuity
                                continuity.record_accepted(self.root, record)
                            except Exception:
                                pass  # Derived index repair never changes an accepted effect.
                        if record['state'] == 'STARTED':
                            record['state'] = 'UNKNOWN'
                            self._save(path, record)
                            result['unknown'] += 1
                        elif (record['state'] == 'RETRY' and record['retry_after'] <= time.time()
                                and record.get('inbox_id') == self.settings['inbox_id']
                                and self._path(record.get('message_id')) == path):
                            retries.append((record['message_id'], path, record))
                    except MailError:
                        pass  # Corrupt records remain immutable; handled per-message.
                fresh, seen, schedule_failed = [], set(), False
                def checkpoint(token):
                    nonlocal schedule_failed
                    schedule['page_token'] = token
                    schedule['pending_new'] = [mid for mid, _, _ in fresh]
                    try:
                        self._save(self.directory / '.schedule', schedule)
                    except Exception:
                        schedule_failed = True
                        raise
                try:
                    if schedule['pending_new']:
                        items = ({'message_id': mid} for mid in schedule['pending_new'])
                    elif isinstance(self.client, Client):
                        items = self.client.list_received(page_token=schedule['page_token'], max_pages=2, checkpoint=checkpoint)
                    else:
                        items = itertools.islice(self.client.list_received(), 200)
                    for item in items:
                        try:
                            mid = item.get('message_id'); path = self._path(mid)
                            if path in seen:
                                continue
                            seen.add(path)
                            if self._read(path) is not None:
                                result['skipped'] += 1
                            else:
                                fresh.append((mid, path, None))
                        except Exception:
                            result['failed'] += 1
                except Exception:
                    # Already-journaled READY/retry work remains serviceable if
                    # discovery fails; no remote error text leaves the gateway.
                    result['failed'] += 1
                if schedule_failed:
                    return result  # No body/send while durable scheduling failed.
                schedule['pending_new'] = [mid for mid, _, _ in fresh]
                self._save(self.directory / '.schedule', schedule)
                queues = dict(new=self._rotate(fresh, schedule['new_cursor']),
                              retry=self._rotate(sorted(retries, key=lambda v: v[1].name), schedule['retry_cursor']))
                attempts, limit = 0, self.settings['max_messages_per_cycle']
                while attempts < 2 * limit and result['processed'] < limit and any(queues.values()):
                    category = schedule['next_category']
                    if not queues[category]:
                        category = 'retry' if category == 'new' else 'new'
                    mid, path, previous = queues[category].pop(0)
                    if category == 'new':
                        schedule['pending_new'].remove(mid)
                    schedule[category + '_cursor'] = path.stem
                    schedule['next_category'] = 'retry' if category == 'new' else 'new'
                    # Advance before the body request, so held/failed messages
                    # cannot monopolize the next poll even after interruption.
                    self._save(self.directory / '.schedule', schedule)
                    attempts += 1
                    result['processed'] += 1
                    self._process(mid, path, responder, result, previous)
                    # Bookkeeping is deliberately outside _process's send
                    # uncertainty handler. ACCEPTED can never be downgraded by
                    # a failed host callback, and selection/fairness is unchanged.
                    if on_processed is not None:
                        try:
                            receipt = self._processing_receipt(path, previous)
                            if receipt is not None: on_processed(receipt)
                        except Exception:
                            pass  # Local reconciliation repairs callback loss.
        except Exception:
            result['failed'] += 1
        return result

    def _processing_receipt(self, path, previous):
        from initiative import source_revision
        current = self._read(path)
        if current is None or current.get('state') not in ('RETRY','ACCEPTED','IGNORED','FAILED','UNKNOWN'):
            return None
        if (current.get('inbox_id') != self.settings['inbox_id']
                or self._path(current.get('message_id')) != path): return None
        before = (source_revision('PRIVATE_RETRY_DUE', previous)[1]
                  if previous and previous.get('state') == 'RETRY' else None)
        after = (source_revision('PRIVATE_RETRY_DUE', current)[1]
                 if current['state'] == 'RETRY' else None)
        if previous and before == after: return None
        return dict(key=path.stem,before_version=before,after_version=after,
                    after_state=current['state'],disposition='REPLACED' if after else 'CONSUMED')

    def _hold_financial(self, message, path, result):
        if not _financial_notice(message):
            return False
        # Preserve the provider's original mail for administrative review. Only
        # a fixed private disposition is stored here; no model observation or
        # previously saved reply may survive as a customer/payment signal.
        self._save(path, dict(message_id=message['message_id'], inbox_id=message['inbox_id'],
                              state='IGNORED', hold_reason='FINANCIAL_NOTICE'))
        result['ignored'] += 1
        return True

    def _process(self, mid, path, responder, result, previous=None):
        record = {'message_id': mid, 'inbox_id': self.settings['inbox_id']}
        if previous and 'observation' in previous:
            record['observation'] = previous['observation']
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
            if self._hold_financial(message, path, result):
                return
            if _should_ignore(message, self.settings['inbox_address']):
                decision = {'action': 'ignore', 'text': ''}
            else:
                import continuity
                history_context = continuity.prepare(self.root, message, self.config)
                if history_context is not None:
                    decision = responder(message, history_context=history_context)
                    reference = getattr(responder, 'last_completion', None)
                    route = continuity.verify_completion(self.root, reference, message, decision)
                    record.update(completion=reference, route=route)
                else:
                    decision = responder(message)
                import commercial
                if commercial.settings(self.config)['state'] == 'ENABLED':
                    observation = getattr(responder, 'last_observation', None)
                    if observation is not None:
                        record['observation'] = observation
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
            # Refresh every path, including legacy and saved READY replies which
            # have no continuity descriptor. A financial destination is never
            # eligible merely because the original message passed the guard.
            current = self.client.get_message(mid)
            if (current.get('message_id') != mid
                    or current.get('inbox_id') != self.settings['inbox_id']):
                raise MailError('Mail identity mismatch')
            if self._hold_financial(current, path, result):
                return
            if _armor_deferred(current) or _should_ignore(current, self.settings['inbox_address']):
                raise MailError('Mail route changed')
            if record.get('completion'):
                continuity.verify_completion(self.root, record['completion'], current, decision)
            record.update(state='STARTED', operation_id='gl-' + uuid.uuid4().hex)
            self._save(path, record)
            started = True
            if record.get('route') is not None:
                response = self.client.reply(mid, decision['text'], record['operation_id'], route=record['route'])
                case = continuity.load_ready(self.root, record['completion'])
                if response.get('thread_id') != case['continuity']['binding']['thread_id']:
                    raise MailError('Mail response thread mismatch')
                record['response_thread_id'] = response['thread_id']
            else:
                response = self.client.reply(mid, decision['text'], record['operation_id'])
            _opaque(response.get('message_id'))
            record.update(state='ACCEPTED', outbound_message_id=response['message_id'])
            self._save(path, record)
            result['accepted'] += 1
            try:
                if record.get('completion'): continuity.record_accepted(self.root, record)
            except Exception:
                pass  # ACCEPTED is durable; index failure cannot cause another POST.
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
