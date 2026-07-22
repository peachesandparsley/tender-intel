"""
track_listings.py — a listing-date ledger for Vinmonopolet, from Open data only.

Vinmonopolet's Open API tells you a product's id, name and lastChanged — but not a
clean "first listed" date, and nothing about which tender a product came from. The
robust way to get listing dates without the Restricted tier is to DIFF the daily Open
catalog snapshots our refresh-vmp-index workflow already pulls: a productId that
wasn't in yesterday's index but is in today's was listed today.

This maintains vmp_listings.json — { productId: {name, first_seen, last_seen, delisted} }
— and prints what was newly listed / delisted since the last run. Over time this is the
evidence base for a real fill-rate: cross-referenced with each tender's launch month,
"a matching product first appeared in the launch window" = the lot was filled.

Honest limits (see datadeling notes in README):
  - Forward-only: we can't reconstruct listing dates for months before we started
    snapshotting. Past plans stay on the recurrence proxy in gap_analysis.py.
  - Attributing a new listing to a specific LOT needs the product's origin/grape/price
    (Restricted tier) or the public product page; the Open index carries only name.
    So this ledger gives dates; lot-matching is a separate, attribute-dependent step.

Run (daily, after the index is refreshed):
  python3 track_listings.py --index vmp_catalog_index.json --ledger vmp_listings.json
Report new listings in a window:
  python3 track_listings.py --ledger vmp_listings.json --since 2026-08-01
"""
import os, sys, json, argparse, datetime


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default


def update(index_path, ledger_path, date):
    idx = load(index_path, None)
    if not idx or not isinstance(idx.get("products"), list):
        sys.exit(f"no usable catalog index at {index_path} (run ingest_vmp.py --api --index first)")
    date = date or idx.get("generated") or datetime.date.today().isoformat()
    ledger = load(ledger_path, {})
    current = {}
    for p in idx["products"]:
        pid = str(p.get("productId") or "").strip()
        if pid:
            current[pid] = (p.get("name") or "").strip()

    new_ids, relisted = [], []
    for pid, name in current.items():
        row = ledger.get(pid)
        if row is None:
            ledger[pid] = {"name": name, "first_seen": date, "last_seen": date, "delisted": None}
            new_ids.append(pid)
        else:
            if row.get("delisted"):            # came back after being gone
                row["delisted"] = None
                relisted.append(pid)
            row["last_seen"] = date
            if name:
                row["name"] = name

    delisted = []
    for pid, row in ledger.items():
        if pid not in current and not row.get("delisted"):
            row["delisted"] = date
            delisted.append(pid)

    json.dump(ledger, open(ledger_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    active = sum(1 for r in ledger.values() if not r.get("delisted"))
    print(f"[{date}] catalog {len(current)} products · ledger {len(ledger)} known ({active} active)")
    print(f"  + {len(new_ids)} newly listed   ~ {len(relisted)} relisted   - {len(delisted)} delisted")
    for pid in new_ids[:15]:
        print(f"    NEW {pid}  {ledger[pid]['name']}")
    if len(new_ids) > 15:
        print(f"    … and {len(new_ids) - 15} more")


def report_since(ledger_path, since):
    ledger = load(ledger_path, {})
    if not ledger:
        sys.exit(f"empty ledger at {ledger_path}")
    rows = sorted(((pid, r) for pid, r in ledger.items() if r.get("first_seen", "") >= since),
                  key=lambda x: x[1]["first_seen"])
    print(f"{len(rows)} products first listed on/after {since}:")
    for pid, r in rows:
        flag = f"  (delisted {r['delisted']})" if r.get("delisted") else ""
        print(f"  {r['first_seen']}  {pid}  {r['name']}{flag}")


def main():
    ap = argparse.ArgumentParser(description="Maintain a Vinmonopolet listing-date ledger by diffing Open catalog snapshots.")
    ap.add_argument("--index", default="vmp_catalog_index.json", help="today's Open catalog index")
    ap.add_argument("--ledger", default="vmp_listings.json", help="the persisted first_seen/last_seen ledger")
    ap.add_argument("--date", help="override the snapshot date (default: index.generated or today)")
    ap.add_argument("--since", help="instead of updating, report products first listed on/after this date")
    args = ap.parse_args()
    if args.since:
        report_since(args.ledger, args.since)
    else:
        update(args.index, args.ledger, args.date)


if __name__ == "__main__":
    main()
