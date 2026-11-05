import hashlib
import json
import platform
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import core  # noqa: E402

FIX = (ROOT / 'tests' / 'fixtures' / 'verisign-example-com.json').read_bytes()
SEEN = []
ROUTES = {'free.test': (404, b'{}'), 'limited.test': (429, b'{}'), 'broken.test': (500, b'{}'),
          'notjson.test': (200, b'hello'), 'ns.test': (200, b'{"objectClassName":"nameserver"}')}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b'', loc=None):
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'application/rdap+json')
            if loc:
                self.send_header('Location', loc)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)
        except OSError:
            pass

    def do_GET(self):
        SEEN.append((self.path, self.headers.get('User-Agent'), self.headers.get('Accept')))
        name = self.path.rsplit('/', 1)[-1]
        if name == 'taken.test':
            self._send(200, FIX)
        elif name in ROUTES:
            self._send(*ROUTES[name])
        elif name == 'slow.test':
            time.sleep(2.5)
            self._send(404, b'{}')
        elif name == 'huge.test':
            self._send(200, b'{"a":"' + b'x' * (core.MAX_BODY + 10) + b'"}')
        elif name == 'moved.test':
            self._send(301, loc='/domain/taken.test')
        elif name == 'loop.test':
            self._send(301, loc='/domain/loop.test')
        else:
            self._send(404, b'{}')


def main():
    srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    m = {'test': 'http://127.0.0.1:%d/' % srv.server_address[1]}
    res = []

    def t(name, ok, detail):
        res.append({'test': name, 'pass': bool(ok), 'detail': detail})

    def chk(d, **kw):
        kw.setdefault('allow_private', True)
        return core.check_domain(d, core.normalize_domain(d), m, timeout=1, **kw)

    boot = core.load_bootstrap()
    t('bootstrap_com_server', boot.get('com') == 'https://rdap.verisign.com/com/v1/', boot.get('com'))
    t('bootstrap_tld_count', len(boot) > 500, len(boot))
    cases = {'Example.COM.': 'example.com', 'https://Sub.Example.com/path?x=1': 'sub.example.com',
             'bücher.de': 'xn--bcher-kva.de', 'bad domain.com': None, '-x.com': None,
             'localhost': None, '1.2.3.4': None, 'a..com': None, 42: None}
    t('normalize_domain', all(core.normalize_domain(k) == v for k, v in cases.items()),
      {str(k): core.normalize_domain(k) for k in cases})
    n = [len(core.normalize_domains(['a.com', 'A.com', '', ' b.com'])),
         len(core.normalize_domains(['d%d.com' % i for i in range(1500)])),
         len(core.normalize_domains('a.com\nb.com\n'))]
    t('dedupe_cap_multiline', n == [2, 1000, 2], n)
    r = chk('taken.test')
    t('registered_record', r['available'] is False and r['rdap_status_code'] == 200
      and r['registered_at'] == '1995-08-14T04:00:00Z' and r['expires_at'] == '2027-08-13T04:00:00Z'
      and r['registrar'] == 'RESERVED-Internet Assigned Numbers Authority' and len(r['nameservers']) == 2
      and len(r['statuses']) == 3, r)
    blob = json.dumps(r).lower()
    t('no_contact_data_in_row', not any(w in blob for w in ('vcard', 'email', 'tel', 'abuse', 'entities')), sorted(r))
    rw = {d: chk(d + '.test') for d in ('free', 'limited', 'broken', 'slow', 'huge', 'notjson', 'ns', 'moved', 'loop')}
    t('unregistered_404', rw['free']['available'] is True and rw['free']['rdap_status_code'] == 404, rw['free'])
    for name, key, code in (('rate_limited_429', 'limited', 'rate_limited'), ('server_error_500', 'broken', 'http_error'),
                            ('oversized_body', 'huge', 'body_too_large'), ('invalid_json', 'notjson', 'invalid_json'),
                            ('non_domain_object', 'ns', 'unexpected_response')):
        t(name, rw[key]['error_code'] == code and rw[key]['available'] is None, rw[key]['error'])
    t('timeout', rw['slow']['error_code'] == 'timeout' and rw['slow']['elapsed_ms'] < 2400,
      [rw['slow']['error_code'], rw['slow']['elapsed_ms']])
    t('redirect_followed', rw['moved']['available'] is False and rw['moved']['redirect_count'] == 1,
      [rw['moved']['available'], rw['moved']['redirect_count']])
    t('redirect_loop_capped', rw['loop']['error_code'] == 'too_many_redirects'
      and rw['loop']['redirect_count'] == core.MAX_REDIRECTS, [rw['loop']['error_code'], rw['loop']['redirect_count']])
    before = len(SEEN)
    u = chk('foo.nosuchtld')
    t('unsupported_tld_no_request', u['error_code'] == 'unsupported_tld' and len(SEEN) == before, u['error_code'])
    inv = core.check_domain('bad domain', None, m)
    t('invalid_domain_row', inv['error_code'] == 'invalid_domain' and inv['domain'] is None, inv['error_code'])
    bl = chk('free.test', allow_private=False)
    t('private_address_blocked_by_default', bl['error_code'] == 'blocked_address', bl['error_code'])
    ua = [s for s in SEEN if s[0].endswith('/domain/taken.test')]
    t('request_headers', bool(ua) and 'autonomous AI agents' in (ua[0][1] or '') and 'rdap+json' in (ua[0][2] or ''), ua[:1])
    t('billing_only_definitive', core.is_billable(r) and core.is_billable(rw['free'])
      and not any(core.is_billable(x) for x in (rw['limited'], rw['slow'], u, inv, bl)), 'errors not billable')
    inputs = ['free.test', 'bad domain', 'taken.test', 'x.nosuchtld', 'moved.test']
    out = core.check_domains(core.normalize_domains(inputs), m, timeout=1, allow_private=True, delay=0.05)
    t('batch_order_and_results', [o['input'] for o in out] == inputs
      and [o['available'] for o in out] == [True, None, False, None, False],
      [(o['input'], o['available'], o['error_code']) for o in out])
    keys = sorted(core._row(None, None))
    t('stable_row_schema', all(sorted(x) == keys for x in [r, u, inv, bl] + list(rw.values()) + out), keys)
    srv.shutdown()
    passed = sum(x['pass'] for x in res)
    rep = {'actor': 'domain-availability',
           'kind': 'offline core tests against a local 127.0.0.1 HTTP server; Apify wrapper and live registries not tested',
           'executed_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'python': platform.python_version(),
           'bootstrap_sha256': hashlib.sha256((ROOT / 'data' / 'rdap-dns-bootstrap.json').read_bytes()).hexdigest(),
           'passed': passed, 'total': len(res), 'results': res}
    (ROOT / 'core-test-results.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    print('passed %d/%d' % (passed, len(res)))
    for x in res:
        if not x['pass']:
            print('FAIL', x['test'], str(x['detail'])[:300])
    return 0 if passed == len(res) else 1


if __name__ == '__main__':
    sys.exit(main())
