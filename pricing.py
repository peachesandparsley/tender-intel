"""
Vinmonopolet price-band engine — 2026 rates (verified against Vinmonopolet's own
published example: kr 199.90 bottle, 13% ABV, 0.75 L, glass -> wholesale kr 80.67).

Sources:
- Vinmonopolet "Priser og avgifter" (avanse model per 2026-01-01)
- Skatteetaten excise rates 2026 (NOK 5.41 per volume-% per litre, 4.7-22% ABV)

Model (per sales unit):
  retail = (wholesale + excise + avanse + packaging) * 1.25   [25% VAT]

  excise    = abv_percent * litres * 5.41
  avanse    = 10.82 * litres + 0.21 * wholesale - reduction
  reduction = 0 if wholesale <= 133.70
              else 0.21 * wholesale * 0.5 * (1 - 133.70 / wholesale)
  avanse clamped to [4.00, 250.00]
  packaging: glass 1.45 | plastic/BiB 2.01 | metal(no deposit) 1.45 | carton 1.55
"""

from dataclasses import dataclass

VAT = 0.25
EXCISE_PER_VOLPCT_L = 5.41          # NOK, beverages >4.7% to 22% ABV (2026)
AVANSE_PER_L = 10.82                # NOK per litre
AVANSE_PCT = 0.21
AVANSE_KNEE = 133.70                # NOK wholesale price where reduction starts
AVANSE_MIN, AVANSE_MAX = 4.00, 250.00
PACKAGING = {"glass": 1.45, "plastic": 2.01, "bib": 2.01, "metal": 1.45, "carton": 1.55}


def excise(abv: float, litres: float) -> float:
    return abv * litres * EXCISE_PER_VOLPCT_L


def avanse(wholesale: float, litres: float) -> float:
    a = AVANSE_PER_L * litres + AVANSE_PCT * wholesale
    if wholesale > AVANSE_KNEE:
        a -= AVANSE_PCT * wholesale * 0.5 * (1 - AVANSE_KNEE / wholesale)
    return min(max(a, AVANSE_MIN), AVANSE_MAX)


def retail_from_wholesale(wholesale: float, abv: float, litres: float,
                          pack: str = "glass") -> float:
    pre_vat = wholesale + excise(abv, litres) + avanse(wholesale, litres) + PACKAGING[pack]
    return pre_vat * (1 + VAT)


def wholesale_from_retail(retail: float, abv: float, litres: float,
                          pack: str = "glass", tol: float = 0.001) -> float:
    """Invert numerically (avanse is piecewise but monotonic in wholesale)."""
    lo, hi = 0.0, retail  # wholesale can never exceed retail
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if retail_from_wholesale(mid, abv, litres, pack) < retail:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@dataclass
class LandedCostAssumptions:
    """From grossist net price (DDP Norway, ex-excise) back to producer FOB."""
    importer_margin_pct: float = 0.25   # importer gross margin on wholesale price
    freight_per_bottle: float = 6.0     # NOK, sea freight ZA->NO consolidated, incl. ins.
    handling_per_bottle: float = 3.0    # NOK, bonded 3PL in/out + EDI fees
    nok_per_zar: float = 0.58           # update at runtime
    nok_per_eur: float = 11.6


def fob_from_retail(retail: float, abv: float, litres: float, pack: str = "glass",
                    a: LandedCostAssumptions = LandedCostAssumptions()) -> dict:
    ws = wholesale_from_retail(retail, abv, litres, pack)
    ex = excise(abv, litres)
    av = avanse(ws, litres)
    fob_nok = ws * (1 - a.importer_margin_pct) - a.freight_per_bottle - a.handling_per_bottle
    return {
        "retail_nok": round(retail, 2),
        "wholesale_nok": round(ws, 2),
        "excise_nok": round(ex, 2),
        "avanse_nok": round(av, 2),
        "packaging_nok": PACKAGING[pack],
        "vat_nok": round(retail - retail / (1 + VAT), 2),
        "importer_gross_margin_nok": round(ws * a.importer_margin_pct, 2),
        "freight_handling_nok": a.freight_per_bottle + a.handling_per_bottle,
        "required_fob_nok": round(fob_nok, 2),
        "required_fob_zar": round(fob_nok / a.nok_per_zar, 2) if fob_nok > 0 else None,
        "required_fob_eur": round(fob_nok / a.nok_per_eur, 2) if fob_nok > 0 else None,
        "viable": fob_nok > 8.0,  # below ~8 NOK FOB no serious producer can supply
    }


if __name__ == "__main__":
    # --- Verification against Vinmonopolet's published example ---
    # kr 199.90 retail, 13% ABV, 0.75 L, glass => wholesale kr 80.67,
    # excise kr 52.75, avanse kr 25.06, VAT kr 39.98
    ws = wholesale_from_retail(199.90, 13.0, 0.75, "glass")
    assert abs(ws - 80.67) < 0.05, f"wholesale check failed: {ws}"
    assert abs(excise(13.0, 0.75) - 52.75) < 0.01
    assert abs(avanse(80.67, 0.75) - 25.06) < 0.01
    r = retail_from_wholesale(80.67, 13.0, 0.75, "glass")
    assert abs(r - 199.90) < 0.05, f"retail check failed: {r}"
    print("All checks against Vinmonopolet's official example PASSED")

    for band in [(129.9, 13.5), (169.9, 13.0), (199.9, 13.5), (249.9, 12.5), (349.9, 13.0)]:
        res = fob_from_retail(band[0], band[1], 0.75)
        print(f"retail {band[0]:>7.2f} kr @ {band[1]}% -> FOB {res['required_fob_nok']:>7.2f} NOK "
              f"= R{res['required_fob_zar']:>7.2f} = €{res['required_fob_eur']:>6.2f}  viable={res['viable']}")
