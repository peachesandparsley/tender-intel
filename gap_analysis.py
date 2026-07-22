"""
gap_analysis.py — where recurring monopoly demand meets little known supply.

Vinmonopolet publishes what it ASKS for (the launch plans), not which lots were
filled. But a lot that keeps being re-requested plan after plan is the fingerprint of
chronically under-served demand — it didn't attract good enough offers and gets
re-issued. This script quantifies that: for every origin × style × grape cluster it
measures how often/across-how-many-plans it is requested, then how few of the wines we
actually know about qualify. High demand + thin known supply = the gaps worth targeting.

Honest scope: "known wines" = the records in this repo (wines.json + seed_sample.json),
a partial sample — NOT the whole world market. So a zero-supply cluster is "no wine WE
KNOW OF qualifies", a sourcing gap for a user of this tool, and recurrence is the
demand-side signal that stands on its own.

Reads:  specs_*.json (all launch plans), wines.json, seed_sample.json (if present)
Writes: gap_analysis.md (ranked report) + gap_analysis.json (structured directory)
Run:    python3 gap_analysis.py
"""
import json, glob, re, collections, statistics

def N(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()
                  .replace("ø", "o").replace("æ", "ae").replace("å", "a").replace("ö", "o").replace("ä", "a"))

PLANS = {}
for f in sorted(glob.glob("specs_*.json")):
    label = re.sub(r"^specs_(plan_)?|_en\.json$|\.json$", "", f)
    try:
        d = json.load(open(f, encoding="utf-8"))
        PLANS[label] = d if isinstance(d, list) else d.get("specs", [])
    except Exception:
        pass

WINES = []
for wf in ("wines.json", "seed_sample.json"):
    try:
        WINES += json.load(open(wf, encoding="utf-8")).get("wines", [])
    except FileNotFoundError:
        pass

GRAPES = ["chardonnay", "chenin blanc", "pinot noir", "pinotage", "cabernet franc", "cabernet sauvignon",
    "merlot", "syrah", "shiraz", "grenache", "garnacha", "cinsault", "mourvedre", "tempranillo", "sangiovese",
    "nebbiolo", "barbera", "riesling", "gruner veltliner", "sauvignon blanc", "malbec", "carmenere", "zinfandel",
    "primitivo", "gamay", "albarino", "godello", "verdejo", "gewurztraminer", "pinot gris", "pinot blanc",
    "viognier", "touriga", "furmint", "assyrtiko", "xinomavro", "agiorgitiko", "carignan", "petit verdot",
    "semillon", "muscat", "moscato", "glera", "vermentino", "fiano", "greco", "montepulciano", "aglianico",
    "corvina", "garganega", "verdicchio", "cortese", "arneis", "dolcetto", "encruzado", "arinto", "baga",
    "mencia", "monastrell", "bobal", "graciano", "macabeo", "touriga nacional", "alvarinho", "mondeuse",
    "tannat", "silvaner", "blaufrankisch", "zweigelt", "saperavi", "sousao"]

SYN = {"shiraz": "syrah", "syrah": "shiraz", "garnacha": "grenache", "grenache": "garnacha",
       "primitivo": "zinfandel", "zinfandel": "primitivo", "mataro": "mourvedre", "mourvedre": "mataro"}


def is_wine(s):
    t = N((s.get("main_type") or "") + " " + (s.get("group") or ""))
    return not re.search(r"beer|cider|spirit|whisky|aquavit|gin|vodka|rum|brandy|mead|sake", t)


def style(s):
    g = N((s.get("group") or "") + " " + (s.get("main_type") or ""))
    if "sparkling" in g or "musserende" in g: return "sparkling"
    if "rose" in g: return "rose"
    if "fortified" in g or "sterkvin" in g: return "fortified"
    if "white" in g or "hvit" in g: return "white"
    if "red" in g or "rod" in g: return "red"
    return "wine"


def spec_grapes(s):
    txt = N(" ".join(str(s.get(k) or "") for k in ("spec", "appellation", "quality")))
    return {g for g in GRAPES if g in txt}


def wine_style(w):
    c = N(w.get("color") or "")
    if "sparkling" in c or "musserende" in c: return "sparkling"
    if "rose" in c: return "rose"
    if "fortified" in c or "sterk" in c: return "fortified"
    if "white" in c or "hvit" in c: return "white"
    if "red" in c or "rod" in c: return "red"
    return "wine"


def grape_match(g, x):
    a, b = N(g), N(x)
    return b in a or a in b or (SYN.get(b) and SYN[b] in a)


