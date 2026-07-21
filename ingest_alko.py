"""
ingest_alko.py — seed the producer/supply side from Finland's monopoly (Alko).

The Finnish mirror of ingest_systembolaget.py. Alko publishes two open feeds:

  1. The price list ("hinnasto") — rich product data: producer, country, region,
     grapes, ABV, sugar, vintage, price, type. No importer column.
  2. A separate "suppliers and importers" list — name, product code, supplier and
     IMPORTER for every product in the general selection (updated three times a year).

Joining them on the product code gives product specs + the Finnish importer, so the
same importer-level gap scoring applies as for Sweden:
  - represented : the wine/producer is already in the Vinmonopolet (NO) catalog
  - pan_nordic  : its Finnish importer is a pan-Nordic group -> already reachable in NO
                  (note: Anora/Altia is FINNISH-origin, so this matters most for FI)
  - open        : neither -> genuine introduction opportunity for a NO importer

A wine listed in Alko but absent from Vinmonopolet is a monopoly-proven producer
unrepresented in Norway. Seeded records are UNVERIFIED, pending producer claim;
producer-only fields (FOB, committed volume, exact grape %) are left blank.

Alko columns vary by export and language (FI/EN); this maps by alias, tab- or
semicolon- or comma-delimited, .xlsx or text. Point --file at the price list and
--importers at the supplier/importer list.

Run: python3 ingest_alko.py --file alko_hinnasto.xlsx --importers alko_suppliers.xlsx \
            --vmp-index vmp_catalog_index.json --out seed_fi.json
Sources: alko.fi/en/alko-inc/for-suppliers (price list + supplier/importer list).
"""
import os, sys, json, re, argparse, datetime, collections

TODAY = datetime.date.today().isoformat()

# Pan-Nordic groups that already cover Norway. Altia is the old Finnish state
# company, now part of Anora — so pan-Nordic reach is especially likely from FI.
PAN_NORDIC = ["anora", "altia", "arcus", "globus", "viinitie"]

# Alko column aliases (Finnish / English) -> canonical field. Lower-cased, loose.
ALIASES = {
    "code":     ["numero", "number", "tuotenumero", "product code", "product number", "id"],
    "name":     ["nimi", "name", "product name", "tuote"],
    "producer": ["valmistaja", "producer", "manufacturer", "tuottaja"],
    "importer": ["maahantuoja", "importer", "tavarantoimittaja", "supplier", "toimittaja"],
    "country":  ["valmistusmaa", "country", "maa", "country of origin"],
    "region":   ["alue", "region", "area", "district"],
    "vintage":  ["vuosikerta", "vintage", "year"],
    "grapes":   ["rypaleet", "rypäleet", "grapes", "grape", "variety", "varieties"],
    "abv":      ["alkoholi", "alcohol", "alcohol %", "abv", "alkoholiprosentti", "alko %", "alko-%"],
    "sugar":    ["sokeri", "sugar", "sugar g/l", "sokeri g/l", "residual sugar"],
    "price":    ["hinta", "price", "hinta eur"],
    "type":     ["tyyppi", "type", "category", "luonnehdinta"],
    "subtype":  ["alatyyppi", "subtype", "erityisryhma", "erityisryhmä"],
    "ethical":  ["eettinen", "ethical", "reilu", "fairtrade", "eettisyys"],
    "organic":  ["luomu", "organic", "eko"],
}


def N(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()
                  .replace("ø", "o").replace("æ", "ae").replace("å", "a")
                  .replace("ö", "o").replace("ä", "a").replace("ü", "u"))


def norm_keys(row):
    out, low = {}, {str(k).strip().lower(): v for k, v in row.items()}
    for field, names in ALIASES.items():
        for n in names:
            for k, v in low.items():
                if k == n or k.startswith(n):
                    if str(v).strip() != "":
                        out[field] = v
                    break
            if field in out:
                break
    return out


COLOR = [("puna", "red"), ("red", "red"), ("rott", "red"),
         ("valko", "white"), ("white", "white"), ("vit", "white"),
         ("rosee", "rose"), ("rose", "rose"), ("ros", "rose"),
         ("kuohu", "sparkling"), ("sparkling", "sparkling"), ("samppanja", "sparkling"),
         ("vahv", "fortified"), ("fortified", "fortified")]


