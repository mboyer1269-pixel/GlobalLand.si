import json, sys, os, time, threading, hashlib, http.server, datetime, py_compile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1,localhost"
from src import core
from src.core import read_feed, fetch, FIELDS
FIX = os.path.join(HERE, "fixtures")
GH = os.path.normpath(os.path.join(ROOT, "..", "..", "research", "fixture-github-blog-feed.xml"))
results, all_rows = [], []

def load(name):
    with open(os.path.join(FIX, name), "rb") as f:
        return f.read()

def rows_for(name, max_items=50, data=None):
    data = load(name) if data is None else data
    rows = read_feed("fixture://" + name, max_items, fetcher=lambda u: data)
    all_rows.extend(rows)
    return rows

def err(rows):
    assert len(rows) == 1 and rows[0]["row_type"] == "error", rows
    return rows[0]["error_code"]

def test(fn):
    try:
        results.append({"name": fn.__name__, "passed": True, "detail": fn()})
    except Exception as e:
        results.append({"name": fn.__name__, "passed": False, "detail": "%s: %s" % (type(e).__name__, str(e)[:400])})
    return fn

@test
def github_blog_saved_fixture():
    with open(GH, "rb") as f:
        data = f.read()
    rows = read_feed("https://github.blog/feed/", 50, fetcher=lambda u: data)
    all_rows.extend(rows)
    items = [r for r in rows if r["row_type"] == "item"]
    assert items, rows[:1]
    assert all(r["feed_format"] == "rss2" and r["title"] and r["link"] and r["published"] for r in items)
    return {"sha256": hashlib.sha256(data).hexdigest(), "items": len(items), "feed_title": items[0]["feed_title"],
            "first": {k: (items[0][k] or "")[:100] for k in ("title", "link", "published", "guid", "summary")}}

@test
def max_items_cap():
    with open(GH, "rb") as f:
        data = f.read()
    rows = read_feed("https://github.blog/feed/", 2, fetcher=lambda u: data)
    assert len(rows) == 2, len(rows)
    return {"rows": 2}

@test
def atom():
    r = rows_for("atom.xml")
    assert len(r) == 2 and r[0]["feed_format"] == "atom" and r[0]["feed_title"] == "Example Atom Feed"
    assert r[0]["link"] == "https://example.org/entries/1", r[0]["link"]
    assert r[0]["published"] == "2026-10-29T08:30:00+02:00", r[0]["published"]
    assert r[0]["summary"] == "Hello & welcome", r[0]["summary"]
    assert r[0]["guid"] == "urn:uuid:entry-1"
    assert r[1]["published"] == "2026-10-28T10:00:00+00:00", r[1]["published"]
    assert r[1]["summary"] == "Bold text" and r[1]["link"] == "https://example.org/entries/2"
    return r

@test
def rss2():
    r = rows_for("rss2.xml")
    assert len(r) == 3 and r[0]["feed_format"] == "rss2"
    assert r[0]["published"] == "2026-11-02T10:15:00+00:00", r[0]["published"]
    assert r[0]["summary"] == "Summary A" and r[0]["guid"] == "item-a" and r[0]["link"] == "https://example.com/a"
    assert r[1]["link"] == "https://example.com/b" and r[1]["published"] is None and r[1]["summary"] == "Body B"
    assert r[2]["guid"] is None and r[2]["published"] is None and r[2]["summary"] is None
    return r

@test
def rss1_rdf():
    r = rows_for("rss1.xml")
    assert len(r) == 1 and r[0]["feed_format"] == "rss1" and r[0]["feed_title"] == "Example RSS 1.0"
    assert r[0]["guid"] == "https://example.net/x" and r[0]["published"] == "2026-10-01T00:00:00+00:00", r[0]
    return r

@test
def malformed():
    c = err(rows_for("malformed.xml")); assert c == "parse_error", c; return c

@test
def empty_channel():
    c = err(rows_for("empty-channel.xml")); assert c == "no_items", c; return c

@test
def empty_body():
    c = err(rows_for("empty", data=b"  \n")); assert c == "empty_document", c; return c

@test
def billion_laughs_rejected():
    c = err(rows_for("billion-laughs.xml")); assert c == "dtd_rejected", c; return c

@test
def xxe_rejected():
    c = err(rows_for("xxe.xml")); assert c == "dtd_rejected", c; return c

