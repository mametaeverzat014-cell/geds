"""V4 reconnaissance: ground-truth tables for the Phase 1 audit.

Prints (1) the 42-event master registry compactly, (2) the v3 benchmark matrix
targets, (3) which candidate-country graph nodes actually exist. No fabrication,
read-only.
"""
from __future__ import annotations
import csv, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
REPO = Path(__file__).resolve().parent.parent.parent
CSV_DIR = REPO / "backend" / "data" / "csv"


def show_master():
    p = CSV_DIR / "master_event_registry.csv"
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    print(f"\n=== master_event_registry.csv  (N={len(rows)}) ===")
    print("id | name | iso3 | gdp% | scenario")
    for r in rows:
        print(f"{r['event_id']:>3} | {r['event_name'][:52]:52} | "
              f"{(r.get('affected_countries_iso3') or '')[:24]:24} | "
              f"{(r.get('gdp_impact_percent') or ''):>7} | {r.get('is_scenario')}")


def show_v3():
    p = CSV_DIR / "benchmark_event_matrix_v3.csv"
    if not p.exists():
        print("\n(no benchmark_event_matrix_v3.csv)")
        return
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    print(f"\n=== benchmark_event_matrix_v3.csv  (N={len(rows)}) ===")
    print("id | name | target_gdp | status_v3 | countries")
    for r in rows:
        print(f"{r.get('event_id',''):>3} | {r.get('event_name','')[:46]:46} | "
              f"{(r.get('target_gdp') or 'NULL'):>8} | "
              f"{(r.get('mapping_status_v3') or ''):10} | "
              f"{(r.get('countries') or '')[:24]}")


def show_presence():
    p = CSV_DIR / "country_sector_presence_real.csv"
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    want = {"MEX", "TUR", "KOR", "THA", "IDN", "MYS", "IRQ", "KWT", "RUS", "ARG", "GRC", "PHL"}
    present: dict[str, list[str]] = {c: [] for c in want}
    allc: set[str] = set()
    for r in rows:
        c = r["country_iso3"]
        allc.add(c)
        if c in want and r.get("presence_status") == "DATA_PRESENT":
            present[c].append(r["sector"])
    print(f"\n=== graph node availability (presence_status==DATA_PRESENT) ===")
    print(f"total distinct countries in presence file: {len(allc)}")
    for c in sorted(want):
        secs = present[c]
        flag = "IN GRAPH" if secs else "*** ABSENT ***"
        print(f"  {c}: {flag}  ({len(secs)} sectors) {','.join(secs[:8])}")


if __name__ == "__main__":
    show_master()
    show_v3()
    show_presence()
