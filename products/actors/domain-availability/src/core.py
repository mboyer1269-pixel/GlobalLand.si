import http.client
import json
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .public_http import request, PublicHTTPError

MAX_DOMAINS = 1000
MAX_BODY = 262144
MAX_REDIRECTS = 3
USER_AGENT = 'GlobalLand-domain-availability/0.1 (Apify Actor built and maintained by autonomous AI agents)'
BOOTSTRAP_PATH = Path(__file__).resolve().parent.parent / 'data' / 'rdap-dns-bootstrap.json'
REDIRECTS = (301, 302, 303, 307, 308)
_LABEL = re.compile(r'^(?!-)[a-z0-9-]{1,63}(?<!-)$')


def normalize_domain(raw):
    if not isinstance(raw, str):
        return None
    d = raw.strip().lower()
    if '://' in d:
        try:
            d = urlsplit(d).hostname or ''
        except ValueError:
            return None
    d = d.rstrip('.')
    if not d or any(c.isspace() for c in d):
        return None
    try:
        d = d.encode('idna').decode('ascii')
    except UnicodeError:
        return None
    labels = d.split('.')
    if len(d) > 253 or len(labels) < 2 or labels[-1].isdigit() or not all(_LABEL.match(x) for x in labels):
        return None
    return d


def normalize_domains(values, limit=MAX_DOMAINS):
    if isinstance(values, str):
        values = values.splitlines()
    if not isinstance(values, list):
        return []
    out, seen = [], set()
    for raw in values:
        if isinstance(raw, str) and not raw.strip():
            continue
        d = normalize_domain(raw)
        key = d or ('invalid:' + repr(raw))
        if key in seen:
            continue
        seen.add(key)
        out.append((raw, d))
        if len(out) >= limit:
            break
    return out


def load_bootstrap(path=BOOTSTRAP_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    mapping = {}
    for entry in data.get('services', []):
        tlds, urls = entry[0], entry[1]
        https = [u for u in urls if isinstance(u, str) and u.startswith('https://')]
        if not https:
            continue
        base = https[0] if https[0].endswith('/') else https[0] + '/'
        for t in tlds:
            mapping[t.lower()] = base
    return mapping


def find_server(domain, mapping):
    if not domain:
        return None
    labels = domain.split('.')
    for i in range(1, len(labels)):
        base = mapping.get('.'.join(labels[i:]))
        if base:
            return base
    return None


def _row(raw, domain):
    return {'input': raw if isinstance(raw, str) else repr(raw), 'domain': domain, 'available': None,
            'rdap_status_code': None, 'statuses': [], 'registered_at': None, 'expires_at': None,
            'registrar': None, 'nameservers': [], 'rdap_server': None, 'redirect_count': 0,
            'error_code': None, 'error': None, 'elapsed_ms': 0, 'checked_at': None}


def _vcard_fn(vcard):
    try:
        for prop in vcard[1]:
            if prop[0] == 'fn' and isinstance(prop[3], str) and prop[3].strip():
                return prop[3].strip()[:200]
    except (TypeError, IndexError, KeyError):
        pass
    return None


def _extract(row, doc):
    # Only registry facts are kept: status, dates, registrar organisation, nameservers.
    # Registrant, admin, tech, abuse and any other contact entity are never read.
    statuses = doc.get('status')
    if isinstance(statuses, list):
        row['statuses'] = [s for s in statuses if isinstance(s, str)][:20]
    for ev in doc.get('events') or []:
        if not isinstance(ev, dict) or not isinstance(ev.get('eventDate'), str):
            continue
        if ev.get('eventAction') == 'registration' and row['registered_at'] is None:
            row['registered_at'] = ev['eventDate']
        elif ev.get('eventAction') == 'expiration' and row['expires_at'] is None:
            row['expires_at'] = ev['eventDate']
    for ent in doc.get('entities') or []:
        if isinstance(ent, dict) and 'registrar' in (ent.get('roles') or []):
            row['registrar'] = _vcard_fn(ent.get('vcardArray'))
            break
    ns = doc.get('nameservers')
    if isinstance(ns, list):
        row['nameservers'] = [n['ldhName'].lower() for n in ns
                              if isinstance(n, dict) and isinstance(n.get('ldhName'), str)][:20]
