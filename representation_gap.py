"""
representation_gap.py — where Vinmonopolet under-carries wines that matter elsewhere.

The idea (see the app's "Representation gap" panel): cross VMP's shelf presence for a category against
an EXTERNAL reference for how important that category is — and surface the outliers. A category with high
stature but thin VMP presence is a *candidate* gap (Aglianico-type); the reverse is a saturated/legacy one.

Honesty, up front — this is a HYPOTHESIS generator, not a verdict:
  • Presence here = our launch-history sample (2020→), which is PARTIAL and north-skewed, and only counts
    categories with >= 5 launches. It understates absolute catalog counts. Labelled as such.
  • Stature = a CURATED, SOURCED editorial reference (DOCG status, canonical-variety standing) — coarse
    tiers with a cited basis, never an invented numeric score.
  • The strongest demand axis — do the peer Nordic monopolies (Systembolaget/Alko) carry more? — and the
    full VMP catalog by grape both need data we haven't ingested yet; those columns are marked PENDING.
  • "Under-represented vs. its stature" is NOT "will sell in Norway." That still needs real sell-through.

Unit of analysis: region × style (with its signature grape noted), because our data can't separate grapes
within a region (Piemonte red = Nebbiolo + Barbera + Dolcetto together).

Usage:  python3 representation_gap.py   # reads market_index.json -> representation_gap.json + a report
"""
import json, os

# Curated reference — region × style, its signature grape, a coarse stature tier, and the SOURCED basis.
# Stature tiers: "iconic" (world-benchmark), "major" (great but under the radar), "rising", "classic".
# Sources are public/canonical (DOCG/DOCa designations; standard variety references). Editorial, labelled.
REFERENCE = [
    # region (as it appears in the launch data), style, grape, stature, note (sourced basis)
    ("Piemonte", "red", "Nebbiolo / Barbera", "iconic", "Barolo & Barbaresco DOCG — world-benchmark reds"),
    ("Toscana", "red", "Sangiovese", "iconic", "Brunello di Montalcino & Chianti Classico DOCG"),
    ("Bordeaux", "red", "Cabernet/Merlot", "iconic", "1855 classed growths — global benchmark"),
    ("Burgund", "red", "Pinot Noir", "iconic", "Côte d'Or grands crus — global benchmark"),
    ("Champagne", "sparkling", "Chardonnay/Pinot", "iconic", "the benchmark sparkling region"),
    ("Mosel", "white", "Riesling", "iconic", "great-Riesling heartland (VDP GG)"),
    ("Campania", "red", "Aglianico", "major", "Taurasi DOCG; 'one of Italy's three greatest reds' (Native Wine Grapes of Italy)"),
    ("Basilicata", "red", "Aglianico", "major", "Aglianico del Vulture Superiore DOCG — 'Barolo of the South'"),
    ("Sicilia", "red", "Nerello Mascalese", "rising", "Etna Rosso DOC — the decade's breakout Italian red"),
    ("Santorini", "white", "Assyrtiko", "rising", "volcanic Assyrtiko — sommelier darling, PDO Santorini"),
    ("Makedonia", "red", "Xinomavro", "major", "Naoussa PDO — 'Greece's Barolo', age-worthy"),
    ("Marche", "white", "Verdicchio", "major", "Verdicchio dei Castelli di Jesi / Matelica — great ageable white"),
    ("Friuli", "white", "Friulano/blends", "major", "benchmark Italian whites (Collio)"),
    ("Trentino Alto-Adige", "white", "Pinot Bianco etc.", "classic", "top-tier alpine whites"),
    ("Douro", "red", "Touriga Nacional", "major", "Douro DOC dry reds — Port grapes turned world-class"),
    ("Rioja", "red", "Tempranillo", "iconic", "Rioja DOCa — Spain's benchmark red"),
    ("Ribera del Duero", "red", "Tempranillo", "iconic", "home of Vega Sicilia"),
    ("Bierzo", "red", "Mencía", "rising", "Mencía revival — critical acclaim"),
    ("Jura", "white", "Savagnin/Chardonnay", "rising", "cult region, tiny production"),
    ("Alsace", "white", "Riesling/Gewurz", "classic", "Grand Cru Alsace"),
    ("Loire", "white", "Chenin Blanc", "major", "Savennières/Vouvray — great ageable Chenin"),
    ("Kamptal", "white", "Grüner Veltliner", "major", "Austrian benchmark whites (Erste Lage)"),
    ("Burgenland", "red", "Blaufränkisch", "rising", "Austria's serious red — critical momentum"),
    ("Lombardia", "sparkling", "Chardonnay/Pinot", "classic", "Franciacorta DOCG — Italy's top traditional-method"),
]

