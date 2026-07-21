"""
scrape_producers.py — seed the producer database from national wine-body directories.

The national bodies publish producer directories *so buyers find their producers* —
that's the point of a trade-promotion body. Scraping those public, factual listings
to bootstrap a lead list is legitimate; this does it respectfully and honestly.

What this gets you: producer identity, region, variety, and the outbound link to the
producer's own site. It does NOT get the tender-critical numbers only a producer holds
(FOB, committed volume, exact grape %, sugar, wood, bottle weight) — those stay blank,
pending producer claim, exactly like every other seeder here. Representation in NO is
DERIVED from the Vinmonopolet catalog index, never assumed.

Do this the right way (see SEED_SOURCES.md "Scraping" for the full rationale):
  * API-first. A faceted search UI (Austrian Wine) is backed by a JSON endpoint —
    take that structured feed rather than parsing rendered HTML.
  * Respect robots.txt / ToS per site, identify a real UA, and rate-limit (--delay).
  * EU database right: extracting a *substantial part* of an EU directory wholesale is
    the legal risk zone. The safe pattern is IDENTIFY producers here, then pull detail
    from each producer's own site / by contacting them — not vacuuming the whole DB.
  * These are LEADS, not facts: unverified, pending producer claim.

Runs a real browser (installed Chromium via Playwright) so JS-rendered / WAF-protected
directories work. Selectors and the API URL are marked VERIFY — confirm them against the
live DOM/Network tab before a production run; the record-building + schema below are
source-independent and tested offline.

Run: python3 scrape_producers.py --source austrian_wine --max 200 --delay 1.5 \
            --vmp-index vmp_catalog_index.json --out seed_at.json
     python3 scrape_producers.py --source wosa --max 200 --out seed_za_scrape.json
"""
import os, sys, json, re, argparse, datetime

TODAY = datetime.date.today().isoformat()
UA = "tender-intel producer-seed/1.0 (+contact: set your email; respectful, rate-limited)"

SOURCES = {
    "austrian_wine": {
        "country": "Austria",
        "body": "Austrian Wine (Österreich Wein)",
        "base": "https://www.austrianwine.com",
        "search": "https://www.austrianwine.com/search/wine",
        # VERIFY against the live Network tab: the faceted search fires a JSON request.
        # Prefer it over DOM scraping. Fill in the real endpoint + params once confirmed.
        "api": None,   # e.g. "https://www.austrianwine.com/api/.../wineries?page={page}"
    },
    "wosa": {
        "country": "South Africa",
        "body": "Wines of South Africa (WoSA)",
        "base": "https://www.wosa.co.za",
        "search": "https://www.wosa.co.za/About-Us/WOSA-Members/",
        "api": None,
    },
}


def N(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()
                  .replace("ø", "o").replace("æ", "ae").replace("å", "a")
                  .replace("ö", "o").replace("ä", "a").replace("ü", "u").replace("ß", "ss"))


def load_vmp_index(path):
    if not path or not os.path.exists(path):
        return None
    d = json.load(open(path, encoding="utf-8"))
    return [(p.get("productId"), N(p.get("name"))) for p in d.get("products", [])]


def representation_no(producer, name, vmp):
    if vmp is None:
        return "candidate for import — VMP catalog check pending", False
    pTok = [t for t in N(producer).split() if len(t) >= 4]
    nTok = [t for t in N(name).split() if len(t) >= 4]
    for pid, hay in vmp:
        p = sum(t in hay for t in pTok)
        n = sum(t in hay for t in nTok)
        if (p >= 1 and n >= 1) or (not pTok and n >= 2) or (not nTok and p >= 2):
            return f"listed in VMP catalog (varenr {pid})", True
    return "unrepresented in NO — open for import", True


def parse_grapes(v):
    out = {}
    for name in re.split(r"[;,/]| und | and ", str(v or "")):
        name = name.strip()
        if name and not name.isdigit():
            out[name.lower()] = 0  # variety known; % pending producer
    return out


def to_record(item, src, idx, vmp):
    """item: {producer, name?, region?, grapes?, url?, certs?}. Source-independent + tested."""
    producer = str(item.get("producer") or "").strip()
    if not producer:
        return None
    name = str(item.get("name") or "").strip()
    rep_no, rep_verified = representation_no(producer, name or producer, vmp)
    status = "represented" if rep_verified and "listed in v" in rep_no.lower() else "open"
    url = str(item.get("url") or src["base"]).strip()
    body = src["body"]
    pub = lambda note: {"tier": "public", "note": f"{note} — {body}", "source": url}
    unk = lambda note: {"tier": "unknown", "note": note}
    certs = [c for c in (item.get("certs") or []) if c]
    return {
        "id": f"seed{src['country'][:2].upper()}s{idx:05d}",
        "producer": producer, "name": name or producer,
        "country": src["country"],
        "region": str(item.get("region") or "").strip(),
        "appellation": str(item.get("region") or "").strip(),
        "grapes": parse_grapes(item.get("grapes")),
        "method": None,
        "vintages_available": [],           # a lead commits no vintage
        "abv": None, "sugar_g_l": None, "wood": None,
        "certs": certs, "cert_on_label": bool(certs),
        "vines_age": None, "maceration_days": None,
        "volume_bottles": None, "fob_eur": None,   # producer only
        "color": "",
        "packaging": {"type": None, "weight_g": None},
        "representation": {"NO": rep_no, "SE": "unknown", "FI": "unknown"},
        "no_gap": status,
        "pending_claim": True,
        "source": f"seed: {body} (public directory) — {url}",
        "audit": {"created_by": f"seed:{body} (scrape)", "created_at": TODAY + "T00:00",
                  "updated_by": f"seed:{body} (scrape)", "updated_at": TODAY + "T00:00",
                  "note": "Public directory listing, UNVERIFIED, pending producer claim. "
                          "FOB, volume, exact grape % and analytical detail to be confirmed by the producer."},
        "verify": {
            "producer": pub("listed in the national body's producer directory"),
            "region": pub("stated in the directory") if item.get("region") else unk("region not listed"),
            "grapes": pub("varieties from the directory; exact % to be confirmed by producer")
                      if item.get("grapes") else unk("varieties to be confirmed by producer"),
            "representation": {"tier": "verified" if rep_verified else "unknown",
                               "note": "derived from the Vinmonopolet catalog index"},
            "certs": pub("certification from the directory") if certs else unk("no certification recorded"),
            "fob_eur": unk("ex-cellar price to be supplied by the producer"),
            "volume_bottles": unk("committed volume to be supplied by the producer"),
            "abv": unk("to be confirmed by producer / tech sheet"),
        },
    }


