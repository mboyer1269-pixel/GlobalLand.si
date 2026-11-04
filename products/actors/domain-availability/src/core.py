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


def check_domain(raw, domain, mapping, timeout=15, allow_private=False, max_redirects=MAX_REDIRECTS):
    row = _row(raw, domain)
    start = time.monotonic()
    try:
        if domain is None:
            raise PublicHTTPError('invalid_domain', 'not a valid domain name')
        base = find_server(domain, mapping)
        if base is None:
            raise PublicHTTPError('unsupported_tld', 'no RDAP server listed in the IANA bootstrap for this TLD')
        row['rdap_server'] = base
        url = base + 'domain/' + domain
        headers = {'Accept': 'application/rdap+json, application/json', 'User-Agent': USER_AGENT}
        while True:
            status, location, body = request(url, 'GET', timeout, read_bytes=MAX_BODY + 1,
                                             headers=headers, allow_private=allow_private)
            if status in REDIRECTS and location:
                if row['redirect_count'] >= max_redirects:
                    raise PublicHTTPError('too_many_redirects', 'more than %d RDAP redirects' % max_redirects)
                row['redirect_count'] += 1
                url = urljoin(url, location)
                continue
            break
        row['rdap_status_code'] = status
        if status == 404:
            row['available'] = True
        elif status == 200:
            if len(body) > MAX_BODY:
                raise PublicHTTPError('body_too_large', 'RDAP response exceeds %d bytes' % MAX_BODY)
            try:
                doc = json.loads(body.decode('utf-8'))
            except (UnicodeDecodeError, ValueError):
                raise PublicHTTPError('invalid_json', 'RDAP response is not valid JSON') from None
            if not isinstance(doc, dict) or doc.get('objectClassName') != 'domain':
                raise PublicHTTPError('unexpected_response', 'RDAP response is not a domain object')
            row['available'] = False
            _extract(row, doc)
        elif status == 429:
            raise PublicHTTPError('rate_limited', 'RDAP server rate limit (HTTP 429); retry later')
        else:
            raise PublicHTTPError('http_error', 'RDAP server returned HTTP %d' % status)
    except PublicHTTPError as e:
        row['error_code'], row['error'] = e.code, str(e)
    except (TimeoutError, socket.timeout):
        row['error_code'], row['error'] = 'timeout', 'RDAP request timed out'
    except ssl.SSLError:
        row['error_code'], row['error'] = 'tls_error', 'TLS handshake or certificate failure'
    except (OSError, http.client.HTTPException, ValueError):
        row['error_code'], row['error'] = 'connection_error', 'could not complete the RDAP request'
    row['elapsed_ms'] = int((time.monotonic() - start) * 1000)
    row['checked_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    return row


def check_domains(items, mapping, timeout=15, allow_private=False, delay=0.5, workers=4):
    # Domains served by one RDAP server run sequentially with a pause; servers run in parallel.
    groups = {}
    for idx, (raw, d) in enumerate(items):
        groups.setdefault(find_server(d, mapping), []).append((idx, raw, d))
    results = [None] * len(items)

    def run(key_group):
        key, group = key_group
        for n, (idx, raw, d) in enumerate(group):
            if n and delay and key and d:
                time.sleep(delay)
            results[idx] = check_domain(raw, d, mapping, timeout, allow_private)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        list(pool.map(run, groups.items()))
    return results


def is_billable(row):
    return row.get('available') is not None
