"""Assembles the self-contained app: inlines SheetJS, embeds specs + wines +
the producer template (base64). Output: tender-intel-app.html"""
import base64, json

html = open("app_template.html", encoding="utf-8").read()
sheetjs = open("package/dist/xlsx.full.min.js", encoding="utf-8").read()
specs = json.load(open("specs_2020_1.json", encoding="utf-8"))
wines = json.load(open("wines.json", encoding="utf-8"))["wines"]
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
open("tender-intel-app.html", "w", encoding="utf-8").write(html)
print(f"tender-intel-app.html written ({len(html)//1024} KB)")