# ----------------------------------------------------------------------------
# Live collection (needs network + a real browser). Selectors marked VERIFY.
# Kept thin and isolated so record-building/schema above stay testable offline.
# ----------------------------------------------------------------------------
def collect_live(source_key, max_items, delay, log=print):
    import time
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright not available. Install it, or feed a --from-json export to --file.")
    src = SOURCES[source_key]
    items = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(user_agent=UA)
        page = ctx.new_page()

        # robots.txt courtesy check
        try:
            page.goto(src["base"] + "/robots.txt", timeout=20000)
            robots = page.inner_text("body")
            if re.search(r"(?im)^\s*disallow:\s*/\s*$", robots):
                log(f"  robots.txt disallows crawling {src['base']} — stopping. "
                    f"Request a data feed / partnership from {src['body']} instead.")
                browser.close(); return []
        except Exception:
            pass  # no robots.txt reachable — proceed politely

        # API-first if we have a confirmed endpoint
        if src.get("api"):
            page_no = 1
            while len(items) < max_items:
                page.goto(src["api"].format(page=page_no), timeout=30000)
                try:
                    data = json.loads(page.inner_text("pre") or page.inner_text("body"))
                except Exception:
                    break
                batch = data if isinstance(data, list) else (data.get("results") or data.get("items") or [])
                if not batch:
                    break
                for row in batch:
                    # VERIFY: map the real JSON field names once the endpoint is confirmed
                    items.append({"producer": row.get("name") or row.get("winery"),
                                  "region": row.get("region") or row.get("area"),
                                  "url": row.get("url"), "grapes": row.get("varieties")})
                    if len(items) >= max_items:
                        break
                page_no += 1
                time.sleep(delay)
        else:
            # DOM fallback — VERIFY these selectors against the live page structure.
            log(f"  no confirmed API for {source_key}; using DOM fallback. "
                f"VERIFY selectors against {src['search']} before trusting output.")
            page.goto(src["search"], timeout=30000)
            time.sleep(delay)
            # VERIFY: card/link selector for each producer in the directory
            cards = page.query_selector_all("a.producer, a.member, li.winery a, .search-result a")
            for c in cards[:max_items]:
                name = (c.inner_text() or "").strip()
                href = c.get_attribute("href") or ""
                if name:
                    items.append({"producer": name,
                                  "url": href if href.startswith("http") else src["base"] + href})
        browser.close()
    log(f"  collected {len(items)} raw listings from {src['body']}")
    return items


def load_json_items(path):
    d = json.load(open(path, encoding="utf-8"))
    return d if isinstance(d, list) else (d.get("items") or d.get("producers") or [])


def main():
    ap = argparse.ArgumentParser(description="Seed producers from a national wine-body directory.")
    ap.add_argument("--source", choices=list(SOURCES), help="which national body to scrape")
    ap.add_argument("--file", help="skip scraping; build records from a JSON export of listings")
    ap.add_argument("--max", type=int, default=200)
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests (be polite)")
    ap.add_argument("--vmp-index", default="vmp_catalog_index.json")
    ap.add_argument("--out", default="seed_scrape.json")
    args = ap.parse_args()

    if not args.source and not args.file:
        ap.error("give --source (to scrape) or --file (to build from an export)")
    # --file lets you attach a known source's schema; default to austrian_wine metadata
    src = SOURCES[args.source] if args.source else SOURCES["austrian_wine"]
    vmp = load_vmp_index(args.vmp_index)

    raw = load_json_items(args.file) if args.file else collect_live(args.source, args.max, args.delay)
    recs = [r for r in (to_record(it, src, i + 1, vmp) for i, it in enumerate(raw)) if r]
    unrep = sum(1 for r in recs if r["no_gap"] == "open")
    json.dump({"generated": TODAY, "source": f"{src['body']} (public directory)", "wines": recs},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(recs)} producer leads -> {args.out}  "
          f"({unrep} open{' — VMP index not loaded' if vmp is None else ''})")


if __name__ == "__main__":
    main()
