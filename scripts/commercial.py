"""Private, unverified interpretations of incoming correspondence.

Only project() is public. progress_snapshot() contains private hashed identities.
Neither function writes, sends, classifies, or changes financial evidence.
"""
import datetime
import hashlib
import itertools
import json
import pathlib
import re
import stat
from email.utils import getaddresses

CATEGORIES = ('UNKNOWN', 'REQUEST', 'EXPLICIT_INTEREST', 'PRICE_QUESTION', 'REJECTION',
              'CUSTOMER_REPORTED_DELIVERY', 'DELIVERY_ISSUE', 'NONCOMMERCIAL')
AUDIENCES = ('UNKNOWN', 'ORDINARY', 'TEST', 'AUTOMATED')
ORIGINS = ('SYNTHETIC', 'AUTOMATED', 'INBOUND_UNVERIFIED', 'UNKNOWN')
MAX_RECORDS = 2000
MAX_RECORD = 128 * 1024
DISCLAIMER = ('Unverified message interpretations, not verified humans, customers, orders, '
              'delivery, payments or profit. Synthetic and automated sources are excluded. '
              'Treasury alone supplies verified revenue. Partial/unavailable is not zero demand.')


def settings(config):
    mail = config.get('agentmail', {})
    if not isinstance(mail, dict): return {'state': 'UNAVAILABLE'}
    value = mail.get('commercial', {})
    if not isinstance(value, dict) or set(value) - {'enabled', 'synthetic_senders'}:
        return {'state': 'UNAVAILABLE'}
    enabled = value.get('enabled', False)
    senders = value.get('synthetic_senders', [])
    if (type(enabled) is not bool or not isinstance(senders, list) or len(senders) > 100
            or any(not isinstance(s, str) or len(s) > 254
                   or not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+', s) for s in senders)):
        return {'state': 'UNAVAILABLE'}
    return {'state': 'ENABLED' if enabled else 'DISABLED', 'synthetic_senders': tuple(senders)}


def _safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Commercial source unavailable')
    return path


def _read(path, limit):
    _safe(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
        raise ValueError('Commercial source unavailable')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit: raise ValueError('Commercial source unavailable')
    return json.loads(raw)


def allowed_experiments(root):
    root = pathlib.Path(root); ids = set(); truncated = False; available = True
    try:
        path = _safe(root / 'work/world/status.json')
        if path.exists():
            world = _read(path, 1024 * 1024)
            missions = world['missions']
            if not isinstance(missions, list): raise ValueError()
            for m in missions:
                ident = m.get('mission_id') if isinstance(m, dict) else None
                if isinstance(ident, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', ident):
                    ids.add('mission:' + ident)
        sites = _safe(root / 'work/products/sites')
        if sites.exists():
            for path in itertools.islice(sites.iterdir(), 201):
                if len(ids) > 100: truncated = True; break
                if (not path.is_symlink() and path.is_dir()
                        and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', path.name)):
                    ids.add('site:' + path.name)
    except (OSError, ValueError, KeyError, TypeError):
        available = False
    return dict(ids=sorted(ids)[:100], truncated=truncated or len(ids) > 100, available=available)


def host_origin(message, config):
    cfg = settings(config)
    if cfg['state'] != 'ENABLED': return 'UNKNOWN'
    sender = message.get('from', '')
    if isinstance(sender, str):
        addresses = [address for _, address in getaddresses([sender])]
        if any(a in cfg['synthetic_senders'] for a in addresses): return 'SYNTHETIC'
    else: addresses = []
    headers = message.get('headers') or {}
    if isinstance(headers, dict):
        headers = {k.lower(): v.lower() for k, v in headers.items()
                   if isinstance(k, str) and isinstance(v, str)}
        if (headers.get('auto-submitted', 'no') != 'no' or 'list-id' in headers
                or headers.get('precedence') in ('bulk', 'list', 'junk')):
            return 'AUTOMATED'
    return 'INBOUND_UNVERIFIED' if len(addresses) == 1 else 'UNKNOWN'


def normalize_observation(raw, message, allowed_experiments, host_origin, provider):
    origin = host_origin if host_origin in ORIGINS else 'UNKNOWN'
    result = dict(category='UNKNOWN', audience='UNKNOWN', experiment_id=None, evidence=None,
                  origin=origin, attribution='UNATTRIBUTED',
                  provider=provider if provider in ('claude', 'codex', 'cursor') else None,
                  observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    if (not isinstance(raw, dict) or set(raw) != {'category', 'audience', 'experiment_id', 'evidence'}
            or raw['category'] not in CATEGORIES or raw['audience'] not in AUDIENCES
            or (raw['experiment_id'] is not None and not isinstance(raw['experiment_id'], str))):
        return result
    # Model output can only downgrade origin, never promote a source.
    if origin != 'SYNTHETIC':
        if raw['audience'] == 'TEST': result['origin'] = 'SYNTHETIC'
        elif raw['audience'] == 'AUTOMATED': result['origin'] = 'AUTOMATED'
    category, evidence = raw['category'], raw['evidence']
    if category in ('UNKNOWN', 'NONCOMMERCIAL'):
        if evidence is not None: return result
    elif (not isinstance(evidence, dict) or set(evidence) != {'field', 'quote'}
          or evidence['field'] not in ('text', 'extracted_text')
          or not isinstance(evidence['quote'], str) or not 1 <= len(evidence['quote']) <= 240
          or not isinstance(message.get(evidence['field']), str)
          or evidence['quote'] not in message[evidence['field']]):
        return result
    result.update(category=category, audience=raw['audience'], evidence=evidence)
    allowed = allowed_experiments.get('ids', [])
    if raw['experiment_id'] is not None and raw['experiment_id'] in allowed:
        result.update(experiment_id=raw['experiment_id'], attribution='MODEL_INFERRED')
    return result


def prompt(root, config):
    if settings(config)['state'] != 'ENABLED': return ''
    return ('\nOptionally add observation to the final summary JSON, with exactly category, audience, '
            'experiment_id, evidence. category is one of ' + ', '.join(CATEGORIES) +
            '; audience is UNKNOWN, ORDINARY, TEST or AUTOMATED. experiment_id is null or one of '
            + json.dumps(allowed_experiments(root)['ids']) + '. This association is inferred only. '
            'evidence is null for UNKNOWN/NONCOMMERCIAL; otherwise exactly {"field":"text" or '
            '"extracted_text","quote":"literal nonempty fragment from that incoming field, max 240 characters"}. '
            'Use UNKNOWN when uncertain. These are unverified interpretations, never financial evidence.\n')


def _scan(root, config):
    cfg = settings(config)
    if cfg['state'] != 'ENABLED': return dict(state=cfg['state'], rows=[], allowed={'ids': [], 'truncated': False})
    directory = pathlib.Path(root) / 'state/private/agentmail'
    allowed = allowed_experiments(root)
    result = dict(state='AVAILABLE', rows=[], allowed=allowed)
    try:
        _safe(directory)
        if not directory.is_dir(): raise ValueError()
        paths = list(itertools.islice(directory.glob('*.json'), MAX_RECORDS + 1))
        if len(paths) > MAX_RECORDS: result['state'] = 'PARTIAL'
        seen = set()
        for path in paths[:MAX_RECORDS]:
            try:
                record = _read(path, MAX_RECORD)
                inbox, mid = record['inbox_id'], record['message_id']
                if (not isinstance(inbox, str) or not isinstance(mid, str) or not inbox or not mid
                        or len(inbox) > 2048 or len(mid) > 2048
                        or record.get('state') not in ('STARTED', 'UNKNOWN', 'ACCEPTED', 'IGNORED', 'FAILED', 'RETRY')):
                    raise ValueError()
                key = hashlib.sha256((inbox + '\0' + mid).encode()).hexdigest()
                if path.name != key + '.json' or key in seen: raise ValueError()
                seen.add(key)
                observation = record.get('observation')
                if observation is not None:
                    if not _valid_observation(observation):
                        raise ValueError()
                result['rows'].append((key, observation))
            except (OSError, ValueError, KeyError, TypeError): result['state'] = 'PARTIAL'
        if not allowed.get('available', True): result['state'] = 'PARTIAL'
    except (OSError, ValueError): result['state'] = 'UNAVAILABLE'
    return result


def _valid_observation(o):
    if (not isinstance(o, dict) or set(o) != {'category', 'audience', 'experiment_id', 'evidence',
            'origin', 'attribution', 'provider', 'observed_at'}
            or o['category'] not in CATEGORIES or o['audience'] not in AUDIENCES
            or o['origin'] not in ORIGINS or o['attribution'] not in ('MODEL_INFERRED', 'UNATTRIBUTED')
            or o['provider'] not in (None, 'claude', 'codex', 'cursor')
            or (o['experiment_id'] is not None and (not isinstance(o['experiment_id'], str)
                or len(o['experiment_id']) > 110))
            or not isinstance(o['observed_at'], str)
            or not re.fullmatch(r'[0-9T:+.Z-]{20,40}', o['observed_at'])):
        return False
    evidence = o['evidence']
    if o['category'] in ('UNKNOWN', 'NONCOMMERCIAL'): return evidence is None
    return (isinstance(evidence, dict) and set(evidence) == {'field', 'quote'}
            and evidence['field'] in ('text', 'extracted_text')
            and isinstance(evidence['quote'], str) and 1 <= len(evidence['quote']) <= 240)


def _interpreted(observation):
    return (observation is not None and observation['origin'] == 'INBOUND_UNVERIFIED'
            and observation['audience'] not in ('TEST', 'AUTOMATED')
            and observation['category'] not in ('UNKNOWN', 'NONCOMMERCIAL'))


def progress_snapshot(root, config):
    scan = _scan(root, config)
    return dict(state=scan['state'], sources=[key for key, _ in scan['rows']],
                interpreted_sources=[key for key, o in scan['rows'] if _interpreted(o)])


def project(root, config):
    scan = _scan(root, config)
    view = dict(state=scan['state'], disclaimer=DISCLAIMER,
                experiment_allowlist_truncated=scan['allowed']['truncated'])
    if scan['state'] not in ('AVAILABLE', 'PARTIAL'): return view
    counts = dict.fromkeys(CATEGORIES, 0); experiments = {}; excluded = 0; unknown = 0
    for _, observation in scan['rows']:
        if not _interpreted(observation):
            if observation and observation['origin'] in ('SYNTHETIC', 'AUTOMATED'): excluded += 1
            else: unknown += 1
            continue
        category = observation['category']; counts[category] += 1
        ident = observation.get('experiment_id')
        if ident in scan['allowed']['ids'] and observation['attribution'] == 'MODEL_INFERRED':
            experiments.setdefault(ident, dict.fromkeys(CATEGORIES, 0))[category] += 1
    view.update(counts=counts, inferred_experiments=experiments, excluded_sources=excluded,
                unclassified_sources=unknown)
    return view
