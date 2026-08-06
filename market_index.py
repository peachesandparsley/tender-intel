"""
Aggregate launch_history.json into a COMPACT market_index.json the app can embed.

The raw history is 5+ MB (12k products) — too big for the self-contained SPA. This distils it into
benchmarks a producer/importer actually asks for:
  - what comparable wines really retailed at (price quartiles), by origin x style and x classification
  - typical volume and vintages, the top producers, and (where known) the importers behind them
  - the importer landscape and the 6-year price/volume trend
Everything is bucketed with a minimum sample so nothing is a claim built on one row.

Usage:  python3 market_index.py            # reads launch_history.json -> market_index.json
"""
import json, os, re, statistics as st
from collections import Counter, defaultdict

MIN_N = 5            # never publish a benchmark from fewer than this many real launches
TOPK = 6            # top producers / importers per bucket

# The launch lists are Norwegian; the app (tender specs, map, match form) speaks English. Canonicalise
# country to English at index time so a benchmark lookup by the form's country name ("France") hits, and
# fold the spelling variants Vinmonopolet uses across six years into one bucket (England/UK/Storbritannia,
# Skottland/Scottland, Irland/Ireland) so a country's real sample isn't split three ways.
COUNTRY_CANON = {
    "frankrike": "France", "tyskland": "Germany", "italia": "Italy", "spania": "Spain",
    "hellas": "Greece", "belgia": "Belgium", "nederland": "Netherlands", "norge": "Norway",
    "sverige": "Sweden", "danmark": "Denmark", "island": "Iceland", "portugal": "Portugal",
    "østerrike": "Austria", "sveits": "Switzerland", "ungarn": "Hungary", "kroatia": "Croatia",
    "libanon": "Lebanon", "polen": "Poland", "tsjekkia": "Czech Republic", "japan": "Japan",
    "mexico": "Mexico", "canada": "Canada", "australia": "Australia", "usa": "USA",
    "jamaica": "Jamaica", "sør-afrika": "South Africa", "chile": "Chile", "argentina": "Argentina",
    "new zealand": "New Zealand", "new zealand ": "New Zealand", "romania": "Romania",
    "skottland": "Scotland", "scottland": "Scotland", "scotland": "Scotland",
    "england": "Great Britain", "uk": "Great Britain", "storbritannia": "Great Britain",
    "great britain": "Great Britain", "irland": "Ireland", "ireland": "Ireland",
}


def canon_country(c):
    if not c:
        return c
    return COUNTRY_CANON.get(c.strip().lower(), c.strip())


def q(xs, p):
    xs = sorted(x for x in xs if x)
    if not xs:
        return None
    i = min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))
    return round(xs[i])


def top(names, k=TOPK):
    return [{"name": n, "n": c} for n, c in Counter(x for x in names if x).most_common(k)]


def bucket(records):
    prices = [r["price"] for r in records if r["price"]]
    vols = [r["qty"] for r in records if r["qty"]]
    vints = [r["vintage"] for r in records if r["vintage"]]
    return {
        "n": len(records),
        "p25": q(prices, .25), "med": q(prices, .5), "p75": q(prices, .75),
        "volMed": q(vols, .5),
        "vintages": [min(vints), max(vints)] if vints else None,
        "producers": top(r["producer"] for r in records),
        "importers": top(r["importer"] for r in records if r["importer"]),
    }


def main():
    R = json.load(open("launch_history.json", encoding="utf-8"))
    for r in R:
        r["country"] = canon_country(r.get("country"))
    years = sorted({r["period"][:4] for r in R})

    by_ct = defaultdict(list)          # (country, type)
    by_ctc = defaultdict(list)         # (country, type, classification)
    by_dt = defaultdict(list)          # (district, type)  — appellation-level
    for r in R:
        c, t = r.get("country"), r.get("type")
        if c and t:
            by_ct[(c, t)].append(r)
            if r.get("classification"):
                by_ctc[(c, t, r["classification"])].append(r)
        if r.get("district") and t:
            by_dt[(r["district"], t)].append(r)

    def dump(d, keys):
        out = []
        for k, recs in d.items():
            if len(recs) < MIN_N:
                continue
            b = bucket(recs)
            b.update(dict(zip(keys, k)))
            out.append(b)
        return sorted(out, key=lambda b: -b["n"])

    # importer landscape (which origins/styles each brings in, how many)
    imp = defaultdict(list)
    for r in R:
        if r.get("importer"):
            imp[r["importer"]].append(r)
    importers = sorted(({
        "name": name, "n": len(recs),
        "origins": [x for x, _ in Counter(r["country"] for r in recs if r["country"]).most_common(4)],
        "styles": [x for x, _ in Counter(r["type"] for r in recs if r["type"]).most_common(4)],
        "medPrice": q([r["price"] for r in recs], .5),
    } for name, recs in imp.items() if len(recs) >= 3), key=lambda x: -x["n"])[:120]

    # 6-year trend
    trend = []
    for y in years:
        ys = [r for r in R if r["period"][:4] == y]
        trend.append({"y": int(y), "n": len(ys), "med": q([r["price"] for r in ys], .5),
                      "vol": sum(r["qty"] for r in ys if r["qty"])})

    idx = {
        "meta": {"n": len(R), "years": [int(y) for y in years],
                 "producers": len({r["producer"] for r in R if r["producer"]}),
                 "importers_known": len(imp),
                 "source": "Vinmonopolet launch lists (actuals), " + f"{years[0]}–{years[-1]}"},
        "byCountryType": dump(by_ct, ("country", "type")),
        "byCountryTypeClass": dump(by_ctc, ("country", "type", "classification")),
        "byDistrictType": dump(by_dt, ("district", "type")),
        "importers": importers,
        "trend": trend,
    }
    json.dump(idx, open("market_index.json", "w", encoding="utf-8"), ensure_ascii=False)
    kb = os.path.getsize("market_index.json") // 1024
    print(f"market_index.json written ({kb} KB): "
          f"{len(idx['byCountryType'])} country×style · {len(idx['byCountryTypeClass'])} ×class · "
          f"{len(idx['byDistrictType'])} district×style · {len(importers)} importers · {len(trend)} years")


if __name__ == "__main__":
    main()
