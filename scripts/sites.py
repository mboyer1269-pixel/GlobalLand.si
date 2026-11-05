"""PUBLISH_SITE: GlobalLand's public websites on Cloudflare (free plan).

Agents write a static site under products/sites/<site>/. The installed host
control, never the sandbox, holds the Cloudflare API token
(/opt/globalland/credentials/cloudflare/token, mode 600) and deploys the site
as one Worker that serves the files embedded in its module, reachable at
https://<prefix><site>.<account>.workers.dev.

Why a Worker and not Pages Direct Upload: the Pages upload API requires a
BLAKE3 hash of every asset (not in Python's standard library, and not
verifiable here without an account). One Worker module is a single documented
PUT, with the same free tier (100 000 requests a day) and commercial use
allowed.

Host-enforced rules:
- only the site's own files, bounded, secret-scanned; binary files are stored
  as <name>.b64 (base64 text) and served decoded;
- index.html must say the site is made by autonomous AI agents;
- going online needs a review APPROVE of the exact site digest by a principal
  independent of the site's authors and of the publisher (review.py, same
  host-bound two-key rule as Apify); `dry_run` returns that digest without any
  external call; hidden files and receipts/ are never published;
- the host only touches Worker scripts whose name starts with the configured
  prefix (default "globalland-"), never the founder's other Workers;
- `online: false` takes a site offline (workers.dev route disabled): the
  emergency switch, which needs no review;
- every deployment is journaled before the first call and verified by fetching
  the public URL and comparing index.html.
"""
import base64
import hashlib
import json
import mimetypes
import pathlib
import re
import tempfile
import time
import urllib.error
import urllib.request
import uuid

from supervisor import atomic_json, check_secrets

API = 'https://api.cloudflare.com/client/v4'
NAME = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?')
ACCOUNT = re.compile(r'[0-9a-f]{32}')
DISCLOSURE = re.compile(r'autonomous\s+AI\s+agents?|agents?\s+IA\s+autonomes?', re.I)
MAX_FILES, MAX_TOTAL = 200, 1_500_000
COMPATIBILITY_DATE = '2026-10-01'
TYPES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.json': 'application/json', '.svg': 'image/svg+xml', '.txt': 'text/plain; charset=utf-8',
         '.xml': 'application/xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
         '.webp': 'image/webp', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.pdf': 'application/pdf'}


class SiteError(ValueError):
    """Refusal or remote failure; message built from literals, names and HTTP codes only."""
    safe_message = True


def settings(config):
    c = config.get('cloudflare') or {}
    if not isinstance(c, dict) or c.get('enabled') is not True:
        return None
    account, prefix = c.get('account_id'), c.get('script_prefix', 'globalland-')
    if not isinstance(account, str) or not ACCOUNT.fullmatch(account):
        raise ValueError('invalid cloudflare account_id')
    if not isinstance(prefix, str) or not re.fullmatch(r'[a-z0-9-]{3,20}', prefix):
        raise ValueError('invalid cloudflare script_prefix')
    return dict(account_id=account, prefix=prefix, require_review=c.get('require_review', True) is not False)


def read_token(root):
    path = pathlib.Path(root) / 'credentials' / 'cloudflare' / 'token'
    if not path.is_file() or path.is_symlink():
        raise SiteError('No Cloudflare integration configured; the founder must install an API token')
    if path.stat().st_mode & 0o077:
        raise SiteError('Cloudflare token file must be readable by its owner only')
    token = path.read_text().strip()
    if not token or len(token) > 512 or any(ch.isspace() for ch in token):
        raise SiteError('Cloudflare token file is invalid')
    return token


def load_site(work, site):
    """{url path: {c: content type, t: text | b: base64}} and the digest of exactly that."""
    if not isinstance(site, str) or not NAME.fullmatch(site):
        raise SiteError('Invalid site name: lowercase letters, digits and hyphens, at most 40')
    base = pathlib.Path(work) / 'products' / 'sites' / site
    if any(p.is_symlink() for p in (base, *base.parents)) or not base.is_dir():
        raise SiteError('Site source not found under products/sites/' + site)
    files, total = {}, 0
    for path in sorted(base.rglob('*')):
        if path.is_symlink():
            raise SiteError('symlinked site file refused')
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        if any(part.startswith('.') or part == 'receipts' for part in rel.split('/')):
            continue  # never publish hidden files or receipts
        size_on_disk = path.stat().st_size
        if size_on_disk > MAX_TOTAL or total + size_on_disk > MAX_TOTAL * 2:
            raise SiteError('Site too large (200 files, 1.5 MB total)')
        raw = path.read_bytes()
        check_secrets(raw)
        if rel.endswith('.b64'):
            rel = rel[:-4]
            try:
                data = base64.b64decode(raw.decode('ascii').strip(), validate=True)
            except (ValueError, UnicodeDecodeError):
                raise SiteError('invalid base64 file') from None
            check_secrets(data)
            entry = {'b': base64.b64encode(data).decode('ascii')}
            size = len(data)
        else:
            try:
                entry = {'t': raw.decode('utf-8')}
            except UnicodeDecodeError:
                raise SiteError('binary files must be stored as <name>.b64') from None
            size = len(raw)
        total += size
        if len(files) >= MAX_FILES or total > MAX_TOTAL:
            raise SiteError('Site too large (200 files, 1.5 MB total)')
        suffix = pathlib.PurePosixPath(rel).suffix.lower()
        entry['c'] = TYPES.get(suffix) or mimetypes.types_map.get(suffix) or 'application/octet-stream'
        files['/' + rel] = entry
    index = files.get('/index.html')
    if not index or 't' not in index:
        raise SiteError('Site needs a text index.html')
    if not DISCLOSURE.search(index['t']):
        raise SiteError('index.html must state that the site is made by autonomous AI agents')
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return files, digest