def color_of(r):
    t = N(str(r.get("type") or "") + " " + str(r.get("subtype") or ""))
    for key, col in COLOR:
        if key in t:
            return col
    return ""


def is_wine(r):
    t = N(str(r.get("type") or "") + " " + str(r.get("subtype") or ""))
    if re.search(r"olut|beer|siideri|cider|vak|spirit|viski|whisky|gin|vodka|konjakki|rommi|liker|likor", t):
        return False
    return bool(re.search(r"viini|wine|puna|valko|rosee|kuohu|samppanja|vahva", t)) or color_of(r) != ""


def parse_grapes(v):
    out = {}
    for name in re.split(r"[;,/]| ja | and ", str(v or "")):
        name = name.strip()
        if name and not name.isdigit():
            out[name.lower()] = 0  # variety known; exact % pending producer
    return out


def parse_num(v):
    if v in (None, ""):
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v))
    return float(m.group(0).replace(",", ".")) if m else None


def parse_certs(r):
    certs = []
    if str(r.get("organic") or "").strip().lower() in ("kyllä", "yes", "1", "true", "luomu", "x") or \
       "luomu" in N(str(r.get("organic") or "")):
        certs.append("Organic")
    eth = N(str(r.get("ethical") or ""))
    if "reilu" in eth or "fair" in eth:
        certs.append("Fairtrade")
    return certs


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


def representation(producer, name, importer, vmp):
    varenr = match_vmp(producer, name, vmp)
    if varenr:
        return "represented", f"listed in VMP catalog (varenr {varenr})"
    if any(t in N(importer) for t in PAN_NORDIC):
        return "pan_nordic", f"Finnish importer '{importer}' is pan-Nordic — likely reachable in NO"
    via = importer or "unknown importer"
    if vmp is None:
        return "open", f"candidate for import — VMP catalog check pending (in FI via {via})"
    return "open", f"unrepresented in NO — open for import (in FI via {via})"


def to_record(r, idx, vmp):
    producer = str(r.get("producer") or "").strip()
    name = str(r.get("name") or "").strip()
    if not producer and not name:
        return None
    importer = str(r.get("importer") or "").strip()
    status, rep_no = representation(producer, name, importer, vmp)
    se_vintage = None  # FI stock year, reference only (a lead commits no vintage)
    vt = parse_num(r.get("vintage"))
    if vt and 1900 < vt < 2100:
        se_vintage = int(vt)
    certs = parse_certs(r)
    sugar = parse_num(r.get("sugar"))
    url = "https://www.alko.fi/en"
    src = "Alko open data"
    pub = lambda note: {"tier": "public", "note": f"{note} — {src}", "source": url}
    unk = lambda note: {"tier": "unknown", "note": note}
    return {
        "id": f"seedFI{idx:05d}",
        "producer": producer, "name": name,
        "country": str(r.get("country") or "").strip(),
        "region": str(r.get("region") or "").strip(),
        "appellation": str(r.get("region") or "").strip(),
        "grapes": parse_grapes(r.get("grapes")),
        "method": "traditional" if color_of(r) == "sparkling" else None,
        "vintages_available": [],           # a lead commits no vintage
        "se_vintage": se_vintage,           # FI-listed bottle year (reference only)
        "abv": parse_num(r.get("abv")),
        "sugar_g_l": sugar, "wood": None, "certs": certs, "cert_on_label": bool(certs),
        "vines_age": None, "maceration_days": None,
        "volume_bottles": None,             # producer only
        "fob_eur": None,                    # producer only
        "retail_eur": parse_num(r.get("price")),
        "color": color_of(r),
        "packaging": {"type": None, "weight_g": None},
        "fi_importer": importer,
        "representation": {"NO": rep_no, "SE": "unknown",
                           "FI": f"listed (importer: {importer})" if importer else "listed"},
        "no_gap": status,
        "pending_claim": True,
        "source": f"seed: Alko (open data) — {url}",
        "audit": {"created_by": "seed:Alko (open data)", "created_at": TODAY + "T00:00",
                  "updated_by": "seed:Alko (open data)", "updated_at": TODAY + "T00:00",
                  "note": "Monopoly-proven (listed in FI), UNVERIFIED for NO purposes, pending producer claim. "
                          "FOB, committed volume and exact grape % to be confirmed by the producer."},
        "verify": {
            "producer": pub("stated in Alko"), "name": pub("stated in Alko"),
            "country": pub("stated in Alko"), "region": pub("stated in Alko"),
            "grapes": pub("varieties from Alko; exact % to be confirmed by producer"),
            "abv": pub("stated in Alko"),
            "certs": (pub("certification flags published by Alko") if certs
                      else unk("no certification recorded in the Alko feed")),
            "sugar_g_l": (pub("residual sugar published by Alko") if sugar is not None
                          else unk("not published; to be confirmed by producer / analysis")),
            "representation": {"tier": "verified" if vmp is not None else "unknown",
                               "note": f"NO gap = {status}, derived from the VMP catalog index + pan-Nordic filter"},
            "fob_eur": unk("ex-cellar price to be supplied by the producer"),
            "volume_bottles": unk("committed volume to be supplied by the producer"),
        },
    }


