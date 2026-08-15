"""
verify_pricing.py — keep the price-band engine honest.

Two layers:

1. INTERNAL (deterministic, offline): re-derive Vinmonopolet's worked price example from
   pricing.py's constants and assert it still reproduces (199.90 kr → wholesale 80.67 kr, excise
   52.75, avanse 25.06, VAT 39.98). This proves the *model arithmetic* is intact. It does NOT
   prove the constants match the outside world — that's what layer 2 is for.

2. LIVE (best-effort, needs network): fetch the current figures from the actual sources and compare
   them to the constants baked into pricing.py:
     - alcohol excise for wine (4.7–22 % ABV) from Skatteetaten
     - Vinmonopolet's markup ("avanse") model from vinmonopolet.no
   A *confirmed* mismatch fails the run (the rates drifted — update pricing.py + the app's RATES).
   A fetch/parse failure only WARNS (sites restructure; that shouldn't red-build CI on its own).

Run:
    python3 verify_pricing.py --selftest   # layer 1 only, offline, deterministic
    python3 verify_pricing.py              # layer 1 + layer 2 (live)
    python3 verify_pricing.py --strict     # also fail when a live source can't be read

Rates change every January. When a live check reports drift, update the constants in BOTH
pricing.py and app_template.html (`const RATES = …`), rebuild, and re-run this.
"""
import argparse, re, sys, urllib.request

import pricing  # single source of truth for the constants + model

UA = "tender-intel pricing-verify/1.0 (+https://github.com/peachesandparsley/tender-intel)"

# Public sources. If a page moves, update the URL here and the parser below together — a fetch
# failure is reported, never silently ignored.
EXCISE_URL = "https://www.skatteetaten.no/en/rates/alcoholic-beverages/"
VMP_MARKUP_URL = "https://www.vinmonopolet.no/om-oss/drift/priser-og-avgifter"

TOL = 0.01   # a rate that differs by more than this is "drift", not rounding


def internal_selftest():
    """Layer 1: the model still reproduces Vinmonopolet's published worked example."""
    ws = pricing.wholesale_from_retail(199.90, 13.0, 0.75, "glass")
    ex = pricing.excise(13.0, 0.75)
    av = pricing.avanse(80.67, 0.75)
    r = pricing.retail_from_wholesale(80.67, 13.0, 0.75, "glass")
    checks = [
        ("wholesale 199.90 -> 80.67", ws, 80.67, 0.05),
        ("excise 13% 0.75L -> 52.75", ex, 52.75, 0.01),
        ("avanse @80.67 -> 25.06", av, 25.06, 0.01),
        ("retail 80.67 -> 199.90", r, 199.90, 0.05),
    ]
    ok = True
    for label, got, want, tol in checks:
        good = abs(got - want) <= tol
        ok = ok and good
        print(f"  [{'ok' if good else 'FAIL'}] {label}: got {got:.2f}, expect {want:.2f}")
    if not ok:
        print("INTERNAL model check FAILED — the arithmetic in pricing.py no longer reproduces the "
              "worked example. This is a code regression, not a rate change.")
    return ok


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def check_excise_live():
    """Layer 2a: Skatteetaten's wine excise (4.7–22 % ABV), NOK per volume-% per litre.
    Returns (status, detail) where status in {ok, drift, unavailable}."""
    try:
        html = _fetch(EXCISE_URL)
    except Exception as e:
        return "unavailable", f"could not fetch {EXCISE_URL}: {e}"
    text = re.sub(r"<[^>]+>", " ", html)                      # strip tags
    text = re.sub(r"\s+", " ", text).replace(" ", " ")
    # Find the wine bracket ("...4.7 up to and including 22 per cent...") and the rate near it.
    m = re.search(r"4[.,]7\D{0,60}22[^.]{0,120}?(\d{1,2}[.,]\d{2})", text)
    if not m:
        return "unavailable", ("fetched the page but couldn't locate the 4.7–22 % wine rate — "
                               "the page layout likely changed; update the parser in verify_pricing.py")
    rate = float(m.group(1).replace(",", "."))
    if abs(rate - pricing.EXCISE_PER_VOLPCT_L) <= TOL:
        return "ok", f"Skatteetaten wine excise {rate:.2f} == pricing.py {pricing.EXCISE_PER_VOLPCT_L:.2f}"
    return "drift", (f"Skatteetaten wine excise is {rate:.2f} kr/vol%/l, but pricing.py uses "
                     f"{pricing.EXCISE_PER_VOLPCT_L:.2f}. Update EXCISE_PER_VOLPCT_L (pricing.py) and "
                     f"RATES.excise (app_template.html).")


def check_vmp_markup_live():
    """Layer 2b: Vinmonopolet's markup constants (best-effort — VMP's page is prose, not a table).
    We confirm the per-litre and percentage figures still appear; we do not hard-parse a formula.
    Returns (status, detail)."""
    try:
        html = _fetch(VMP_MARKUP_URL)
    except Exception as e:
        return "unavailable", f"could not fetch {VMP_MARKUP_URL}: {e}"
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).replace(" ", " ")
    per_l = f"{pricing.AVANSE_PER_L:.2f}".replace(".", ",")   # NO decimals
    pct = f"{round(pricing.AVANSE_PCT * 100)}"
    seen_l = per_l in text or f"{pricing.AVANSE_PER_L:.2f}" in text
    seen_pct = re.search(rf"\b{pct}\s*(%|prosent)", text) is not None
    if seen_l and seen_pct:
        return "ok", f"Vinmonopolet page still shows {per_l} kr/l and {pct} % markup"
    return "unavailable", ("fetched the VMP page but couldn't confirm the markup constants "
                           f"({per_l} kr/l, {pct} %) — verify the avanse model manually at "
                           f"{VMP_MARKUP_URL}")


def main():
    ap = argparse.ArgumentParser(description="Verify the Vinmonopolet price-band engine.")
    ap.add_argument("--selftest", action="store_true", help="internal model check only (offline)")
    ap.add_argument("--strict", action="store_true", help="fail if a live source can't be read")
    args = ap.parse_args()

    print("Internal model check (offline):")
    if not internal_selftest():
        sys.exit(1)
    if args.selftest:
        print("Internal check passed.")
        return

    print("\nLive rate checks:")
    drift = False
    unavailable = False
    for name, fn in [("excise (Skatteetaten)", check_excise_live),
                     ("markup (Vinmonopolet)", check_vmp_markup_live)]:
        status, detail = fn()
        tag = {"ok": "ok", "drift": "DRIFT", "unavailable": "warn"}[status]
        print(f"  [{tag}] {name}: {detail}")
        drift = drift or status == "drift"
        unavailable = unavailable or status == "unavailable"

    if drift:
        print("\nRATE DRIFT detected — update the constants in pricing.py AND app_template.html "
              "(const RATES), rebuild, and re-run.")
        sys.exit(1)
    if unavailable and args.strict:
        print("\n--strict: a live source could not be verified.")
        sys.exit(1)
    print("\nAll resolvable checks passed."
          + (" (some live sources could not be read — see warnings)" if unavailable else ""))


if __name__ == "__main__":
    main()
