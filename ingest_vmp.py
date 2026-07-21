"""
ingest_vmp.py — populate the wine database with TRUSTWORTHY data from
Vinmonopolet's own product catalog (the authoritative, public source).

Every field written by this script comes straight from Vinmonopolet, so records
are marked `verified` with a source and a check date. The numbers only the
producer holds — ex-cellar FOB, committed volume, grape percentages, tech-sheet
detail — are deliberately left blank and flagged `unknown`. They must come from
the producer upload, never guessed. That boundary is the whole point: nothing is
shown as verified unless it came from a real source.

Two ways to feed it (either works, pick what you have access to):

  A) Live API — register once for a free subscription key at
     https://api.vinmonopolet.no, then:
         export VMP_API_KEY=xxxxxxxx
         python3 ingest_vmp.py --api --out wines_verified.json

  B) Local export — download the assortment from the portal's Excel/PowerQuery
     workbooks (or any CSV/JSON carrying the documented product fields), then:
         python3 ingest_vmp.py --file assortment.json --out wines_verified.json

Records are keyed on the Vinmonopolet code (varenr): re-running refreshes each
record and advances `checked_at`, so a ✓ that ages past your freshness window
can fall back to ◦ in the app. This writes a separate file by default and does
NOT clobber the demo wines.json unless you explicitly pass --out wines.json.

Field mapping (VMP product object -> our wine record) is per the documented
product schema: code, name, mainProducer, mainCountry, district/subDistrict,
mainCategory/mainSubCategory, abv, containerSize/Type, vintage, price,
wholesaler/distributor, and the sensory axes fullness/freshness/tannins.
"""
import os, sys, json, argparse, datetime, re, urllib.request

API_BASE = os.environ.get("VMP_API_BASE", "https://apis.vinmonopolet.no")
API_KEY = os.environ.get("VMP_API_KEY", "")
# Confirm the exact products endpoint/params in the portal after you subscribe;
# this is the commonly-used details path. The --file route needs no endpoint.
API_PATH = os.environ.get("VMP_API_PATH", "/products/v0/details-normal")
TODAY = datetime.date.today().isoformat()


def g(product, *keys):
    """First non-empty value among the given field-name aliases."""
    for k in keys:
        val = product.get(k)
        if val not in (None, ""):
            return val
    return None


def map_color(product):
    cat = " ".join(str(v) for v in [g(product, "mainCategory"), g(product, "mainSubCategory"),
                                     g(product, "productType")] if v).lower()
    method = None
    if "musserende" in cat or "sparkling" in cat:
        color = "sparkling rose" if ("rosé" in cat or "rose" in cat) else "sparkling white"
        method = "traditional" if any(x in cat for x in ("champagne", "cava", "cap classique")) else "sparkling"
    elif "rosé" in cat or "rosevin" in cat:
        color = "rose"
    elif "hvit" in cat or "white" in cat:
        color = "white"
    elif "rød" in cat or "rod" in cat or "red" in cat:
        color = "red"
    elif "sterkvin" in cat or "fortified" in cat:
        color = "fortified"
    else:
        color = ""
    return color, method


def parse_litres(container):
    m = re.search(r"([\d.,]+)", str(container or ""))
    if not m:
        return None
    val = float(m.group(1).replace(",", "."))
    return val / 100 if val > 10 else val  # handle "75 cl" vs "0.75 l"


