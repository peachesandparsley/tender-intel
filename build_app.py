"""Assembles the self-contained app: inlines SheetJS, embeds specs + wines +
the producer template (base64). Output: index.html (the file GitHub Pages serves).

Launch plans are auto-discovered: every specs_*.json in this folder is embedded, newest
first (the newest is tagged "(live)"). Drop in more historical plans — parse the Excel
from vinmonopolet.no with parse_lanseringsplan.py to specs_YYYY_H.json — and they flow
into the app, the gap analysis and the recurrence stats with no code change."""
import base64, json, os, glob, re


def plan_label(fname):
    lab = re.sub(r"^specs_(plan_)?", "", os.path.basename(fname))
    lab = re.sub(r"(_en)?\.json$", "", lab)
    return lab.replace("_", "-")            # "2026_1" -> "2026-1"


def plan_year_half(fname):
    nums = re.findall(r"\d+", os.path.basename(fname))
    return (nums[0] if nums else "0", nums[1] if len(nums) > 1 else "0")


# Vinmonopolet publishes each plan in Norwegian and English. When only the Norwegian
# edition is available, its country names ("Italia", "Frankrike", "Sør-Afrika") would
# otherwise sit apart from the English plans — splitting the country filter, the gap
# clusters, and the map (whose geometry is English). Canonicalise country to English at
# embed time so every plan speaks one language. Token-level so compound origins
# ("Belgia eller Norge") map cleanly too. Style words (Rødvin/Hvitvin/Musserende) already
# survive via the app's ø→o normaliser, so only country needs translating here.
COUNTRY_NO2EN = {
    "frankrike": "France", "italia": "Italy", "spania": "Spain", "tyskland": "Germany",
    "hellas": "Greece", "belgia": "Belgium", "nederland": "Netherlands", "norge": "Norway",
    "sverige": "Sweden", "danmark": "Denmark", "storbritannia": "Great Britain",
    "skottland": "Scotland", "tsjekkia": "Czech Republic", "østerrike": "Austria",
    "europa": "Europe", "norden": "Nordics", "sør-afrika": "South Africa",
    "sveits": "Switzerland", "ungarn": "Hungary", "kroatia": "Croatia", "libanon": "Lebanon",
    "eller": "or", "og": "and",
}
_CTOKEN = re.compile(r"[A-Za-zÀ-ÿ]+(?:-[A-Za-zÀ-ÿ]+)?")


def canon_country(s):
    if not s:
        return s
    return _CTOKEN.sub(lambda m: COUNTRY_NO2EN.get(m.group(0).lower(), m.group(0)), s)


def load_plans():
    # newest first; within the same year/half prefer the English edition
    files = sorted(glob.glob("specs_*.json"),
                   key=lambda f: (plan_year_half(f), "_en" in f), reverse=True)
    plans, seen = {}, set()
    for f in files:
        yh = plan_year_half(f)
        if yh in seen:
            continue
        seen.add(yh)
        specs = json.load(open(f, encoding="utf-8"))
        y, h = plan_year_half(f)
        for i, sp in enumerate(specs):
            if sp.get("country"):
                sp["country"] = canon_country(sp["country"])
            # Some editions (Norwegian sheets) leave `ref` blank and put the article number
            # in `spec` instead. ref is the app's stable tender identity (shortlist keys,
            # titles), so recover the real number from spec when it's a bare varenr (and clear
            # the junk out of spec); otherwise synthesise a deterministic per-row id.
            if not str(sp.get("ref") or "").strip():
                sv = str(sp.get("spec") or "").strip()
                if re.fullmatch(r"\d{6,10}", sv):
                    sp["ref"], sp["spec"] = sv, ""
                else:
                    sp["ref"] = f"{y}-{h}#{i + 1:03d}"
        plans[plan_label(f) + (" (live)" if not plans else "")] = specs
    return plans

# Baseline wine schema — seed records (from the cross-monopoly / directory seeders)
# carry a leaner shape; fill any missing keys so the app renders/matches them safely.
WINE_DEFAULTS = {
    "region": "", "appellation": "", "grapes": {}, "color": "", "method": None,
    "vintages_available": [], "abv": None, "sugar_g_l": None, "acid_g_l": None,
    "wood": None, "certs": [], "cert_on_label": False, "vines_age": None,
    "maceration_days": None, "profile": None, "packaging": {"type": None, "weight_g": None},
    "closure": None, "storable": None, "volume_bottles": None, "fob_eur": None,
    "representation": {}, "catalog_no": None,
}


def normalize(w):
    out = dict(WINE_DEFAULTS)
    out.update(w)
    return out


html = open("app_template.html", encoding="utf-8").read()
sheetjs = open("package/dist/xlsx.full.min.js", encoding="utf-8").read()
# The app ships with NO seed wines. The wine side is filled by users adding their own
# portfolios (real FOB and all) — the whole point of the tool — matched against the real
# tender data. Seed leads (Systembolaget open-data wines, Wikidata producers) were cosmetic:
# already commercialised, no ex-cellar price, not genuine introduction opportunities — so they
# are no longer embedded. A real, sourced wines.json, if ever added, is still picked up.
curated = json.load(open("wines.json", encoding="utf-8"))["wines"] if os.path.exists("wines.json") else []
wines = [normalize(w) for w in curated]
print(f"wines embedded: {len(wines)} (seed leads removed — users add their own portfolios)")
tpl_b64 = base64.b64encode(open("producer_upload_template.xlsx", "rb").read()).decode()
imp_b64 = base64.b64encode(open("importer_portfolio_template.xlsx", "rb").read()).decode()

plans = load_plans()
print(f"plans: {len(plans)} — {', '.join(plans)}")
world = open("world_paths.json", encoding="utf-8").read()
html = html.replace("/*WORLD*/[]", world)
html = html.replace("/*SHEETJS*/", sheetjs.replace("</script>", "<\\/script>"))
html = html.replace("/*PLANS*/{}", json.dumps(plans, ensure_ascii=False))
html = html.replace("/*WINES*/[]", json.dumps(wines, ensure_ascii=False))
html = html.replace('"/*TEMPLATE_B64*/"', json.dumps(tpl_b64))
html = html.replace('"/*IMPORTER_TEMPLATE_B64*/"', json.dumps(imp_b64))
open("index.html", "w", encoding="utf-8").write(html)
print(f"index.html written ({len(html)//1024} KB)")
