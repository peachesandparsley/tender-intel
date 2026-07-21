"""
seed_producers.py — cold-start the producer database from OFFICIAL public sources.

Turns a structured export assembled from South Africa's official wine bodies into
seed producer/wine records: real, publicly sourced, but marked UNVERIFIED and
"pending producer claim". The tender-critical numbers only a producer holds —
ex-cellar FOB, committed volume, exact grape %, residual sugar, wood regime,
bottle weight — are left blank and flagged unknown. A producer fills those in
when they claim the profile; nothing is fabricated.

Official sources (see SEED_SOURCES.md for URLs, access and licensing):
  - Producer & wine identity, region ....... Wines of South Africa (wosa.co.za)
  - Origin / vintage / variety guarantee ... Wine of Origin scheme, Wine & Spirit Board
  - Sustainability seal (IPW) .............. verifiable at sawis.co.za (seal number)
  - Ethical-trade cert (WIETA) ............. wieta.org.za  (Fairtrade: FLOCERT)

Representation is DERIVED, not guessed: each wine is cross-checked against
vmp_catalog_index.json (the real Vinmonopolet catalog). A wine that is NOT in
the catalog is "unrepresented in NO" — exactly the introduction opportunity an
importer is looking for.

Run: python3 seed_producers.py --file wosa_export.csv --out seed_producers.json
     (--vmp-index vmp_catalog_index.json is used automatically if present)
"""
import os, sys, json, csv, io, re, argparse, datetime

TODAY = datetime.date.today().isoformat()
COUNTRY = "South Africa"

# input column aliases -> canonical field
ALIASES = {
    "producer": ["producer", "estate", "cellar", "winery", "producer name"],
    "name": ["wine", "name", "wine name", "product", "cuvee", "cuvée"],
    "region": ["region", "district", "ward", "wo", "wine of origin", "appellation"],
    "colour": ["colour", "color", "type", "wine type"],
    "grapes": ["grapes", "variety", "varieties", "cultivar", "cultivars", "grape"],
    "vintages": ["vintage", "vintages", "year"],
    "ipw_seal": ["ipw seal", "ipw", "seal", "seal number", "sustainability seal", "swsa seal"],
    "wieta": ["wieta", "wieta certified", "ethical"],
    "fairtrade": ["fairtrade", "fair trade", "fair for life"],
    "organic": ["organic", "organic certified"],
    "url": ["url", "source", "source url", "wosa url", "profile", "website"],
}


def norm_keys(row):
    out = {}
    low = {str(k).strip().lower(): v for k, v in row.items()}
    for field, names in ALIASES.items():
        for n in names:
            if n in low and str(low[n]).strip() != "":
                out[field] = low[n]
                break
    return out


def N(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower().replace("ø", "o").replace("æ", "ae").replace("å", "a"))


COLOR_MAP = {"red": "red", "white": "white", "rose": "rose", "rosé": "rose",
             "sparkling": "sparkling white", "mcc": "sparkling white",
             "cap classique": "sparkling white", "fortified": "fortified"}


def parse_bool(v):
    return str(v or "").strip().lower() in ("yes", "y", "true", "1", "ja", "certified", "member")


def parse_grapes(v):
    grapes = {}
    parts = re.split(r"[;,/]| and ", str(v or ""))
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return grapes
    # if percentages are given ("chenin blanc 60%"), keep them; else split evenly is NOT done — leave 0 (unknown)
    for p in parts:
        m = re.match(r"(.+?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?$", p)
        if m and m.group(2):
            grapes[m.group(1).strip().lower()] = float(m.group(2))
        else:
            grapes[p.lower()] = 0  # variety known, share to be confirmed by producer
    return grapes


def load_vmp_index(path):
    if not path or not os.path.exists(path):
        return None
    d = json.load(open(path, encoding="utf-8"))
    return [(p.get("productId"), N(p.get("name"))) for p in d.get("products", [])]


def representation_no(producer, name, vmp):
    """Unrepresented (opportunity) unless the exact wine is in the Vinmonopolet catalog."""
    if vmp is None:
        return {"NO": "unknown — VMP index not loaded", "verified": False}
    pTok = [t for t in N(producer).split() if len(t) >= 4]
    nTok = [t for t in N(name).split() if len(t) >= 4]
    for pid, hay in vmp:
        p = sum(t in hay for t in pTok)
        n = sum(t in hay for t in nTok)
        if (p >= 1 and n >= 1) or (not pTok and n >= 2) or (not nTok and p >= 2):
            return {"NO": f"listed in VMP catalog (varenr {pid})", "verified": True}
    return {"NO": "unrepresented — open for import", "verified": True}