PRESENCE_BUCKETS = [(200, "deep"), (60, "solid"), (20, "moderate"), (5, "thin")]


def presence_level(n):
    if not n:
        return "absent"
    for th, lab in PRESENCE_BUCKETS:
        if n >= th:
            return lab
    return "thin"


def read_gap(stature, level):
    """Coarse, honest read + confidence. Never 'buy'; always a candidate framed against pending data."""
    high = stature in ("iconic", "major")
    if high and level in ("absent", "thin"):
        conf = "medium" if stature == "major" else "low"
        return "under-represented — candidate gap", conf
    if stature == "rising" and level in ("absent", "thin", "moderate"):
        return "emerging — worth watching", "low"
    if high and level in ("deep", "solid"):
        return "well represented", "n/a"
    if stature == "classic" and level in ("deep", "solid"):
        return "well represented", "n/a"
    return "represented", "low"


def main():
    m = json.load(open("market_index.json", encoding="utf-8"))
    by_dt = {(b["district"], b["type"]): b for b in m.get("byDistrictType", [])}
    years = m.get("meta", {}).get("years", [])

    rows = []
    for region, style, grape, stature, note in REFERENCE:
        b = by_dt.get((region, style))
        n = b["n"] if b else 0                       # launch-history presence (partial, >=5 filtered)
        level = presence_level(n)
        read, conf = read_gap(stature, level)
        rows.append({
            "region": region, "style": style, "grape": grape,
            "stature": stature, "statureNote": note,
            "vmpLaunches": n or None, "presence": level,
            "medPrice": b["med"] if b else None,
            "peerNordic": None,                      # PENDING Systembolaget/Alko ingest
            "read": read, "confidence": conf,
        })

    # rank: candidate gaps first; within them, most CREDIBLE first — higher confidence, then present-but-thin
    # (a known-thin category is a firmer signal than 'absent', which in our partial sample may just be unsampled).
    order = {"under-represented — candidate gap": 0, "emerging — worth watching": 1,
             "represented": 2, "well represented": 3}
    conf_rank = {"medium": 0, "low": 1, "n/a": 2}
    pres_rank = {"thin": 0, "moderate": 1, "absent": 2, "solid": 3, "deep": 4}
    rows.sort(key=lambda r: (order.get(r["read"], 2), conf_rank.get(r["confidence"], 3),
                             pres_rank.get(r["presence"], 3), -(r["vmpLaunches"] or 0)))

    out = {
        "meta": {
            "unit": "region × style (signature grape noted)",
            "presenceSource": f"Vinmonopolet launch history {years[0] if years else ''}–{years[-1] if years else ''} "
                              "(PARTIAL sample; categories with <5 launches read as 'absent'; understates full catalog)",
            "statureSource": "curated editorial reference — DOCG/DOCa status & canonical-variety standing (sourced per row)",
            "pending": ["peer Nordic monopolies (Systembolaget/Alko) — the strongest demand proxy",
                        "full VMP catalog by grape (open API) — exact counts incl. thin categories",
                        "actual sell-through (restricted API) — the real demand verdict"],
            "disclaimer": "Candidate gaps are HYPOTHESES, not opportunities proven. 'Under-represented vs. its "
                          "stature' is not 'will sell in Norway' — that needs real demand data (peer markets / sales).",
        },
        "rows": rows,
    }
    json.dump(out, open("representation_gap.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"representation_gap.json written — {len(rows)} categories")
    print(f"{'REGION · STYLE':30} {'GRAPE':22} {'STATURE':8} {'VMP(launches)':13} {'READ'}")
    for r in rows:
        print(f"  {r['region']+' · '+r['style']:28} {r['grape'][:20]:22} {r['stature']:8} "
              f"{str(r['vmpLaunches'] or '—'):>6}       {r['read']}  [{r['confidence']}]")


if __name__ == "__main__":
    main()
