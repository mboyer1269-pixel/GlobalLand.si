#!/usr/bin/env python3
"""GlobalLand one-notice source-reconciliation brief. Offline, stdlib only.
Made by autonomous AI agents. Usage:
  python3 -I reconcile.py PASTED.txt NOTICE_ID [NOW_ISO_UTC]
Prints a plain-text EN/FR reply. Exit 0 = brief, 2 = input refused."""
import sys, json, hashlib, re
from datetime import datetime, timezone
LIMIT = 20000
EM = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PH = re.compile(r"\+\d[\d ()-]{7,}\d")
def out(s):
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()
def red(s):
    return PH.sub("[phone redacted]", EM.sub("[email redacted]", str(s or "")))
def utc(s):
    mo = re.search(r"([+-])(\d{2}):?(\d{2})$", str(s).strip())
    if mo and (int(mo.group(2)) > 23 or int(mo.group(3)) > 59):
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else None
def fmt(d):
    return d.strftime("%Y-%m-%d %H:%M UTC")
DISC = "Produced by autonomous AI agents (GlobalLand). Not legal or procurement advice. / Produit par des agents d'IA autonomes (GlobalLand). Ce n'est pas un avis juridique ni en marchés publics."
def refuse(en, fr):
    out("REFUSED / REFUSÉ\nEN: " + en + "\nFR: " + fr + "\n" + DISC)
    sys.exit(2)
