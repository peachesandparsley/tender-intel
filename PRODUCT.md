# Tender Intelligence — Product Blueprint
### Working title: the tender-matching platform for Nordic alcohol monopoly suppliers
*Drafted July 2026. Status: engine prototyped and validated on real Vinmonopolet data.*

---

## 1. One-paragraph thesis

The Nordic alcohol monopolies (Vinmonopolet, Systembolaget, Alko) are the only major
retail buyers on earth that publish exactly what they want to buy — origin, style,
certifications, price band — on a fixed schedule, and judge submissions blind. Hundreds
of importers and thousands of producers compete for those tenders using spreadsheets
and folklore. The product ingests every published tender, maintains verified producer/
wine data, and tells each subscriber which tenders they can win, with the price math
solved. Most tender losses are price-band misses, not quality misses; the product
eliminates that entire failure class.

## 2. What exists today (validated prototype)

- **Ingestion**: parser handling Vinmonopolet's real tender format (validated on the
  actual 2020-1 file: 94/94 specs parsed), tolerant of layout drift and both languages.
- **Pricing engine**: full Norwegian retail-price decomposition (excise, avanse model
  with knee and cap, VAT, packaging), verified to the øre against Vinmonopolet's own
  published example. Reverse-solves required producer FOB from any price band.
- **Matching engine**: origin-agnostic portfolio matching. Each subscriber's portfolio
  (producers with origin terms, style tags, certifications, price floors) is scored
  per spec; proven on real data (an Austrian producer in the test portfolio surfaced
  the two real Austrian tenders in the 2020-1 plan; certification requirements in specs
  match producers holding those certs).
- **UI**: single-page dashboard — ranked winnable specs with per-spec reasoning,
  interactive FOB calculator, portfolio view. Light/dark, accessible palette.

## 3. Who pays, and for what

| Segment | Size (est.) | Pain | Willingness to pay |
|---|---|---|---|
| Norwegian importers/grossister | ~200 active | Manual spec-watching, price-band errors | Core: NOK 800–2,000/mo |
| Swedish importers (Systembolaget) | ~500+ | Same, larger market | Same tier |
| Finnish importers (Alko) | ~150 | Same | Same tier |
| Producers/export managers (global) | thousands | Zero visibility into Nordic tenders | Freemium → €50–150/mo alerts |
| Producer-country trade bodies (Wines of X, chambers) | dozens | Members ask "how do we get into Systembolaget?" | Group licenses |

Importers first (they act on every plan, money on the line per tender, trivially
positive ROI on one won listing). Producers second, *free profiles first* — their
self-maintained data is the asset; charging them for visibility too early poisons
signal quality. Trade bodies are the distribution hack into the producer side.

## 4. Product architecture

```
┌────────────────────────────────────────────────────────────┐
│ INGESTION (per monopoly adapter)                           │
│  VMP: lanseringsplan xlsx 2×/yr + partiutvalg + catalog    │
│  SYB: offertförfrågningar (rolling) + catalog API          │
│  ALKO: purchase plans + catalog                            │
│  → normalized spec schema (the v2 parser's schema)         │
├────────────────────────────────────────────────────────────┤
│ DATA / VERIFICATION LAYER                                  │
│  Producer profiles: pre-built from public data, then       │
│  claimed & corrected by producers ("verified" flags with   │
│  sources: cert registries, existing monopoly listings,     │
│  published prices, competition results)                    │
│  Historical spec DB: every plan ever published →           │
│  recurrence & price-band analytics (the moat)              │
├────────────────────────────────────────────────────────────┤
│ MATCHING & PRICING ENGINE (exists)                         │
│  per-market price decomposition (NO done; SE/FI: flat      │
│  per-litre excise + Systembolaget/Alko markup models)      │
│  portfolio × spec fit scoring with reasons                 │
├────────────────────────────────────────────────────────────┤
│ DELIVERY                                                   │
│  Importer dashboard + email/Slack alerts on new plans      │
│  Producer alerts: "a tender matching your wines opened"    │
│  Matchmaking: importer without a producer for a winnable   │
│  spec ↔ producer without an importer (introduction fee)    │
└────────────────────────────────────────────────────────────┘
```

An LLM layer (Claude) earns its place in three spots: parsing free-text spec clauses
into structured requirements (the "1) ... 2) ..." lists), auto-drafting producer
profiles from scattered public sources, and generating per-tender briefing memos
("why you, why this price, what to submit"). All three are assistive, with the
structured engine as ground truth — never the reverse.

## 5. The moat, ranked

1. **Historical spec database** — no one else has collected every plan since 20xx;
   recurrence analytics ("Austrian grüner appears in 70% of H1 plans, band drifting
   +15 kr/yr") only exist if you started collecting first.
2. **Verified producer data** — registry-anchored, producer-corrected, importer-trusted.
   Slow to build, slow to copy.
3. **Being the operating insider** — credibility with both sides (founder runs real
   tenders through the same engine).
4. Software itself — thin moat; assume it gets copied.

## 6. Honest risk register

- **Market size ceiling**: ~1,000 paying importers across three countries at best.
  This is a €0.5–1.5M ARR business at maturity, not venture-scale. Fine if intended.
- **Monopoly format/policy changes**: adapters must be maintained; a monopoly could
  launch its own matching portal (unlikely — procurement neutrality — but possible).
- **Data licensing**: monopoly catalogs are public; Platter's/ratings data needs
  licensing if used. Cert registries are lookup-able but scraping ToS need checking.
- **Two-sided timing**: producer side is eager (monopoly listing is transformative),
  so noise, not scarcity, is the risk — gatekeep quality from day one.
- **Founder time**: competes with the import business itself. Mitigation: the tool IS
  the import business's back office; productize only after it wins real tenders.

## 7. Roadmap

**Phase 0 — now (done):** engine + dashboard, validated on real data.
**Phase 1 — dogfood (3–6 mo):** collect all obtainable historical plans; run the
importer's own tenders through it; build Systembolaget adapter (their
offertförfrågningar are rolling — better cadence for alerts than VMP's 2×/yr).
**Phase 2 — first customers (6–12 mo):** 5–10 Norwegian/Swedish importers at founder
pricing; email alerts; per-market pricing engines complete; historical analytics v1.
**Phase 3 — producer side (12–18 mo):** free claimed profiles, producer alerts,
first trade-body deal; matchmaking introductions.
**Phase 4 — expand or hold:** Iceland/Faroes (ÁTVR/Rúsdrekkasøla), Canada (LCBO/SAQ
publish similar tender calls — a 10× market with the same product), or stay Nordic
and profitable.

## 8. Immediate next actions

1. Collect historical lanseringsplaner (Vinmonopolet archive pages, Wayback Machine,
   importer contacts) → seed the historical DB.
2. Systembolaget adapter: their launch plan + offert format.
3. Excise/markup models for SE and FI in `pricing.py` (config per market).
4. Producer-profile auto-enrichment prototype against public monopoly catalogs.
5. Name, domain, and a one-page site with a waitlist form.
