"""
ingest_systembolaget.py — seed the producer/supply side from Sweden's monopoly.

The smart cold-start: Systembolaget's full assortment is open data, and a wine
listed in Sweden but NOT in Vinmonopolet is a monopoly-PROVEN producer that is
unrepresented in Norway — a far higher-quality lead than a trade-body directory,
with real specs already attached (producer, region, GRAPES, ABV, vintage, price).

Representation is scored at the IMPORTER level, not the wine level, because Nordic
importers are mostly country-by-country BUT a few groups are pan-Nordic (Anora
above all). So a wine gets one of:
  - represented   : the wine/producer is already in the Vinmonopolet catalog
  - pan_nordic    : its Swedish supplier is a pan-Nordic group -> already reachable in NO
  - open          : neither -> genuine introduction opportunity for a NO importer

Data:  Systembolaget open mirror -> data/assortment.json
       (github.com/AlexGustafsson/systembolaget-api-data), or the official
       api-portal.systembolaget.se. Fields confirmed against that mirror.

Run:   python3 ingest_systembolaget.py --file assortment.json \
              --vmp-index vmp_catalog_index.json --out seed_se.json
"""
import os, sys, json, re, argparse, datetime, collections

TODAY = datetime.date.today().isoformat()

# Pan-Nordic importers/groups that already cover Norway (extend as you learn more).
# Matched as a substring against the Swedish supplierName.
PAN_NORDIC = ["anora", "altia", "arcus", "globus"]

CAT_COLOR = [("rott", "red"), ("rod", "red"), ("red", "red"),
             ("vitt", "white"), ("vit", "white"), ("white", "white"),
             ("rose", "rose"), ("mousserande", "sparkling"), ("sparkling", "sparkling"),
             ("starkvin", "fortified"), ("fortified", "fortified")]


def N(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()
                  .replace("ø", "o").replace("æ", "ae").replace("å", "a").replace("ö", "o").replace("ä", "a"))


def color_of(p):
    cats = " ".join(N(str(p.get(k) or "")) for k in ("categoryLevel2", "categoryLevel3", "categoryLevel1"))
    for key, col in CAT_COLOR:
        if key in cats:
            return col
    return ""


def is_wine(p):
    return N(str(p.get("categoryLevel1") or "")) .strip() in ("vin",) or "vin" == N(str(p.get("categoryLevel1") or "")).strip()


def parse_grapes(p):
    g = p.get("grapes")
    out = {}
    if isinstance(g, list):
        for name in g:
            if str(name).strip():
                out[str(name).strip().lower()] = 0  # variety known; exact % pending producer
    elif isinstance(g, str) and g.strip():
        for name in re.split(r"[;,/]", g):
            if name.strip():
                out[name.strip().lower()] = 0
    return out


def parse_certs(p):
    """Real, public certification flags carried in the Systembolaget feed — these are
    verifiable facts (organic/ethical/kosher/sustainable), and several are literal
    tender gates, so they are worth seeding (unlike producer-only analytical data)."""
    certs = []
    if p.get("isOrganic"):
        certs.append("Organic")
    lbl = str(p.get("ethicalLabel") or "").strip()
    if p.get("isEthical") or lbl:
        certs.append("Fairtrade" if "fair" in lbl.lower() or not lbl else lbl)
    if p.get("isKosher"):
        certs.append("Kosher")
    if p.get("isSustainableChoice"):
        certs.append("Sustainable choice (Systembolaget)")
    # de-dup while preserving order
    seen, out = set(), []
    for c in certs:
        if c.lower() not in seen:
            seen.add(c.lower()); out.append(c)
    return out


def parse_sugar(p):
    """sugarContentGramPer100ml -> g/l (public analytical figure Systembolaget prints)."""
    v = p.get("sugarContentGramPer100ml")
    try:
        return round(float(v) * 10, 1) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def match_vmp(producer, name, vmp):
    if vmp is None:
        return None
    pTok = [t for t in N(producer).split() if len(t) >= 4]
    nTok = [t for t in N(name).split() if len(t) >= 4]
    for pid, hay in vmp:
        p = sum(t in hay for t in pTok)
        n = sum(t in hay for t in nTok)
        if (p >= 1 and n >= 1) or (not pTok and n >= 2) or (not nTok and p >= 2):
            return pid
    return None


def representation(producer, name, supplier, vmp):
    varenr = match_vmp(producer, name, vmp)
    if varenr:
        return "represented", f"listed in VMP catalog (varenr {varenr})"
    if any(t in N(supplier) for t in PAN_NORDIC):
        return "pan_nordic", f"Swedish supplier '{supplier}' is pan-Nordic — likely reachable in NO"
    via = supplier or "unknown supplier"
    if vmp is None:
        # No catalog cross-check was run — don't assert "unrepresented", only that it's a
        # candidate for import whose VMP status is pending the live catalog check.
        return "open", f"candidate for import — VMP catalog check pending (in SE via {via})"
    return "open", f"unrepresented in NO — open for import (in SE via {via})"


