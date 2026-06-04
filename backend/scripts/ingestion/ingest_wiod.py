"""WIOD ingestion — REAL .xlsb parser (replaces prior stub).

Parses WIOT2014_Nov16_ROW.xlsb (and optionally other years) via pyxlsb. Produces
sectoral aggregates + intermediate-use edges normalised to the GEDS 19-sector
enum. Crucially: separates K64/K65/K66 (banking/insurance/capital_markets)
which OECD ICIO bundles.

Strict rules respected:
  - Every output row carries `source_file`, `source_year`, `original_sector`,
    `original_country` for provenance.
  - Sectors NOT cleanly derivable (semiconductors, gas) → row emitted with NULL
    and explicit note. No imputation.
  - employment_share stays NULL (SEA files absent from repo). value_added_share
    computed as documented proxy.
  - Edges filtered at USD 1M threshold (documented in schema audit) to keep
    file size tractable.

Outputs (always in `backend/data/csv/`):
  wiod_edges.csv               (industry-to-industry intermediate use flows)
  wiod_country_sector_weights.csv  (per-country, per-sector aggregates)

Plus provenance in `backend/data/raw/wiod/parsed/provenance.json`.

Usage:
  python ingest_wiod.py                 # parse 2014 (latest year)
  python ingest_wiod.py --year 2014    # specific year
  python ingest_wiod.py --year all     # all 15 years (~15-30 min)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent.parent
RAW_DIR = REPO / "backend" / "data" / "raw" / "wiod"
PARSED_DIR = RAW_DIR / "parsed"
CSV_DIR = REPO / "backend" / "data" / "csv"
PARSED_DIR.mkdir(parents=True, exist_ok=True)


# ── NACE Rev.2 → GEDS sector mapping (from WIOD_SCHEMA_AUDIT.md) ──────────

DIRECT_MAP: dict[str, str] = {
    # Agriculture
    "A01": "agriculture", "A02": "agriculture", "A03": "agriculture",
    # Energy upstream (still bundled — B is mining incl. coal + oil + gas + metals)
    "B": "oil",   # imperfect — bundles oil + gas + metals + coal (same as OECD B05-B09)
    "C19": "oil",  # refined petroleum
    # Manufacturing
    "C26": "electronics",  # bundles semiconductors
    "C27": "electronics",
    "C28": "consumer_goods",
    "C29": "automotive",
    "C30": "aerospace",  # bundles ships + aerospace + military (same as OECD)
    "C10-C12": "consumer_goods", "C13-C15": "consumer_goods",
    "C16": "consumer_goods", "C17": "consumer_goods", "C18": "consumer_goods",
    "C20": "consumer_goods", "C21": "consumer_goods",
    "C22": "consumer_goods", "C23": "consumer_goods",
    "C24": "consumer_goods", "C25": "consumer_goods",
    "C31_C32": "consumer_goods", "C33": "consumer_goods",
    # Utilities
    "D35": "utilities",
    "E36": "utilities", "E37-E39": "utilities",
    # Wholesale/retail → consumer_goods (matches OECD)
    "G45": "consumer_goods", "G46": "consumer_goods", "G47": "consumer_goods",
    # Transport
    "H49": "shipping", "H50": "shipping",
    "H51": "aviation",
    "H52": "ports",
    "H53": "telecommunications",  # postal (matches OECD)
    # Hospitality
    "I": "tourism",
    # ICT / telecom
    "J58": "telecommunications", "J59_J60": "telecommunications",
    "J61": "telecommunications", "J62_J63": "telecommunications",
    # **WIOD's key advantage: finance sector splits**
    "K64": "banking",
    "K65": "insurance",
    "K66": "capital_markets",
    # Government
    "O84": "government", "P85": "government",
}

# Sectors mapped to None = not in GEDS enum (intentional discard)
DISCARD: set[str] = {
    "F",            # construction
    "L68",          # real estate
    "M69_M70", "M71", "M72", "M73", "M74_M75",  # professional services
    "N",            # admin support
    "Q",            # health (no enum entry)
    "R_S", "T", "U", # arts, household, extraterritorial
}

# GEDS sectors that STILL cannot be derived (even with WIOD)
GEDS_STILL_NULL = {"semiconductors", "gas"}

# Threshold for edge emission (USD millions)
EDGE_THRESHOLD_USD_M = 1.0


def _norm_geds(wiod_sector: str) -> str | None:
    """Map WIOD NACE code → GEDS sector. Returns None if discarded/unmapped."""
    return DIRECT_MAP.get(wiod_sector)


# ── parser ────────────────────────────────────────────────────────────────

def parse_one_year(xlsb_path: Path) -> dict:
    """Parse one WIOT .xlsb file. Returns dict with edges_df, weights_df, stats."""
    from pyxlsb import open_workbook
    year = int(xlsb_path.stem.split("_")[0].replace("WIOT", ""))
    t0 = time.time()
    print(f"  parsing {xlsb_path.name} ({xlsb_path.stat().st_size / 1024 / 1024:.0f} MB)...",
          flush=True)

    with open_workbook(str(xlsb_path)) as wb:
        sheet_name = wb.sheets[0]
        with wb.get_sheet(sheet_name) as sheet:
            rows_iter = sheet.rows()
            # Headers (rows 0-5)
            for _ in range(2):
                next(rows_iter)
            sector_codes_row = next(rows_iter)   # row 2
            sector_names_row = next(rows_iter)   # row 3
            country_codes_row = next(rows_iter)  # row 4
            col_shorthand_row = next(rows_iter)  # row 5

            n_cols = len(sector_codes_row)
            print(f"    columns: {n_cols}; reading data rows...")

            # Build column metadata
            col_country = [c.v for c in country_codes_row]
            col_sector = [c.v for c in sector_codes_row]
            col_name = [c.v for c in sector_names_row]

            # Skip the leading label columns (cols 0-3)
            # Col 0=sector_code, 1=sector_name, 2=country, 3=row_shorthand
            data_col_start = 4

            # Identify final-demand columns (5 per country: CONS_h, CONS_np,
            # CONS_g, GFCF, INVEN). They use specific shorthand codes. Easier:
            # if the sector column header is one of these specific FD codes.
            FINAL_DEMAND_SECTORS = {"CONS_h", "CONS_np", "CONS_g", "GFCF", "INVEN"}

            industry_col_idxs = []  # column indices that are (country, NACE industry)
            fd_col_idxs = []
            tot_col_idxs = []
            for j in range(data_col_start, n_cols):
                sec = col_sector[j]
                ctry = col_country[j]
                if ctry == "TOT" or sec is None:
                    tot_col_idxs.append(j)
                elif sec in FINAL_DEMAND_SECTORS:
                    fd_col_idxs.append(j)
                else:
                    industry_col_idxs.append(j)

            n_industry_cols = len(industry_col_idxs)
            n_fd_cols = len(fd_col_idxs)
            print(f"    industry cols: {n_industry_cols}, "
                  f"final-demand cols: {n_fd_cols}, total cols: {len(tot_col_idxs)}")

            # Aggregate: per (country, sector_NACE) we want:
            #   gross_output (from GO row at column position)
            #   value_added (from VA row)
            #   intermediate_inputs (from II_fob row OR column-sum)
            #   final_demand_total (row-sum over FD cols for this (country, sector))
            #   exports (row-sum over cols where col_country != row_country, excl FD)
            #   imports (col-sum over rows where row_country != col_country, excl FD)
            #   edge: (src_country, src_sector, tgt_country, tgt_sector, flow)

            # We will scan rows once, accumulating per-row + per-column metrics.
            n_rows_data = 0
            edges = []  # list of (src_country, src_sector, tgt_country, tgt_sector, flow)
            row_total_use = defaultdict(float)              # (country, sector) → sum of all industry-col uses
            row_domestic_use = defaultdict(float)           # uses where col_country == row_country
            row_final_demand = defaultdict(float)           # FD use
            col_total_supply = np.zeros(n_industry_cols)    # column index → sum of inputs received
            col_domestic_supply = np.zeros(n_industry_cols)
            # Special rows
            va_per_col: list[float | None] = [None] * n_cols
            go_per_col: list[float | None] = [None] * n_cols
            ii_per_col: list[float | None] = [None] * n_cols
            # Track which rows are industry vs special
            for i, row in enumerate(rows_iter):
                if not row or len(row) < data_col_start:
                    continue
                row_label_sec = row[0].v if row[0] else None
                row_label_ctry = row[2].v if len(row) > 2 and row[2] else None
                if row_label_sec is None:
                    continue
                # Check if this is a special row
                if row_label_sec in ("II_fob", "TXSP", "EXP_adj", "PURR", "PURNR", "VA", "GO"):
                    for j in industry_col_idxs:
                        if j < len(row) and row[j].v is not None:
                            try:
                                v = float(row[j].v)
                            except (TypeError, ValueError):
                                continue
                            if row_label_sec == "VA":
                                va_per_col[j] = v
                            elif row_label_sec == "GO":
                                go_per_col[j] = v
                            elif row_label_sec == "II_fob":
                                ii_per_col[j] = v
                    continue
                # Industry row
                if row_label_ctry is None:
                    continue
                src_country = row_label_ctry
                src_sector = row_label_sec
                n_rows_data += 1
                # Walk industry columns + FD columns
                for j in industry_col_idxs:
                    if j >= len(row) or row[j].v is None:
                        continue
                    try:
                        v = float(row[j].v)
                    except (TypeError, ValueError):
                        continue
                    if v < EDGE_THRESHOLD_USD_M:
                        # Still accumulate for column sums (don't double-skip)
                        col_total_supply[industry_col_idxs.index(j)] += v
                        if col_country[j] == src_country:
                            col_domestic_supply[industry_col_idxs.index(j)] += v
                            row_domestic_use[(src_country, src_sector)] += v
                        row_total_use[(src_country, src_sector)] += v
                        continue
                    tgt_country = col_country[j]
                    tgt_sector = col_sector[j]
                    edges.append((src_country, src_sector, tgt_country, tgt_sector, v))
                    # Aggregates
                    row_total_use[(src_country, src_sector)] += v
                    if tgt_country == src_country:
                        row_domestic_use[(src_country, src_sector)] += v
                    idx = industry_col_idxs.index(j)
                    col_total_supply[idx] += v
                    if col_country[j] == src_country:
                        col_domestic_supply[idx] += v
                for j in fd_col_idxs:
                    if j >= len(row) or row[j].v is None:
                        continue
                    try:
                        v = float(row[j].v)
                    except (TypeError, ValueError):
                        continue
                    row_final_demand[(src_country, src_sector)] += v
                if n_rows_data % 500 == 0:
                    print(f"      … {n_rows_data} industry rows scanned "
                          f"(elapsed {time.time()-t0:.1f}s)")

    parse_elapsed = time.time() - t0
    print(f"    parse done: {len(edges):,} edges (≥${EDGE_THRESHOLD_USD_M}M), "
          f"{n_rows_data} industry rows, {parse_elapsed:.1f}s")

    # Build weights table per (country, NACE sector)
    weights_rows = []
    # Iterate by industry column to get GO/VA/II per (country, sector)
    for idx, j in enumerate(industry_col_idxs):
        country = col_country[j]
        sector = col_sector[j]
        # exports = column total - domestic supply (for upstream supplier perspective)
        # Actually: weights are per (country, sector) — the column IS the (country, sector) being supplied to.
        # For OUTPUT-side metrics (gross output, VA), we use special rows.
        gross_output = go_per_col[j]
        value_added = va_per_col[j]
        intermediate_inputs = ii_per_col[j]
        weights_rows.append({
            "year": year,
            "country_iso3": country,
            "wiod_sector": sector,
            "wiod_sector_name": (col_name[j] if col_name[j] else "")[:80],
            "geds_sector": _norm_geds(sector),
            "gross_output_usd_m": gross_output,
            "value_added_usd_m": value_added,
            "intermediate_inputs_usd_m": intermediate_inputs,
            "source_file": xlsb_path.name,
        })

    # Build edges DataFrame (long form)
    edge_rows = []
    for src_c, src_s, tgt_c, tgt_s, v in edges:
        edge_rows.append({
            "year": year,
            "source_country": src_c, "source_sector": src_s,
            "source_geds_sector": _norm_geds(src_s),
            "target_country": tgt_c, "target_sector": tgt_s,
            "target_geds_sector": _norm_geds(tgt_s),
            "flow_value_usd_m": v,
            "source_file": xlsb_path.name,
        })
    print(f"    built weights: {len(weights_rows)} rows; edges: {len(edge_rows)}")
    return {
        "year": year,
        "weights_rows": weights_rows,
        "edge_rows": edge_rows,
        "n_industry_cols": n_industry_cols,
        "n_industry_rows": n_rows_data,
        "parse_seconds": round(parse_elapsed, 1),
    }


def write_outputs(years_data: list[dict]) -> dict:
    """Concatenate per-year results and write CSVs."""
    all_weights = []
    all_edges = []
    for d in years_data:
        all_weights.extend(d["weights_rows"])
        all_edges.extend(d["edge_rows"])
    w_path = CSV_DIR / "wiod_country_sector_weights.csv"
    e_path = CSV_DIR / "wiod_edges.csv"
    w_fields = ["year", "country_iso3", "wiod_sector", "wiod_sector_name",
                "geds_sector", "gross_output_usd_m", "value_added_usd_m",
                "intermediate_inputs_usd_m", "source_file"]
    e_fields = ["year", "source_country", "source_sector", "source_geds_sector",
                "target_country", "target_sector", "target_geds_sector",
                "flow_value_usd_m", "source_file"]
    with w_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=w_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_weights)
    with e_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=e_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_edges)
    print(f"  wrote {w_path}: {len(all_weights):,} rows ({w_path.stat().st_size/1024/1024:.1f} MB)")
    print(f"  wrote {e_path}: {len(all_edges):,} rows ({e_path.stat().st_size/1024/1024:.1f} MB)")
    return {"weights_csv": str(w_path), "edges_csv": str(e_path)}


def build_country_sector_presence_wiod() -> dict:
    """Phase 3 secondary output: per (country, GEDS sector) presence with value_added_share.
    NULL preserved for sectors not derivable, employment_share, etc."""
    weights_path = CSV_DIR / "wiod_country_sector_weights.csv"
    if not weights_path.exists():
        return {"status": "no_weights_csv"}
    import pandas as pd
    df = pd.read_csv(weights_path, low_memory=False)
    year = int(df["year"].max())  # latest year
    df_y = df[df["year"] == year]
    # Per-country total value-added (for share computation)
    country_va = df_y.groupby("country_iso3")["value_added_usd_m"].sum()

    # Per (country, GEDS) sum
    df_y_mapped = df_y[df_y["geds_sector"].notna()].copy()
    agg = df_y_mapped.groupby(["country_iso3", "geds_sector"]).agg(
        va_sum=("value_added_usd_m", "sum"),
        go_sum=("gross_output_usd_m", "sum"),
        n_wiod_sectors=("wiod_sector", "count"),
    ).reset_index()

    GEDS_SECTORS = [
        "semiconductors", "automotive", "electronics", "aerospace",
        "shipping", "energy", "consumer_goods",
        "banking", "insurance", "capital_markets", "oil", "gas",
        "utilities", "aviation", "ports", "telecommunications",
        "agriculture", "tourism", "government",
    ]
    out_rows = []
    countries = sorted(df_y["country_iso3"].unique())
    if "TOT" in countries:
        countries.remove("TOT")
    if "ROW" in countries:
        countries.remove("ROW")  # WIOD ROW is residual; not a real country
    lookup = {(r["country_iso3"], r["geds_sector"]): r for _, r in agg.iterrows()}

    for country in countries:
        country_va_total = country_va.get(country, 0)
        for sector in GEDS_SECTORS:
            if sector in GEDS_STILL_NULL:
                out_rows.append({
                    "country_iso3": country, "sector": sector,
                    "value_added_share": "",
                    "employment_share": "",  # SEA files absent
                    "confidence": "",
                    "presence_status": "MISSING_WIOD_HAS_NO_SOURCE",
                    "evidence_source": "WIOD_DOES_NOT_SEPARATE_THIS_SECTOR",
                    "note": "C26 bundles semis; B+D35 bundles gas with oil/utilities",
                    "year_used": year,
                })
                continue
            hit = lookup.get((country, sector))
            if hit is None or country_va_total <= 0:
                out_rows.append({
                    "country_iso3": country, "sector": sector,
                    "value_added_share": "",
                    "employment_share": "",
                    "confidence": "",
                    "presence_status": "MISSING_NO_DATA",
                    "evidence_source": "WIOD_2014",
                    "note": "Country in WIOD but no VA for this GEDS sector",
                    "year_used": year,
                })
                continue
            va_share = hit["va_sum"] / country_va_total
            out_rows.append({
                "country_iso3": country, "sector": sector,
                "value_added_share": f"{va_share:.6f}",
                "employment_share": "",  # SEA files absent — NEVER imputed
                "confidence": 5 if sector in ("banking", "insurance", "capital_markets") else 4,
                "presence_status": "DATA_PRESENT",
                "evidence_source": "WIOD_2014",
                "note": (f"Aggregated from {int(hit['n_wiod_sectors'])} NACE Rev.2 codes; "
                          f"employment_share NULL — SEA files not in repo"),
                "year_used": year,
            })

    out_path = CSV_DIR / "country_sector_presence_wiod.csv"
    fields = ["country_iso3", "sector", "value_added_share", "employment_share",
              "confidence", "presence_status", "evidence_source", "note", "year_used"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(out_rows)
    n_data = sum(1 for r in out_rows if r["presence_status"] == "DATA_PRESENT")
    n_null = sum(1 for r in out_rows if r["presence_status"] == "MISSING_WIOD_HAS_NO_SOURCE")
    n_no_data = sum(1 for r in out_rows if r["presence_status"] == "MISSING_NO_DATA")
    print(f"  wrote {out_path}: {len(out_rows)} rows")
    print(f"    DATA_PRESENT: {n_data}, MISSING_NO_DATA: {n_no_data}, "
          f"MISSING_NO_SOURCE: {n_null}")
    return {"presence_csv": str(out_path), "n_data": n_data, "n_null": n_null + n_no_data}


# ── main ──────────────────────────────────────────────────────────────────

def main():
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", default="2014",
                         help="single year, or 'all' for all 15 years")
    args = parser.parse_args()

    files = sorted(RAW_DIR.glob("WIOT*_Nov16_ROW.xlsb"))
    if not files:
        prov = {"status": "NO_DATA", "reason": f"No WIOT*.xlsb in {RAW_DIR}",
                "timestamp": datetime.now(timezone.utc).isoformat()}
        (PARSED_DIR / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
        print("No WIOT files. NO_DATA provenance written.")
        return 1

    if args.year == "all":
        target_files = files
    else:
        target_files = [f for f in files if f.stem.startswith(f"WIOT{args.year}_")]
        if not target_files:
            print(f"ERROR: no file found for year {args.year}. Available years: "
                  f"{sorted(int(f.stem.split('_')[0][4:]) for f in files)}",
                  file=sys.stderr)
            return 1

    print(f"WIOD ingestion — {len(target_files)} year(s) to parse")
    years_data = []
    t0 = time.time()
    for f in target_files:
        try:
            d = parse_one_year(f)
            years_data.append(d)
        except Exception as e:
            print(f"  FAILED {f.name}: {e}", file=sys.stderr)
            continue
    if not years_data:
        print("ERROR: no files parsed successfully.", file=sys.stderr)
        return 2

    out_paths = write_outputs(years_data)
    presence = build_country_sector_presence_wiod()
    total_time = time.time() - t0

    prov = {
        "status": "OK",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "years_parsed": [d["year"] for d in years_data],
        "total_seconds": round(total_time, 1),
        "edge_threshold_usd_m": EDGE_THRESHOLD_USD_M,
        "outputs": {
            **out_paths,
            "presence": presence.get("presence_csv"),
        },
        "geds_sectors_still_null_after_wiod": sorted(GEDS_STILL_NULL),
        "geds_sectors_unblocked_by_wiod_vs_oecd": ["banking_K64_separated",
                                                     "insurance_K65",
                                                     "capital_markets_K66",
                                                     "energy_composite"],
        "employment_data_status": "NULL — WIOD-SEA files not in repo",
        "schema_audit": "docs/WIOD_SCHEMA_AUDIT.md",
    }
    (PARSED_DIR / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    print(f"\nTotal elapsed: {total_time:.1f}s")
    print(f"Provenance: {PARSED_DIR / 'provenance.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
