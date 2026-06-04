"""Phase 3 — OVERWRITE country_sector_presence_real.csv from OECD ICIO only.

Inputs:
  backend/data/csv/oecd_country_sector_weights.csv  (from real parser)
  backend/data/raw/wb_gdp_2019.json                 (per-country GDP, real)

Strict rules:
  - For each (country, GEDS sector) emit ONE row.
  - gdp_share = sum(value_added of OECD sectors mapping to this GEDS sector)
                / sum(value_added of all OECD sectors for this country).
    NULL if country not in OECD or value_added not available.
  - employment_share = NULL (WIOD still absent).
  - trade_share = sum(exports + imports for matching OECD sectors)
                  / sum(exports + imports for all OECD sectors of country).
  - confidence = 5 when OECD provides data, NULL otherwise.
  - GEDS sectors that don't map to any OECD code → NULL row with explicit note.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent
CSV_DIR = REPO / "backend" / "data" / "csv"

# GEDS 19-sector enum (matches Industry enum)
GEDS_SECTORS = [
    "semiconductors", "automotive", "electronics", "aerospace",
    "shipping", "energy", "consumer_goods",
    "banking", "insurance", "capital_markets", "oil", "gas",
    "utilities", "aviation", "ports", "telecommunications",
    "agriculture", "tourism", "government",
]

# GEDS sectors that CANNOT be derived from OECD (per schema audit)
GEDS_NOT_IN_OECD = {"semiconductors", "gas", "insurance", "capital_markets",
                    "energy"}  # 'energy' is composite — leave NULL, use oil + gas + utilities instead


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    weights_path = CSV_DIR / "oecd_country_sector_weights.csv"
    if not weights_path.exists():
        print(f"ERROR: {weights_path} not found. Run ingest_oecd_icio.py first.", file=sys.stderr)
        return 1

    print(f"Loading {weights_path}...")
    df = pd.read_csv(weights_path, low_memory=False)
    print(f"  rows: {len(df):,}, years: {sorted(df['year'].unique())}")

    # Use most recent year (2022 — actually 2021 may be the last with full data; let's check)
    # Strategy: aggregate by (country, geds_sector) over the most recent year with non-null geds_sector
    latest_year = int(df["year"].max())
    print(f"  using latest year: {latest_year}")
    df_y = df[df["year"] == latest_year].copy()

    # Per-country totals (for shares)
    country_va = df_y.groupby("country_iso3")["value_added_usd_m"].sum()
    country_trade = df_y.groupby("country_iso3").apply(
        lambda g: (g["exports_total_usd_m"].fillna(0) + g["imports_total_usd_m"].fillna(0)).sum()
    )
    # Per-(country, GEDS sector) sums
    # Note geds_sector is NaN for OECD codes that don't map (we use these for total denominator)
    df_y_mapped = df_y[df_y["geds_sector"].notna()]
    grouped = df_y_mapped.groupby(["country_iso3", "geds_sector"]).agg(
        va_sum=("value_added_usd_m", "sum"),
        gross_output_sum=("gross_output_usd_m", "sum"),
        exports_sum=("exports_total_usd_m", "sum"),
        imports_sum=("imports_total_usd_m", "sum"),
        n_oecd_sectors_aggregated=("oecd_sector", "count"),
    ).reset_index()

    # Build presence rows: for every (country, GEDS sector), 19 × n_countries rows
    all_countries = sorted(df_y["country_iso3"].unique())
    print(f"  OECD countries: {len(all_countries)}")
    print(f"  GEDS sectors: {len(GEDS_SECTORS)}")

    rows_out = []
    lookup = {(r["country_iso3"], r["geds_sector"]): r for _, r in grouped.iterrows()}

    for country in all_countries:
        country_va_total = country_va.get(country, 0)
        country_trade_total = country_trade.get(country, 0)
        for sector in GEDS_SECTORS:
            if sector in GEDS_NOT_IN_OECD:
                # No clean OECD evidence — emit NULL row with explicit note
                rows_out.append({
                    "country_iso3": country,
                    "sector": sector,
                    "gdp_share": "",
                    "employment_share": "",
                    "trade_share": "",
                    "confidence": "",
                    "presence_status": "MISSING_OECD_HAS_NO_SOURCE",
                    "evidence_source": "OECD_ICIO_DOES_NOT_SEPARATE_THIS_SECTOR",
                    "note": (
                        "OECD ICIO has no clean line item for this sector. See "
                        "OECD_ICIO_SCHEMA_AUDIT.md for the bundling explanation. "
                        "Requires supplementary source (SIA / EIA / ECB) — NOT in repo."
                    ),
                    "year_used": latest_year,
                })
                continue

            hit = lookup.get((country, sector))
            if hit is None or country_va_total <= 0:
                rows_out.append({
                    "country_iso3": country,
                    "sector": sector,
                    "gdp_share": "",
                    "employment_share": "",
                    "trade_share": "",
                    "confidence": "",
                    "presence_status": "MISSING_NO_DATA",
                    "evidence_source": "OECD_ICIO",
                    "note": "Country present in OECD but no value_added in mapping",
                    "year_used": latest_year,
                })
                continue

            va_share = hit["va_sum"] / country_va_total if country_va_total > 0 else None
            trade_share = ((hit["exports_sum"] + hit["imports_sum"]) / country_trade_total
                           if country_trade_total > 0 else None)
            rows_out.append({
                "country_iso3": country,
                "sector": sector,
                "gdp_share": f"{va_share:.6f}" if va_share is not None else "",
                "employment_share": "",  # WIOD still missing → NULL preserved
                "trade_share": f"{trade_share:.6f}" if trade_share is not None else "",
                "confidence": 5,
                "presence_status": "DATA_PRESENT",
                "evidence_source": "OECD_ICIO",
                "note": (
                    f"Aggregated from {int(hit['n_oecd_sectors_aggregated'])} OECD ISIC sectors; "
                    f"gross_output={hit['gross_output_sum']:,.0f} USD m"
                ),
                "year_used": latest_year,
            })

    out_path = CSV_DIR / "country_sector_presence_real.csv"
    fields = ["country_iso3", "sector", "gdp_share", "employment_share",
              "trade_share", "confidence", "presence_status",
              "evidence_source", "note", "year_used"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows_out)

    n_data = sum(1 for r in rows_out if r["presence_status"] == "DATA_PRESENT")
    n_missing_no_data = sum(1 for r in rows_out if r["presence_status"] == "MISSING_NO_DATA")
    n_missing_no_source = sum(1 for r in rows_out if r["presence_status"] == "MISSING_OECD_HAS_NO_SOURCE")
    print(f"\nWrote {out_path}")
    print(f"  total rows: {len(rows_out)} ({len(all_countries)} countries × {len(GEDS_SECTORS)} sectors)")
    print(f"  DATA_PRESENT: {n_data}")
    print(f"  MISSING_NO_DATA: {n_missing_no_data}")
    print(f"  MISSING_OECD_HAS_NO_SOURCE (semis/gas/insurance/capital_markets/energy): {n_missing_no_source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
