# Link checker core: one stable row per supplied URL. Python standard library only.
import ssl, time, socket, http.client
from .public_http import request, resolve, PublicHTTPError
from urllib.parse import urlsplit, urljoin
from concurrent.futures import ThreadPoolExecutor

TIMEOUT_S = 15
MAX_REDIRECTS = 10
MAX_URLS = 1000
GET_READ_BYTES = 1024
USER_AGENT = "link-checker-actor/0.1 (Apify Actor; built and maintained by autonomous AI agents)"
FIELDS = ["url", "final_url", "status_code", "redirect_count", "ok", "error_code", "error", "elapsed_ms"]
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
# HEAD answers that often mean "HEAD unsupported" rather than a broken link: retry once with GET.
HEAD_FALLBACK_STATUSES = {400, 403, 405, 501}
NO_NETWORK_CODES = {"invalid_scheme", "invalid_url", "blocked_address"}


class LinkError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def _row(url, **kw):
    r = {k: None for k in FIELDS}
    r.update(url=url, redirect_count=0, ok=False)
    r.update(kw)
    return r


def _request(url, method, timeout, allow_private=False):
    try:
        status, location, _ = request(url, method, timeout, GET_READ_BYTES,
                                     {"User-Agent": USER_AGENT, "Accept": "*/*"}, allow_private)
        return status, location
    except PublicHTTPError as e:
        raise LinkError(e.code, str(e)) from None
    except (socket.timeout, TimeoutError):
        raise LinkError("timeout", "no response within %ss" % timeout)
    except ssl.SSLError:
        raise LinkError("tls_error", "TLS verification or connection failed") from None
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise LinkError("network_error", ("%s: %s" % (type(e).__name__, e))[:200])


def check_url(url, timeout=TIMEOUT_S, max_redirects=MAX_REDIRECTS, allow_private=False, requester=None):
    def req(target, method, request_timeout):
        if requester is None:
            return _request(target, method, request_timeout, allow_private)
        # Custom requesters are a Python test seam, never an Actor input.
        try:
            resolve(target, allow_private)
        except PublicHTTPError as e:
            raise LinkError(e.code, str(e)) from None
        return requester(target, method, request_timeout)
    t0 = time.monotonic()
    cur, seen, n = url, {url}, 0

    def done(**kw):
        return _row(url, final_url=cur if isinstance(cur, str) else None, redirect_count=n,
                    elapsed_ms=int((time.monotonic() - t0) * 1000), **kw)
    try:
        while True:
            status, loc = req(cur, "HEAD", timeout)
            if status in HEAD_FALLBACK_STATUSES:
                status, loc = req(cur, "GET", timeout)
            if status in REDIRECT_STATUSES and loc:
                nxt = urljoin(cur, loc.strip())
                n += 1
                if nxt in seen:
                    cur = nxt
                    return done(status_code=status, error_code="redirect_loop", error="redirect loop after %d redirects" % n)
                if n > max_redirects:
                    cur = nxt
                    return done(status_code=status, error_code="too_many_redirects", error="more than %d redirects" % max_redirects)
                seen.add(nxt)
                cur = nxt
                continue
            ok = 200 <= status < 300
            return done(status_code=status, ok=ok, error_code=None if ok else "http_%d" % status,
                        error=None if ok else "HTTP %d" % status)
    except LinkError as e:
        return done(error_code=e.code, error=str(e)[:300])
    except Exception as e:
        return done(error_code="internal_error", error=("%s: %s" % (type(e).__name__, e))[:300])


def normalize_urls(urls):
    clean = [u.strip() for u in (urls or []) if isinstance(u, str) and u.strip()]
    return list(dict.fromkeys(clean))[:MAX_URLS]


def _host(u):
    try:
        return (urlsplit(u).hostname or "").lower()
    except ValueError:
        return ""


def check_urls(urls, workers=8, per_host_delay_s=0.0, **kw):
    # Different hosts run in parallel; URLs of the same starting host run one at a time.
    urls = normalize_urls(urls)
    groups = {}
    for i, u in enumerate(urls):
        groups.setdefault(_host(u), []).append(i)
    out = [None] * len(urls)

    def run(idxs):
        for k, i in enumerate(idxs):
            if k and per_host_delay_s:
                time.sleep(per_host_delay_s)
            out[i] = check_url(urls[i], **kw)
    if groups:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(groups)))) as ex:
            list(ex.map(run, groups.values()))
    return out


def is_billable(row):
    return row.get("error_code") not in NO_NETWORK_CODES
