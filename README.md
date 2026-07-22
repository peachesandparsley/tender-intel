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
| `pricing.py` | Norwegian price/excise/avanse engine (2026 rates, verified) |
| `parse_lanseringsplan.py` | Parser for Vinmonopolet tender Excel files (both format generations) |
| `clauses.py` | Clause-level spec parsing (grapes, sugar, wood, certs, bottle weight…) |
| `match.py` / `match_wines.py` | Portfolio scoring and wine↔spec eligibility engines |
| `import_wines.py` | Producer bulk-upload validator |
| `ingest_vmp.py` | Populates the wine DB with **verified** data from Vinmonopolet's own catalog (API key or portal export); producer-only fields stay flagged for confirmation |
| `demand_map.py` | Ranks recurring tender demand (origin × grape × style × price × cert) → where to seed producers first (writes `demand_map.md`) |
| `gap_analysis.py` | Cross-plan **gap directory**: which origin × style × grape clusters are chronically re-requested (a proxy for unfilled lots — VMP doesn't publish awards) vs. how few known wines qualify. Ranks by gap score → where to focus. Writes `gap_analysis.md` + `.json`. Also a live tab in the app (Analytics) |
| `seed_producers.py` | Cold-starts the producer DB from **official** public sources (WoSA / WO scheme / IPW / WIETA), marked unverified-pending-claim; derives representation from the VMP index (see `SEED_SOURCES.md`) |
| `ingest_systembolaget.py` | Cross-monopoly seed (Sweden): turns the open Systembolaget assortment into supply-side leads — a wine listed in SE but not in VMP is a monopoly-proven, NO-unrepresented producer. Scores the NO gap at the **importer** level (`represented` / `pan_nordic` via Anora et al. / `open`) against the VMP index. Extracts real public grapes/certs/sugar; FOB/volume left for the producer |
| `ingest_alko.py` | Cross-monopoly seed (Finland): the Alko mirror of the above — joins Alko's price list with its supplier+importer list on product code, then scores the same NO gap (Anora/Altia is Finnish-origin, so `pan_nordic` matters most here) |
| `scrape_producers.py` | Seeds producers from a national body's **public directory** (Austrian Wine API-first, WoSA via Chromium) → same schema, representation derived from the VMP index. API-first, rate-limited, EU-database-right aware (see `SEED_SOURCES.md`) |
| `make_seed_sample.py` | Curates a capped, origin-diverse, English-normalised sample of the (large) seed files for the app to inline |
| `make_*_template.py` | Generators for the producer/importer Excel templates |
| `wines.json` | Wine records (real producers; estimates flagged in audit fields) |
| `specs_*.json` | Parsed tender plans: 2020-1, 2026-1, 2026-2, 2027-1 |
| `PRODUCT.md` / `DEPLOY.md` | Product blueprint and the Supabase production path |

## Rebuild after editing

```bash
python3 build_app.py   # regenerates index.html; needs package/dist/xlsx.full.min.js (npm pack xlsx@0.18.5)
```

`build_app.py` also inlines `seed_sample.json` (curated cross-monopoly supply-side
leads) into `WINES` alongside `wines.json`, normalising each to the full schema. The
leads are auto-badged (they carry `seed:` provenance) and shown as unverified,
pending-claim. Regenerate the sample with `make_seed_sample.py`, or let the
`refresh-seed-sample` workflow do it weekly.

Commit `index.html` and GitHub Pages redeploys automatically (~1 min).

## Working on this repo with Claude

Grant the Claude GitHub integration access to this repository, then in any new
Claude task say e.g. "work on peachesandparsley/tender-intel — add X". Claude
edits, rebuilds and pushes; the live site updates itself.
