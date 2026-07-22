"""
fetch_launch_plans.py — download Vinmonopolet launch plans and parse them to specs_*.json.

Vinmonopolet publishes every launch plan (the tender documents) back through 2022, both
halves, with English editions, plus an archive of past launches. build_app.py already
auto-discovers every specs_*.json, so the only missing link is getting the Excel files.
This does that on a machine that can reach vinmonopolet.no (your laptop, or the GitHub
Actions runner — the sandbox this repo is edited in cannot).

Three ways to point it at plans, most reliable first:
  1. Direct .xlsx URLs         — copy the download links off the archive page into
                                  plan_urls.txt (one per line) or pass with --url.
  2. Plan / archive page URLs  — it fetches the HTML and extracts the .xlsx links
                                  (best-effort; the site is a SPA, so if a page is fully
                                  client-rendered the link may not be in the HTML — then
                                  fall back to method 1).
  3. Built-in default pages    — the known plan/archive pages, tried automatically.

For each Excel it derives YYYY_H, prefers the English edition, parses via
parse_lanseringsplan.parse_workbook, and writes specs_YYYY_H.json (skips ones that
already exist unless --force). Then run build_app.py.

Run:  python3 fetch_launch_plans.py                 # try default pages + plan_urls.txt
      python3 fetch_launch_plans.py --url <xlsx-url>
      python3 fetch_launch_plans.py --from plan_urls.txt --force
"""
import os, sys, re, json, argparse, urllib.request, urllib.error
from urllib.parse import urljoin

UA = "Mozilla/5.0 (compatible; tender-intel launch-plan fetcher; respectful, low-volume)"

# Known landing pages (English where available). The archive links out to older plans.
DEFAULT_PAGES = [
    "https://www.vinmonopolet.no/english/product-launches-tender-plan",
    "https://www.vinmonopolet.no/lanseringer/arkiv",
    "https://www.vinmonopolet.no/content/lanseringer/tidligere-lanseringer",
    "https://www.vinmonopolet.no/lanseringer/lanseringsplan-2026-1",
    "https://www.vinmonopolet.no/lanseringer/lanseringsplan-2026-2",
    "https://www.vinmonopolet.no/lanseringer/lanseringsplan-2025-1",
    "https://www.vinmonopolet.no/lanseringer/lanseringsplan-2023",
]


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,nb"})
    with urllib.request.urlopen(req, timeout=45) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def xlsx_links(html, base):
    """Every .xlsx URL referenced in the page HTML / embedded JSON state, absolutised."""
    raw = re.findall(r'["\'(]([^"\'()\s]+?\.xlsx)(?:["\')?#]|$)', html, re.I)
    out, seen = [], set()
    for u in raw:
        full = urljoin(base, u.replace("\\/", "/"))
        if full not in seen:
            seen.add(full); out.append(full)
    return out


HALF = [(r"andre|second|_2(?!\d)|2[-_ ]?halv|h2\b", 2), (r"forste|first|_1(?!\d)|1[-_ ]?halv|h1\b", 1)]


def name_for(url):
    """Derive specs_YYYY_H.json from a plan URL/filename (year required, half best-effort)."""
    s = url.lower()
    ym = re.search(r"(20\d\d)", s)
    if not ym:
        return None
    year = ym.group(1)
    m2 = re.search(re.escape(year) + r"[-_ ]?([12])(?!\d)", s)   # a "-1"/"-2" right after the year
    half = int(m2.group(1)) if m2 else next((h for pat, h in HALF if re.search(pat, s)), 1)
    return f"specs_{year}_{half}.json"


def is_english(url):
    return bool(re.search(r"english|_en\b|/en/|-en\.|engelsk", url.lower()))


def fetch_all(sources, force):
    # expand any HTML pages into the .xlsx links they reference
    xlsx = []
    for src in sources:
        if src.lower().endswith(".xlsx"):
            xlsx.append(src); continue
        try:
            links = xlsx_links(get(src), src)
            print(f"  {len(links):2} xlsx links on {src}")
            xlsx += links
        except Exception as e:
            print(f"  ! could not read {src}: {e}")

    # dedupe by target file, preferring the English edition
    by_name = {}
    for u in xlsx:
        nm = name_for(u)
        if not nm:
            continue
        if nm not in by_name or (is_english(u) and not is_english(by_name[nm])):
            by_name[nm] = u

    if not by_name:
        return []
    try:
        from parse_lanseringsplan import parse_workbook   # needs openpyxl
    except ImportError:
        sys.exit("openpyxl is required to parse .xlsx files — install it: pip install openpyxl")
    made = []
    for nm, url in sorted(by_name.items(), reverse=True):
        if os.path.exists(nm) and not force:
            print(f"  = {nm} exists — skip (use --force to refresh)")
            continue
        try:
            tmp = "_plan_tmp.xlsx"
            open(tmp, "wb").write(get(url, binary=True))
            specs = parse_workbook(tmp)
            os.remove(tmp)
            if not specs:
                print(f"  ! {url} parsed to 0 specs — skipped"); continue
            json.dump(specs, open(nm, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"  + {nm}  ({len(specs)} specs)  <- {url}")
            made.append(nm)
        except Exception as e:
            print(f"  ! failed on {url}: {e}")
    return made


def main():
    ap = argparse.ArgumentParser(description="Download + parse Vinmonopolet launch plans to specs_*.json.")
    ap.add_argument("--url", action="append", default=[], help="a direct .xlsx (or page) URL; repeatable")
    ap.add_argument("--from", dest="fromfile", default="plan_urls.txt", help="file of URLs, one per line")
    ap.add_argument("--no-defaults", action="store_true", help="don't try the built-in default pages")
    ap.add_argument("--force", action="store_true", help="re-parse even if specs_YYYY_H.json exists")
    args = ap.parse_args()

    sources = list(args.url)
    if os.path.exists(args.fromfile):
        sources += [l.strip() for l in open(args.fromfile, encoding="utf-8") if l.strip() and not l.startswith("#")]
    if not args.no_defaults:
        sources += DEFAULT_PAGES
    # de-dupe, keep order
    sources = list(dict.fromkeys(sources))

    print(f"fetching from {len(sources)} source(s)…")
    made = fetch_all(sources, args.force)
    if made:
        print(f"\n{len(made)} plan(s) written: {', '.join(made)}")
        print("Now run: python3 build_app.py")
    else:
        print("\nNo new plans written. If the pages are client-rendered, copy the direct "
              ".xlsx download links off the archive page into plan_urls.txt and re-run.")


if __name__ == "__main__":
    main()
