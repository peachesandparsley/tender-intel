"""
Wine ↔ spec eligibility engine (the marketplace loop).

For every spec, checks every wine record clause-by-clause:
  pass    — wine data satisfies the clause
  fail    — wine data contradicts it (hard clauses disqualify)
  unknown — wine record lacks the field (producer confirmation needed)

Output: marketplace.json — per spec, eligible wines with clause verdicts,
FOB feasibility, and representation status.

Usage: python3 match_wines.py specs.json [-o marketplace.json]
"""
import json, re, sys, unicodedata
from clauses import clauses_for_spec
from pricing import fob_from_retail
from match import guess_abv, spec_text, norm as mnorm

def norm(s):
    s = (s or "").translate(str.maketrans({"ø":"o","Ø":"o","æ":"ae","Æ":"ae","ü":"u","é":"e","è":"e","ä":"a","ö":"o"}))
    return unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().lower()

def grape_pct(wine, variety):
    v = norm(variety)
    for g, pct in wine["grapes"].items():
        gn = norm(g)
        if v in gn or gn in v:
            return pct
    # common synonyms
    syn = {"mataro": "mourvedre", "mourvedre": "mataro", "shiraz": "syrah", "syrah": "shiraz"}
    for g, pct in wine["grapes"].items():
        gn = norm(g)
        if syn.get(v) and syn[v] in gn:
            return pct
    return 0

def check(clause, wine):
    t = clause["type"]
    if t == "grape":
        vs = clause.get("varieties", [])
        if clause["mode"] == "single":
            v = vs[0] if vs else ""
            return "pass" if grape_pct(wine, v) == 100 else "fail"
        if clause["mode"] == "min_pct":
            total = sum(grape_pct(wine, v) for v in vs) or max((grape_pct(wine, v) for v in vs), default=0)
            return "pass" if total >= clause["pct"] else "fail"
        if clause["mode"] == "any_of":
            return "pass" if sum(grape_pct(wine, v) for v in vs) >= 99 else "fail"
    if t == "method":
        if wine.get("method") is None: return "fail"
        return "pass" if norm(clause["method"]).split(" ")[0] in norm(wine["method"]) else "fail"
    if t == "vintage":
        avail = wine.get("vintages_available") or []
        if 0 in avail: return "pass"  # NV
        if "min_year" in clause:
            return "pass" if any(y >= clause["min_year"] for y in avail) else "fail"
        return "pass" if set(clause.get("years", [])) & set(avail) else "fail"
    if t == "sugar_max":
        s = wine.get("sugar_g_l")
        if s is None: return "unknown"
        return "pass" if s <= clause["g_l"] else "fail"
    if t == "wood":
        w = norm(wine.get("wood") or "")
        if not w: return "unknown"
        if clause["mode"] == "none_or_discreet":
            return "pass" if ("none" in w or "discreet" in w or "old" in w) else "fail"
        if clause["mode"] == "barrel_required":
            return "pass" if ("barrel" in w or "ferment" in w or "new" in w or "oak" in w) and "none" not in w else "fail"
    if t == "cert":
        held = [norm(c) for c in wine.get("certs", [])]
        need = clause["certs"]
        ok = any(any(norm(n) in h or h in norm(n) for h in held) for n in need)
        if not ok: return "fail"
        if clause.get("on_label") and not wine.get("cert_on_label"):
            return "unknown"
        return "pass"
    if t == "volume_min":
        v = wine.get("volume_bottles")
        if v is None: return "unknown"
        return "pass" if v >= clause["bottles"] else "fail"
    if t == "maceration":
        d = wine.get("maceration_days")
        if d is None: return "unknown"
        return "pass" if clause["min_days"] <= d <= clause["max_days"] else "fail"
    if t == "vines_age":
        a = wine.get("vines_age")
        if a is None: return "unknown"
        return "pass" if a >= clause["min_years"] else "fail"
    if t == "abv_max":
        a = wine.get("abv")
        if a is None: return "unknown"
        return "pass" if a <= clause["pct"] else "fail"
    if t == "appellation":
        wa = norm(wine.get("appellation") or "") + " " + norm(wine.get("country",""))
        ca = norm(clause["text"])
        # match on significant tokens (skip generic words)
        toks = [w for w in re.findall(r"[a-z]{4,}", ca) if w not in
                ("from","with","wine","quality","aoc","aop","doc","docg",
                 "valle","valley","region","south","north","west","east",
                 "coast","upper","lower")]
        return "pass" if toks and all(any(tk in wa for tk in toks[:2]) for _ in [0]) and any(tk in wa for tk in toks) else "fail"
    if t in ("offer_rule", "packaging_rule", "confirmation_rule"):
        return "info"
    return "unknown"