def main():
    path, nid = sys.argv[1], sys.argv[2].strip()
    now = utc(sys.argv[3]) if len(sys.argv) > 3 else datetime.now(timezone.utc)
    raw = open(path, "rb").read()
    if len(raw) >= LIMIT:
        refuse(f"pasted text is {len(raw)} bytes; this offer accepts under {LIMIT} bytes.", f"le texte collé fait {len(raw)} octets ; l'offre accepte moins de {LIMIT} octets.")
    h = hashlib.sha256(raw).hexdigest()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        refuse(f"pasted text is not complete UTF-8 OCDS JSON ({type(e).__name__}); sha256 {h}. Please paste the full release package text.", f"le texte collé n'est pas un JSON OCDS UTF-8 complet ; sha256 {h}. Collez le paquet complet.")
    rels = doc.get("releases", [doc]) if isinstance(doc, dict) else []
    rel = next((r for r in rels if isinstance(r, dict) and r.get("id") == nid), None)
    if rel is None:
        ids = [r.get("id") for r in rels if isinstance(r, dict)]
        refuse(f"notice {nid} is not in the pasted text (release ids found: {ids}); sha256 {h}.", f"l'avis {nid} n'est pas dans le texte collé (identifiants : {ids}) ; sha256 {h}.")
    canon = hashlib.sha256(json.dumps(rel, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    t = rel.get("tender") or {}
    lots = t.get("lots") or []
    flags = []
    unk = ["tender documents (not provided, not read)", "clarification deadline (not in the pasted structured fields)", "your eligibility and portal registration requirements"]
    st = t.get("status")
    if st != "active":
        flags.append(f"tender.status is {st!r}, not 'active': check whether this is still an open tender.")
    end = (t.get("tenderPeriod") or {}).get("endDate")
    endu = utc(end) if end else None
    if endu is None:
        flags.append(f"submission deadline missing or without timezone (tenderPeriod.endDate={end!r}).")
        dl = "not determinable"
    else:
        dl = fmt(endu) + f" (as published: {end})"
        if endu <= now:
            flags.append(f"deadline {fmt(endu)} has already passed at {fmt(now)}.")
    alltext = " ".join([str(rel.get("description") or ""), str(t.get("description") or "")] + [str(l.get("description") or "") for l in lots])
    vals = []
    if isinstance(t.get("value"), dict):
        vals.append(f"tender: {t['value'].get('amount')} {t['value'].get('currency')}")
    for l in lots:
        if isinstance(l.get("value"), dict):
            vals.append(f"lot {l.get('id')}: {l['value'].get('amount')} {l['value'].get('currency')}")
    if not vals:
        unk.append("contract value and currency (no value field in the pasted release)")
    L = []
    for l in lots:
        cp = l.get("contractPeriod") or {}
        lid = l.get("id")
        crit = "; ".join(f"{c.get('name') or c.get('type')} {c.get('description')}" for c in (l.get("awardCriteria") or {}).get("criteria", []))
        L.append(f"  Lot {lid}: {red(l.get('description'))}\n    durationInDays={cp.get('durationInDays')} startDate={cp.get('startDate')} maxExtentDate={cp.get('maxExtentDate')} hasRenewal={l.get('hasRenewal')} renewal={red((l.get('renewal') or {}).get('description'))!r} hasOptions={l.get('hasOptions')}\n    Award weights: {crit or 'not stated'}")
        d = str(l.get("description") or "")
        m = re.search(r"initial (?:contract )?term (?:will be|is) (\d+) years?", d, re.I)
        if m and cp.get("durationInDays"):
            diff = cp["durationInDays"] - int(m.group(1)) * 365
            if abs(diff) > 7:
                flags.append(f"lot {lid}: text says initial term {m.group(1)} years; structured durationInDays={cp['durationInDays']} ({diff:+d} days vs {m.group(1)}x365). Minor; confirm in tender documents.")
        mo = re.search(r"[^.]*\boptions?\b[^.]*", d, re.I)
        if mo and l.get("hasOptions") is False:
            flags.append(f"lot {lid}: text mentions an option ('{mo.group(0).strip()}') but structured hasOptions=false (hasRenewal={l.get('hasRenewal')}); the extension may be coded as renewal only.")
        s, x = utc(cp.get("startDate")), utc(cp.get("maxExtentDate"))
        mm = re.search(r"maximum[^.]{0,80}?\(?(\d+)\)?\s*years", alltext, re.I)
        if s and x and mm and abs((x - s).days / 365.25 - int(mm.group(1))) > 0.5:
            flags.append(f"lot {lid}: text states a maximum of {mm.group(1)} years but structured startDate..maxExtentDate spans {(x - s).days / 365.25:.1f} years.")
    must = []
    srcs = [str(rel.get("description") or "")] + [str(c.get("description") or "") for c in (t.get("selectionCriteria") or {}).get("criteria", [])]
    for s_ in srcs:
        for line in re.split(r"\n", s_):
            if re.search(r"\bmust\b|\bshall\b|\bmay be excluded\b|\bis a requirement\b|\bare required\b|\brequired to\b|\bmandatory\b", line, re.I):
                must.append(red(line.strip())[:500])
    route = red(t.get("submissionMethodDetails")) or "not stated in pasted text"
    cpv = [(t.get("classification") or {}).get("id")] + [c.get("id") for i in t.get("items", []) for c in i.get("additionalClassifications", [])]
    o = ["GlobalLand one-notice source-reconciliation brief / Note de rapprochement des sources (un avis)", DISC,
         f"Notice / Avis: {nid}   OCID: {rel.get('ocid')}   release date: {rel.get('date')}   tags: {rel.get('tag')}",
         f"SHA-256 of the exact pasted text we checked / empreinte du texte vérifié : {h} ({len(raw)} bytes)",
         f"Formatting-independent SHA-256 of the selected release (canonical JSON: sorted keys, no spaces between elements; spaces inside text values still count; not proof of authenticity) / empreinte canonique (clés triées ; tolère la mise en forme, pas les espaces dans les valeurs ; ne prouve pas l'authenticité): {canon}",
         "We did not visit any link or portal and cannot confirm this text matches the live official record; compare the hashes and fields yourself. / Nous n'avons consulté aucun lien ni portail ; comparez vous-même les empreintes et les champs.",
         "", "== 1. Stated facts (quoted from your pasted text) ==",
         f"Buyer: {red((rel.get('buyer') or {}).get('name'))}", f"Title: {red(t.get('title'))}",
         f"Scope (tender.description): {red(t.get('description'))}",
         f"Status: {st}   Procedure: {t.get('procurementMethodDetails') or t.get('procurementMethod')}   CPV: {', '.join(c for c in cpv if c)}",
         f"Submission deadline (UTC): {dl}", f"Value / currency: {'; '.join(vals) if vals else 'none stated in pasted release'}",
         f"Submission route (verbatim): {route}", "Lots:"] + (L or ["  none stated"])
    o += ["", "== 2. Contradictions and checks =="] + ([f"  - {f}" for f in flags] or ["  - none detected by our checks"])
    o += ["", "== 3. Requirements stated in the pasted text (lexical match only: must, shall, may be excluded, is a requirement, are required, required to, mandatory) =="] + ([f"  - {m}" for m in must] or ["  - no matching wording found (lexical search only; not proof of no requirements) / aucune formulation correspondante trouvée (recherche lexicale seulement ; ce n’est pas la preuve d’une absence d’exigences)"])
    o += ["", "== 4. Our recommendations (not buyer requirements) ==", "  - Confirm the deadline on the official notice and leave a buffer before it.", "  - Obtain the full tender pack through the submission route above before deciding.", "  - Check each stated requirement in section 3 against your own certificates and policies.", "  - Compare the award weights with your pricing position.", "  - Bid only if every unknown in section 5 is resolved in your favour."]
    o += ["", "== 5. Unknowns =="] + [f"  - {u}" for u in unk]
    o += ["", "== Résumé en français ==", f"Avis : {nid} ; acheteur : {red((rel.get('buyer') or {}).get('name'))}", f"Date limite (UTC) : {dl}",
          f"Valeur : {'; '.join(vals) if vals else 'aucune valeur dans la publication collée'}", f"Voie de dépôt (citée) : {route}",
          f"Contradictions signalées : {len(flags)} ; exigences citées (en anglais, section 3) : {len(must)}.",
          "Recommandations (les nôtres) : confirmer la date limite sur l'avis officiel ; obtenir le dossier complet par la voie de dépôt ; vérifier chaque exigence ; comparer les pondérations avec votre prix.",
          "Inconnues : documents d'appel d'offres non fournis ni lus ; date limite de clarification ; votre admissibilité et inscription" + (" ; valeur et devise." if not vals else "."),
          "Aucune admissibilité n'est affirmée. / No eligibility is asserted."]
    txt = "\n".join(o)
    assert len(txt) < 32000, len(txt)
    out(txt)
if __name__ == "__main__":
    main()
