"""
Clause-level parsing of tender spec text.

Vinmonopolet specs are numbered requirement lists ("1) ... 2) ..."). This module
splits them and classifies each clause into a typed, parameterized requirement
that wine records can be checked against.

Clause types:
  grape       {mode: single|min_pct|exact_pct, variety, pct}
  vintage     {years: [..]} or {min_year}
  sugar_max   {g_l}
  wood        {mode: none_or_discreet | barrel_required | required}
  cert        {certs: [..], on_label: bool}
  volume_min  {bottles}
  maceration  {min_days, max_days}
  appellation {text}          (from the spec's appellation field)
  offer_rule  informational (one offer per producer etc.) — not wine-checkable
  other       unclassified — shown to the user, treated as unknown
"""
import re

GRAPE_WORDS = r"[A-Za-zàâäéèêëïîôöùûüç' \-]+?"

def split_clauses(text):
    parts = re.split(r"\s*\d+\)\s*", text or "")
    return [p.strip().rstrip(".") for p in parts if p.strip()]

def _varieties(text):
    return [v.strip().lower() for v in re.split(r",| and/or | or | og |/", text)
            if v.strip() and len(v.strip()) > 2]

def classify(clause):
    c = clause.lower()

    if re.search(r"cap classique|mcc\b", c):
        return {"type": "method", "method": "traditional (Cap Classique)"}
    if re.search(r"traditional method|methode traditionnelle|tradisjonell metode", c):
        return {"type": "method", "method": "traditional"}
    if re.search(r"charmat|tank method", c):
        return {"type": "method", "method": "charmat"}

    m = re.search(rf"single grape variety ({GRAPE_WORDS})(?:$|[.,;(])", clause, re.I)
    if m:
        return {"type": "grape", "mode": "single", "varieties": _varieties(m.group(1))}
    m = re.search(r"based on (?:min\.?|minimum)?\s*(\d+)\s*%\s*(.+)", clause, re.I)
    if m:
        return {"type": "grape", "mode": "min_pct", "pct": int(m.group(1)),
                "varieties": _varieties(m.group(2))}
    m = re.search(r"based on ([A-Z].+)", clause)
    if m and not re.search(r"\d", m.group(1)):
        return {"type": "grape", "mode": "any_of", "varieties": _varieties(m.group(1))}

    m = re.search(r"max\.?\s*(\d+(?:[.,]\d+)?)\s*g/l sugar", c)
    if m:
        return {"type": "sugar_max", "g_l": float(m.group(1).replace(",", "."))}

    if re.search(r"no or discreet (?:use of )?(?:wood|oak)|no or discreet wood influence|no influence of wood|no wood", c):
        return {"type": "wood", "mode": "none_or_discreet"}
    if re.search(r"\d+\s*% barrel fermented|barrel fermented|barrique|oak matured", c):
        return {"type": "wood", "mode": "barrel_required"}

    certs = []
    if re.search(r"fairtrade|fair for life", c): certs.append("Fairtrade")
    if re.search(r"organic|okologisk|økologisk", c): certs.append("Organic")
    if re.search(r"biodynam", c): certs.append("Biodynamic")
    if re.search(r"wieta", c): certs.append("WIETA")
    if re.search(r"\bipw\b|\bwsb\b|integrity & sustainability", c): certs.append("IPW/WSB")
    if re.search(r"terra vitis|equalitas|entwine|sustainable winegrowing|certified sustainable", c):
        certs.append("Sustainability scheme")
    elif re.search(r"sustainab", c): certs.append("Sustainability scheme")
    if re.search(r"vegan", c): certs.append("Vegan")
    if certs:
        return {"type": "cert", "certs": certs,
                "on_label": bool(re.search(r"label", c))}

    m = re.search(r"(?:min\.?|minimum)\s*([\d\s]{3,7})bottles", c) or \
        re.search(r"one-lot min\.?\s*([\d\s]+) bottles", c)
    if m:
        return {"type": "volume_min", "bottles": int(m.group(1).replace(" ", ""))}

    m = re.search(r"(\d+)\s*-\s*(\d+)\s*days.{0,20}maceration", c)
    if m:
        return {"type": "maceration", "min_days": int(m.group(1)), "max_days": int(m.group(2))}

    m = re.search(r"min\.?\s*(\d+)\s*years? old vines", c)
    if m:
        return {"type": "vines_age", "min_years": int(m.group(1))}

    m = re.search(r"max\.?\s*(\d+(?:[.,]\d+)?)\s*% alcohol", c)
    if m:
        return {"type": "abv_max", "pct": float(m.group(1).replace(",", "."))}

    if re.search(r"only one offer|per producer|lowest priced offer|regardless of wholesaler", c):
        return {"type": "offer_rule"}
    if re.search(r"deposit system|refundable packaging|aluminium or pet", c):
        return {"type": "packaging_rule"}
    if re.search(r"to be confirmed by the producer|written confirmation", c):
        return {"type": "confirmation_rule"}

    return {"type": "other"}

def parse_vintage(vintage_text):
    t = (vintage_text or "").lower()
    years = [int(y) for y in re.findall(r"(20\d\d|19\d\d)", t)]
    if not years:
        return None
    if "more recent" in t or "or younger" in t:
        return {"type": "vintage", "min_year": min(years)}
    return {"type": "vintage", "years": years}

def clauses_for_spec(spec):
    out = []
    for cl in split_clauses(spec.get("spec", "")):
        rec = classify(cl)
        rec["text"] = cl
        # "Certification must appear on label" as its own clause -> attach to prior cert
        if (rec["type"] == "other" and re.search(r"certification.*label", cl, re.I)
                and out and out[-1]["type"] == "cert"):
            out[-1]["on_label"] = True
            continue
        out.append(rec)
    v = parse_vintage(spec.get("vintage", ""))
    if v:
        v["text"] = f"Vintage: {spec['vintage']}"
        out.append(v)
    if spec.get("appellation"):
        out.append({"type": "appellation", "text": spec["appellation"]})
    return out
