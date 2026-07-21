"""Assembles the self-contained app: inlines SheetJS, embeds specs + wines +
the producer template (base64). Output: index.html (the file GitHub Pages serves)."""
import base64, json, os

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


def load_seeds():
    """Merge every curated seed sample present. Seeds already carry seed: provenance
    (so the app auto-badges them as sample leads); we only backfill the schema."""
    seeds = []
    for path in ("seed_sample.json",):
        if os.path.exists(path):
            seeds += json.load(open(path, encoding="utf-8")).get("wines", [])
    return [normalize(w) for w in seeds]


html = open("app_template.html", encoding="utf-8").read()
sheetjs = open("package/dist/xlsx.full.min.js", encoding="utf-8").read()
specs = json.load(open("specs_2020_1.json", encoding="utf-8"))
wines = json.load(open("wines.json", encoding="utf-8"))["wines"]
seeds = load_seeds()
wines = wines + seeds
print(f"wines: {len(wines) - len(seeds)} curated + {len(seeds)} seed leads = {len(wines)}")
tpl_b64 = base64.b64encode(open("producer_upload_template.xlsx", "rb").read()).decode()
imp_b64 = base64.b64encode(open("importer_portfolio_template.xlsx", "rb").read()).decode()

plans = {
    "2027-1 (live)": json.load(open("specs_plan_2027_1_en.json", encoding="utf-8")),
    "2026-2": json.load(open("specs_plan_2026_2_en.json", encoding="utf-8")),
    "2026-1": json.load(open("specs_plan_2026_1_en.json", encoding="utf-8")),
    "2020-1": specs,
}
world = open("world_paths.json", encoding="utf-8").read()
html = html.replace("/*WORLD*/[]", world)
html = html.replace("/*SHEETJS*/", sheetjs.replace("</script>", "<\\/script>"))
html = html.replace("/*PLANS*/{}", json.dumps(plans, ensure_ascii=False))
html = html.replace("/*WINES*/[]", json.dumps(wines, ensure_ascii=False))
html = html.replace('"/*TEMPLATE_B64*/"', json.dumps(tpl_b64))
html = html.replace('"/*IMPORTER_TEMPLATE_B64*/"', json.dumps(imp_b64))
open("index.html", "w", encoding="utf-8").write(html)
print(f"index.html written ({len(html)//1024} KB)")