WORKER = """// Generated by GlobalLand (scripts/sites.py). Static site served from this module.
const FILES = %s;
const HEADERS = {'x-content-type-options': 'nosniff', 'referrer-policy': 'strict-origin-when-cross-origin',
  'x-frame-options': 'DENY', 'permissions-policy': 'camera=(), microphone=(), geolocation=()'};
function bytes(b64) { const s = atob(b64); const a = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) a[i] = s.charCodeAt(i); return a; }
export default {
  async fetch(request) {
    if (request.method !== 'GET' && request.method !== 'HEAD') return new Response('Method Not Allowed', {status: 405, headers: {allow: 'GET, HEAD'}});
    let path;
    try { path = decodeURIComponent(new URL(request.url).pathname); } catch { return new Response('Bad Request', {status: 400}); }
    if (path.endsWith('/')) path += 'index.html';
    const file = FILES[path] || FILES[path + '.html'] || FILES[path + '/index.html'];
    if (!file) {
      const missing = FILES['/404.html'];
      return new Response(missing ? missing.t : 'Not found', {status: 404, headers: {...HEADERS, 'content-type': 'text/html; charset=utf-8'}});
    }
    const body = request.method === 'HEAD' ? null : (file.b ? bytes(file.b) : file.t);
    return new Response(body, {headers: {...HEADERS, 'content-type': file.c, 'cache-control': 'public, max-age=300'}});
  }
};
"""


def build_module(files):
    # ensure_ascii escapes U+2028/U+2029 too, so the literal is always valid JS.
    return WORKER % json.dumps(files, sort_keys=True, ensure_ascii=True)


def catalog_site(root, site):
    """Use a bounded operation directory, never the mutable sparse work view."""
    if not isinstance(site, str) or not NAME.fullmatch(site):
        raise SiteError('Invalid site name: lowercase letters, digits and hyphens, at most 40')
    root = pathlib.Path(root)
    if not (root / 'source.git').exists() and not (root / 'source.git').is_symlink():
        return (*load_site(root / 'work', site), None)
    from public_source import PublicSource, PublicSourceError
    try:
        source = PublicSource(root)
        with tempfile.TemporaryDirectory(prefix='globalland-site-') as operation:
            # Encoded binary assets can exceed the decoded publication limit.
            source.export(['products/sites/' + site + '/'], operation, MAX_TOTAL * 2)
            return (*load_site(operation, site), source.revision)
    except PublicSourceError:
        raise SiteError('Site source catalog unavailable or invalid') from None


class Client:
    def __init__(self, token, transport=None):
        self._token = token
        self.transport = transport or self._urllib

    def _urllib(self, method, path, body=None, content_type='application/json'):
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
        request = urllib.request.Request(API + path, data=data, method=method, headers={
            'Authorization': 'Bearer ' + self._token, 'Content-Type': content_type,
            'User-Agent': 'GlobalLand/3 host publisher'})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.status, json.loads(response.read(4 * 1024 * 1024) or b'{}')
        except urllib.error.HTTPError as error:
            return error.code, None

    def call(self, method, path, body=None, content_type='application/json'):
        status, value = self.transport(method, path, body, content_type)
        if status != 200 or not isinstance(value, dict) or value.get('success') is False:
            raise SiteError('Cloudflare API %s returned HTTP %d' % (method, status))
        return value.get('result', {})


def multipart(module, metadata):
    boundary = 'globalland-' + uuid.uuid4().hex
    parts = [
        ('metadata', None, 'application/json', json.dumps(metadata).encode()),
        ('worker.js', 'worker.js', 'application/javascript+module', module.encode()),
    ]
    out = b''
    for name, filename, ctype, data in parts:
        disposition = 'form-data; name="%s"' % name + ('; filename="%s"' % filename if filename else '')
        out += ('--%s\r\nContent-Disposition: %s\r\nContent-Type: %s\r\n\r\n' % (boundary, disposition, ctype)).encode() + data + b'\r\n'
    out += ('--%s--\r\n' % boundary).encode()
    return out, 'multipart/form-data; boundary=' + boundary