def to_wine(product, idx):
    code = str(g(product, "code", "varenummer", "productId") or "").strip()
    color, method = map_color(product)
    vintage = g(product, "vintage")
    vintages = [int(vintage)] if str(vintage or "").isdigit() and int(vintage) > 1900 else []
    F, Fr, T = g(product, "fullness"), g(product, "freshness"), g(product, "tannins")
    prof = {"fylde": F, "friskhet": Fr, "garvestoffer": T} if any(v not in (None, "") for v in (F, Fr, T)) else None
    wholesaler = str(g(product, "wholesaler", "distributor") or "").strip()
    url = g(product, "url") or f"https://www.vinmonopolet.no/p/{code}"
    src = f"Vinmonopolet catalog (varenr {code})"
    ver = lambda note: {"tier": "verified", "note": f"{note} — {src}, {TODAY}", "source": url}
    unk = lambda note: {"tier": "unknown", "note": note}
    return {
        "id": f"vmp{code or idx}",
        "producer": str(g(product, "mainProducer") or "").strip(),
        "name": str(g(product, "name") or "").strip(),
        "country": str(g(product, "mainCountry") or "").strip(),
        "region": " / ".join(x for x in [str(g(product, "district") or "").strip(),
                                         str(g(product, "subDistrict") or "").strip()] if x),
        "appellation": "",
        "grapes": {},                    # producer/tech-sheet only
        "method": method,
        "vintages_available": vintages,
        "abv": g(product, "abv"),
        "sugar_g_l": g(product, "sugar", "sweetness_g_l"),
        "wood": None,
        "certs": [],
        "cert_on_label": False,
        "vines_age": None,
        "maceration_days": None,
        "volume_bottles": None,          # producer only (committed volume)
        "fob_eur": None,                 # producer only (ex-cellar price)
        "retail_nok": g(product, "price"),
        "profile": prof,
        "color": color,
        "packaging": {"type": g(product, "containerType"), "weight_g": None},
        "catalog_no": {"status": "listed", "product_id": code,
                       "checked_by": "Vinmonopolet catalog", "checked_at": TODAY,
                       "note": g(product, "name")},
        "representation": {"NO": f"importer: {wholesaler}" if wholesaler else "listed in VMP catalog",
                           "SE": "unknown", "FI": "unknown"},
        "source": src,
        "audit": {"created_by": "vmp-ingest", "created_at": TODAY + "T00:00",
                  "updated_by": "vmp-ingest", "updated_at": TODAY + "T00:00",
                  "note": "Verified fields from Vinmonopolet's catalog. FOB, volume and grape % must be confirmed by the producer."},
        "verify": {
            "producer": ver("stated in the catalog"), "name": ver("stated in the catalog"),
            "country": ver("stated in the catalog"), "region": ver("stated in the catalog"),
            "abv": ver("stated in the catalog"), "profile": ver("taste profile from the catalog"),
            "representation": ver("wholesaler stated in the catalog"),
            "fob_eur": unk("ex-cellar price must be supplied by the producer"),
            "volume_bottles": unk("available volume must be supplied by the producer"),
            "grapes": unk("grape % must be supplied by the producer / tech sheet"),
        },
    }


def fetch_api():
    if not API_KEY:
        sys.exit("Set VMP_API_KEY (free key from https://api.vinmonopolet.no), or use --file with a portal export.")
    products, start, page = [], 0, 100
    while True:
        url = f"{API_BASE}{API_PATH}?start={start}&maxResults={page}"
        req = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": API_KEY,
                                                   "Accept": "application/json"})
        batch = json.load(urllib.request.urlopen(req, timeout=60))
        items = batch if isinstance(batch, list) else (batch.get("products") or batch.get("results") or [])
        if not items:
            break
        products += items
        start += page
        print(f"  fetched {len(products)}…", file=sys.stderr)
        if len(items) < page:
            break
    return products


def load_file(path):
    raw = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        data = json.loads(raw)
        return data if isinstance(data, list) else (data.get("products") or data.get("results") or [])
    import csv, io
    return list(csv.DictReader(io.StringIO(raw)))


def main():
    ap = argparse.ArgumentParser(description="Populate the wine DB with verified Vinmonopolet catalog data.")
    ap.add_argument("--api", action="store_true", help="pull live from the VMP API (needs VMP_API_KEY)")
    ap.add_argument("--file", help="ingest a local export (JSON or CSV) from the portal instead")
    ap.add_argument("--out", default="wines_verified.json", help="output file (default keeps demo wines.json intact)")
    args = ap.parse_args()

    if args.api:
        products = fetch_api()
    elif args.file:
        products = load_file(args.file)
    else:
        ap.error("pass --api or --file")

    wines = [to_wine(p, i) for i, p in enumerate(products) if str(g(p, "code", "varenummer", "productId") or "").strip()]
    merged = {}
    if os.path.exists(args.out):
        for w in json.load(open(args.out, encoding="utf-8")).get("wines", []):
            merged[(w.get("catalog_no") or {}).get("product_id")] = w
    for w in wines:
        merged[w["catalog_no"]["product_id"]] = w
    out = {"wines": list(merged.values())}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(wines)} verified records written/merged -> {args.out} ({len(out['wines'])} total)")


if __name__ == "__main__":
    main()
