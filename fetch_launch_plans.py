"""
fetch_launch_plans.py — download Vinmonopolet launch plans and parse them to specs_*.json.

Vinmonopolet publishes every launch plan (the tender documents) back through 2022, both
halves, with English editions, plus an archive of past launches. build_app.py already
auto-discovers every specs_*.json, so the only missing link is getting the Excel files.
This does that on a machine that can reach vinmonopolet.no (your laptop, or the GitHub
Actions runner — the sandbox this repo is edited in cannot).

Point it at plans two ways (most reliable first):
  1. Direct .xlsx URLs         — copy the download links off vinmonopolet.no's Lanseringer
                                  section into plan_urls.txt (one per line) or pass --url.
  2. Plan / archive page URLs  — pass a page URL and it extracts the .xlsx links from the
                                  HTML (best-effort; the site is a SPA, so if a page is
                                  fully client-rendered the link may not be there — then
                                  use method 1).
(No page URLs are hard-coded: the exact archive paths aren't verified, and guessed URLs
would mislead more than help. You supply the real links.)

For each Excel it derives YYYY_H, prefers the English edition, parses via
parse_lanseringsplan.parse_workbook, and writes specs_YYYY_H.json (skips ones that
already exist unless --force). Then run build_app.py.

Run:  python3 fetch_launch_plans.py                 # try default pages + plan_urls.txt
      python3 fetch_launch_plans.py --url <xlsx-url>
      python3 fetch_launch_plans.py --from plan_urls.txt --force
"""
import os, sys, re, json, glob, argparse, urllib.request, urllib.error
from collections import Counter
from urllib.parse import urljoin

UA = "Mozilla/5.0 (compatible; tender-intel launch-plan fetcher; respectful, low-volume)"

# No hard-coded page URLs: the exact archive/plan paths on vinmonopolet.no are not
# verified from here, and shipping guessed URLs would be worse than none. Put the REAL
# .xlsx download links (or plan-page URLs) in plan_urls.txt — grab them from the
# "Lanseringer" section on vinmonopolet.no.
DEFAULT_PAGES = []


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


def period_of_name(name):
    """(year, half) from a specs_*.json filename, or None."""
    ym = re.search(r"(20\d\d)", name or "")
    if not ym:
        return None
    year = int(ym.group(1))
    m2 = re.search(re.escape(ym.group(1)) + r"[-_ ]?([12])(?!\d)", name)
    return (year, int(m2.group(1))) if m2 else (year, None)


def existing_periods():
    """(year, half) already covered by any specs_*.json in the repo."""
    out = set()
    for f in glob.glob("specs_*.json"):
        p = period_of_name(os.path.basename(f))
        if p:
            out.add(p)
    return out


MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
          "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
          "januar": 1, "februar": 2, "mars": 3, "mai": 5, "juni": 6, "juli": 7,
          "oktober": 10, "desember": 12}


def period_from_specs(specs):
    """Derive (year, half) from a parsed plan, URL-independent.

    Every tender's article number is YYYY + MM(launch month) + sequence (e.g. 202607001
    = 2026, July → 2nd half) — the authoritative period signal. It normally sits in `ref`,
    but Norwegian-edition sheets shift columns and it lands in `spec`, so check both.
    (An earlier launch-month + deadline-year heuristic misdated a Norwegian 2026-2 sheet as
    2027-2 — the deadline runs months *before* the launch — so we no longer guess from
    dates; if no article number is present we return None rather than mislabel the plan.)"""
    yh = Counter()
    for s in specs:
        for fld in ("ref", "spec"):
            v = re.sub(r"\D", "", str(s.get(fld) or ""))
            m = re.match(r"(20\d\d)(\d{2})\d", v)   # YYYYMM + at least one sequence digit
            if m and 1 <= int(m.group(2)) <= 12:
                y, mo = int(m.group(1)), int(m.group(2))
                yh[(y, 1 if mo <= 6 else 2)] += 1
                break
    if not yh:
        return None
    return yh.most_common(1)[0][0]


EN_COUNTRIES = {"italy", "france", "spain", "germany", "south africa", "united states",
                "greece", "hungary", "austria", "new zealand"}
NO_COUNTRIES = {"italia", "frankrike", "spania", "tyskland", "sor-afrika", "usa",
                "hellas", "ungarn", "osterrike", "new zealand"}


def specs_look_english(specs):
    """Heuristic language sniff from country values (editions differ only in language)."""
    cc = Counter(re.sub(r"[^a-z ]", "", (s.get("country") or "").lower().replace("ø", "o").replace("å", "a").replace("æ", "ae"))
                 for s in specs if s.get("country"))
    en = sum(v for k, v in cc.items() if k in EN_COUNTRIES)
    no = sum(v for k, v in cc.items() if k in NO_COUNTRIES)
    return en >= no   # tie -> prefer English (matches the repo's existing editions)


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
    xlsx = list(dict.fromkeys(xlsx))   # de-dupe URLs, keep order
    if not xlsx:
        return []

    try:
        from parse_lanseringsplan import parse_workbook   # needs openpyxl
    except ImportError:
        sys.exit("openpyxl is required to parse .xlsx files — install it: pip install openpyxl")

    have = existing_periods()          # (year, half) already in the repo
    # Vinmonopolet's CDN filenames are opaque hashes, so the plan period can't be read
    # from the URL — download, parse, then derive it from the launch dates inside.
    picked = {}   # (year, half) -> {"specs", "url", "english"}
    for url in xlsx:
        # fast path: if the URL itself names a period we already have, skip the download
        p_url = period_of_name(name_for(url) or "")
        if p_url and p_url[1] and p_url in have and not force:
            print(f"  = {p_url[0]}-{p_url[1]} already in repo (from URL) — skip")
            continue
        try:
            tmp = "_plan_tmp.xlsx"
            open(tmp, "wb").write(get(url, binary=True))
            specs = parse_workbook(tmp)
            os.remove(tmp)
        except Exception as e:
            print(f"  ! failed on {url}: {e}"); continue
        if not specs:
            print(f"  ! {url} parsed to 0 specs — skipped"); continue
        per = period_from_specs(specs) or (p_url if p_url and p_url[1] else None)
        if not per:
            print(f"  ! {url}: couldn't determine plan period (no launch dates) — skipped"); continue
        if per in have and not force:
            print(f"  = {per[0]}-{per[1]} already in repo ({len(specs)} specs) — skip"); continue
        eng = is_english(url) or specs_look_english(specs)
        prev = picked.get(per)
        if prev is None or (eng and not prev["english"]):   # prefer the English edition
            picked[per] = {"specs": specs, "url": url, "english": eng}
            print(f"  · {per[0]}-{per[1]}: {len(specs)} specs {'[en]' if eng else '[no]'}  <- {url}")

    made = []
    for (year, half), info in sorted(picked.items()):
        nm = f"specs_{year}_{half}.json"
        json.dump(info["specs"], open(nm, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"  + {nm}  ({len(info['specs'])} specs)")
        made.append(nm)
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
