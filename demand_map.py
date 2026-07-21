"""
demand_map.py — where to seed producer data first.

Reads every parsed tender plan (specs_*.json) and maps the RECURRING demand:
which origin x grape x style combinations Vinmonopolet asks for again and again,
at what price band, and how often certifications are required. That tells you
which unrepresented producers to seed first — the ones that map onto tenders
that keep coming back, not every producer on earth.

Run: python3 demand_map.py   (also writes demand_map.md)
"""
import json, glob, re, collections, statistics

PLANS = {}
for f in sorted(glob.glob("specs_*.json")):
    label = re.sub(r"^specs_(plan_)?|_en\.json$|\.json$", "", f)
    try:
        PLANS[label] = json.load(open(f, encoding="utf-8"))
    except Exception:
        pass


def N(s):
    return (s or "").lower().replace("ø", "o").replace("æ", "ae").replace("å", "a")


GRAPES = ["chardonnay", "chenin blanc", "pinot noir", "pinotage", "cabernet franc",
    "cabernet sauvignon", "merlot", "syrah", "shiraz", "grenache", "garnacha", "cinsault",
    "mourvedre", "tempranillo", "sangiovese", "nebbiolo", "barbera", "riesling",
    "gruner veltliner", "sauvignon blanc", "malbec", "carmenere", "zinfandel", "primitivo",
    "gamay", "albarino", "godello", "verdejo", "gewurztraminer", "pinot gris", "pinot blanc",
    "viognier", "touriga", "furmint", "assyrtiko", "xinomavro", "agiorgitiko", "carignan",
    "petit verdot", "semillon", "muscat", "moscato", "glera", "vermentino", "fiano", "greco",
    "montepulciano", "aglianico", "corvina", "garganega", "verdicchio", "trebbiano", "cortese",
    "arneis", "dolcetto", "nero d", "nascetta", "grillo", "nerello", "mencia", "monastrell",
    "bobal", "graciano", "macabeo", "xarel", "parellada", "palomino", "touriga nacional",
    "alvarinho", "arinto", "encruzado", "aligote", "savagnin", "trousseau", "mondeuse",
    "tannat", "silvaner", "blaufrankisch", "zweigelt", "welschriesling", "kadarka", "saperavi"]


def is_wine(s):
    t = N((s.get("main_type") or "") + " " + (s.get("group") or ""))
    return not re.search(r"beer|ale|lager|cider|spirit|whisky|aquavit|gin|vodka|rum|brandy|liqueur|akevitt|ol\b|brennevin", t)


def style(s):
    g = N(s.get("group") or "")
    if "sparkling" in g or "musserende" in g:
        return "sparkling"
    if "fortified" in g or "sterkvin" in g:
        return "fortified"
    if "rose" in g:
        return "rose"
    if "white" in g or "hvit" in g:
        return "white"
    if "red" in g or "rod" in g:
        return "red"
    return "wine"


def spec_grapes(s):
    txt = N(" ".join(str(s.get(k) or "") for k in ("spec", "appellation", "quality")))
    found = {g for g in GRAPES if g in txt}
    if re.search(r"traditional method|methode traditionnelle|cap classique", txt):
        found.add("traditional method")
    return found


def certs_required(s):
    txt = N(" ".join(str(s.get(k) or "") for k in ("spec", "quality")))
    return bool(re.search(r"organic|okologisk|fairtrade|biodynam|wieta|\bipw\b|sustainab|vegan", txt))


def band(s):
    p = s.get("price_hi") or s.get("price_lo")
    if not p:
        return None
    for lo, hi, lab in [(0, 150, "<150"), (150, 200, "150-200"), (200, 250, "200-250"),
                        (250, 350, "250-350"), (350, 1e9, "350+")]:
        if lo <= p < hi:
            return lab
    return None


wine_specs = {k: [s for s in v if is_wine(s)] for k, v in PLANS.items()}
n_plans = len(PLANS)

origin = collections.defaultdict(lambda: {"plans": set(), "count": 0})
grape = collections.defaultdict(lambda: {"plans": set(), "count": 0})
combo = collections.defaultdict(lambda: {"plans": set(), "count": 0, "prices": [], "cert": 0})

for plan, specs in wine_specs.items():
    for s in specs:
        c = (s.get("country") or "").strip() or "Open"
        st = style(s)
        p = s.get("price_hi") or s.get("price_lo")
        origin[c]["plans"].add(plan); origin[c]["count"] += 1
        gs = spec_grapes(s)
        for g in gs:
            grape[g]["plans"].add(plan); grape[g]["count"] += 1
        for g in (gs or {None}):
            key = (c, st, g)
            combo[key]["plans"].add(plan); combo[key]["count"] += 1
            if p:
                combo[key]["prices"].append(p)
            if certs_required(s):
                combo[key]["cert"] += 1

lines = []
def out(s=""):
    print(s); lines.append(s)

out(f"# Recurring tender demand — where to seed producers first")
out(f"\nPlans analysed: {n_plans} ({', '.join(PLANS)}) · "
    f"{sum(len(v) for v in wine_specs.values())} wine specs\n")

out("## Origins by recurrence (appears in N of {} plans)".format(n_plans))
for c, d in sorted(origin.items(), key=lambda x: (-len(x[1]["plans"]), -x[1]["count"]))[:15]:
    out(f"  {len(d['plans'])}/{n_plans} plans · {d['count']:3} specs · {c}")

out("\n## Grapes by recurrence")
for g, d in sorted(grape.items(), key=lambda x: (-len(x[1]["plans"]), -x[1]["count"]))[:18]:
    out(f"  {len(d['plans'])}/{n_plans} plans · {d['count']:3} specs · {g}")

out("\n## SEED TARGETS — origin x style x grape, ranked by recurrence then volume")
out("   (median price cap in kr; cert% = share requiring a certification)")
ranked = sorted(combo.items(), key=lambda x: (-len(x[1]["plans"]), -x[1]["count"]))
shown = 0
for (c, st, g), d in ranked:
    if g is None or c == "Open":
        continue
    med = int(statistics.median(d["prices"])) if d["prices"] else 0
    certpct = round(100 * d["cert"] / d["count"]) if d["count"] else 0
    out(f"  {len(d['plans'])}/{n_plans} · {d['count']:2}x · {c} {st} {g}"
        f"  — ~{med} kr, cert {certpct}%")
    shown += 1
    if shown >= 25:
        break

open("demand_map.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n(written to demand_map.md)")
