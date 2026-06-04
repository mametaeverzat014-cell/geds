"""Phase 4 — Merge OECD ICIO + WIOD evidence into country_sector_presence_real.csv.

Strict merge rules (per user spec):
  - OECD remains primary source for trade/output structure
  - WIOD fills labor/employment-proxy fields AND splits OECD K bundle
  - If both sources have data for the same field → preserve BOTH, add conflict_note
  - Never overwrite silently
  - NULL preserved when both sources are absent

Updates `backend/data/csv/country_sector_presence_real.csv` IN PLACE with
a backup written to `country_sector_presence_real_oecd_only_backup.csv`.
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CSV_DIR = REPO / "backend" / "data" / "csv"


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    oecd_path = CSV_DIR / "country_sector_presence_real.csv"
    wiod_path = CSV_DIR / "country_sector_presence_wiod.csv"
    if not oecd_path.exists() or not wiod_path.exists():
        print(f"ERROR: missing inputs", file=sys.stderr)
        return 1

    # Backup OECD-only version
    backup_path = CSV_DIR / "country_sector_presence_real_oecd_only_backup.csv"
    backup_path.write_text(oecd_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Backed up OECD-only → {backup_path}")

    # Load both
    with oecd_path.open(encoding="utf-8", newline="") as f:
        oecd_rows = list(csv.DictReader(f))
    with wiod_path.open(encoding="utf-8", newline="") as f:
        wiod_rows = list(csv.DictReader(f))

    oecd_by_key = {(r["country_iso3"], r["sector"]): r for r in oecd_rows}
    wiod_by_key = {(r["country_iso3"], r["sector"]): r for r in wiod_rows}
    all_keys = sorted(set(oecd_by_key.keys()) | set(wiod_by_key.keys()))

    print(f"OECD keys: {len(oecd_by_key)}; WIOD keys: {len(wiod_by_key)}; "
          f"union: {len(all_keys)}")

    merged_rows = []
    n_both = n_oecd_only = n_wiod_only = n_neither = n_conflict = 0
    for key in all_keys:
        country, sector = key
        oecd = oecd_by_key.get(key, {})
        wiod = wiod_by_key.get(key, {})

        # Pull values from each source. OECD has gdp_share + trade_share (no employment).
        # WIOD has value_added_share (proxy for labor) + employment_share (NULL).
        oecd_gdp = oecd.get("gdp_share", "")
        oecd_trade = oecd.get("trade_share", "")
        oecd_status = oecd.get("presence_status", "")
        oecd_source = oecd.get("evidence_source", "")
        oecd_note = oecd.get("note", "")

        wiod_va = wiod.get("value_added_share", "")
        wiod_emp = wiod.get("employment_share", "")
        wiod_status = wiod.get("presence_status", "")
        wiod_source = wiod.get("evidence_source", "")
        wiod_note = wiod.get("note", "")

        # Status booleans
        has_oecd_data = oecd_status == "DATA_PRESENT"
        has_wiod_data = wiod_status == "DATA_PRESENT"

        # Conflict detection: both have value-added derived numbers
        # OECD gdp_share ≈ WIOD value_added_share (both are VA-based shares,
        # different vintages 2022 vs 2014, different sector aggregations).
        # We do NOT overwrite. We keep both columns.
        conflict_note = ""
        if has_oecd_data and has_wiod_data:
            n_both += 1
            try:
                oecd_v = float(oecd_gdp) if oecd_gdp else None
                wiod_v = float(wiod_va) if wiod_va else None
                if oecd_v is not None and wiod_v is not None:
                    diff_rel = abs(oecd_v - wiod_v) / max(oecd_v, wiod_v, 1e-9)
                    if diff_rel > 0.30:  # >30% disagreement
                        n_conflict += 1
                        conflict_note = (f"CONFLICT: OECD gdp_share={oecd_v:.4f} (2022) vs "
                                         f"WIOD value_added_share={wiod_v:.4f} (2014), "
                                         f"relative diff={diff_rel:.2%}. Vintages differ.")
            except ValueError:
                pass
        elif has_oecd_data:
            n_oecd_only += 1
        elif has_wiod_data:
            n_wiod_only += 1
        else:
            n_neither += 1

        # Final presence status
        if has_oecd_data or has_wiod_data:
            presence_status = "DATA_PRESENT"
        else:
            # Both NULL — see why
            if (oecd_status == "MISSING_OECD_HAS_NO_SOURCE"
                or wiod_status == "MISSING_WIOD_HAS_NO_SOURCE"):
                presence_status = "MISSING_NO_SOURCE_ANY"
            else:
                presence_status = "MISSING_NO_DATA"

        # Composite confidence
        if has_oecd_data and has_wiod_data:
            confidence = 5  # two sources confirm
        elif has_oecd_data or has_wiod_data:
            confidence = 4
        else:
            confidence = ""

        # Source citation (no overwrite — both shown)
        sources = []
        if has_oecd_data:
            sources.append("OECD_ICIO_2022")
        if has_wiod_data:
            sources.append("WIOD_2014")
        evidence_source = "+".join(sources) if sources else "NONE"

        # Composite note
        notes = []
        if oecd_note:
            notes.append(f"OECD: {oecd_note[:100]}")
        if wiod_note:
            notes.append(f"WIOD: {wiod_note[:100]}")
        if conflict_note:
            notes.insert(0, conflict_note)
        composite_note = " | ".join(notes)

        merged_rows.append({
            "country_iso3": country,
            "sector": sector,
            "gdp_share_oecd": oecd_gdp,           # OECD source preserved
            "trade_share_oecd": oecd_trade,
            "value_added_share_wiod": wiod_va,    # WIOD source preserved separately
            "employment_share": wiod_emp,         # NULL — SEA files absent
            "confidence": confidence,
            "presence_status": presence_status,
            "evidence_source": evidence_source,
            "conflict_note": conflict_note,
            "note": composite_note[:300],
            "year_oecd": oecd.get("year_used", ""),
            "year_wiod": wiod.get("year_used", ""),
        })

    fields = ["country_iso3", "sector",
              "gdp_share_oecd", "trade_share_oecd",
              "value_added_share_wiod", "employment_share",
              "confidence", "presence_status", "evidence_source",
              "conflict_note", "note", "year_oecd", "year_wiod"]
    with oecd_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(merged_rows)

    print(f"\nMerge stats:")
    print(f"  Total merged rows: {len(merged_rows)}")
    print(f"  Both OECD and WIOD have data: {n_both}")
    print(f"    of which CONFLICTING (>30% disagreement): {n_conflict}")
    print(f"  OECD-only DATA_PRESENT: {n_oecd_only}")
    print(f"  WIOD-only DATA_PRESENT: {n_wiod_only}")
    print(f"  Neither has data: {n_neither}")
    print(f"\nWrote (in place, overwriting prior OECD-only): {oecd_path}")
    print(f"Backup of OECD-only: {backup_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
