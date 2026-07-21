# Producer-seed sources — official only

Principle: the producer database is cold-started **only from official / authoritative
public sources**, and every seeded record is marked **unverified, pending producer
claim**. The tender-critical numbers a producer alone holds — ex-cellar FOB,
committed volume, exact grape %, residual sugar, wood regime, bottle weight — are
never seeded; the producer supplies them on claiming. Representation is *derived*
from the real Vinmonopolet catalog (not in the catalog → unrepresented), never
assumed.

**Seed broadly, not by grape.** Within an origin, seed the *whole* producer set
from its official body (WoSA lists every SA producer, not just the common
varieties) — the long-tail/niche tenders are exactly where competition is lowest
and an unrepresented producer most easily wins, so narrow seeding would throw away
the best opportunities. `demand_map.py` is for **sequencing origins and
prioritising active producer recruitment**, not a cap on what gets seeded.

Seed *order* by that map: South Africa first — it hits three recurring targets
(Syrah, Chenin, Cap Classique) and its certification bodies give *verifiable* cert
data for the lanes where a certification is the gate.

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

## How to find producer data — per origin (the actual access points)

Each origin's national body publishes a producer directory — that's the primary
seed source. Access differs: some are searchable databases, some annual
directories, and Italy/France are fragmented across regional bodies.

| Origin | Where to find producers | Access / note |
|---|---|---|
| **South Africa** | Wines of South Africa — `wosa.co.za` | producer directory; certs at `sawis.co.za` (IPW seal) + `wieta.org.za` |
| **Austria** | Austrian Wine — `austrianwine.com/wines-wineries` | **searchable DB, ~4,000 self-bottling producers** (confirmed) |
| **Germany** | Deutsches Weininstitut — `winesofgermany.com` | producer directory; VDP members at `vdp.de` |
| **New Zealand** | NZ Winegrowers — `nzwine.com` | member directory; SWNZ-certified flagged there |
| **Australia** | Wine Australia — `wineaustralia.com`; Winetitles Wine Industry Directory — `winetitles.com.au/industry-directory` | official body + a comprehensive directory (producers, varieties, GI) |
| **Portugal** | Wines of Portugal — `winesofportugal.com`; IVV — `ivv.gov.pt` | body directory; IVV holds official registers |
| **Spain** | Foods & Wines from Spain (ICEX) — `foodswinesfromspain.com`; each DO's Consejo Regulador | ICEX producer database + per-DO member lists |
| **Italy** | fragmented — the **Consorzio** for each DOC/DOCG (e.g. Consorzio Barolo Barbaresco), Federdoc, ISMEA | no single feed — go per recurring appellation |
| **France** | fragmented — regional **interprofessions** (CIVC Champagne, BIVB Burgundy, CIVB Bordeaux…); INAO — `inao.gouv.fr` (appellations) | go per recurring region |
| **Chile** | Wines of Chile — `winesofchile.org` | body directory |
| **USA** | Wine Institute (California) — `wineinstitute.org`; TTB COLA (labels) | body + label registry |

Fragmentation isn't as bad as it looks: for Italy/France the demand map already
tells you *which* appellations/regions recur (Champagne + Burgundy for FR;
Barolo/Langhe + Verdicchio for IT), so you only chase those consorzi/interprofessions.

## Certification registries — verifiable, any origin

Add (and later verify) cert flags with a real source + date:

| Cert | Registry | Access |
|---|---|---|
| EU organic | **TRACES** — official EU organic operators database | search operator by name/country |
| Fairtrade | **FLOCERT** — `flocert.net/fairtrade-customer-search`; Fairtrade Finder — `fairtrade.net` | search by name / country / FLOID |
| Biodynamic | **Demeter International** — `demeter.net` | certified producers, 65+ countries |
| Sustainability | Terra Vitis (FR) `terravitis.com` · HVE (FR) · SWNZ (`nzwine.com`) · Nachhaltig Austria · Sustainable Winegrowing Australia · IPW/SWSA (`sawis.co.za`) | per-scheme registers |

## Enrichment sources (secondary — licensed, and NOT for core specs)

Consumer wine apps (CellarTracker, Vivino, Vinify) came up as possible data. What
they actually offer, and why they're secondary here:

| App | Offers | Reality for us |
|---|---|---|
| **CellarTracker** | community ratings, tasting notes, wine metadata | personal/**non-commercial** licence; reuse/derivative works prohibited; no open API (needs a license/revenue agreement) |
| **Vivino** | huge ratings/reviews/prices | **no public API** (shut years ago); ToS **prohibits scraping** |
| **Vinify** | cellar management; **Liv-ex** market value | a tool, not a data feed; Liv-ex = fine/**investment** wine (narrow, mostly Bordeaux/Burgundy) |

Three reasons these are enrichment, not a source of truth:
1. **Not what tenders judge on.** Vinmonopolet judges *blind* on spec compliance +
   price. A Vivino/CellarTracker score doesn't make a wine eligible.
2. **Licensing, not scraping.** All three are proprietary and ToS-restricted;
   scraping them would violate the very "official/solid sources" rule this file
   sets. Use only via a formal agreement.
3. **Skew.** Ratings favour famous wines; Liv-ex covers investment wine — the
   opposite of the unrepresented long tail we care about.

Where they *can* help, via proper licensing, as a **secondary signal**: a
quality/credibility score to help an importer rank wines that already match, and a
market-price sanity check. Treat as phase-2, never as the spec source.

Legitimately-open metadata alternatives worth a look: **Wikidata** (open licence;
structured producer/region/variety) and **Wine-Searcher** (paid API; prices +
aggregated critic scores).

## Rules

- Prefer an official **data feed / export / partnership** over scraping. Check each
  body's terms of use; the trade bodies are distribution partners — approach them
  directly for a producer feed.
- A seeded record is a **lead, not a fact**: shown as unverified so an importer
  reads it as "worth confirming," and a producer is prompted to claim & complete it.
- Never seed FOB/volume/analytical data. If a source implies them, drop them —
  they must come from the producer.
