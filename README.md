# Tender Intelligence

Nordic alcohol-monopoly tender matching: parses Vinmonopolet lanseringsplaner into
clause-level specs, matches wine records against them, washes matches against the
live catalog, and computes required producer FOB from retail price bands
(pricing model verified against Vinmonopolet's published example).

Two role-based entry points sit at the front of the app:

- **Opportunities** (importers) — tenders ranked by an opportunity score
  (unrepresented candidates / introductions, margin headroom, deadline proximity),
  each carrying an **evidence-strength** indicator (how sourced/verified the
  candidates behind the score are). Expand a tender for the best-matched wines, their
  economics and NO status; star candidates into a shortlist, export it as CSV, and
  pull a **calendar (.ics) of deadline reminders**. The buy-side value that justifies
  paying.
- **Match my wine** (producers) — no upload needed: describe a wine (or click a real
  lead) and instantly see which tenders it can win, the FOB to hit, and how many
  wines are *listed so far* for it (an honest marketplace-visibility count, not a
  claim of no competition). Then **claim & complete the profile** — fill the fields
  only a producer holds (FOB, volume, grape %, sugar, wood, vintages), which flips the
  wine from unconfirmed lead to sourced data and raises its evidence strength. This is
  the discovery hook *and* the mechanism for getting accurate data into the pool.

**Live app:** `index.html` — a fully self-contained single-page app (no server,
works offline). Served via GitHub Pages at the repository's Pages URL.

## Structure

| File | Purpose |
|---|---|
| `index.html` | The built app (everything inlined: engines, data, SheetJS, world map) |
| `app_template.html` | App source template — edit this, then rebuild |
| `build_app.py` | Assembles `index.html` from the template + data files |
| `pricing.py` | Norwegian price/excise/avanse engine. Model reproduces Vinmonopolet's worked example; rate constants are Jan-2026 and re-confirmed by `verify_pricing.py` |
| `verify_pricing.py` | Keeps the calculator honest: a deterministic internal check (the model still reproduces VMP's example) **plus** a live check that fetches Skatteetaten (wine excise) and Vinmonopolet (markup) and fails on confirmed rate drift. The `verify-pricing` workflow runs it monthly |
| `parse_lanseringsplan.py` | Parser for Vinmonopolet tender Excel files (both format generations) |
| `parse_launch_list.py` | Parser for Vinmonopolet's historical **launch lists** (`data-from-vinmonopolet/*.xlsx`) — what actually got listed, one row per product: producer, origin (to vineyard), classification, vintage, ABV, **real retail price**, quantity, per-store allocation, and the importer. Consolidates all 82 files (2020→) into `launch_history.json` (~12k products) |
| `market_index.py` | Distils `launch_history.json` into a compact `market_index.json` the app embeds: real price quartiles, typical volume, vintages, top producers **and importers** by origin × style (and × classification, and by appellation), the importer landscape, and the 6-year price/volume trend. Every benchmark rests on ≥ 5 real launches |
| `clauses.py` | Clause-level spec parsing (grapes, sugar, wood, certs, bottle weight…) |
| `match.py` / `match_wines.py` | Portfolio scoring and wine↔spec eligibility engines |
| `import_wines.py` | Producer bulk-upload validator |
| `ingest_vmp.py` | Populates the wine DB with **verified** data from Vinmonopolet's own catalog (API key or portal export); producer-only fields stay flagged for confirmation |
| `fetch_launch_plans.py` | Downloads Vinmonopolet launch-plan Excel files (from `plan_urls.txt` or the known pages) and parses them to `specs_*.json` → thickens the recurrence/gap data. Runs where vinmonopolet.no is reachable (your machine / the `refresh-launch-plans` workflow) |
| `track_listings.py` | Diffs the daily Open-API catalog snapshots into a listing-date ledger (`vmp_listings.json`: first_seen / last_seen per product). Forward-looking evidence for a real fill-rate — cross-reference a new listing's date with a tender's launch month to see which lots actually got filled (see the fill-rate note below) |
| `demand_map.py` | Ranks recurring tender demand (origin × grape × style × price × cert) → where to seed producers first (writes `demand_map.md`) |
| `gap_analysis.py` | Cross-plan **gap directory**: which origin × style × grape clusters are chronically re-requested (a proxy for unfilled lots — VMP doesn't publish awards) vs. how few known wines qualify. Ranks by gap score → where to focus. Writes `gap_analysis.md` + `.json`. Also a live tab in the app (Analytics) |
| `seed_producers.py` | Cold-starts the producer DB from **official** public sources (WoSA / WO scheme / IPW / WIETA), marked unverified-pending-claim; derives representation from the VMP index (see `SEED_SOURCES.md`) |
| `ingest_systembolaget.py` | Cross-monopoly seed (Sweden): turns the open Systembolaget assortment into supply-side leads — a wine listed in SE but not in VMP is a monopoly-proven, NO-unrepresented producer. Scores the NO gap at the **importer** level (`represented` / `pan_nordic` via Anora et al. / `open`) against the VMP index. Extracts real public grapes/certs/sugar; FOB/volume left for the producer |
| `ingest_alko.py` | Cross-monopoly seed (Finland): the Alko mirror of the above — joins Alko's price list with its supplier+importer list on product code, then scores the same NO gap (Anora/Altia is Finnish-origin, so `pan_nordic` matters most here) |
| `scrape_producers.py` | Seeds producers from a national body's **public directory** (Austrian Wine API-first, WoSA via Chromium) → same schema, representation derived from the VMP index. API-first, rate-limited, EU-database-right aware (see `SEED_SOURCES.md`) |
| `make_seed_sample.py` | Curates a capped, origin-diverse, English-normalised sample of the (large) seed files (offline analysis input for `gap_analysis.py` — **not** inlined into the app; the app ships with no seed wines) |
| `make_*_template.py` | Generators for the producer/importer Excel templates |
| `specs_*.json` | Parsed tender plans: 2020-1, 2026-1, 2026-2, 2027-1 |
| `PRODUCT.md` / `DEPLOY.md` | Product blueprint and the Supabase production path |

## Rebuild after editing

```bash
python3 build_app.py   # regenerates index.html; needs package/dist/xlsx.full.min.js (npm pack xlsx@0.18.5)
```

**The app ships with no seed wines.** The wine side is filled by users adding their own
portfolios — the real ex-cellar price (FOB) and all — matched against the real tender data.
Seed leads (Systembolaget open-data wines, Wikidata producers, the old Claude-generated
`wines.json`) were removed: they were either invented, or cosmetic (already commercialised
elsewhere, no FOB, not genuine introduction opportunities). If a real, sourced `wines.json`
is ever added it is embedded; otherwise `WINES` starts empty and grows as producers and
importers add their portfolios.

Commit `index.html` and GitHub Pages redeploys automatically (~1 min).

## Demand intelligence (built for five years of plans)

The Analytics tab reads every loaded plan **in chronological order** and profiles demand at
an *actionable* grain — **sub-region × style × grape × price band** (e.g. `Chablis ·
Chardonnay · 200–350 kr`), not the useless `France · white`. For each profile it reports how
often it recurs, its **trend** (↗ emerging / ● persistent / ↘ fading, from the plans' time
order), how recently it was asked, and how often it also carries a certification requirement.
The same signal rides as a ↻/↗ badge on every tender in the browse table and match results.

This is deliberately **thin at 3–4 plans and comes into its own across ~10** (five years of
half-yearly plans): granular profiles only start recurring — and trends only become real —
with that much history. The engine (`profileKey` / `demandRows` / `trendOf` in
`app_template.html`) scales to any number of plans with no code change. Feed it history via the
section below.

## Market benchmark — grounded in six years of actual launches

Vinmonopolet's historical **launch lists** (not the tender requests — what actually got listed and
sold) are the strongest data in the app. `parse_launch_list.py` consolidates every file in
`data-from-vinmonopolet/` into `launch_history.json`; `market_index.py` distils that into the compact
`market_index.json` the build embeds.

This launch history powers five things across the app:

- **Market benchmark** (in *Match my wine*) — describing a wine surfaces what comparable wines *actually
  retailed at* (25th / median / 75th-percentile real prices), typical volume, vintage span, the
  most-launched producers, and **the importers behind them**. Give a **district / appellation** and it
  sharpens to appellation level (Burgundy, not "France red") — English/French names are aliased to the
  list's Norwegian spellings.
- **Market** tab — browse the whole dataset: the six-year premiumisation trend (median launch price
  kr 755→1003, +33%) and a filterable benchmark table by origin × style *and* by appellation × style,
  each row expandable to its top producers and importers.
- **Importers / Producers** tab — a dual finder over the launch history. *Importers*: every importer's
  whole book (origins and styles they bring in, price tier, median volume, active years) — a producer's
  route to market, an importer's view of the competition; corporate-suffix variants ("Nafstad" /
  "Nafstad AS") are merged. *Producers*: every producer's actual Vinmonopolet track record — what
  launched, at what prices, in which styles/districts, over which years, and which importers carried
  them. Producer is recorded on ~100% of rows, so a producer can reliably look themselves (or a rival) up.
- **Backtest** — each historically-matched tender now carries the real market price band for its
  origin × style.
- **Analytics** — every recurring demand profile is annotated with real **supply** (how many
  comparable wines actually launched, and their median price) — demand and supply side by side, no
  fabricated ratio.

**Honest coverage.** Importer is recorded on only ~15% of launches (mostly the spirits lists), so every
importer display carries a caveat ("importer recorded on N of M launches") — it's who's *named*, not the
whole field. Every benchmark states its sample size; buckets with fewer than five real launches are never
shown. `parse_launch_list.py` self-audits on every run (per-file rows, and a warning for any content sheet
with no detectable header) so a reimport can't silently drop data.

To refresh after adding more launch lists:

```bash
python3 parse_launch_list.py    # data-from-vinmonopolet/*.xlsx -> launch_history.json
python3 market_index.py         # launch_history.json -> market_index.json
python3 build_app.py            # embeds it into index.html
```

## Thicken the database with more launch plans

Launch plans are **auto-discovered** — every `specs_*.json` in the repo is embedded
(newest tagged "(live)"), and each one deepens the demand-intelligence, gap and trend stats.
To add a historical plan:

1. Download the Excel from Vinmonopolet's launch-plan archive (the **Lanseringer**
   section on vinmonopolet.no; English editions are published alongside the Norwegian
   ones, back through 2022, both halves). Grab the real download link from the site — the
   exact archive path isn't hard-coded here so nothing is guessed.
