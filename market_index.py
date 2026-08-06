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


# Importer names carry inconsistent corporate suffixes across six years of lists ("Nafstad" vs
# "Nafstad AS", "Moestue Grape Selections" vs "…AS"), splitting one real importer into two or three
# buckets. Strip the trailing corporate form (AS/ASA/A-S/AB/…) — but NOT geographic words like
# "Norge"/"Norway", which distinguish a real Norwegian subsidiary — so a firm's true book is whole.
_IMP_SUFFIX = re.compile(r"[\s,]+(?:a/s|as|asa|ab|ans|da|sa|ltd|inc|co)\.?$", re.I)


def canon_importer(s):
    if not s:
        return s
    s = s.strip()
    prev = None
    while prev != s:                       # peel repeated suffixes, e.g. "… Wines AS AB"
        prev, s = s, _IMP_SUFFIX.sub("", s).strip()
    return s


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
        # importer is recorded on only a minority of rows (mostly the spirits lists) — carry HOW MANY
        # so the UI can say "who's named on impKnown of n launches", not imply it's the whole field.
        "impKnown": sum(1 for r in records if r["importer"]),
        "p25": q(prices, .25), "med": q(prices, .5), "p75": q(prices, .75),
        "volMed": q(vols, .5),
        "vintages": [min(vints), max(vints)] if vints else None,
        "producers": top(r["producer"] for r in records),
        "importers": top(r["importer"] for r in records if r["importer"]),
    }


def counted(names, k=TOPK):
    return [{"name": n, "n": c} for n, c in Counter(x for x in names if x).most_common(k)]


def _detail(name, recs, extra_key, extra_field):
    """Shared shape for an importer OR a producer: their whole book from the history."""
    prices = [r["price"] for r in recs if r["price"]]
    vols = [r["qty"] for r in recs if r["qty"]]
    yrs = [int(r["period"][:4]) for r in recs if r["period"][:4].isdigit()]
    d = {
        "name": name, "n": len(recs),
        "p25": q(prices, .25), "med": q(prices, .5), "p75": q(prices, .75),
        "volMed": q(vols, .5),
        "origins": counted((r["country"] for r in recs), 6),
        "styles": counted((r["type"] for r in recs), 6),
        "districts": counted((r["district"] for r in recs), 6),
        "years": [min(yrs), max(yrs)] if yrs else None,
    }
    d[extra_key] = counted((r[extra_field] for r in recs if r[extra_field]), 6)
    return d


def importer_detail(name, recs):
    return _detail(name, recs, "producers", "producer")   # which producers this importer brings in


def producer_detail(name, recs):
    d = _detail(name, recs, "importers", "importer")       # which importers have carried this producer
    d["impKnown"] = sum(1 for r in recs if r["importer"])  # honest: importer known on how many of their rows
    return d


def main():
    R = json.load(open("launch_history.json", encoding="utf-8"))
    for r in R:
        r["country"] = canon_country(r.get("country"))
        r["importer"] = canon_importer(r.get("importer"))
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

    # importer landscape (each importer's whole book — origins/styles/districts, price tier, volume, span)
    imp = defaultdict(list)
    for r in R:
        if r.get("importer"):
            imp[r["importer"]].append(r)
    importers = sorted((importer_detail(name, recs) for name, recs in imp.items() if len(recs) >= 3),
                       key=lambda x: -x["n"])[:150]

    # producer track record (each producer's whole book — origins/styles/districts, price tier, volume,
    # span, and which importers carried them). Producer is recorded on ~100% of rows, so this is the most
    # complete lens in the dataset — a producer can look up their own real Vinmonopolet launch history.
    prod = defaultdict(list)
    for r in R:
        if r.get("producer"):
            prod[r["producer"]].append(r)
    producers = sorted((producer_detail(name, recs) for name, recs in prod.items() if len(recs) >= 3),
                       key=lambda x: -x["n"])[:300]

    # 6-year trend
    trend = []
    for y in years:
        ys = [r for r in R if r["period"][:4] == y]
        trend.append({"y": int(y), "n": len(ys), "med": q([r["price"] for r in ys], .5),
                      "vol": sum(r["qty"] for r in ys if r["qty"])})

    imp_cov = sum(1 for r in R if r.get("importer"))
    idx = {
        "meta": {"n": len(R), "years": [int(y) for y in years],
                 "producers": len({r["producer"] for r in R if r["producer"]}),
                 "importers_known": len(imp),
                 # honest coverage: importer recorded on this many of n rows (mostly the spirits lists)
                 "impCoverage": round(imp_cov / len(R), 3), "impCoverageN": imp_cov,
                 "source": "Vinmonopolet launch lists (actuals), " + f"{years[0]}–{years[-1]}"},
        "byCountryType": dump(by_ct, ("country", "type")),
        "byCountryTypeClass": dump(by_ctc, ("country", "type", "classification")),
        "byDistrictType": dump(by_dt, ("district", "type")),
        "importers": importers,
        "producers": producers,
        "trend": trend,
    }
    json.dump(idx, open("market_index.json", "w", encoding="utf-8"), ensure_ascii=False)
    kb = os.path.getsize("market_index.json") // 1024
    print(f"market_index.json written ({kb} KB): "
          f"{len(idx['byCountryType'])} country×style · {len(idx['byCountryTypeClass'])} ×class · "
          f"{len(idx['byDistrictType'])} district×style · {len(importers)} importers · {len(producers)} producers · "
          f"{len(trend)} years · importer coverage {int(100 * idx['meta']['impCoverage'])}%")


if __name__ == "__main__":
    main()