def load_table(path):
    """Read .xlsx (via openpyxl if available) or a delimited text/CSV file into dict rows."""
    if not path:
        return []
    if path.lower().endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl
        except ImportError:
            sys.exit("openpyxl needed for .xlsx (pip install openpyxl), or export the price list as CSV/TSV.")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        head = [str(h or "").strip() for h in rows[0]]
        return [dict(zip(head, r)) for r in rows[1:]]
    raw = open(path, encoding="utf-8-sig", errors="replace").read()
    if path.lower().endswith(".json"):
        d = json.loads(raw)
        return d if isinstance(d, list) else (d.get("products") or d.get("rows") or [])
    # sniff delimiter
    import csv, io
    sample = raw[:5000]
    delim = "\t" if sample.count("\t") >= sample.count(";") and sample.count("\t") >= sample.count(",") \
        else (";" if sample.count(";") >= sample.count(",") else ",")
    return list(csv.DictReader(io.StringIO(raw), delimiter=delim))


def build_importer_index(path):
    """Map product code -> importer from the supplier/importer list."""
    idx = {}
    for row in load_table(path):
        r = norm_keys(row)
        code = str(r.get("code") or "").strip()
        imp = str(r.get("importer") or "").strip()
        if code and imp:
            idx[code] = imp
    return idx


def load_vmp_index(path):
    if not path or not os.path.exists(path):
        return None
    d = json.load(open(path, encoding="utf-8"))
    return [(p.get("productId"), N(p.get("name"))) for p in d.get("products", [])]


def main():
    ap = argparse.ArgumentParser(description="Seed the supply side from Alko's open data (Finland).")
    ap.add_argument("--file", required=True, help="Alko price list (xlsx / csv / tsv)")
    ap.add_argument("--importers", help="Alko supplier+importer list (joined on product code)")
    ap.add_argument("--vmp-index", default="vmp_catalog_index.json", help="Vinmonopolet index for the NO gap")
    ap.add_argument("--out", default="seed_fi.json")
    args = ap.parse_args()

    vmp = load_vmp_index(args.vmp_index)
    imp_idx = build_importer_index(args.importers) if args.importers else {}

    recs = []
    for i, row in enumerate(load_table(args.file)):
        r = norm_keys(row)
        if not is_wine(r):
            continue
        # graft importer from the second feed if not present on the price-list row
        code = str(r.get("code") or "").strip()
        if not r.get("importer") and code in imp_idx:
            r["importer"] = imp_idx[code]
        rec = to_record(r, len(recs) + 1, vmp)
        if rec:
            recs.append(rec)

    by = collections.Counter(r["no_gap"] for r in recs)
    json.dump({"generated": TODAY, "source": "Alko open data", "wines": recs},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(recs)} FI wines -> {args.out}")
    print(f"  NO gap: open={by['open']}  pan_nordic={by['pan_nordic']}  represented={by['represented']}"
          f"{'   (VMP index not loaded — gap unresolved)' if vmp is None else ''}"
          f"{'' if imp_idx else '   (no importer list — pan_nordic unresolved)'}")


if __name__ == "__main__":
    main()
