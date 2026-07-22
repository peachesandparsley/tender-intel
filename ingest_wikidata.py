"""
ingest_wikidata.py — seed the producer spine, one country at a time, from Wikidata.

Why Wikidata first: the national promotion bodies (WoSA, Austrian Wine, NZ Winegrowers…)
publish member directories, but each is a differently-structured, often JS-rendered,
sometimes WAF-protected site — and the EU database right makes vacuuming a whole directory
the legal risk zone. Wikidata sidesteps all of that: it is CC0 (public domain), machine-
readable via SPARQL, and already holds wineries by country with their region and official
website. So we take the *producer spine* from Wikidata (identity + region + website + the
Vinmonopolet-dedup), then enrich wine-level detail (grapes, certs, vintages) later from each
producer's own site — the legitimate "identify here, pull detail from the producer" pattern.

What a record gets: producer, country, region, website. NO wine-level grape/cert data yet
(Wikidata rarely has it per winery) and NONE of the tender-critical producer-only numbers
(FOB, volume) — those stay blank, exactly like every other seeder. Representation in NO is
DERIVED from the Vinmonopolet catalog index (dedup), never assumed.

Network note: query.wikidata.org must be reachable, so run this on the GitHub Actions runner
(the refresh-producers workflow) or your own machine — the repo's editing sandbox is offline.

Run:  python3 ingest_wikidata.py --country ZA --max 400 --vmp-index vmp_catalog_index.json
      python3 ingest_wikidata.py --country AT --out seed_wd_at.json
      python3 ingest_wikidata.py --selftest         # offline: parse a fixture, no network
"""
import os, sys, json, argparse, urllib.parse, urllib.request, datetime

# Reuse the tested, source-independent record builder + VMP dedup from scrape_producers.py.
from scrape_producers import to_record, load_vmp_index

TODAY = datetime.date.today().isoformat()
UA = "tender-intel wikidata-seed/1.0 (respectful; CC0 data; +set-your-contact)"
ENDPOINT = "https://query.wikidata.org/sparql"

# ISO-2 -> (Wikidata country QID, display name). Extend as we add countries.
COUNTRIES = {
    "FR": ("Q142", "France"), "IT": ("Q38", "Italy"), "DE": ("Q183", "Germany"),
    "ES": ("Q29", "Spain"), "AT": ("Q40", "Austria"), "PT": ("Q45", "Portugal"),
    "ZA": ("Q258", "South Africa"), "AU": ("Q408", "Australia"), "NZ": ("Q664", "New Zealand"),
    "CL": ("Q298", "Chile"), "US": ("Q30", "United States"), "AR": ("Q414", "Argentina"),
    "GR": ("Q41", "Greece"), "HU": ("Q28", "Hungary"), "GE": ("Q230", "Georgia"),
}

# A winery is `instance of / subclass of winery (Q1414722)`, OR any entity whose product is
# wine (P1056 = wine, Q282) — the UNION hedges against items typed only one way. Region via
# "located in the administrative territorial entity" (P131); website via P856.
QUERY = """
SELECT DISTINCT ?item ?itemLabel ?regionLabel ?website WHERE {
  { ?item wdt:P31/wdt:P279* wd:Q1414722 . }
  UNION
  { ?item wdt:P1056 wd:Q282 . }
  ?item wdt:P17 wd:%(country)s .
  OPTIONAL { ?item wdt:P131 ?region . }
  OPTIONAL { ?item wdt:P856 ?website . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,%(lang)s". }
}
LIMIT %(limit)d
"""

LANG = {"FR": "fr", "IT": "it", "DE": "de", "ES": "es", "AT": "de", "PT": "pt",
        "ZA": "en", "AU": "en", "NZ": "en", "CL": "es", "US": "en", "AR": "es",
        "GR": "el", "HU": "hu", "GE": "ka"}


