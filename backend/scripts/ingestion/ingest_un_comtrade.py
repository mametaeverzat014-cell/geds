"""UN Comtrade ingestion pipeline.

Operates on the 96 real parquet files in `backend/data/raw/comtrade/`.
These were fetched from the UN Comtrade API (free tier, 2019 reference year)
via `comtradeapicall` per `comtrade_edges.csv` source URLs.

Output:
  backend/data/raw/comtrade/parsed/sectoral_trade_share_2019.csv
  backend/data/raw/comtrade/parsed/provenance.json

Sectors derivable from HS codes in this dataset:
  - electronics       (HS 8471, 8517, 8528)
  - semiconductors    (HS 8541, 8542)
  - automotive        (HS 8703, 8704, 8708)

Sectors NOT derivable from this dataset (will be NULL downstream):
  - aerospace, shipping, energy, consumer_goods, banking, insurance,
    capital_markets, oil, gas, utilities, aviation, ports,
    telecommunications, agriculture, tourism, government

Reporter coverage in this dataset (12 countries):
  CHN, DEU, JPN, KOR, MYS, MEX, NLD, IND, VNM, THA, USA, M49=490 (Taiwan)
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent
RAW_DIR = REPO / "backend" / "data" / "raw" / "comtrade"
PARSED_DIR = RAW_DIR / "parsed"
PARSED_DIR.mkdir(parents=True, exist_ok=True)

# M49 numeric country code → ISO3 (subset present in this pull)
M49_TO_ISO3 = {
    "156": "CHN", "392": "JPN", "276": "DEU", "410": "KOR",
    "458": "MYS", "704": "VNM", "484": "MEX", "528": "NLD",
    "842": "USA", "764": "THA", "699": "IND",
    "490": "TWN",  # M49=490 is "Other Asia, not elsewhere specified" — Comtrade
                   # uses this for Taiwan since Taiwan is not in ISO M49 due to
                   # its political status; conventional Comtrade↔ISO3 mapping.
}

# HS code → GEDS sector (3 of 19 sectors covered by available pulls)
HS_TO_SECTOR = {
    "8471": "electronics",      # data processing machines
    "8517": "electronics",      # telephony
    "8528": "electronics",      # monitors/projectors
    "8541": "semiconductors",   # diodes/transistors
    "8542": "semiconductors",   # integrated circuits
    "8703": "automotive",       # passenger cars
    "8704": "automotive",       # trucks
    "8708": "automotive",       # parts
}


def ingest() -> tuple[Path | None, dict]:
    files = sorted(RAW_DIR.glob("*.parquet"))
    if not files:
        prov = {
            "pipeline": "ingest_un_comtrade",
            "status": "NO_DATA",
            "reason": f"No parquet files found in {RAW_DIR}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (PARSED_DIR / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
        return None, prov

    import pandas as pd

    # Aggregate per (reporter, sector) total trade value
    per_reporter_sector_value: dict[tuple[str, str], float] = defaultdict(float)
    per_reporter_total_value: dict[str, float] = defaultdict(float)
    per_reporter_partners: dict[tuple[str, str], set] = defaultdict(set)
    per_reporter_hs_codes: dict[tuple[str, str], set] = defaultdict(set)

    n_files_parsed = 0
    n_rows_total = 0
    for f in files:
        # Filename pattern: comtrade_A_M_<reporterM49>_<HScode>_<year>.parquet
        parts = f.stem.split("_")
        if len(parts) < 6:
            continue
        reporter_m49 = parts[3]
        hs_code = parts[4]
        iso3 = M49_TO_ISO3.get(reporter_m49)
        sector = HS_TO_SECTOR.get(hs_code)
        if iso3 is None or sector is None:
            continue
        df = pd.read_parquet(f)
        n_files_parsed += 1
        n_rows_total += len(df)
        # primaryValue is the USD value of the trade flow (CIF or FOB depending on flow direction)
        if "primaryValue" not in df.columns:
            continue
        # We want IMPORTS into the reporter (flowCode == 'M') — proxy for the reporter's
        # downstream sector dependency. Could also sum imports + exports for total volume.
        if "flowCode" in df.columns:
            for flow in ("M", "X"):
                sub = df[df["flowCode"] == flow]
                if sub.empty:
                    continue
                total_val = float(sub["primaryValue"].sum())
                per_reporter_sector_value[(iso3, sector)] += total_val
                per_reporter_total_value[iso3] += total_val
                if "partnerISO" in sub.columns:
                    per_reporter_partners[(iso3, sector)].update(sub["partnerISO"].dropna().unique())
                per_reporter_hs_codes[(iso3, sector)].add(hs_code)

    # Emit one row per (country, sector) with non-zero trade
    out_rows = []
    for (iso3, sector), value in per_reporter_sector_value.items():
        total = per_reporter_total_value[iso3]
        share = value / total if total > 0 else None
        partners = sorted(per_reporter_partners.get((iso3, sector), set()))
        hs_codes_used = sorted(per_reporter_hs_codes.get((iso3, sector), set()))
        out_rows.append({
            "country_iso3": iso3,
            "sector": sector,
            "trade_value_usd": round(value, 2),
            "trade_share_of_country_total": round(share, 6) if share is not None else "",
            "n_partner_countries": len(partners),
            "n_hs_codes": len(hs_codes_used),
            "hs_codes": ";".join(hs_codes_used),
            "reference_year": 2019,
            "_source_origin": "UN Comtrade API (parquet pulls)",
        })

    out_path = PARSED_DIR / "sectoral_trade_share_2019.csv"
    if out_rows:
        with out_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader(); w.writerows(out_rows)
    prov = {
        "pipeline": "ingest_un_comtrade",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "n_parquet_files_parsed": n_files_parsed,
        "n_rows_in_source_parquets": n_rows_total,
        "n_output_rows": len(out_rows),
        "countries_covered": sorted({r["country_iso3"] for r in out_rows}),
        "sectors_covered": sorted({r["sector"] for r in out_rows}),
        "sectors_NOT_covered_by_this_pull": sorted(set(
            ["aerospace", "shipping", "energy", "consumer_goods", "banking",
             "insurance", "capital_markets", "oil", "gas", "utilities",
             "aviation", "ports", "telecommunications", "agriculture",
             "tourism", "government"]
        )),
        "hs_codes_used": sorted(HS_TO_SECTOR.keys()),
        "reference_year": 2019,
        "source_url_pattern": "https://comtrade.un.org/data/?r={reporter}&p=all&px=HS&cc={hs}&y=2019",
    }
    (PARSED_DIR / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    return out_path, prov


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print("UN Comtrade ingestion pipeline (real data)")
    print(f"  source dir: {RAW_DIR}")
    print(f"  parsed dir: {PARSED_DIR}")
    out, prov = ingest()
    if prov["status"] != "OK":
        print(f"  status: {prov['status']}")
        return 1
    print(f"  parsed {prov['n_parquet_files_parsed']} files, {prov['n_rows_in_source_parquets']:,} rows")
    print(f"  emitted {prov['n_output_rows']} (country, sector) rows")
    print(f"  countries: {prov['countries_covered']}")
    print(f"  sectors: {prov['sectors_covered']}")
    print(f"  sectors NOT covered (will be NULL downstream): {len(prov['sectors_NOT_covered_by_this_pull'])}")
    print(f"  wrote: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
