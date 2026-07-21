# Producer-seed sources

Principle: the producer database is cold-started from **authoritative public
sources** — official trade bodies, the national origin schemes, certification
registries, and the **open catalogs of the other Nordic monopolies** — and every
seeded record is marked **unverified, pending producer claim**. The tender-critical
numbers a producer alone holds — ex-cellar FOB, committed volume, exact grape %,
residual sugar, wood regime, bottle weight — are never seeded; the producer supplies
them on claiming. Representation is *derived* from the real Vinmonopolet catalog (not
in the catalog → unrepresented), never assumed.

Two ways in, both built:
- **Cross-monopoly** (`ingest_systembolaget.py`, `ingest_alko.py`): a wine listed in
  Sweden/Finland but absent from Vinmonopolet is a monopoly-proven producer that is
  unrepresented in Norway — a high-quality lead with real specs (grapes, certs, sugar,
  region, ABV) already attached. This is the strongest cold-start: structured, official,
  free, pre-vetted by another monopoly.
- **Directory** (`seed_producers.py`, `scrape_producers.py`): the national wine bodies'
  own producer directories — the primary identity/region/variety source per origin.

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

## Scraping public directories — the balanced stance

Scraping the national bodies' **public, factual producer directories** to bootstrap a
lead list is legitimate and normal — the bodies publish them precisely so buyers find
their producers. It is not the "last resort" an earlier version of this file implied.
Do it the right way (`scrape_producers.py` implements this):

1. **API-first.** A faceted search UI (e.g. Austrian Wine's `/search/wine`) is backed
   by a JSON endpoint — take that structured feed rather than parsing rendered HTML.
   Check the browser Network tab to find it.
2. **Use a real browser, politely.** These sites sit behind bot protection (both
   austrianwine.com and wosa.co.za return 403 to plain HTTP clients). Drive a real
   Chromium via Playwright, set an honest User-Agent, and rate-limit (`--delay`).
   Respect `robots.txt` and each site's terms.
3. **Mind the EU database right.** The EU Database Directive gives the *maker of a
   database* a sui-generis right against extraction of a **substantial part**, even of
   non-copyrightable facts. Vacuuming an entire EU directory wholesale is the risk zone;
   the safe pattern is **identify** producers from the directory, then pull detail from
   each producer's **own** site / by contacting them. (WoSA/South Africa is outside this
   regime — its ToS is the thing to check there.)
4. **It only fills the lead layer.** Scraping yields identity, region, variety, website —
   never FOB, volume, exact grape %, sugar, wood or bottle weight. So a scraped record is
   still unverified and pending producer claim; scraping widens the top of the funnel, it
   does not shortcut verification.

A trade body is also a **distribution partner**: for anything beyond public identity,
approach them directly for a producer feed — many will give one because being found by
importers is their mission.

## Rules

- **API/feed/partnership first, respectful scraping second, wholesale extraction never.**
  For public identity data, scraping a directory the right way (above) is fine; for
  substantial datasets or anything an EU database right covers, get a feed/partnership.
- A seeded record is a **lead, not a fact**: shown as unverified so an importer
  reads it as "worth confirming," and a producer is prompted to claim & complete it.
- Never seed FOB/volume/analytical data. If a source implies them, drop them —
  they must come from the producer.
- Certification and residual-sugar flags that a monopoly *publishes* (Systembolaget's
  `isOrganic`/`ethicalLabel`, Alko's `luomu`) are verifiable public facts and ARE
  seeded — they're often literal tender gates. They remain unverified-for-NO until the
  producer confirms.
