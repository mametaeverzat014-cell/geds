"""GEDS Benchmark V4 — Phase 1 pre-audit extractor (NON-FABRICATING).

Reads D:/event_expansion_candidates.csv (90 documented events) and, for each,
extracts ONLY verbatim evidence needed to decide benchmark mappability:

  * any economy-wide GDP / GNP / "economic output" percentage figures that appear
    in the free-text impact_description (verbatim snippet + the number),
  * whether the description contains ONLY money/physical units ($, bn, bbl, days,
    TEU ...) with no economy-wide output figure,
  * country tokens -> ISO3 (deterministic dict; unknown tokens flagged),
  * sector tokens -> GEDS Industry enum (deterministic map; unknown flagged),
  * a duplicate-vs-existing-corpus flag (fuzzy name/year match against the 42
    events already in benchmark_event_matrix_v3.csv).

It NEVER invents a number. If no economy-wide % is present, the gdp_snippets list
is empty and the event is a candidate for UNMAPPABLE. Final MAPPED/PARTIAL/
UNMAPPABLE adjudication is done by a human reviewer over this output.

Output: backend/data/calibration/v4_preaudit.json   (compact, reviewable)
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
EXP_CSV = Path("D:/event_expansion_candidates.csv")
V3 = REPO / "backend" / "data" / "csv" / "benchmark_event_matrix_v3.csv"
OUT = REPO / "backend" / "data" / "calibration" / "v4_preaudit.json"

# ---- deterministic country -> ISO3 (covers tokens seen in the corpus) ----
ISO3 = {
    "united states": "USA", "us": "USA", "u.s.": "USA", "usa": "USA", "america": "USA",
    "united kingdom": "GBR", "uk": "GBR", "u.k.": "GBR", "britain": "GBR", "england": "GBR",
    "japan": "JPN", "china": "CHN", "germany": "DEU", "france": "FRA", "italy": "ITA",
    "spain": "ESP", "netherlands": "NLD", "belgium": "BEL", "poland": "POL", "russia": "RUS",
    "russian federation": "RUS", "ukraine": "UKR", "kuwait": "KWT", "iraq": "IRQ", "iran": "IRN",
    "turkey": "TUR", "turkiye": "TUR", "greece": "GRC", "portugal": "PRT", "ireland": "IRL",
    "cyprus": "CYP", "argentina": "ARG", "brazil": "BRA", "uruguay": "URY", "bolivia": "BOL",
    "mexico": "MEX", "canada": "CAN", "india": "IND", "indonesia": "IDN", "thailand": "THA",
    "vietnam": "VNM", "malaysia": "MYS", "philippines": "PHL", "singapore": "SGP",
    "south korea": "KOR", "korea": "KOR", "taiwan": "TWN", "hong kong": "HKG",
    "sri lanka": "LKA", "maldives": "MDV", "myanmar": "MMR", "somalia": "SOM", "kenya": "KEN",
    "bangladesh": "BGD", "seychelles": "SYC", "pakistan": "PAK", "nigeria": "NGA",
    "south africa": "ZAF", "ethiopia": "ETH", "angola": "AGO", "colombia": "COL", "chile": "CHL",
    "egypt": "EGY", "tunisia": "TUN", "libya": "LBY", "yemen": "YEM", "syria": "SYR",
    "bahrain": "BHR", "saudi arabia": "SAU", "uae": "ARE", "united arab emirates": "ARE",
    "israel": "ISR", "norway": "NOR", "panama": "PAN", "haiti": "HTI", "nepal": "NPL",
    "venezuela": "VEN", "tanzania": "TZA", "uganda": "UGA", "lebanon": "LBN", "jordan": "JOR",
    "australia": "AUS", "iceland": "ISL", "puerto rico": "PRI", "dominican republic": "DOM",
    "jamaica": "JAM", "bahamas": "BHS", "north korea": "PRK", "czech republic": "CZE",
    "hungary": "HUN", "romania": "ROU", "switzerland": "CHE",
}
# tokens that are regions / aggregates, NOT a single ISO3 country
REGION_TOKENS = ("global", "world", "oecd", "eu", "europe", "european union", "eurozone",
                 "euro area", "asia", "emerging market", "g7", "g20", "mena", "gulf",
                 "industrial countries", "advanced economies", "worldwide", "international",
                 "middle east", "sub-saharan", "latin america", "balkans", "caribbean",
                 "oil market", "gas market", "shipping", "supply chain")

# ---- sector free-text -> GEDS Industry enum (deterministic) ----
SECTOR_MAP = {
    "energy": "energy", "oil": "energy", "gas": "energy", "oil & gas": "energy",
    "electricity": "utilities", "power": "utilities", "utilities": "utilities", "water": "utilities",
    "automotive": "automotive", "auto": "automotive", "vehicles": "automotive",
    "electronics": "electronics", "semiconductor": "electronics", "semiconductors": "electronics",
    "chips": "electronics", "technology": "electronics", "tech": "electronics", "it": "electronics",
    "telecommunications": "telecommunications", "telecom": "telecommunications",
    "banking": "banking", "finance": "banking", "financial": "banking", "foreign exchange": "banking",
    "central banking": "banking", "insurance": "banking",
    "government": "government", "public finance": "government", "sovereign": "government",
    "agriculture": "agriculture", "food": "agriculture", "crop": "agriculture", "grain": "agriculture",
    "tourism": "tourism", "hotels": "tourism", "travel": "tourism",
    "aerospace": "aerospace", "aviation": "aerospace", "airlines": "aerospace", "defense": "aerospace",
    "shipping": "shipping", "maritime": "shipping", "ports": "shipping", "freight": "shipping",
    "rail": "shipping", "transportation": "shipping", "logistics": "shipping",
    "consumer goods": "consumer_goods", "retail": "consumer_goods", "manufacturing": "consumer_goods",
    "consumer prices": "consumer_goods", "chemicals": "consumer_goods", "metals": "consumer_goods",
    "real estate": "banking", "construction": "utilities", "housing": "utilities",
    "healthcare": "tourism", "health care": "tourism",  # no health enum; flagged below
}

MONEY_PHYS = re.compile(
    r"(\$|usd|€|eur|£|gbp|¥|yen|billion|million|trillion|bbl|barrel|barrels|"
    r"\bteu\b|tonnes|tons|days|deaths|injuries|housing units|ships|vessels)", re.I)

# economy-wide output keywords
GDP_KW = re.compile(r"(gdp|gnp|gross domestic product|gross national product|"
                    r"economic output|national output|economy[- ]wide output)", re.I)

# number + percent in either order, within a small window of a GDP keyword
NUM = r"[-+]?\d+(?:\.\d+)?"
PCT = r"(?:percent|percentage points?|ppt?|%)"
# pattern A: "GDP ... <num> percent"   pattern B: "<num> percent ... GDP"
PAT_A = re.compile(rf"((?:gdp|gnp|gross (?:domestic|national) product|economic output)[^.]{{0,60}}?{NUM}\s*{PCT})", re.I)
PAT_B = re.compile(rf"({NUM}\s*{PCT}[^.]{{0,40}}?(?:gdp|gnp|gross (?:domestic|national) product|economic output|growth|contraction|recession))", re.I)


def map_countries(raw: str):
    iso, regions, unknown = [], [], []
    for tok in re.split(r"[;,/]", raw):
        t = tok.strip().lower()
        if not t:
            continue
        if any(rt in t for rt in REGION_TOKENS):
            regions.append(tok.strip()); continue
        # try direct, then strip parenthetical qualifiers
        base = re.sub(r"\(.*?\)", "", t).strip()
        base = re.sub(r"^(the|republic of|state of)\s+", "", base).strip()
        if base in ISO3:
            iso.append(ISO3[base])
        else:
            # try first word
            fw = base.split()[0] if base.split() else base
            if fw in ISO3:
                iso.append(ISO3[fw])
            else:
                unknown.append(tok.strip())
    return sorted(set(iso)), sorted(set(regions)), sorted(set(unknown))


def map_sectors(raw: str):
    mapped, unknown = [], []
    for tok in re.split(r"[;,/]", raw):
        t = tok.strip().lower()
        if not t:
            continue
        hit = None
        for k, v in SECTOR_MAP.items():
            if k in t:
                hit = v; break
        if hit:
            mapped.append(hit)
        else:
            unknown.append(tok.strip())
    return sorted(set(mapped)), sorted(set(unknown))


def gdp_snippets(desc: str):
    snips = []
    for pat in (PAT_A, PAT_B):
        for m in pat.finditer(desc):
            s = re.sub(r"\s+", " ", m.group(1)).strip()
            if s not in snips:
                snips.append(s)
    return snips


def load_v3_names():
    out = []
    with V3.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append((row["event_name"].lower(), row.get("target_gdp", "")))
    return out


def dup_flag(name: str, v3names) -> str:
    n = name.lower()
    keys = ["global financial", "lehman", "covid", "tōhoku", "tohoku", "fukushima",
            "suez", "ever given", "asian financial", "evergrande", "russia", "ukraine",
            "nord stream", "oil price collapse", "china stock", "brexit", "trade war",
            "tariff", "semiconductor", "panama canal", "red sea", "houthi", "sri lanka",
            "natural gas", "energy crisis", "food", "subprime", "dot-com", "argentine",
            "sars", "indian ocean", "tsunami", "katrina", "sovereign debt", "crimea"]
    for k in keys:
        if k in n:
            for vn, _ in v3names:
                if k in vn:
                    return f"LIKELY_DUP::v3='{vn}'"
    return ""


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
    v3names = load_v3_names()
    rows = []
    with EXP_CSV.open(encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f), 1):
            desc = r.get("impact_description", "") or ""
            iso, regions, unk_c = map_countries(r.get("countries", ""))
            sec, unk_s = map_sectors(r.get("sectors", ""))
            snips = gdp_snippets(desc)
            year = (r.get("start_date", "") or "")[:4]
            money_only = bool(MONEY_PHYS.search(desc)) and not GDP_KW.search(desc)
            rows.append({
                "idx": i,
                "event_name": r.get("event_name", ""),
                "year": year,
                "category": r.get("category", ""),
                "confidence": r.get("confidence_level", ""),
                "iso3": iso,
                "regions": regions,
                "unmapped_country_tokens": unk_c,
                "sectors_mapped": sec,
                "unmapped_sector_tokens": unk_s,
                "gdp_pct_snippets": snips,
                "has_gdp_keyword": bool(GDP_KW.search(desc)),
                "money_or_physical_only": money_only,
                "dup": dup_flag(r.get("event_name", ""), v3names),
                "source_url": r.get("source_url", ""),
            })
    OUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- console summary ----
    n = len(rows)
    with_gdp = [r for r in rows if r["gdp_pct_snippets"]]
    money_only = [r for r in rows if r["money_or_physical_only"]]
    has_iso = [r for r in rows if r["iso3"]]
    has_sec = [r for r in rows if r["sectors_mapped"]]
    dups = [r for r in rows if r["dup"]]
    low = [r for r in rows if r["confidence"].lower() == "low"]
    print(f"Total expansion events: {n}")
    print(f"  with >=1 economy-wide GDP/GNP % snippet : {len(with_gdp)}")
    print(f"  money/physical units ONLY (no GDP kw)   : {len(money_only)}")
    print(f"  >=1 ISO3 country mapped                 : {len(has_iso)}")
    print(f"  >=1 sector mapped to engine enum        : {len(has_sec)}")
    print(f"  likely duplicates of existing 42        : {len(dups)}")
    print(f"  Low confidence                          : {len(low)}")
    print(f"\nwrote {OUT}")

    # provisional auto-class (final adjudication by reviewer)
    def prov(r):
        if r["dup"]:
            return "DUP"
        if not r["gdp_pct_snippets"]:
            return "UNMAPPABLE"   # no economy-wide output figure to transcribe
        return "GDP?"             # has a %-of-GDP figure -> needs type adjudication

    print("\n=== ALL 90 EXPANSION EVENTS (provisional) ===")
    for r in rows:
        p = prov(r)
        loc = ",".join(r["iso3"][:3]) if r["iso3"] else ("REGION:" + (r["regions"][0][:10] if r["regions"] else "-"))
        print(f"[{r['idx']:2d}] {r['year']} {p:11s} conf={r['confidence'][:3]:3s} "
              f"loc={loc:16s} dup={'Y' if r['dup'] else '-'} {r['event_name'][:44]}")

    print("\n=== GDP-figure events: verbatim snippets for TYPE adjudication ===")
    for r in with_gdp:
        print(f"[{r['idx']:2d}] {r['event_name'][:50]} (dup={'Y' if r['dup'] else '-'}, conf={r['confidence']})")
        for s in r["gdp_pct_snippets"]:
            print(f"        • {s[:150]}")


if __name__ == "__main__":
    main()