2. Parse it: `python3 parse_lanseringsplan.py <plan.xlsx> -o specs_YYYY_H.json`
   (the parser handles both format generations).
3. `python3 build_app.py` — it's picked up automatically. Commit the new
   `specs_*.json` + `index.html`.

**Hands-off option:** `fetch_launch_plans.py` downloads + parses plans automatically (on
a machine that can reach vinmonopolet.no). Paste the direct `.xlsx` links into
`plan_urls.txt` (most reliable — the site is a SPA), or let it try the known plan pages;
the `refresh-launch-plans` workflow runs it monthly and commits any new plans + rebuilt
app. See `plan_urls.txt` for how to grab the links.

## From gap proxy to real fill-rate

`gap_analysis.py` currently proxies "unfilled" with **re-request recurrence** because
Vinmonopolet publishes what it asks for, not which lots were awarded. The Open API
(`products-v0`, no application needed — see `vinmonopolet.no/om-oss/presse/datadeling`)
closes the loop with **listing dates**:

1. `track_listings.py` records when each product first appears in the catalog (via daily
   snapshot diffs; the monthly sales-per-article feed is an alternative first-sale-month
   signal). Runs in the `refresh-vmp-index` workflow once `VMP_API_KEY` is set.
2. Cross-reference a new listing's date with a tender's **launch month**: a product
   appearing in the launch window ⇒ that lot was filled; a lot whose category gets no
   matching new listing ⇒ unfilled.

Two honest limits: it is **forward-only** (no historical snapshots for past plans), and
attributing a listing to a specific *lot* needs the product's origin/grape/price — the
**Restricted** tier (or the public product page). Category-level fill (origin × style
counts vs. demand) is computable from Open data alone.

## Working on this repo with Claude

Grant the Claude GitHub integration access to this repository, then in any new
Claude task say e.g. "work on peachesandparsley/tender-intel — add X". Claude
edits, rebuilds and pushes; the live site updates itself.