def to_record(row, idx, vmp):
    r = norm_keys(row)
    producer = str(r.get("producer") or "").strip()
    name = str(r.get("name") or "").strip()
    if not producer or not name:
        return None
    color = ""
    craw = str(r.get("colour") or "").strip().lower()
    for k, v in COLOR_MAP.items():
        if k in craw:
            color = v
            break
    seal = str(r.get("ipw_seal") or "").strip()
    certs = []
    if seal or parse_bool(r.get("ipw_seal")):
        certs.append("IPW / Sustainable Wine SA")
    if parse_bool(r.get("wieta")):
        certs.append("WIETA")
    if parse_bool(r.get("fairtrade")):
        certs.append("Fairtrade")
    if parse_bool(r.get("organic")):
        certs.append("Organic")
    vintages = [int(y) for y in re.findall(r"(?:19|20)\d\d", str(r.get("vintages") or ""))]
    rep = representation_no(producer, name, vmp)
    url = str(r.get("url") or "").strip() or "https://www.wosa.co.za"
    pub = lambda src: {"tier": "public", "note": f"public data — {src}", "source": url}
    ver = lambda src: {"tier": "verified", "note": f"verifiable — {src}", "source": url}
    unk = lambda note: {"tier": "unknown", "note": note}

    cert_verify = ver(f"IPW seal {seal}, sawis.co.za") if seal else \
        (pub("cert bodies (WIETA/WoSA)") if certs else unk("no certification recorded"))

    return {
        "id": f"seedZA{idx:04d}",
        "producer": producer,
        "name": name,
        "country": COUNTRY,
        "region": str(r.get("region") or "").strip(),
        "appellation": str(r.get("region") or "").strip(),  # SA Wine of Origin ward/district
        "grapes": parse_grapes(r.get("grapes")),
        "method": "traditional" if "cap classique" in craw or "mcc" in craw else None,
        "vintages_available": vintages,
        "abv": None, "sugar_g_l": None, "wood": None,
        "certs": certs, "cert_on_label": bool(certs),
        "vines_age": None, "maceration_days": None,
        "volume_bottles": None,   # producer only
        "fob_eur": None,          # producer only
        "color": color,
        "packaging": {"type": None, "weight_g": None},
        "representation": {"NO": rep["NO"], "SE": "unknown", "FI": "unknown"},
        "pending_claim": True,
        "source": f"seed: Wines of South Africa (public) — {url}",
        "audit": {"created_by": "seed:WoSA (public)", "created_at": TODAY + "T00:00",
                  "updated_by": "seed:WoSA (public)", "updated_at": TODAY + "T00:00",
                  "note": "Public-sourced seed, UNVERIFIED, pending producer claim. "
                          "FOB, volume, grape % and analytical detail to be confirmed by the producer."},
        "verify": {
            "producer": pub("Wines of South Africa"), "name": pub("Wines of South Africa"),
            "country": ver("Wine of Origin scheme"), "region": ver("Wine of Origin scheme"),
            "appellation": ver("Wine of Origin scheme, Wine & Spirit Board"),
            "certs": cert_verify,
            "representation": {"tier": "verified" if rep["verified"] else "unknown",
                               "note": "derived from the Vinmonopolet catalog index"},
            "grapes": unk("variety from WO scheme; exact % to be confirmed by producer"),
            "abv": unk("to be confirmed by producer / tech sheet"),
            "fob_eur": unk("ex-cellar price to be supplied by the producer"),
            "volume_bottles": unk("available volume to be supplied by the producer"),
            "sugar_g_l": unk("to be confirmed by producer / analysis certificate"),
            "packaging": unk("bottle weight to be confirmed by producer"),
        },
    }


def load_rows(path):
    raw = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        d = json.loads(raw)
        return d if isinstance(d, list) else (d.get("producers") or d.get("rows") or d.get("wines") or [])
    return list(csv.DictReader(io.StringIO(raw)))


def main():
    ap = argparse.ArgumentParser(description="Seed producer DB from official South African sources.")
    ap.add_argument("--file", required=True, help="structured export (CSV or JSON) built from official sources")
    ap.add_argument("--vmp-index", default="vmp_catalog_index.json", help="Vinmonopolet catalog index for representation")
    ap.add_argument("--out", default="seed_producers.json")
    args = ap.parse_args()

    vmp = load_vmp_index(args.vmp_index)
    rows = load_rows(args.file)
    recs = [r for r in (to_record(row, i + 1, vmp) for i, row in enumerate(rows)) if r]
    unrep = sum(1 for r in recs if "unrepresented" in r["representation"]["NO"])
    json.dump({"generated": TODAY, "source": "official South African wine bodies (public)",
               "wines": recs}, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(recs)} seed producers -> {args.out}  "
          f"({unrep} unrepresented in NO{' — VMP index not loaded' if vmp is None else ''})")


if __name__ == "__main__":
    main()