def wine_has_grape(w, x):
    return any(grape_match(g, x) for g in (w.get("grapes") or {}))


CERT_RE = re.compile(r"organic|okologisk|fairtrade|biodynam|sustainab|\bipw\b|\bwsb\b|terra vitis|equalitas|vegan|demeter", re.I)


def build():
    clusters = {}
    for plan, specs in PLANS.items():
        for s in specs:
            if not is_wine(s):
                continue
            country = (s.get("country") or "").strip() or "Open"
            st = style(s)
            grapes = spec_grapes(s) or {""}
            price = s.get("price_hi") or s.get("price_lo")
            cert = bool(CERT_RE.search(s.get("spec") or ""))
            for g in grapes:
                key = (country, st, g)
                c = clusters.setdefault(key, {"country": country, "style": st, "grape": g,
                                              "plans": set(), "requests": 0, "prices": [], "cert": 0})
                c["plans"].add(plan); c["requests"] += 1
                if price: c["prices"].append(price)
                if cert: c["cert"] += 1
    open_re = re.compile(r"unrepresented|open for import|candidate for import", re.I)
    for c in clusters.values():
        qual = [w for w in WINES if
                (c["country"] == "Open" or N(w.get("country")) == N(c["country"]) or N(c["country"]) in N(w.get("country")) or N(w.get("country")) in N(c["country"]))
                and (c["style"] == "wine" or wine_style(w) == c["style"])
                and (not c["grape"] or wine_has_grape(w, c["grape"]))]
        c["supply"] = len(qual)
        c["open"] = sum(1 for w in qual if open_re.search((w.get("representation") or {}).get("NO", "")))
        c["n_plans"] = len(c["plans"])
        c["med_price"] = int(statistics.median(c["prices"])) if c["prices"] else 0
        c["cert_pct"] = round(100 * c["cert"] / c["requests"]) if c["requests"] else 0
        c["gap_score"] = round(c["requests"] * c["n_plans"] / (c["supply"] + 1), 1)
        c["chronic"] = c["n_plans"] >= 2
        c["unmet"] = c["supply"] == 0
        c["plans"] = sorted(c["plans"])
    return sorted(clusters.values(), key=lambda c: -c["gap_score"])


def main():
    rows = build()
    n_plans = len(PLANS)
    chronic = [c for c in rows if c["chronic"]]
    unmet = [c for c in rows if c["unmet"]]
    json.dump({"generated_from": sorted(PLANS), "n_plans": n_plans,
               "known_wines": len(WINES), "clusters": rows},
              open("gap_analysis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    L = []
    def out(s=""): print(s); L.append(s)
    out("# Tender gap analysis — under-served demand to target\n")
    out(f"Plans analysed: {n_plans} ({', '.join(PLANS)}) · known wines: {len(WINES)}\n")
    out(f"- **{len(rows)}** demand clusters (origin × style × grape)")
    out(f"- **{len(chronic)}** recurring (requested in ≥2 plans)")
    out(f"- **{len(unmet)}** unmet (no known wine in this database qualifies)\n")
    out("Gap score = requests × number of plans ÷ (known qualifying wines + 1). "
        "«Known wines» = this repo's sample, not the whole market.\n")
    out("## Top gaps to target\n")
    out("| Origin | Style | Grape | Plans | Reqs | ~kr | Cert% | Known | Open | Gap | Flags |")
    out("|---|---|---|---|--:|--:|--:|--:|--:|--:|---|")
    for c in rows[:40]:
        flags = " ".join(f for f, on in [("unmet", c["unmet"]), ("recurring", c["chronic"])] if on)
        out(f"| {c['country']} | {c['style']} | {c['grape'] or '—'} | {c['n_plans']}/{n_plans} | "
            f"{c['requests']} | {c['med_price'] or '–'} | {c['cert_pct'] or '–'} | {c['supply']} | "
            f"{c['open'] or '–'} | {c['gap_score']} | {flags} |")
    out("\n## Chronic + unmet (recurring demand, zero known supply — the cleanest openings)\n")
    for c in [c for c in rows if c["chronic"] and c["unmet"]][:25]:
        g = c["grape"] or "any grape"
        out(f"- **{c['country']} {c['style']} — {g}** · {c['requests']} requests across "
            f"{c['n_plans']}/{n_plans} plans · ~{c['med_price'] or '?'} kr"
            f"{' · cert ' + str(c['cert_pct']) + '%' if c['cert_pct'] else ''}")

    open("gap_analysis.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n(written to gap_analysis.md + gap_analysis.json)")


if __name__ == "__main__":
    main()
