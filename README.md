# Tender Intelligence

Nordic alcohol-monopoly tender matching: parses Vinmonopolet lanseringsplaner into
clause-level specs, matches wine records against them, washes matches against the
live catalog, and computes required producer FOB from retail price bands
(pricing model verified against Vinmonopolet's published example).

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
| `seed_producers.py` | Cold-starts the producer DB from **official** public sources (WoSA / WO scheme / IPW / WIETA), marked unverified-pending-claim; derives representation from the VMP index (see `SEED_SOURCES.md`) |
| `make_*_template.py` | Generators for the producer/importer Excel templates |
| `wines.json` | Wine records (real producers; estimates flagged in audit fields) |
| `specs_*.json` | Parsed tender plans: 2020-1, 2026-1, 2026-2, 2027-1 |
| `PRODUCT.md` / `DEPLOY.md` | Product blueprint and the Supabase production path |

## Rebuild after editing

```bash
python3 build_app.py   # regenerates index.html; needs package/dist/xlsx.full.min.js (npm pack xlsx@0.18.5)
```

Commit `index.html` and GitHub Pages redeploys automatically (~1 min).

## Working on this repo with Claude

Grant the Claude GitHub integration access to this repository, then in any new
Claude task say e.g. "work on peachesandparsley/tender-intel — add X". Claude
edits, rebuilds and pushes; the live site updates itself.
