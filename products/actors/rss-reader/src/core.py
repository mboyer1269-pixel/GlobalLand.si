# RSS 2.0 / RSS 1.0 (RDF) / Atom parsing core. Python standard library only.
import re, html, socket, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from xml.parsers import expat
from email.utils import parsedate_to_datetime
from datetime import datetime

MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_S = 20
SUMMARY_MAX = 1000
USER_AGENT = "rss-reader-actor/0.1 (built and maintained by autonomous AI agents)"
FIELDS = ["row_type", "feed_url", "feed_title", "feed_format", "title", "link",
          "published", "summary", "guid", "error_code", "error"]


class FeedError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


class _Refused(Exception):
    pass


def _row(feed_url, **kw):
    r = {k: None for k in FIELDS}
    r["feed_url"] = feed_url
    r.update(kw)
    return r


def error_row(feed_url, code, msg):
    return _row(feed_url, row_type="error", error_code=code, error=str(msg)[:300])


_DTD = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _qn(n):
    return "{" + n if "}" in n else n


def _refuse(*_a):
    raise _Refused("DOCTYPE/ENTITY declarations are refused (entity expansion disabled)")


def _parse_xml(data):
    # expat with every DTD/entity hook refusing: no entity is expanded or fetched, whatever the encoding.
    tb = ET.TreeBuilder()
    p = expat.ParserCreate(namespace_separator="}")
    p.StartElementHandler = lambda name, attrs: tb.start(_qn(name), {_qn(k): v for k, v in attrs.items()})
    p.EndElementHandler = lambda name: tb.end(_qn(name))
    p.CharacterDataHandler = tb.data
    p.StartDoctypeDeclHandler = _refuse
    p.EntityDeclHandler = _refuse
    p.ExternalEntityRefHandler = _refuse
    p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    p.Parse(data, True)
    return tb.close()


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _children(el, *names):
    return [c for c in el if _local(c.tag) in names]


def _text(el, *names):
    if el is None:
        return None
    for c in _children(el, *names):
        t = "".join(c.itertext()).strip()
        if t:
            return t
    return None


def _clean(s, cap=SUMMARY_MAX):
    if s is None:
        return None
    s = html.unescape(_TAG.sub(" ", s))
    s = _WS.sub(" ", _TAG.sub(" ", s)).strip()
    return s[:cap] if s else None


def _date(s):
    if not s:
        return None
    s = s.strip()
    try:
        dt = parsedate_to_datetime(s)
    except Exception:
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(re.sub(r"[zZ]$", "+00:00", s))
        except Exception:
            return None
    return dt.isoformat()


def _atom_link(entry):
    best = None
    for l in _children(entry, "link"):
        href = (l.get("href") or "").strip()
        if not href:
            continue
        if l.get("rel", "alternate") == "alternate":
            return href
        best = best or href
    return best


def parse_feed(data, feed_url, max_items=50):
    if not data or not data.strip():
        raise FeedError("empty_document", "response body is empty")
    if len(data) > MAX_BYTES:
        raise FeedError("too_large", "document exceeds %d bytes" % MAX_BYTES)
    # No byte-level DOCTYPE scan: real feeds embed "<!DOCTYPE" inside CDATA HTML (github.blog does).
    # Refusal happens in the expat DTD/entity hooks, which only fire on a real declaration.
    try:
        root = _parse_xml(data)
    except _Refused as e:
        raise FeedError("dtd_rejected", str(e))
    except expat.ExpatError as e:
        raise FeedError("parse_error", "XML parse error: %s" % e)
    kind = _local(root.tag)
    if kind == "rss":
        ch = (_children(root, "channel") or [None])[0]
        if ch is None:
            raise FeedError("not_a_feed", "rss element without channel")
        feed_title, items, fmt = _text(ch, "title"), _children(ch, "item"), "rss2"
    elif kind == "RDF":
        ch = (_children(root, "channel") or [None])[0]
        feed_title, items, fmt = _text(ch, "title"), _children(root, "item"), "rss1"
    elif kind == "feed":
        feed_title, items, fmt = _text(root, "title"), _children(root, "entry"), "atom"
    else:
        raise FeedError("not_a_feed", "root element <%s> is not rss, RDF or feed" % kind[:40])
    feed_title = _clean(feed_title, 300)
    rows = []
    for it in items[:max_items]:
        if fmt == "atom":
            link = _atom_link(it)
            guid = _text(it, "id")
            published = _date(_text(it, "published") or _text(it, "updated"))
            summary = _clean(_text(it, "summary") or _text(it, "content"))
        else:
            guid = _text(it, "guid")
            link = _text(it, "link")
            if not link and guid and guid.lower().startswith(("http://", "https://")):
                if (_children(it, "guid")[0].get("isPermaLink") or "true").lower() != "false":
                    link = guid
            published = _date(_text(it, "pubDate") or _text(it, "date"))
            summary = _clean(_text(it, "description") or _text(it, "encoded"))
            if fmt == "rss1" and not guid:
                guid = it.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about")
        rows.append(_row(feed_url, row_type="item", feed_title=feed_title, feed_format=fmt,
                         title=_clean(_text(it, "title"), 500), link=link, published=published,
                         summary=summary, guid=guid))
    return rows, fmt, len(items)


def fetch(url, timeout=TIMEOUT_S, max_bytes=MAX_BYTES):
    if not isinstance(url, str) or not re.match(r"^https?://", url, re.I):
        raise FeedError("invalid_url", "only http(s) URLs are accepted")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        raise FeedError("http_error", "HTTP %s" % e.code)
    except (socket.timeout, TimeoutError):
        raise FeedError("timeout", "no data within %ss" % timeout)
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise FeedError("timeout", "no data within %ss" % timeout)
        raise FeedError("network_error", str(e.reason)[:200])
    except (OSError, ValueError) as e:
        raise FeedError("network_error", str(e)[:200])
    if len(data) > max_bytes:
        raise FeedError("too_large", "response exceeds %d bytes" % max_bytes)
    return data


def read_feed(url, max_items=50, fetcher=fetch):
    try:
        rows, _fmt, _total = parse_feed(fetcher(url), url, max_items)
        if not rows:
            return [error_row(url, "no_items", "feed parsed but contains no items")]
        return rows
    except FeedError as e:
        return [error_row(url, e.code, e)]
    except Exception as e:
        return [error_row(url, "internal_error", "%s: %s" % (type(e).__name__, e))]
