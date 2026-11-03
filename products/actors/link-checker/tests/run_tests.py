# Offline tests for link-checker core against a local 127.0.0.1 server only.
import os, sys, json, time, socket, threading, platform
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from src import core

STATE = {"inflight": 0, "max_inflight": 0, "uas": set(), "methods": [], "lock": threading.Lock()}
REDIR = {"/r1": "/r2", "/r2": "/r3", "/r3": "/ok", "/loop-a": "/loop-b", "/loop-b": "/loop-a",
         "/to-ftp": "ftp://127.0.0.1/file", "/rel": "ok"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _go(self, method):
        with STATE["lock"]:
            STATE["inflight"] += 1
            STATE["max_inflight"] = max(STATE["max_inflight"], STATE["inflight"])
            STATE["uas"].add(self.headers.get("User-Agent", ""))
            STATE["methods"].append((method, self.path))
        try:
            p = self.path
            code, loc = 200, None
            if p in REDIR:
                code, loc = (302 if p == "/r3" else 301), REDIR[p]
            elif p.startswith("/chain/"):
                code, loc = 301, "/chain/%d" % (int(p[7:]) + 1)
            elif p == "/missing":
                code = 404
            elif p == "/err":
                code = 500
            elif p == "/slow":
                time.sleep(3)
            elif p.startswith("/delay"):
                time.sleep(0.15)
            elif p == "/nohead" and method == "HEAD":
                code = 405
            body = b"ok" * 4096
            self.send_response(code)
            if loc:
                self.send_header("Location", loc)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if method == "GET":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with STATE["lock"]:
                STATE["inflight"] -= 1

    def do_HEAD(self):
        self._go("HEAD")

    def do_GET(self):
        self._go("GET")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d" % srv.server_address[1]
s = socket.socket(); s.bind(("127.0.0.1", 0)); DEAD = s.getsockname()[1]; s.close()

results = []


def case(name, row, **expect):
    fails = ["%s=%r expected %r" % (k, row.get(k), v) for k, v in expect.items() if row.get(k) != v]
    if list(row.keys()) != core.FIELDS:
        fails.append("fields %r" % list(row.keys()))
    results.append({"name": name, "passed": not fails, "failures": fails, "row": row})


C = lambda u, **k: core.check_url(u, allow_private=True, **k)
case("200_ok", C(B + "/ok"), status_code=200, ok=True, redirect_count=0, error_code=None, final_url=B + "/ok")
case("301_301_302_chain", C(B + "/r1"), status_code=200, ok=True, redirect_count=3, final_url=B + "/ok")
case("relative_location", C(B + "/rel"), status_code=200, ok=True, redirect_count=1, final_url=B + "/ok")
case("404", C(B + "/missing"), status_code=404, ok=False, error_code="http_404")
case("500", C(B + "/err"), status_code=500, ok=False, error_code="http_500")
case("head_405_get_fallback", C(B + "/nohead"), status_code=200, ok=True)
t = time.monotonic(); r = C(B + "/slow", timeout=1); dt = time.monotonic() - t
case("timeout_1s", r, ok=False, error_code="timeout", status_code=None)
results[-1]["wall_s"] = round(dt, 2)
if dt > 2.5:
    results[-1]["passed"] = False; results[-1]["failures"].append("took %.2fs" % dt)
case("redirect_loop", C(B + "/loop-a"), ok=False, error_code="redirect_loop", redirect_count=2, final_url=B + "/loop-a")
case("too_many_redirects", C(B + "/chain/0", max_redirects=5), ok=False, error_code="too_many_redirects", redirect_count=6)
case("redirect_to_ftp_refused", C(B + "/to-ftp"), ok=False, error_code="invalid_scheme", redirect_count=1, final_url="ftp://127.0.0.1/file")
case("invalid_scheme_ftp", C("ftp://127.0.0.1/x"), ok=False, error_code="invalid_scheme")
case("invalid_scheme_javascript", C("javascript:alert(1)"), ok=False, error_code="invalid_scheme")
case("invalid_port", C("http://127.0.0.1:99999/"), ok=False, error_code="invalid_url")
case("connection_refused", C("http://127.0.0.1:%d/" % DEAD, timeout=2), ok=False, error_code="network_error")
case("loopback_blocked_by_default", core.check_url(B + "/ok"), ok=False, error_code="blocked_address")
case("private_10_blocked_by_default", core.check_url("http://10.0.0.1/"), ok=False, error_code="blocked_address")

STATE["max_inflight"] = 0
urls = [B + "/delay%d" % i for i in range(6)] + [B + "/delay0"]
t = time.monotonic(); rows = core.check_urls(urls, workers=8, allow_private=True); dt = time.monotonic() - t
ok = len(rows) == 6 and all(r["ok"] for r in rows) and STATE["max_inflight"] == 1 and [r["url"] for r in rows] == urls[:6]
results.append({"name": "same_host_concurrency_1_and_dedupe", "passed": ok, "failures": [] if ok else ["max_inflight=%d rows=%d" % (STATE["max_inflight"], len(rows))],
                "max_inflight": STATE["max_inflight"], "rows": len(rows), "wall_s": round(dt, 2)})

big = core.check_urls(["ftp://x/%d" % i for i in range(1200)], allow_private=True)
ok = len(big) == 1000 and all(r["error_code"] == "invalid_scheme" for r in big) and not any(core.is_billable(r) for r in big)
results.append({"name": "cap_1000_and_not_billable", "passed": ok, "failures": [] if ok else ["len=%d" % len(big)]})

ua_ok = STATE["uas"] == {core.USER_AGENT}
results.append({"name": "user_agent_identifies_actor", "passed": ua_ok, "failures": [] if ua_ok else [repr(STATE["uas"])], "seen": sorted(STATE["uas"])})
fb = [m for m in STATE["methods"] if m[1] == "/nohead"]
ok = fb == [("HEAD", "/nohead"), ("GET", "/nohead")]
results.append({"name": "fallback_method_sequence", "passed": ok, "failures": [] if ok else [repr(fb)]})
srv.shutdown()

passed = sum(r["passed"] for r in results)
report = {"suite": "link-checker core (offline, 127.0.0.1 only)", "executed_at_unix": int(time.time()),
          "python": platform.python_version(), "passed": passed, "total": len(results),
          "scope_note": "Tests the stdlib core only. The Apify SDK wrapper (src/main.py) is not executed here.", "results": results}
with open(os.path.join(ROOT, "core-test-results.json"), "w") as f:
    json.dump(report, f, indent=1)
print("passed %d/%d" % (passed, len(results)))
for r in results:
    if not r["passed"]:
        print("FAIL", r["name"], r["failures"][:3])
