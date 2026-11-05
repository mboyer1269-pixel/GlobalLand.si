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
import re

MAX_RECEIPT = 1024 * 1024
MAX_JOURNAL = 64 * 1024 * 1024
RECEIPT = re.compile(r'products/receipts/TASK-[0-9]{4,12}\.json')


class ReviewSourceError(ValueError):
    safe_message = True


def _record_authors(root, raw, prefix, found):
    from tools import task_origin
    try:
        record = json.loads(raw)
        if not isinstance(record, dict) or not isinstance(record.get('task'), str) or not isinstance(record.get('outputs'), dict):
            raise ValueError()
        if any(isinstance(name, str) and name.startswith(prefix) for name in record['outputs']):
            found.add(task_origin(root, {'id': record['task']})[1])
    except (TypeError, ValueError):
        raise ReviewSourceError('Publication author provenance unavailable or invalid') from None


def authors(root, folder, revision=None):
    """Providers (or EXTERNAL) whose tasks wrote files under `folder` (e.g. products/sites/x)."""
    root = pathlib.Path(root)
    prefix = folder.rstrip('/') + '/'
    found = set()
    catalog = (root / 'source.git').exists() or (root / 'source.git').is_symlink()
    try:
        if catalog:
            from catalog_views import source_for, entries, bounded_bytes
            source = source_for(root, revision=revision)
            for entry in entries(source, 'products/receipts/'):
                if RECEIPT.fullmatch(entry['path']):
                    _record_authors(root, bounded_bytes(source, entry['path'], MAX_RECEIPT), prefix, found)
        else:
            receipts = root / 'work' / 'products' / 'receipts'
            for path in receipts.glob('TASK-*.json'):
                if path.is_symlink():
                    continue
                try:
                    raw = path.read_text()
                    record = json.loads(raw)
                except (OSError, ValueError):
                    continue  # explicit legacy fixtures retain their old semantics
                if isinstance(record, dict) and isinstance(record.get('outputs'), dict):
                    _record_authors(root, raw, prefix, found)
        # A pending publication lives in its host journal, not in committed Git.
        # Union its receipt with committed authors; never let an overlay erase them.
        for path in (root / 'state').glob('TASK-*.json'):
            if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
                raise ReviewSourceError('Publication author provenance unavailable or invalid')
            compact = root / 'state/results' / path.name
            if compact.exists() or compact.is_symlink():
                from result_envelope import read_result
                if read_result(root, path).get('state') == 'PUBLISHED':
                    continue  # committed receipts are authoritative, no artifact-body read
            if path.stat().st_size > MAX_JOURNAL:
                raise ValueError()
            with path.open('rb') as stream:
                raw = stream.read(MAX_JOURNAL + 1)
            if len(raw) > MAX_JOURNAL:
                raise ValueError()
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise ValueError()
            if record.get('state') == 'PUBLISHED':
                continue
            files = record.get('files') or {}
            if not isinstance(files, dict):
                raise ValueError()
            for name, raw in files.items():
                if RECEIPT.fullmatch(name):
                    if not isinstance(raw, str) or len(raw.encode()) > MAX_RECEIPT:
                        raise ValueError()
                    _record_authors(root, raw, prefix, found)
    except (OSError, ValueError, RuntimeError):
        raise ReviewSourceError('Publication author provenance unavailable or invalid') from None
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
