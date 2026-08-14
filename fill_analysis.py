"""
fill_analysis.py — did the tenders VMP ASKED for actually get FILLED?

We have two real datasets:
  - the request side: specs_*.json (tender lots — country × style × price band × window, with a ref like 202001001)
  - the outcome side: launch_history.json (what actually launched — product, price, period YYYY-MM)

They share no lot ID (ref 202001001 is a tender number; the launch lists key on product varenummer),
so this is a PROFILE + WINDOW join, not an exact-lot match: for each requested lot we look for a launched
product of the same country × style, priced within the band, in the lot's launch window. A match = the lot
was (plausibly) filled; no match = not filled.

The honesty hinge is COVERAGE: absence only means "not filled" if our launch lists would have shown it.
So every lot is also tagged with how many products of its country launched in-window at all. A lot with
zero country-coverage is 'no-data' (we can't tell), NOT 'unmet'. Only lots whose country *did* launch
in-window, yet no matching product appeared, are a real 'not filled'.

Usage:  python3 fill_analysis.py
"""
import json, glob, re, unicodedata
from collections import Counter, defaultdict

COUNTRY_CANON = {  # launch lists are Norwegian; specs are English — fold to English
    "frankrike": "france", "tyskland": "germany", "italia": "italy", "spania": "spain",
    "hellas": "greece", "belgia": "belgium", "nederland": "netherlands", "norge": "norway",
    "sverige": "sweden", "danmark": "denmark", "island": "iceland", "osterrike": "austria",
    "sveits": "switzerland", "ungarn": "hungary", "kroatia": "croatia", "libanon": "lebanon",
    "polen": "poland", "tsjekkia": "czech republic", "sor-afrika": "south africa",
    "storbritannia": "great britain", "england": "great britain", "uk": "great britain",
    "skottland": "scotland", "scottland": "scotland", "irland": "ireland",
}


def norm(s):
    s = (s or "").translate(str.maketrans({"ø": "o", "Ø": "o", "æ": "ae", "å": "a", "Å": "a"}))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def cc(s):
    n = norm(s)
    return COUNTRY_CANON.get(n, n)


# spec group → launch-list canonical type
def spec_style(group, main_type):
    g = norm(group) or norm(main_type)
    if "sparkl" in g or "musser" in g:
        return "sparkling"
    if "rose" in g:
        return "rose"
    if "red" in g or "rodvin" in g:
        return "red"
    if "white" in g or "hvitvin" in g:
        return "white"
    if "fort-" in g or "fortified" in g or "sterkvin" in g:
        return "fortified"
    return g


def ref_window(ref):
    """(year, month) the lot targets, from ref YYYYMM… ; window = that month .. +6 months."""
    m = re.match(r"(\d{4})(\d{2})", str(ref or ""))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def in_window(period, y, mo, months_after=6):
    pm = re.match(r"(\d{4})-(\d{2})", period or "")
    if not pm:
        return False
    py, pmo = int(pm.group(1)), int(pm.group(2))
    start = y * 12 + (mo - 1)
    idx = py * 12 + (pmo - 1)
    return start - 1 <= idx <= start + months_after      # allow 1 month early, up to 6 late


def main():
    R = json.load(open("launch_history.json", encoding="utf-8"))
    for r in R:
        r["_cc"] = cc(r.get("country"))
    launch_years = sorted({r["period"][:4] for r in R})
    last_launch = max(int(r["period"][:4]) * 12 + int(r["period"][5:7]) for r in R)

    plans = {}
    for f in sorted(glob.glob("specs_*.json")):
        d = json.load(open(f, encoding="utf-8"))
        plans[f] = d if isinstance(d, list) else d.get("specs", [])

    overall = Counter()
    per_plan = {}
    unmet_examples = []
    for f, specs in plans.items():
        c = Counter()
        for s in specs:
            if norm(s.get("main_type")) not in ("wine", "") and "vin" not in norm(s.get("group")):
                continue  # wine lots only (skip spirits/beer tender lines for this pass)
            w = ref_window(s.get("ref"))
            if not w:
                c["no_ref"] += 1
                continue
            y, mo = w
            scountry, sstyle = cc(s.get("country")), spec_style(s.get("group"), s.get("main_type"))
            hi = s.get("price_hi") or s.get("price_lo")
            # candidate launched products in the window
            winrecs = [r for r in R if in_window(r["period"], y, mo)]
            country_cov = sum(1 for r in winrecs if r["_cc"] == scountry)
            def price_ok(r):
                if not hi or not r.get("price"):
                    return True
                return r["price"] <= float(hi) * 1.05
            matches = [r for r in winrecs
                       if r["_cc"] == scountry and (not sstyle or r.get("type") == sstyle) and price_ok(r)]
            window_end = y * 12 + (mo - 1) + 6
            if matches:
                c["met"] += 1
            elif window_end > last_launch:
                c["pending"] += 1                    # launch window not fully elapsed in our data
            elif country_cov == 0:
                c["no_data"] += 1                    # that country never appears in our lists for the window
            else:
                c["not_met"] += 1                    # country launched in-window, but nothing matched the lot
                if len(unmet_examples) < 25:
                    unmet_examples.append((f.split("/")[-1], s.get("ref"), s.get("country"),
                                           s.get("group"), s.get("price_text"), country_cov))
        per_plan[f] = c
        overall.update(c)

    def line(name, c):
        judged = c["met"] + c["not_met"]
        fr = f"{100*c['met']/judged:.0f}%" if judged else "—"
        return (f"{name:26} met={c['met']:>3} not_met={c['not_met']:>3} "
                f"no_data={c['no_data']:>3} pending={c['pending']:>3}  fill={fr}")

    print("Launch-list coverage:", launch_years[0], "→", launch_years[-1])
    print("(fill = met / (met+not_met); no_data = that origin never in our lists for the window)\n")
    for f, c in per_plan.items():
        print(" ", line(f.split("/")[-1], c))
    print("\n", line("ALL PLANS", overall))
    print("\nSample 'not filled' lots (origin DID launch in-window, but no matching product):")
    for ex in unmet_examples[:15]:
        print(f"   {ex[0]}  {ex[1]}  {ex[2]} · {ex[3]} · {ex[4]}  (country had {ex[5]} launches in-window)")


if __name__ == "__main__":
    main()
