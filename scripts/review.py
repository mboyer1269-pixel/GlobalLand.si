"""Two-key rule shared by every public effect (Apify listings, websites).

Who wrote the content is established by the host, never by the brain: each
EXEC that publishes files leaves products/receipts/<TASK>.json, and the task
identifier maps to the think turn and the provider that ran it
(tools.task_origin). A public effect needs the latest review of the exact
digest to be an APPROVE recorded by the host with a provenance that is
independent from:
- every provider that authored files in the published folder, and
- the turn and provider asking to publish.
The founder (review_admin.py) is always independent. Agent names prove
nothing: one brain can type any of them.
"""
import json
import pathlib


def authors(root, folder):
    """Providers (or EXTERNAL) whose tasks wrote files under `folder` (e.g. products/sites/x)."""
    from tools import task_origin
    root = pathlib.Path(root)
    receipts = root / 'work' / 'products' / 'receipts'
    prefix = folder.rstrip('/') + '/'
    found = set()
    if not receipts.is_dir():
        return found
    for path in receipts.glob('TASK-*.json'):
        if path.is_symlink():
            continue
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        outputs = record.get('outputs') if isinstance(record, dict) else None
        if isinstance(outputs, dict) and any(isinstance(name, str) and name.startswith(prefix) for name in outputs):
            found.add(task_origin(root, {'id': record.get('task', '')})[1])
    return found


def approved(reviews, subject, digest, author, origin=None, content_authors=()):
    relevant = [r for r in reviews or [] if r.get('subject') == subject and r.get('digest') == digest]
    if not relevant:
        return False
    latest = max(relevant, key=lambda r: (r.get('at') or 0, r.get('seq') or 0))
    if latest.get('verdict') != 'APPROVE' or latest.get('reviewer') == author:
        return False
    if latest.get('host_provider') == 'FOUNDER':
        return True
    if not latest.get('host_provider') or not latest.get('host_turn'):
        return False
    turn, provider = origin or (None, None)
    independent_of = set(content_authors) | {provider}
    return latest['host_provider'] not in independent_of and latest['host_turn'] != turn
