# Producer-seed sources — official only

Principle: the producer database is cold-started **only from official / authoritative
public sources**, and every seeded record is marked **unverified, pending producer
claim**. The tender-critical numbers a producer alone holds — ex-cellar FOB,
committed volume, exact grape %, residual sugar, wood regime, bottle weight — are
never seeded; the producer supplies them on claiming. Representation is *derived*
from the real Vinmonopolet catalog (not in the catalog → unrepresented), never
assumed.

Seed order follows `demand_map.py` (what tenders actually ask for, repeatedly).
South Africa is first: it hits three recurring targets (Syrah, Chenin, Cap
Classique) and its certification bodies give *verifiable* cert data for the lanes
where a certification is the gate.

## South Africa (built — `seed_producers.py`)

| Data | Official source | Access | Note |
|---|---|---|---|
| Producer & wine identity, region | **Wines of South Africa (WoSA)** — wosa.co.za | published producer directory | also the trade body = a distribution channel to producers |
| Origin / vintage / variety guarantee | **Wine of Origin (WO) scheme**, Wine & Spirit Board (WSB) | on-label guarantee since 1974; seal-verifiable | authoritative for region + variety |
| Sustainability certification (IPW) | **Sustainable Wine SA (SWSA) / IPW** — seal lookup at **sawis.co.za** | enter the seal number → traces the bottle | >95% of SA growers/cellars certified; seal number makes it *verified*, not just public |
| Ethical-trade certification | **WIETA** — wieta.org.za | certified-member list | or **Fairtrade** via FLOCERT |
| Industry statistics + seal verification | **SAWIS** — sawis.co.za | public | backs the IPW seal check |

Provenance written per field: identity/region → `public` (WoSA) or `verified`
(WO scheme); certs → `verified` when an IPW seal number is present, else `public`;
representation → `verified` (derived from the VMP index); FOB/volume/grape %/ABV →
`unknown`, pending claim.

## Next origins (from the demand map) — official bodies to source from

| Origin | Recurring targets | Trade body (identity/region) | Classification | Sustainability / cert |
|---|---|---|---|---|
| **Germany** | Riesling, Pinot Noir | Deutsches Weininstitut (deutscheweine.de) | VDP (vdp.de); Prädikat/GG | EU organic (TRACES), Fair'n Green |
| **Austria** | Riesling/Grüner (cert-heavy) | Austrian Wine (austrianwine.com) | DAC | Nachhaltig Austria; EU organic |
| **New Zealand** | Pinot Noir, Sauvignon Blanc | NZ Winegrowers (nzwine.com) | GI | Sustainable Winegrowing NZ (SWNZ) |
| **Portugal** | Encruzado, sparkling | ViniPortugal (viniportugal.pt); IVV | DOC/DOP via regional CVRs | EU organic |
| **France** | sparkling Chardonnay, Cab Franc, Mondeuse | official interprofessions (CIVC, etc.) | AOC/AOP (INAO) | EU organic, Terra Vitis, HVE |

Cross-origin certification registries (authoritative, verifiable):
EU organic — TRACES / EU organic certificate database · Fairtrade — FLOCERT ·
Biodynamic — Demeter.

## Rules

- Prefer an official **data feed / export / partnership** over scraping. Check each
  body's terms of use; the trade bodies are distribution partners — approach them
  directly for a producer feed.
- A seeded record is a **lead, not a fact**: shown as unverified so an importer
  reads it as "worth confirming," and a producer is prompted to claim & complete it.
- Never seed FOB/volume/analytical data. If a source implies them, drop them —
  they must come from the producer.