def to_record(p, idx, vmp):
    producer = str(p.get("producerName") or "").strip()
    name = " ".join(x for x in [str(p.get("productNameBold") or "").strip(),
                                str(p.get("productNameThin") or "").strip()] if x)
    if not producer and not name:
        return None
    supplier = str(p.get("supplierName") or "").strip()
    status, rep_no = representation(producer, name, supplier, vmp)
    vintage = p.get("vintage")
    se_vintage = int(vintage) if str(vintage or "").isdigit() and 1900 < int(vintage) < 2100 else None
    # A lead commits NO vintage: the SE-listed year only proves the wine exists, it is
    # not a bid offer, and tenders are forward-looking. Keep it for display (se_vintage),
    # but leave vintages_available empty so vintage clauses read "unknown", not "fail".
    certs = parse_certs(p)
    sugar = parse_sugar(p)
    url = f"https://www.systembolaget.se/produkt/{p.get('productId', '')}"
    src = "Systembolaget open data"
    pub = lambda note: {"tier": "public", "note": f"{note} — {src}", "source": url}
    unk = lambda note: {"tier": "unknown", "note": note}
    return {
        "id": f"seedSE{idx:05d}",
        "producer": producer, "name": name,
        "country": str(p.get("country") or "").strip(),
        "region": " / ".join(x for x in [str(p.get("originLevel1") or "").strip(),
                                         str(p.get("originLevel2") or "").strip()] if x),
        "appellation": str(p.get("originLevel2") or p.get("originLevel1") or "").strip(),
        "grapes": parse_grapes(p),
        "method": "traditional" if color_of(p) == "sparkling" else None,
        "vintages_available": [],        # a lead commits no vintage — see se_vintage
        "se_vintage": se_vintage,        # year of the SE-listed bottle (reference only)
        "abv": p.get("alcoholPercentage"),
        "sugar_g_l": sugar, "wood": None, "certs": certs, "cert_on_label": bool(certs),
        "vines_age": None, "maceration_days": None,
        "volume_bottles": None,          # committed volume — producer only
        "fob_eur": None,                 # ex-cellar — producer only
        "retail_sek": p.get("price"),
        "color": color_of(p),
        "packaging": {"type": None, "weight_g": None},
        "se_supplier": supplier,
        "representation": {"NO": rep_no, "SE": f"listed (supplier: {supplier})" if supplier else "listed", "FI": "unknown"},
        "no_gap": status,                # represented | pan_nordic | open
        "pending_claim": True,
        "source": f"seed: Systembolaget (open data) — {url}",
        "audit": {"created_by": "seed:Systembolaget (open data)", "created_at": TODAY + "T00:00",
                  "updated_by": "seed:Systembolaget (open data)", "updated_at": TODAY + "T00:00",
                  "note": "Monopoly-proven (listed in SE), UNVERIFIED for NO purposes, pending producer claim. "
                          "FOB, committed volume and exact grape % to be confirmed by the producer."},
        "verify": {
            "producer": pub("stated in Systembolaget"), "name": pub("stated in Systembolaget"),
            "country": pub("stated in Systembolaget"), "region": pub("stated in Systembolaget"),
            "grapes": pub("varieties from Systembolaget; exact % to be confirmed by producer"),
            "abv": pub("stated in Systembolaget"),
            "certs": (pub("certification flags published by Systembolaget") if certs
                      else unk("no certification recorded in the Systembolaget feed")),
            "sugar_g_l": (pub("residual sugar published by Systembolaget") if sugar is not None
                          else unk("not published; to be confirmed by producer / analysis")),
            "representation": {"tier": "verified" if vmp is not None else "unknown",
                               "note": f"NO gap = {status}, derived from the VMP catalog index + pan-Nordic filter"},
            "fob_eur": unk("ex-cellar price to be supplied by the producer"),
            "volume_bottles": unk("committed volume to be supplied by the producer"),
        },
    }


def load_vmp_index(path):
    if not path or not os.path.exists(path):
        return None
    d = json.load(open(path, encoding="utf-8"))
    return [(p.get("productId"), N(p.get("name"))) for p in d.get("products", [])]


def load_rows(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, list):
        return d
    return d.get("products") or d.get("articles") or d.get("assortment") or d.get("wines") or []


def main():
    ap = argparse.ArgumentParser(description="Seed the supply side from Systembolaget's open assortment.")
    ap.add_argument("--file", required=True, help="Systembolaget assortment.json (from the open mirror)")
    ap.add_argument("--vmp-index", default="vmp_catalog_index.json", help="Vinmonopolet index for the NO gap")
    ap.add_argument("--out", default="seed_se.json")
    args = ap.parse_args()

    vmp = load_vmp_index(args.vmp_index)
    rows = [p for p in load_rows(args.file) if is_wine(p)]
    recs = [r for r in (to_record(p, i + 1, vmp) for i, p in enumerate(rows)) if r]
    by = collections.Counter(r["no_gap"] for r in recs)
    json.dump({"generated": TODAY, "source": "Systembolaget open data",
               "wines": recs}, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(recs)} SE wines -> {args.out}")
    print(f"  NO gap: open={by['open']}  pan_nordic={by['pan_nordic']}  represented={by['represented']}"
          f"{'   (VMP index not loaded — gap unresolved)' if vmp is None else ''}")


if __name__ == "__main__":
    main()
