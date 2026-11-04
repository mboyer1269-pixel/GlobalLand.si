"""Operator inspection/publication through the installed durable host contract."""
import datetime
import fcntl
import hashlib
import json
import pathlib
import sys
import time

ROOT = pathlib.Path('/opt/globalland')
SITE = 'welfare-tender-brief'
DIGEST = 'af0b1e99a1d3c24095c313fbd438d8bf854bc1b34c8abeb29ce3db5eccee116e'
sys.path.insert(0, str(ROOT / 'control'))
from supervisor import Supervisor, atomic_json
from sites import Client, load_site, read_token, settings
from review import approved, authors
from tools import validate_envelope


def durable_request():
    """Bind one reviewed content digest to one immutable executor request.

    The supervisor owns replay/recovery. A second operator invocation must not
    turn a completed or uncertain effect into a new task and publish it again.
    Caller holds the global supervisor lock.
    """
    path = ROOT / 'state/private' / ('contact-site-request-' + DIGEST + '.json')
    if path.is_symlink():
        raise ValueError('Unsafe publication request path')
    reused = path.exists()
    if reused:
        if path.stat().st_size > 16384:
            raise ValueError('Invalid durable publication request')
        record = json.loads(path.read_text())
        if (not isinstance(record, dict) or set(record) != {'site', 'digest', 'task'}
                or record['site'] != SITE or record['digest'] != DIGEST):
            raise ValueError('Invalid durable publication request')
        task = record['task']
    else:
        task = {'id': 'TASK-' + str(int(time.time()) * 100 + 77), 'type': 'TOOL',
                'action': 'PUBLISH_SITE', 'submitted_by': 'ACQUISITION',
                'created_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'estimated_cost_cad': 0, 'args': {'site': SITE}}
    # Validate before writing a request or starting the supervisor's journal.
    validate_envelope(task)
    if (task['action'] != 'PUBLISH_SITE' or task['submitted_by'] != 'ACQUISITION'
            or task['args'] != {'site': SITE}):
        raise ValueError('Unexpected durable publication task')
    if not reused:
        journal = ROOT / 'state' / (task['id'] + '.json')
        if journal.exists() or journal.is_symlink():
            raise ValueError('Task identifier already used; no effect attempted')
        atomic_json(path, {'site': SITE, 'digest': DIGEST, 'task': task})
    return task, reused


def receipt_pending(task, result):
    # On replay execute_tool returns the stored result without the additional
    # publication=PENDING marker; inspect the durable journal as well.
    path = ROOT / 'state' / (task['id'] + '.json')
    if path.is_symlink() or not path.is_file():
        return True
    try:
        record = json.loads(path.read_text())
        published = isinstance(record, dict) and record.get('state') == 'PUBLISHED'
    except (OSError, ValueError):
        published = False
    return 'publication' in result or not published


def main(mode):
    if mode not in ('inspect', 'publish'):
        raise ValueError('Unknown mode')
    with (ROOT / 'state/supervisor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        app = Supervisor()
        world, bank, config = app.services()
        files, digest = load_site(ROOT / 'work', SITE)
        if digest != DIGEST:
            raise ValueError('Page changed; review the new version before publication')
        cfg = settings(config)
        if not cfg or not cfg['require_review']:
            raise ValueError('Expected enabled Cloudflare and independent review')
        api = Client(read_token(ROOT))
        subdomain = api.call('GET', '/accounts/' + cfg['account_id'] + '/workers/subdomain')
        if subdomain.get('subdomain') != 'global-land':
            raise ValueError('Unexpected subdomain')
        origin = ('OPERATOR-CLOUDFLARE-20261104', 'codex')
        content_authors = authors(ROOT, 'products/sites/' + SITE) | {'codex', 'claude'}
        review_ready = approved(world.reviews(), 'site:' + SITE, digest, 'ACQUISITION', origin, content_authors)
        out = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'account_access_verified': True, 'site': SITE, 'digest': digest,
               'index_sha256': hashlib.sha256(files['/index.html']['t'].encode()).hexdigest(),
               'review_ready': review_ready, 'content_authors': sorted(content_authors),
               'url': 'https://globalland-' + SITE + '.global-land.workers.dev/'}
        if mode == 'publish':
            if not review_ready:
                raise ValueError('Independent review of the final content is required')
            if bank.snapshot()['state'] in ('HALTED', 'EXTINCT'):
                raise ValueError('World may not publish')
            task, reused = durable_request()
            result = app.execute_tool(task, world, bank, config, origin=origin)
            out['task_id'] = task['id']
            out['durable_request_reused'] = reused
            out['task_status'] = result['status']
            try:
                result_data = json.loads(result['output'])
            except (ValueError, TypeError):
                result_data = {}
            if not isinstance(result_data, dict):
                result_data = {}
            out['publication_status'] = result_data.get('status', 'NOT_VERIFIED')
            out['public_receipt_pending'] = receipt_pending(task, result)
            atomic_json(ROOT / 'state/private/contact-site-publication.json', out)
        else:
            atomic_json(ROOT / 'state/private/contact-site-preflight.json', out)
        print(json.dumps(out))
        if mode == 'publish':
            return 0 if (out['task_status'] == 'DONE'
                         and out['publication_status'] == 'ONLINE_VERIFIED'
                         and not out['public_receipt_pending']) else 1
        return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1]))
    except Exception as error:
        # Host safe errors only; never dump responses or credential config.
        print(json.dumps({'status': 'FAILED', 'exception_type': type(error).__name__}))
        raise SystemExit(1) from None