@test
def utf16_doctype_rejected_by_expat_hook():
    data = load("billion-laughs.xml").decode("utf-8").encode("utf-16")
    assert not core._DTD.search(data), "byte regex unexpectedly matched"
    c = err(rows_for("billion-laughs.utf16", data=data)); assert c == "dtd_rejected", c; return c

@test
def not_a_feed():
    c = err(rows_for("not-a-feed.xml")); assert c == "not_a_feed", c; return c

@test
def html_named_entity_recovered():
    r = rows_for("undefined-entity.xml")
    assert r[0]["row_type"] == "item" and r[0]["feed_title"] == "A B", r; return r[0]["feed_title"]

@test
def unknown_entity_is_parse_error():
    c = err(rows_for("bogus", data=b"<rss><channel><title>&bogusentity;</title><item><title>x</title></item></channel></rss>")); assert c == "parse_error", c; return c

@test
def oversize_document():
    c = err(rows_for("big", data=b"<rss>" + b" " * (core.MAX_BYTES + 1) + b"</rss>")); assert c == "too_large", c; return c

@test
def invalid_url_scheme():
    rows = read_feed("file:///etc/passwd"); all_rows.extend(rows)
    c = err(rows); assert c == "invalid_url", c; return c

ATOM = load("atom.xml")
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        code, body = 200, ATOM
        if self.path == "/slow":
            time.sleep(3)
        elif self.path == "/big":
            body = b"<rss>" + b" " * 5000 + b"</rss>"
        elif self.path != "/ok":
            code, body = 404, b"nope"
        try:
            self.send_response(code); self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        except Exception:
            pass

srv = None
try:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    BASE = "http://127.0.0.1:%d" % srv.server_address[1]
    @test
    def loopback_ok():
        rows = read_feed(BASE + "/ok", fetcher=lambda u: fetch(u, allow_private=True)); all_rows.extend(rows)
        assert len(rows) == 2 and rows[0]["row_type"] == "item", rows; return len(rows)
    @test
    def loopback_timeout():
        t = time.time(); rows = read_feed(BASE + "/slow", fetcher=lambda u: fetch(u, timeout=1, allow_private=True)); el = time.time() - t
        all_rows.extend(rows); c = err(rows); assert c == "timeout" and el < 2.5, (c, el); return {"code": c, "elapsed_s": round(el, 2)}
    @test
    def loopback_bounded_read():
        rows = read_feed(BASE + "/big", fetcher=lambda u: fetch(u, max_bytes=1000, allow_private=True)); all_rows.extend(rows)
        c = err(rows); assert c == "too_large", c; return c
    @test
    def loopback_http_404():
        rows = read_feed(BASE + "/missing", fetcher=lambda u: fetch(u, allow_private=True)); all_rows.extend(rows)
        c = err(rows); assert c == "http_error" and "404" in rows[0]["error"], rows; return rows[0]["error"]
except OSError as e:
    results.append({"name": "loopback_server", "passed": False, "detail": "could not bind: %s" % e})

@test
def stable_fields_all_rows():
    bad = [r for r in all_rows if list(r.keys()) != FIELDS]
    assert not bad, bad[:1]; return {"rows_checked": len(all_rows), "fields": FIELDS}

@test
def wrapper_byte_compiles():
    for f in ("main.py", "__main__.py"):
        py_compile.compile(os.path.join(ROOT, "src", f), doraise=True)
    return "compiled only; apify SDK not installed here, wrapper not executed"

if srv:
    srv.shutdown()
out = {"actor": "rss-reader", "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
       "python": sys.version.split()[0],
       "scope": "Real execution of src/core.py on saved/handcrafted fixtures and a local 127.0.0.1 HTTP server. No live third-party feed was fetched in this run. src/main.py (Apify SDK wrapper) was byte-compiled only, never executed; no Apify build exists.",
       "passed": sum(r["passed"] for r in results), "failed": sum(not r["passed"] for r in results), "tests": results}
with open(os.path.join(ROOT, "core-test-results.json"), "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print("passed", out["passed"], "failed", out["failed"])
for r in results:
    if not r["passed"]:
        print("FAIL", r["name"], str(r["detail"])[:200])
sys.exit(1 if out["failed"] else 0)
