"""SYNTHETIC rehearsal of the CAD49 one-notice reconciliation offer. Not a customer request. Made by autonomous AI agents."""
import subprocess, json, hashlib, sys, re, pathlib, platform
D = pathlib.Path(__file__).resolve().parent
R = D / "reconcile.py"
RAW = pathlib.Path(sys.argv[1])
OUT = D / "out"; OUT.mkdir(exist_ok=True)
res = []
def chk(name, cond, detail=""):
    res.append({"check": name, "pass": bool(cond), "detail": str(detail)[:300]})
def run(f, nid, now):
    p = subprocess.run([sys.executable, "-I", str(R), str(f), nid, now], capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr
NOW = "2026-11-12T06:00:00Z"
SITE_HASH = {"105246-2026": "fc9d73060c235441", "105838-2026": "15b59fac2748825f"}
for nid, dl in [("105246-2026", "2026-12-07 12:00 UTC"), ("105838-2026", "2027-01-08 12:00 UTC")]:
    f = RAW / f"{nid}.json"; b = f.read_bytes(); rel = json.loads(b)["releases"][0]
    rc, out, err = run(f, nid, NOW)
    (OUT / f"brief-{nid}.txt").write_text(out, encoding="utf-8")
    chk(f"{nid} exit 0", rc == 0, err[-300:])
    chk(f"{nid} input under 20000 bytes", len(b) < 20000, len(b))
    chk(f"{nid} input hash equals hash cited on live page", hashlib.sha256(b).hexdigest().startswith(SITE_HASH[nid]))
    chk(f"{nid} reply cites exact input sha256", hashlib.sha256(b).hexdigest() in out)
    chk(f"{nid} deadline in UTC", dl in out)
    chk(f"{nid} buyer quoted", rel["buyer"]["name"] in out)
    chk(f"{nid} route verbatim", rel["tender"].get("submissionMethodDetails", "") in out)
    chk(f"{nid} EN+FR AI disclosure", "autonomous AI agents" in out and "agents d'IA autonomes" in out)
    chk(f"{nid} no email address in reply", not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", out))
    chk(f"{nid} sections 1-5 + FR", all(s in out for s in ["== 1.", "== 2.", "== 3.", "== 4.", "== 5.", "Resume en francais"]))
    chk(f"{nid} no eligibility claim", not re.search(r"you (are eligible|qualify)|vous (etes|êtes) (admissible|eligible)", out, re.I))
    chk(f"{nid} tender docs listed as unknown EN/FR", "tender documents (not provided, not read)" in out and "documents d'appel d'offres non fournis" in out)
    chk(f"{nid} reply < 32000 chars and UTF-8", len(out) < 32000 and out.encode("utf-8").decode("utf-8") == out, len(out))
    chk(f"{nid} recommendations labelled as ours", "Our recommendations (not buyer requirements)" in out)
b46 = (RAW / "105246-2026.json").read_bytes(); out46 = (OUT / "brief-105246-2026.txt").read_text(encoding="utf-8")
chk("105246 mandatory ISO 9001 requirement quoted", "ISO 9001" in out46)
chk("105246 regulation 58 exclusion quoted", "regulation 58" in out46)
chk("105246 option text vs hasOptions=false flagged", "hasOptions=false" in out46)
chk("105246 weights quality 40 price 60", "Quality 40" in out46 and "price 60" in out46)
chk("105246 no value -> unknown", "no value field" in out46)
tmp = OUT / "tmp"; tmp.mkdir(exist_ok=True)
re_ind = json.dumps(json.loads(b46), indent=1, ensure_ascii=False).encode(); (tmp / "reindent.json").write_bytes(re_ind)
rc, o2, _ = run(tmp / "reindent.json", "105246-2026", NOW)
canon = lambda o: re.search(r"empreinte canonique: ([0-9a-f]{64})", o).group(1)
chk("reindented paste: raw hash differs", hashlib.sha256(re_ind).hexdigest() != hashlib.sha256(b46).hexdigest())
chk("reindented paste: canonical hash unchanged", rc == 0 and canon(o2) == canon(out46))
(tmp / "big.json").write_bytes(b46 + b" " * 7000)
rc, o3, _ = run(tmp / "big.json", "105246-2026", NOW); chk("oversize refused exit 2", rc == 2 and "REFUSED" in o3, o3[:200])
(tmp / "trunc.json").write_bytes(b46[: len(b46) // 2])
rc, o4, _ = run(tmp / "trunc.json", "105246-2026", NOW); chk("truncated paste refused exit 2", rc == 2 and "not complete" in o4, o4[:200])
rc, o5, _ = run(RAW / "105246-2026.json", "105838-2026", NOW); chk("wrong notice id refused", rc == 2 and "is not in the pasted text" in o5, o5[:200])
rc, o6, _ = run(RAW / "105246-2026.json", "105246-2026", "2026-12-08T00:00:00Z"); chk("past deadline flagged", rc == 0 and "has already passed" in o6)
for p in tmp.iterdir(): p.unlink()
tmp.rmdir()
ok = sum(r["pass"] for r in res)
summary = {"label": "SYNTHETIC REHEARSAL - not a customer request, delivery, accepted order or revenue", "mission": "TENDER-OFFER-FULFILLMENT-REHEARSAL", "author": "BUILDER (autonomous AI agent)", "run_now_utc": NOW, "python": platform.python_version(), "reconcile_sha256": hashlib.sha256(R.read_bytes()).hexdigest(), "inputs": {"105246-2026": hashlib.sha256(b46).hexdigest(), "105838-2026": hashlib.sha256((RAW / "105838-2026.json").read_bytes()).hexdigest()}, "passed": ok, "total": len(res), "checks": res}
(D / "rehearsal-results.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
print(ok, "/", len(res)); [print("FAIL", r) for r in res if not r["pass"]]
