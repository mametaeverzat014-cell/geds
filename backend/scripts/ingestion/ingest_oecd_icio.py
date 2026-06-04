"""OECD ICIO ingestion — REAL CSV parser.

Replaces the prior placeholder. Parses the 7 yearly OECD ICIO SML CSVs in
backend/data/raw/oecd_icio/<year>_SML.csv into 2 normalised CSVs.

Strict rules respected:
  - Every output row has source_file + source_year columns.
  - Original OECD sector code preserved alongside GEDS-normalised name.
  - Original OECD country code preserved alongside ISO3 (they happen to match).
  - Edge flows ≥ USD 1M only (threshold documented in OECD_ICIO_SCHEMA_AUDIT.md).
  - Sectors that cannot be derived from OECD (semiconductors, gas, insurance,
    capital_markets) are NOT emitted as edges — they would be NULL anyway.
  - Aggregate weights table emits NULL for any field that has no OECD source.

Outputs:
  backend/data/csv/oecd_icio_edges.csv
  backend/data/csv/oecd_country_sector_weights.csv
  backend/data/raw/oecd_icio/parsed/provenance.json
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent.parent.parent
RAW_DIR = REPO / "backend" / "data" / "raw" / "oecd_icio"
PARSED_DIR = RAW_DIR / "parsed"
CSV_DIR = REPO / "backend" / "data" / "csv"
PARSED_DIR.mkdir(parents=True, exist_ok=True)


# ── OECD → GEDS sector mapping (from OECD_ICIO_SCHEMA_AUDIT.md) ────────────

# Clean direct maps (one OECD sector → one GEDS sector)
DIRECT_MAP: dict[str, str] = {
    "A01": "agriculture", "A02": "agriculture", "A03": "agriculture",
    "C26": "electronics",          # NOTE: bundles semis (no clean split possible)
    "C27": "electronics",
    "C29": "automotive",
    "C302T309": "aerospace",       # NOTE: bundles rail/military
    "H49": "shipping",
    "H50": "shipping",
    "H51": "aviation",
    "H52": "ports",
    "I": "tourism",
    "J58T60": "telecommunications",
    "J61": "telecommunications",
    "J62_63": "telecommunications",
    "K": "banking",                # NOTE: bundles insurance + capital_markets
    "O": "government",
    "P": "government",
    "D": "utilities",
    "E": "utilities",
    "B06": "oil",                  # NOTE: bundles gas
    "C19": "oil",                  # refined petroleum
    # Consumer-goods aggregate
    "C10T12": "consumer_goods", "C13T15": "consumer_goods",
    "C16": "consumer_goods", "C17_18": "consumer_goods",
    "C20": "consumer_goods", "C21": "consumer_goods",
    "C22": "consumer_goods", "C23": "consumer_goods",
    "C28": "consumer_goods", "C31T33": "consumer_goods",
    "G": "consumer_goods",
}

# GEDS sectors that cannot be derived from OECD ICIO (will be NULL downstream)
GEDS_NOT_IN_OECD = {"semiconductors", "gas", "insurance", "capital_markets"}

# Final demand column codes (excluded from industry rows/cols)
FINAL_DEMAND_CODES = {"HFCE", "NPISH", "GGFC", "GFCF", "INVNT", "DPABR"}

# Special row labels (column-wise summaries)
SPECIAL_ROWS = {"TLS", "VA", "OUT"}

# Edge threshold (USD millions)
EDGE_THRESHOLD_USD_M = 1.0


def _parse_label(label: str) -> tuple[str, str] | None:
    """Decode 'COUNTRY_SECTOR' label. Returns (country, sector) or None."""
    if not label or label in SPECIAL_ROWS:
        return None
    if "_" not in label:
        return None
    country, sector = label.split("_", 1)
    return country, sector


def _is_industry(sector: str) -> bool:
    """Industry sector (not final-demand) — for filtering."""
    return sector not in FINAL_DEMAND_CODES


def _normalise_to_geds(oecd_sector: str) -> str | None:
    """Map OECD ISIC code to GEDS sector. Returns None if no clean mapping."""
    return DIRECT_MAP.get(oecd_sector)


def parse_one_year(csv_path: Path) -> tuple[pd.DataFrame, dict]:
    """Parse one ICIO CSV.
    Returns (long-form DataFrame of cells above threshold, stats dict).
    """
    year = int(csv_path.stem.split("_")[0])
    t0 = time.time()
    print(f"  parsing {csv_path.name} ({csv_path.stat().st_size / 1024 / 1024:.0f} MB)...", flush=True)
    df = pd.read_csv(csv_path, low_memory=False)
    # First col is the row label
    df = df.set_index(df.columns[0])
    # Drop "OUT" column (we'll use OUT row instead for weights)
    df_no_out_col = df.drop(columns=["OUT"]) if "OUT" in df.columns else df
    load_time = time.time() - t0

    # Separate industry rows from special rows
    industry_row_mask = ~df_no_out_col.index.isin(SPECIAL_ROWS)
    industry_df = df_no_out_col.loc[industry_row_mask]
    # Separate industry columns from final-demand columns
    industry_cols = []
    final_demand_cols = []
    for c in industry_df.columns:
        parsed = _parse_label(c)
        if parsed is None:
            continue
        ctry, sec = parsed
        if sec in FINAL_DEMAND_CODES:
            final_demand_cols.append(c)
        else:
            industry_cols.append(c)

    # Build long-form edges: row × col with flow >= threshold
    t1 = time.time()
    arr = industry_df[industry_cols].to_numpy(dtype=np.float64)
    # Filter mask
    mask = arr >= EDGE_THRESHOLD_USD_M
    rows_idx, cols_idx = np.where(mask)
    n_edges = len(rows_idx)
    row_labels = industry_df.index.to_numpy()
    col_labels = np.array(industry_cols)

    edges_data = {
        "source_label": row_labels[rows_idx],
        "target_label": col_labels[cols_idx],
        "flow_value_usd_m": arr[rows_idx, cols_idx],
    }
    edges_df = pd.DataFrame(edges_data)
    # Split labels
    edges_df[["source_country", "source_sector"]] = edges_df["source_label"].str.split("_", n=1, expand=True)
    edges_df[["target_country", "target_sector"]] = edges_df["target_label"].str.split("_", n=1, expand=True)
    edges_df = edges_df.drop(columns=["source_label", "target_label"])
    edges_df["year"] = year
    edges_df["source_file"] = csv_path.name
    edge_time = time.time() - t1

    # Per-(country, sector) weights
    t2 = time.time()
    # gross_output: OUT column for each (country, sector) (industry rows only)
    out_col = df["OUT"] if "OUT" in df.columns else None
    # value_added: VA row, industry columns
    va_row = df.loc["VA"] if "VA" in df.index else None
    # intermediate_inputs: column sum over industry rows
    intermediate_inputs = industry_df[industry_cols].sum(axis=0)  # series indexed by col_label
    # final_demand (domestic + foreign): row sum over final-demand columns (this is consumption-side)
    if final_demand_cols:
        final_demand_total = industry_df[final_demand_cols].sum(axis=1)  # series indexed by row_label
    else:
        final_demand_total = pd.Series(0.0, index=industry_df.index)
    # exports: row sum over industry cols where target country != source country
    # imports: column sum over industry rows where source country != target country
    # We need to compute these row/col-wise per (country, sector). Do via long form for speed.
    # Build a (source_country, source_sector, target_country, target_sector) long form WITHOUT threshold,
    # then group. But that's 4050 × 4050 = 16M cells — too much memory.
    # Instead: compute exports per row by subtracting domestic-row-sum from total row sum.
    industry_arr_full = industry_df[industry_cols].to_numpy(dtype=np.float64)
    row_labels_full = industry_df.index.to_numpy()
    col_labels_full = np.array(industry_cols)
    # Per-row total over all industry cols
    row_total_intermediate_use = industry_arr_full.sum(axis=1)
    # Per-row domestic use (cols whose country = row country)
    # Build vectorised: for each row i, sum cols where col_country == row_country
    row_countries = np.array([lbl.split("_", 1)[0] for lbl in row_labels_full])
    col_countries = np.array([lbl.split("_", 1)[0] for lbl in col_labels_full])
    # For each row, find matching column country indices
    # Use boolean broadcast over (n_rows, n_cols) — memory intensive but each is uint8
    # n_rows × n_cols = 4050 × 4050 = 16M bytes ≈ 16 MB. Fine.
    country_match = row_countries[:, None] == col_countries[None, :]
    domestic_intermediate_use_per_row = (industry_arr_full * country_match).sum(axis=1)
    # Exports = row sum to foreign cols (intermediate) + row sum to foreign final demand
    foreign_intermediate_use_per_row = row_total_intermediate_use - domestic_intermediate_use_per_row
    if final_demand_cols:
        fd_arr = industry_df[final_demand_cols].to_numpy(dtype=np.float64)
        fd_col_countries = np.array([c.split("_", 1)[0] for c in final_demand_cols])
        fd_country_match = row_countries[:, None] == fd_col_countries[None, :]
        domestic_final_per_row = (fd_arr * fd_country_match).sum(axis=1)
        foreign_final_per_row = fd_arr.sum(axis=1) - domestic_final_per_row
    else:
        domestic_final_per_row = np.zeros(len(row_labels_full))
        foreign_final_per_row = np.zeros(len(row_labels_full))
    exports_per_row = foreign_intermediate_use_per_row + foreign_final_per_row

    # Imports per (country, sector): symmetric — col_total - domestic_col_total
    col_total_intermediate_use = industry_arr_full.sum(axis=0)
    domestic_col_use = (industry_arr_full * country_match).sum(axis=0)
    imports_per_col = col_total_intermediate_use - domestic_col_use
    # Note: final-demand cols don't have "imports" in the same sense (they're consumption).

    # Build per-(country, sector) aggregate DataFrame
    # Rows: each industry row label
    weights = pd.DataFrame({
        "label": row_labels_full,
        "gross_output_usd_m": (out_col.loc[row_labels_full].to_numpy(dtype=np.float64)
                                if out_col is not None else np.full(len(row_labels_full), np.nan)),
        "intermediate_inputs_usd_m": intermediate_inputs.reindex(row_labels_full).to_numpy(dtype=np.float64),
        "final_demand_total_usd_m": final_demand_total.reindex(row_labels_full).to_numpy(dtype=np.float64),
        "domestic_final_demand_usd_m": domestic_final_per_row,
        "foreign_final_demand_exports_usd_m": foreign_final_per_row,
        "exports_total_usd_m": exports_per_row,
        "imports_total_usd_m": imports_per_col,
    })
    weights[["country_iso3", "oecd_sector"]] = weights["label"].str.split("_", n=1, expand=True)
    # value_added: VA row, indexed by industry column label
    if va_row is not None:
        va_lookup = va_row.reindex(row_labels_full).to_numpy(dtype=np.float64)
        weights["value_added_usd_m"] = va_lookup
    else:
        weights["value_added_usd_m"] = np.nan
    weights = weights.drop(columns=["label"])
    weights["geds_sector"] = weights["oecd_sector"].map(_normalise_to_geds)
    weights["year"] = year
    weights["source_file"] = csv_path.name
    weight_time = time.time() - t2

    print(f"    edges: {n_edges:,} above ${EDGE_THRESHOLD_USD_M}M threshold "
          f"(load {load_time:.1f}s, edges {edge_time:.1f}s, weights {weight_time:.1f}s)")

    # Map sectors in edges
    edges_df["source_geds_sector"] = edges_df["source_sector"].map(_normalise_to_geds)
    edges_df["target_geds_sector"] = edges_df["target_sector"].map(_normalise_to_geds)
    return edges_df, {
        "year": year, "file": csv_path.name,
        "n_edges": n_edges,
        "n_weight_rows": len(weights),
        "load_seconds": round(load_time, 1),
        "edge_seconds": round(edge_time, 1),
        "weight_seconds": round(weight_time, 1),
    }, weights


# Override: parse_one_year was defined to return 2-tuple. Re-export as 3-tuple by handling above.

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    files = sorted(RAW_DIR.glob("*_SML.csv"))
    if not files:
        prov = {"status": "NO_DATA", "reason": f"No *_SML.csv in {RAW_DIR}",
                "timestamp": datetime.now(timezone.utc).isoformat()}
        (PARSED_DIR / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
        print("No CSVs found. NO_DATA provenance written.")
        return 1

    print(f"OECD ICIO ingestion — found {len(files)} yearly CSVs")
    all_edges = []
    all_weights = []
    per_year = []
    t0 = time.time()
    for f in files:
        edges_df, stats, weights_df = parse_one_year(f)
        all_edges.append(edges_df)
        all_weights.append(weights_df)
        per_year.append(stats)

    print()
    print("Concatenating + writing outputs...")
    edges_all = pd.concat(all_edges, ignore_index=True)
    weights_all = pd.concat(all_weights, ignore_index=True)

    edges_path = CSV_DIR / "oecd_icio_edges.csv"
    edges_cols = ["year", "source_country", "source_sector", "source_geds_sector",
                  "target_country", "target_sector", "target_geds_sector",
                  "flow_value_usd_m", "source_file"]
    edges_all[edges_cols].to_csv(edges_path, index=False)
    print(f"  wrote {edges_path}: {len(edges_all):,} rows, "
          f"{edges_path.stat().st_size / 1024 / 1024:.0f} MB")

    weights_path = CSV_DIR / "oecd_country_sector_weights.csv"
    weights_cols = ["year", "country_iso3", "oecd_sector", "geds_sector",
                    "gross_output_usd_m", "value_added_usd_m",
                    "intermediate_inputs_usd_m", "final_demand_total_usd_m",
                    "domestic_final_demand_usd_m", "foreign_final_demand_exports_usd_m",
                    "exports_total_usd_m", "imports_total_usd_m", "source_file"]
    weights_all[weights_cols].to_csv(weights_path, index=False)
    print(f"  wrote {weights_path}: {len(weights_all):,} rows, "
          f"{weights_path.stat().st_size / 1024 / 1024:.0f} MB")

    total_time = time.time() - t0
    prov = {
        "status": "OK",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_seconds": round(total_time, 1),
        "edge_threshold_usd_m": EDGE_THRESHOLD_USD_M,
        "per_year": per_year,
        "outputs": {
            "oecd_icio_edges.csv": {"rows": len(edges_all), "path": str(edges_path)},
            "oecd_country_sector_weights.csv": {"rows": len(weights_all), "path": str(weights_path)},
        },
        "sector_mapping": {
            "direct_oecd_to_geds": DIRECT_MAP,
            "geds_sectors_not_derivable_from_oecd": sorted(GEDS_NOT_IN_OECD),
        },
        "source_files": [str(f) for f in files],
        "schema_audit": "docs/OECD_ICIO_SCHEMA_AUDIT.md",
    }
    (PARSED_DIR / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    print(f"\nTotal elapsed: {total_time:.1f}s")
    print(f"Provenance: {PARSED_DIR / 'provenance.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