def default_fetch(url):
    from tools import fetch_public
    raw, _, status = fetch_public(url)
    return status, raw


class Publisher:
    def __init__(self, root, config, client=None, reviews=None, origin=None, fetch=default_fetch, sleep=time.sleep):
        self.root = pathlib.Path(root)
        self.settings = settings(config)
        self.client = client
        self.reviews = reviews or []
        self.origin = origin
        self.fetch = fetch
        self.sleep = sleep

    def _client(self):
        if self.settings is None:
            raise SiteError('Cloudflare integration not enabled by the founder')
        if self.client is None:
            self.client = Client(read_token(self.root))
        return self.client

    def publish(self, task):
        args = task['args']
        site = args['site']
        if args.get('online') is False:
            # Emergency switch first: it must work even if the source is now invalid or gone.
            if not isinstance(site, str) or not NAME.fullmatch(site):
                raise SiteError('Invalid site name: lowercase letters, digits and hyphens, at most 40')
            if self.settings is None:
                raise SiteError('Cloudflare integration not enabled by the founder')
            script = self.settings['prefix'] + site
            self._client().call('POST', '/accounts/%s/workers/scripts/%s/subdomain' % (self.settings['account_id'], script),
                                {'enabled': False, 'previews_enabled': False})
            return dict(status='OFFLINE', site=site, script=script)
        files, digest, revision = catalog_site(self.root, site)
        if args.get('dry_run') is True:
            index = files['/index.html']['t'].encode()
            return dict(status='DRY_RUN', site=site, review_digest=digest, files=len(files),
                        bytes=sum(len(v.get('t', '')) + len(v.get('b', '')) for v in files.values()),
                        index_sha256=hashlib.sha256(index).hexdigest(),
                        note='A review APPROVE of subject site:%s with this review_digest, recorded in another turn by another provider, by Grok or by the founder, is needed to go online.' % site)
        if self.settings is None:
            raise SiteError('Cloudflare integration not enabled by the founder')
        script = self.settings['prefix'] + site
        account = self.settings['account_id']
        api = self._client()
        if self.settings['require_review']:
            from review import approved, authors
            if not approved(self.reviews, 'site:' + site, digest, task.get('submitted_by'), self.origin,
                            authors(self.root, 'products/sites/' + site, revision=revision)):
                raise SiteError('Going online needs a WORLD review APPROVE of site:%s for the review_digest returned by a dry_run, recorded in another turn by a provider that neither wrote the site nor asks to publish it, by Grok through GitHub or by the founder' % site)
        path = self.root / 'state' / 'sites' / ('%s-%s.json' % (site, digest[:24]))
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        record = json.loads(path.read_text()) if path.exists() else dict(site=site, script=script, digest=digest, step='STARTED', tasks=[])
        record['tasks'] = (record.get('tasks') or []) + [task['id']]
        atomic_json(path, record)  # recorded before any external call
        body, ctype = multipart(build_module(files), {'main_module': 'worker.js', 'compatibility_date': COMPATIBILITY_DATE})
        api.call('PUT', '/accounts/%s/workers/scripts/%s' % (account, script), body, ctype)
        api.call('POST', '/accounts/%s/workers/scripts/%s/subdomain' % (account, script), {'enabled': True, 'previews_enabled': False})
        subdomain = api.call('GET', '/accounts/%s/workers/subdomain' % account).get('subdomain')
        if not isinstance(subdomain, str) or not re.fullmatch(r'[a-z0-9-]{1,63}', subdomain):
            raise SiteError('Cloudflare account has no workers.dev subdomain; the founder must choose one in the dashboard')
        url = 'https://%s.%s.workers.dev/' % (script, subdomain)
        record.update(step='DEPLOYED', url=url)
        atomic_json(path, record)
        expected = hashlib.sha256(files['/index.html']['t'].encode()).hexdigest()
        verified = False
        for attempt in range(5):
            try:
                status, raw = self.fetch(url)
                if status == 200 and hashlib.sha256(raw).hexdigest() == expected:
                    verified = True
                    break
            except (ValueError, OSError):
                pass
            self.sleep(3 * (attempt + 1))
        result = dict(status='ONLINE_VERIFIED' if verified else 'ONLINE_UNVERIFIED', site=site, url=url, script=script,
                      review_digest=digest,
                      note=None if verified else 'Deployed but the public URL did not serve the new index.html yet; check again later.')
        record.update(step='DONE', result=result)
        atomic_json(path, record)
        return result

    @staticmethod
    def task_status(result):
        return {'ONLINE_VERIFIED': 'DONE', 'OFFLINE': 'DONE', 'DRY_RUN': 'DONE', 'ONLINE_UNVERIFIED': 'TIMEOUT'}.get(result.get('status'), 'FAILED')