def origin_ok(spec, wine):
    sc, wc = norm(spec.get("country","")), norm(wine["country"])
    if not sc or sc == "-" or "open" in sc or "all countries" in sc: return True
    if "europe" in sc:
        return wc in ("austria","portugal","france","italy","spain","germany","greece","hungary","england","slovenia","croatia")
    return wc in sc or sc in wc

def group_ok(spec, wine):
    g = norm(spec.get("group","")) or norm(spec.get("main_type",""))
    mt = norm(spec.get("main_type",""))
    # wine records only match wine specs — never beer/cider/spirits
    if any(w in g + " " + mt for w in ("fermented","beer","ale","lager","cider","mead",
                                       "spirit","whisky","aquavit","gin","vodka","rum")):
        return False
    if mt and "wine" not in mt:
        return False
    sparkling = "sparkling" in g or "musserende" in g or "semi-sparkling" in g
    if sparkling != bool(wine.get("method")):
        return False
    color = norm(wine.get("color",""))
    if "rose" in g:  return "rose" in color
    if "red" in g or "rodvin" in g:   return "red" in color
    if "white" in g or "hvitvin" in g: return "white" in color
    return True

def evaluate(spec, wine, fob_req):
    if not origin_ok(spec, wine) or not group_ok(spec, wine):
        return None
    verdicts = []
    for cl in clauses_for_spec(spec):
        v = check(cl, wine)
        verdicts.append({"clause": cl["text"][:90], "type": cl["type"], "verdict": v})
    hard = [v for v in verdicts if v["verdict"] in ("pass","fail","unknown")]
    fails = sum(1 for v in hard if v["verdict"] == "fail")
    unknowns = sum(1 for v in hard if v["verdict"] == "unknown")
    passes = sum(1 for v in hard if v["verdict"] == "pass")
    if fails:
        return None
    price_ok = None
    if fob_req and fob_req.get("required_fob_eur") and wine.get("fob_eur") is not None:
        price_ok = wine["fob_eur"] <= fob_req["required_fob_eur"]
    return {
        "wine_id": wine["id"], "wine": wine["name"], "producer": wine["producer"],
        "country": wine["country"], "fob_eur": wine.get("fob_eur"),
        "passes": passes, "unknowns": unknowns, "total_checked": len(hard),
        "price_ok": price_ok,
        "representation_no": wine.get("representation", {}).get("NO", "unknown"),
        "verdicts": verdicts,
    }

if __name__ == "__main__":
    specs = json.load(open(sys.argv[1], encoding="utf-8"))
    wines = json.load(open("wines.json", encoding="utf-8"))["wines"]
    out = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else "marketplace.json"
    market = []
    for spec in specs:
        hi = spec.get("price_hi") or spec.get("price_lo")
        fob = fob_from_retail(float(hi), guess_abv(spec_text(spec)), spec.get("litres") or 0.75) if hi else None
        matches = sorted(filter(None, (evaluate(spec, w, fob) for w in wines)),
                         key=lambda m: (-(m["price_ok"] is True), m["unknowns"], -m["passes"]))
        if matches:
            market.append({"ref": spec["ref"], "group": spec["group"],
                           "country": spec["country"], "price_text": spec["price_text"],
                           "launch": spec["launch"], "selection": spec["selection"],
                           "required_fob_eur": fob["required_fob_eur"] if fob else None,
                           "matches": matches})
    json.dump(market, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(specs)} specs, {len(wines)} wines -> {len(market)} specs with eligible wines -> {out}")
    for m in market:
        best = m["matches"][0]
        print(f"  {m['ref']} {m['group']} | {m['country']} | {m['price_text']} (need ≤€{m['required_fob_eur']})")
        for x in m["matches"]:
            tag = "OPEN" if "unrepresented" in x["representation_no"] else "taken"
            price = "€ok" if x["price_ok"] else ("€HIGH" if x["price_ok"] is False else "€?")
            print(f"      {x['producer']} — {x['wine']} [{x['passes']}✓ {x['unknowns']}? / {x['total_checked']}] {price} rep:{tag}")
