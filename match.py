"""
Matching engine v3 — origin-agnostic.

Scores every tender spec against an importer's PORTFOLIO (portfolio.json).
Nothing about any specific country is hardcoded: each producer carries its own
origin_terms, style tags and certifications, and every spec is scored per
producer. A spec's headline score = its best producer fit.

Usage: python3 match.py specs.json [-o opportunities.json] [--portfolio portfolio.json]
"""
import json, re, sys, unicodedata
from pricing import fob_from_retail

OPEN_WORDS = ["apen", "open", "alle land", "any origin", "verden", "all countries",
              "fri opprinnelse", "europe"]  # 'europe' = open within Europe

# style tag -> regex over spec text (grapes, methods, categories)
STYLE_PATTERNS = {
    "chenin blanc": r"chenin",
    "chenin blanc old-vine": r"chenin",
    "pinotage": r"pinotage",
    "pinot noir": r"pinot noir",
    "chardonnay": r"chardonnay",
    "cap classique": r"cap classique|mcc|traditional method|methode traditionnelle|sparkling",
    "syrah": r"syrah|shiraz",
    "grenache": r"grenache",
    "cinsault": r"cinsault",
    "sauvignon blanc": r"sauvignon",
    "bordeaux blend": r"bordeaux|cabernet|merlot|cab\.? franc",
    "cabernet sauvignon": r"cabernet",
    "low-intervention": r"natural|low.intervention|orange|skin.contact|lavintervensjon|naturvin",
    "fairtrade": r"fairtrade|fair for life|ethical|etisk",
    "gruner veltliner": r"gr.ner veltliner",
    "riesling": r"riesling",
    "field blend red": r"field blend|red blend",
    "port": r"\bport\b|lbv|tawny|ruby",
}
CERT_PATTERNS = {
    "Fairtrade": r"fairtrade|fair for life",
    "WIETA": r"wieta|ethical",
    "Organic (EU)": r"organic|okologisk|biodynam",
    "Old Vine Project": r"old vines?|heritage vineyard|gamle stokker|min\.? \d+ years? old vines",
}

def norm(s):
    s = (s or "").translate(str.maketrans({"ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae"}))
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

def guess_abv(text):
    if re.search(r"sparkling|musserende|cap classique|mcc", text): return 12.5
    if re.search(r"fortified|sterkvin|port|sherry|madeira", text): return 19.0
    if re.search(r"riesling|kabinett|moscato", text): return 11.0
    return 13.5

def spec_text(spec):
    return norm(" ".join([spec.get("country",""), spec.get("region",""),
                          spec.get("appellation",""), spec.get("group",""),
                          spec.get("spec","")]))

def origin_status(spec, producer):
    """'direct' | 'open' | 'excluded' for this producer."""
    text = spec_text(spec)
    country = norm(spec.get("country", ""))
    if any(t in text for t in producer.get("origin_terms", [norm(producer["country"])])):
        return "direct"
    if any(w in country for w in OPEN_WORDS) or country in ("", "-"):
        # 'europe' opens only to European producers
        if "europe" in country and norm(producer["country"]) not in (
                "austria","portugal","france","italy","spain","germany","greece","hungary"):
            return "excluded"
        return "open"
    return "excluded"

def fit(spec, producer, fob_req):
    text = spec_text(spec)
    status = origin_status(spec, producer)
    if status == "excluded":
        return None
    s, why = (5.0, ["origin: named in spec"]) if status == "direct" else (2.0, ["origin: open"])

    style_hits = [t for t in producer["styles"]
                  if t in STYLE_PATTERNS and re.search(STYLE_PATTERNS[t], text)]
    if not style_hits:
        return None  # producer has nothing matching the style asked for
    s += min(3.0, 2.0 * len(style_hits))
    why.append("styles: " + ", ".join(sorted(set(style_hits))))

    cert_hits = [c for c, pat in CERT_PATTERNS.items()
                 if re.search(pat, text) and c in producer.get("certs", [])]
    if cert_hits:
        s += 1.5; why.append("certs requested & held: " + ", ".join(cert_hits))

    if fob_req and fob_req.get("required_fob_zar") and producer.get("fob_zar"):
        lo, hi = producer["fob_zar"]
        r = fob_req["required_fob_zar"]
        if r >= lo:
            s += 1.0; why.append(f"price fits (needs ≤R{r:.0f}, producer from R{lo})")
        else:
            s -= 2.0; why.append(f"price tight (needs ≤R{r:.0f}, producer starts R{lo})")
    return {"producer": producer["name"], "fit": round(s, 1), "why": why}

def score_spec(spec, portfolio):
    text = spec_text(spec)
    hi = spec.get("price_hi") or spec.get("price_lo")
    fob = fob_from_retail(float(hi), guess_abv(text), spec.get("litres") or 0.75) if hi else None

    fits = sorted((f for p in portfolio if (f := fit(spec, p, fob))),
                  key=lambda x: -x["fit"])
    best = fits[0]["fit"] if fits else 0.0
    reasons = fits[0]["why"] if fits else ["no portfolio producer matches origin+style"]
    if fob and not fob["viable"]:
        best -= 3; reasons = reasons + ["price band below viable supply"]
    return {**spec,
            "sa_origin": "SA" if fits and "named in spec" in fits[0]["why"][0] else
                         ("open" if fits else "other"),   # field name kept for dashboard compat
            "score": round(best, 1), "reasons": reasons, "fob": fob,
            "candidate_producers": [f["producer"] for f in fits[:5]],
            "fits": fits[:5]}

if __name__ == "__main__":
    pf = "portfolio.json"
    if "--portfolio" in sys.argv:
        pf = sys.argv[sys.argv.index("--portfolio") + 1]
    specs = json.load(open(sys.argv[1], encoding="utf-8"))
    portfolio = json.load(open(pf, encoding="utf-8"))["producers"]
    out = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else "opportunities.json"
    ranked = sorted((score_spec(sp, portfolio) for sp in specs), key=lambda r: -r["score"])
    json.dump(ranked, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    winnable = [r for r in ranked if r["score"] >= 5]
    print(f"{len(specs)} specs vs {len(portfolio)}-producer portfolio -> {len(winnable)} winnable -> {out}")
    for r in ranked[:8]:
        print(f"  [{r['score']:>4}] {r['ref']} {r['group']} | {r['country'] or '—'} | "
              f"{r['price_text']} | {', '.join(r['candidate_producers'][:3]) or '—'}")
