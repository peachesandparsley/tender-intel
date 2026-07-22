"""
make_seed_sample.py — curate a small, representative sample of supply-side leads
for the self-contained app.

The full seed files (seed_se.json / seed_fi.json / seed_producers.json) can hold
thousands of leads — too many to inline into index.html, and enough to make the
in-browser matcher (O(specs x wines)) sluggish. This picks a diverse, useful
subset:
  - opportunities first: no_gap == "open" (unrepresented in NO) before pan_nordic;
    "represented" wines are already on Vinmonopolet and are dropped (not a lead);
  - richer records first: has grapes AND/OR certs (they match more tender clauses
    and demo the value);
  - origin diversity: capped per country so one country can't dominate;
  - country names normalised to English so leads match the (English) tender specs.

Everything stays exactly as seeded: unverified, pending_claim, producer-only
fields blank. This only *selects and translates the origin label* — it invents
nothing.

Run: python3 make_seed_sample.py --in seed_se.json [seed_fi.json ...] \
             --per-country 22 --cap 240 --out seed_sample.json
"""
import json, argparse, collections

# Systembolaget/Alko print country in the local language; the tender specs (and
# wines.json) use English. Map so origins actually match. Extend as needed.
COUNTRY_EN = {
    "frankrike": "France", "ranska": "France",
    "italien": "Italy", "italia": "Italy",
    "spanien": "Spain", "espanja": "Spain",
    "tyskland": "Germany", "saksa": "Germany",
    "portugal": "Portugal", "portugali": "Portugal",
    "osterrike": "Austria", "österrike": "Austria", "itavalta": "Austria",
    "sydafrika": "South Africa", "etela-afrikka": "South Africa", "etelä-afrikka": "South Africa",
    "australien": "Australia", "australia": "Australia",
    "nya zeeland": "New Zealand", "uusi-seelanti": "New Zealand",
    "usa": "USA", "yhdysvallat": "USA",
    "chile": "Chile", "argentina": "Argentina", "arg": "Argentina",
    "grekland": "Greece", "kreikka": "Greece",
    "ungern": "Hungary", "unkari": "Hungary",
    "libanon": "Lebanon", "schweiz": "Switzerland", "sveitsi": "Switzerland",
    "sverige": "Sweden", "ruotsi": "Sweden", "suomi": "Finland", "finland": "Finland",
    "bulgarien": "Bulgaria", "slovenien": "Slovenia", "cypern": "Cyprus",
    "georgien": "Georgia", "kroatien": "Croatia", "rumanien": "Romania",
    "rumänien": "Romania", "israel": "Israel", "moldavien": "Moldova",
    "ukraina": "Ukraine", "nordmakedonien": "North Macedonia",
    "storbritannien": "United Kingdom", "tjeckien": "Czechia",
    "luxemburg": "Luxembourg", "armenien": "Armenia", "uruguay": "Uruguay",
    "libanon2": "Lebanon", "turkiet": "Türkiye", "brasilien": "Brazil",
}


def country_en(c):
    return COUNTRY_EN.get((c or "").strip().lower(), (c or "").strip())


def richness(w):
    return (1 if w.get("grapes") else 0) + (1 if w.get("certs") else 0) + \
           (1 if w.get("abv") else 0) + (1 if w.get("vintages_available") else 0)


GAP_RANK = {"open": 0, "pan_nordic": 1}  # "represented" excluded entirely


def main():
    ap = argparse.ArgumentParser(description="Curate a capped app sample from seed files.")
    ap.add_argument("--in", dest="inp", nargs="+", required=True, help="seed_*.json file(s)")
    ap.add_argument("--per-country", type=int, default=22)
    ap.add_argument("--cap", type=int, default=240)
    ap.add_argument("--out", default="seed_sample.json")
    args = ap.parse_args()

    pool = []
    for path in args.inp:
        try:
            pool += json.load(open(path, encoding="utf-8")).get("wines", [])
        except FileNotFoundError:
            print(f"  (skipped missing {path})")

    # drop already-represented; normalise origin; keep only leads with an origin
    leads = []
    for w in pool:
        if w.get("no_gap") == "represented":
            continue
        w = dict(w)
        w["country"] = country_en(w.get("country"))
        if not w["country"]:
            continue
        leads.append(w)

    # best-first: opportunity, then richness
    leads.sort(key=lambda w: (GAP_RANK.get(w.get("no_gap"), 2), -richness(w)))

    per = collections.Counter()
    picked = []
    for w in leads:
        c = w["country"]
        if per[c] >= args.per_country:
            continue
        per[c] += 1
        picked.append(w)
        if len(picked) >= args.cap:
            break

    src = sorted({w.get("source", "").split(" — ")[0].replace("seed: ", "") for w in picked})
    json.dump({"generated": picked and picked[0]["audit"]["created_at"][:10] or "",
               "note": "Curated app sample of supply-side leads — unverified, pending producer claim.",
               "sources": src, "wines": picked},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(picked)} leads -> {args.out}")
    print("  by origin: " + ", ".join(f"{c}={n}" for c, n in per.most_common()))
    print("  by gap:    " + ", ".join(f"{k}={v}" for k, v in
                                       collections.Counter(w.get('no_gap') for w in picked).most_common()))


if __name__ == "__main__":
    main()
