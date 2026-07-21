# From single-file demo to real product — deployment guide

The HTML app proves the logic. Making it real means adding the four things a
single file can't have: **persistence, accounts, background jobs, payments.**
Recommended stack: Supabase + Vercel — both have free tiers that carry you to
your first paying customers.

## Step 1 — Supabase project (~1 hour)

Create a project at supabase.com (EU region — Frankfurt/Stockholm — for GDPR
locality). You get Postgres, auth, storage and edge functions in one.

Core schema (SQL editor, adapt from the JSON shapes already in the code):

```sql
create table organizations (            -- importers & producers
  id uuid primary key default gen_random_uuid(),
  kind text check (kind in ('importer','producer')),
  name text not null, country text, created_at timestamptz default now()
);
create table profiles (                 -- users, linked to Supabase auth
  id uuid primary key references auth.users,
  org_id uuid references organizations, role text default 'member'
);
create table plans (                    -- one row per lanseringsplan file
  id uuid primary key default gen_random_uuid(),
  monopoly text check (monopoly in ('VMP','SYB','ALKO')),
  period text, source_file text, uploaded_at timestamptz default now()
);
create table specs (                    -- parsed tender specifications
  id uuid primary key default gen_random_uuid(),
  plan_id uuid references plans, ref text, launch text, selection text,
  main_type text, "group" text, country text, region text, appellation text,
  spec text, vintage text, litres numeric, price_text text,
  price_lo numeric, price_hi numeric, deadline date, quality text,
  clauses jsonb                          -- output of the clause parser
);
create table wines (                    -- the marketplace listing unit
  id uuid primary key default gen_random_uuid(),
  producer_org uuid references organizations,
  producer_name text, name text, country text, region text, appellation text,
  grapes jsonb, method text, vintages int[], abv numeric, sugar_g_l numeric,
  wood text, certs text[], cert_on_label bool, vines_age int,
  maceration_days int, volume_bottles int, fob_eur numeric,
  representation jsonb, color text,
  verified jsonb default '{}',           -- field -> {source, checked_at}
  source text, created_at timestamptz default now()
);
create table matches (                  -- cached eligibility results
  spec_id uuid references specs, wine_id uuid references wines,
  passes int, unknowns int, price_ok bool, verdicts jsonb,
  primary key (spec_id, wine_id)
);
create table introductions (            -- the billable handshake
  id uuid primary key default gen_random_uuid(),
  spec_id uuid references specs, wine_id uuid references wines,
  importer_org uuid references organizations,
  status text default 'requested',       -- requested/accepted/submitted/won
  created_at timestamptz default now()
);
```

**Row-level security (the part not to skip):** enable RLS on every table.
Specs and plans: readable by any authenticated user. Wines: producers write
only rows where `producer_org = their org`; importers read all. Matches:
readable by subscribers. Introductions: visible only to the two parties.
FOB prices are the sensitive field — consider a `fob_visible_to` policy
(e.g. hidden until an introduction is accepted).

## Step 2 — Port the engines (~a day)

Everything in the app's `<script>` is already the product logic in JS:
pricing, clause parser, eligibility engine, plan parser, producer-file
validator. They move unchanged into either:
- **Supabase Edge Functions** (Deno/TS) for server-side matching on upload, or
- a thin **Next.js** app (deployed on Vercel) that imports them as modules.

Recompute `matches` whenever a plan or wine changes (a Postgres trigger
calling an edge function, or a queue). The Excel producer-upload flow becomes:
upload to Supabase Storage → edge function parses/validates (same code) →
inserts wines → returns the same per-row report.

## Step 3 — Ingestion jobs (~a day)

A scheduled job (Supabase cron or GitHub Actions):
- **VMP:** poll the lanseringer pages twice daily; new xlsx → parse → insert plan+specs. (Server-side fetching of the CDN works fine outside this sandbox.)
- **SYB/ALKO:** same pattern once those adapters are written (Systembolaget's rolling offer requests make this a real-time alert product).
- **Catalog sync:** nightly pull of Vinmonopolet's open product API → seed/refresh producer skeletons and importer portfolios, and join launches back to specs for the win-analytics layer.
- **Alerts:** on new specs, email every org whose wines/portfolio match (Resend or Postmark; both trivial from an edge function).

## Step 4 — Auth, payments, hosting (~a day)

- **Auth:** Supabase magic-link email auth (wine trade hates passwords). Org invite flow: first user creates the org, invites colleagues.
- **Payments:** Stripe Checkout + customer portal. Two products: importer subscription (monthly, ~NOK 990–1,990), producer premium (later — keep free at launch). Gate premium API routes on `stripe_subscription_status`.
- **Hosting:** Vercel for the Next.js front end; custom domain (~150 kr/yr). The current HTML app doubles as a public read-only demo — a great landing page asset.

## Step 5 — Legal & practical (before charging money)

- Norwegian AS or ENK for invoicing; MVA registration past 50k NOK revenue.
- Terms: you republish public tender data (fine) but add a disclaimer that the monopoly's own documents are authoritative.
- GDPR: EU-hosted Supabase + a standard DPA (they provide one). You store business contact data only.
- Trademark check on the product name before buying the domain.

## Cost reality

Supabase free tier + Vercel free tier + domain ≈ **under 500 kr/year** until you
have real traffic. First paid tiers (~$25/mo Supabase Pro) only when customers
arrive. The expensive ingredient is your time; the infrastructure is nearly free.

## Sequence

1. Supabase project + schema + RLS (day 1)
2. Next.js shell with auth, port engines, wire the three flows that already work in the demo: plan upload, producer upload, marketplace view (week 1)
3. VMP ingestion cron + email alerts (week 2)
4. Load 2027-1 live plan + historical archive; invite 3–5 friendly importers free (week 3+)
5. Stripe when someone asks "what does it cost?" — the correct moment to add billing