def fetch(country_qid, lang, limit):
    q = QUERY % {"country": country_qid, "lang": lang, "limit": limit}
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": q, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def rows_to_items(sparql_json):
    """Wikidata SPARQL JSON -> deduped {producer, region, url} items (one per winery)."""
    by_item = {}
    for b in sparql_json.get("results", {}).get("bindings", []):
        qid = b.get("item", {}).get("value", "")
        label = b.get("itemLabel", {}).get("value", "").strip()
        # skip rows whose label is just the bare Q-id (no English/local label exists)
        if not label or label.startswith("Q") and label[1:].isdigit():
            continue
        it = by_item.setdefault(qid, {"producer": label, "region": "", "url": ""})
        region = b.get("regionLabel", {}).get("value", "").strip()
        if region and not region.startswith("Q") and not it["region"]:
            it["region"] = region
        web = b.get("website", {}).get("value", "").strip()
        if web and not it["url"]:
            it["url"] = web
    return list(by_item.values())


def build(country_iso, sparql_json, vmp):
    src = {"country": COUNTRIES[country_iso][1],
           "body": "Wikidata (CC0)", "base": "https://www.wikidata.org"}
    items = rows_to_items(sparql_json)
    recs = []
    for i, it in enumerate(items):
        it.setdefault("url", src["base"])
        rec = to_record(it, src, i, vmp)
        if rec:
            rec["id"] = f"wd{country_iso}{i:05d}"
            recs.append(rec)
    return recs


FIXTURE = {"results": {"bindings": [
    {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "itemLabel": {"value": "Klein Constantia"},
     "regionLabel": {"value": "Constantia"}, "website": {"value": "https://www.kleinconstantia.com"}},
    {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "itemLabel": {"value": "Klein Constantia"},
     "regionLabel": {"value": "Western Cape"}},
    {"item": {"value": "http://www.wikidata.org/entity/Q2"}, "itemLabel": {"value": "Kanonkop Wine Estate"},
     "regionLabel": {"value": "Stellenbosch"}, "website": {"value": "https://www.kanonkop.co.za"}},
    {"item": {"value": "http://www.wikidata.org/entity/Q3"}, "itemLabel": {"value": "Q999999"}},  # unlabeled -> skipped
]}}


def selftest():
    items = rows_to_items(FIXTURE)
    assert len(items) == 2, f"expected 2 labelled wineries, got {len(items)}"
    kc = next(i for i in items if i["producer"] == "Klein Constantia")
    assert kc["region"] == "Constantia", kc          # first non-Q region wins
    assert kc["url"].endswith("kleinconstantia.com"), kc
    recs = build("ZA", FIXTURE, None)
    assert len(recs) == 2 and recs[0]["country"] == "South Africa"
    assert recs[0]["fob_eur"] is None and recs[0]["volume_bottles"] is None   # never invented
    assert recs[0]["pending_claim"] is True
    print("selftest OK — parsing + record build + no-invented-fields all pass")


def main():
    ap = argparse.ArgumentParser(description="Seed producers for one country from Wikidata (CC0).")
    ap.add_argument("--country", help="ISO-2 code, e.g. ZA, AT, NZ, DE, FR")
    ap.add_argument("--max", type=int, default=600, help="row cap")
    ap.add_argument("--vmp-index", help="vmp_catalog_index.json for the NO dedup")
    ap.add_argument("--out", help="output file (default seed_wd_<cc>.json)")
    ap.add_argument("--selftest", action="store_true", help="offline fixture test, no network")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    cc = (args.country or "").upper()
    if cc not in COUNTRIES:
        sys.exit(f"--country must be one of: {', '.join(COUNTRIES)}")
    qid, name = COUNTRIES[cc]
    print(f"querying Wikidata for wineries in {name} ({qid})…")
    data = fetch(qid, LANG.get(cc, "en"), args.max)
    vmp = load_vmp_index(args.vmp_index)
    recs = build(cc, data, vmp)
    rep = sum(1 for r in recs if r["no_gap"] == "represented")
    out = args.out or f"seed_wd_{cc.lower()}.json"
    json.dump({"wines": recs}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  {len(recs)} producers -> {out}  ({rep} already in VMP, {len(recs) - rep} open/pending)")
    if not recs:
        print("  (0 rows — the winery QID/UNION may need adjusting for this country; check the query.)")


if __name__ == "__main__":
    main()
