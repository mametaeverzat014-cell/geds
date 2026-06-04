"""Phase 2 deliverable generator — benchmark_event_matrix_v4.csv.

Builds the complete, auditable V4 benchmark ledger:
  * 42 carried-forward registry events (NULL targets preserved verbatim);
  * 7 net-new audited events promoted from the 90 expansion candidates
    (1 MAPPED + 6 PARTIAL), with the exact seed nodes used by the engine run;
  * 87 excluded expansion candidates (NULL target preserved, exclusion reason recorded).

engine_eligible + v4_corpus columns mark precisely which rows feed each evaluation
set (current N=21 / v4_primary N=22 / v4_max N=28). No synthetic targets.
"""
from __future__ import annotations
import csv, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
REPO = Path(__file__).resolve().parent.parent.parent
CALIB = REPO / "backend" / "data" / "calibration"
CSV_DIR = REPO / "backend" / "data" / "csv"
OUT = CSV_DIR / "benchmark_event_matrix_v4.csv"

ELIGIBLE_21 = {1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 14, 15, 16, 21, 22, 23, 24, 26, 27, 28, 30}

# New engine-eligible events — exact seed nodes/targets as used by run_benchmark_v4.py.
# (event_id, name, year, iso3, seed_sector, target, status, corpus, source)
NEW_EVENTS = [
    (101, "1994 Mexican Peso Crisis (Tequila Crisis)", "1994", "MEX", "banking",
     "0.048", "MAPPED", "v4_primary;v4_max",
     "World Bank projected 1995 Mexico GDP -4.8% (IMF history vol. c10.pdf); WB *projection*, realized ~-6% not in cited source so not substituted"),
    (102, "1999 Turkey Izmit (Kocaeli) Earthquake", "1999", "TUR", "consumer_goods",
     "0.05", "PARTIAL", "v4_max",
     "OECD 1999 Turkish earthquake report '5 percent drop in GDP' (figure-type ambiguous vs 3%-of-GDP damage figure)"),
    (103, "1997 Asian Financial Crisis (Korea)", "1997", "KOR", "banking",
     "0.07", "PARTIAL", "v4_max", "World Bank GEP 1998-99 country output-contraction tables (approx)"),
    (104, "1997 Asian Financial Crisis (Thailand)", "1997", "THA", "banking",
     "0.07", "PARTIAL", "v4_max", "World Bank GEP 1998-99 country output-contraction tables (approx)"),
    (105, "1997 Asian Financial Crisis (Malaysia)", "1997", "MYS", "banking",
     "0.05", "PARTIAL", "v4_max", "World Bank GEP 1998-99 country output-contraction tables (approx)"),
    (106, "1997 Asian Financial Crisis (Indonesia)", "1997", "IDN", "banking",
     "0.15", "PARTIAL", "v4_max", "World Bank GEP 1998-99 country output-contraction tables (approx)"),
    (107, "1997 Asian Financial Crisis (Philippines)", "1997", "PHL", "banking",
     "0.005", "PARTIAL", "v4_max", "World Bank GEP 1998-99 country output-contraction tables (approx)"),
]

OVERRIDE_IDX = {7, 4, 5}  # candidate idxs promoted to NEW_EVENTS (excluded from the 'excluded' list)

HEADER = [
    "event_id", "event_name", "year", "countries_iso3", "sectors_or_seed",
    "target_gdp", "target_source", "confidence", "mapping_status_v4",
    "engine_eligible", "v4_corpus", "record_type", "source_url", "v4_note",
]


def classify_excluded(r: dict) -> str:
    dup = (r.get("dup") or "").strip()
    if dup:
        return f"UNMAPPABLE: duplicate of existing registry event ({dup})"
    if (not r.get("has_gdp_keyword")) or r.get("money_or_physical_only"):
        return "UNMAPPABLE: no GDP%-of-output figure (money/physical units only)"
    snips = r.get("gdp_pct_snippets") or []
    why = (snips[0] if snips else "GDP keyword without usable % figure")
    return f"UNMAPPABLE: GDP% present but wrong figure-type ('{why}')"


def main() -> int:
    cand = json.loads((CALIB / "v4_preaudit.json").read_text(encoding="utf-8"))
    v3 = list(csv.DictReader((CSV_DIR / "benchmark_event_matrix_v3.csv").open(encoding="utf-8")))

    rows: list[list[str]] = []

    # ---- 42 carried-forward registry events (preserve NULL) ----
    for rr in v3:
        eid_s = rr.get("event_id", "")
        try:
            eid = int(eid_s)
        except ValueError:
            eid = -1
        elig = eid in ELIGIBLE_21
        target = (rr.get("target_gdp") or "").strip()  # may be 'NULL' or '' -> preserve as-is
        corpus = "current;v4_primary;v4_max" if elig else "none"
        rows.append([
            eid_s,
            rr.get("event_name", ""),
            "",  # year not in v3 matrix
            rr.get("countries", ""),
            rr.get("sectors_mapped", ""),
            target,  # NULL preserved verbatim
            f"carried_forward_v3 (peer_reviewed={rr.get('has_peer_review','')})",
            rr.get("confidence", ""),
            rr.get("mapping_status_v3", ""),
            "YES" if elig else "no",
            corpus,
            "registry_existing",
            "",
            (rr.get("v3_change_note") or "").replace("\n", " "),
        ])

    # ---- 7 net-new audited events ----
    cand_by_idx = {r["idx"]: r for r in cand}
    idx_for_new = {101: 7, 102: 4, 103: 5, 104: 5, 105: 5, 106: 5, 107: 5}
    for (eid, name, year, iso3, seed_sector, target, status, corpus, source) in NEW_EVENTS:
        url = cand_by_idx.get(idx_for_new[eid], {}).get("source_url", "")
        rows.append([
            str(eid), name, year, iso3, f"{iso3}:{seed_sector}",
            target, source, "High", status, "YES", corpus, "expansion_new",
            url, f"promoted from expansion candidate idx={idx_for_new[eid]}",
        ])

    # ---- 87 excluded expansion candidates (NULL target preserved) ----
    n_excl = 0
    for r in cand:
        if r["idx"] in OVERRIDE_IDX:
            continue
        n_excl += 1
        reason = classify_excluded(r)
        rows.append([
            f"C{r['idx']:02d}",
            r["event_name"],
            r.get("year", ""),
            ",".join(r.get("iso3") or []),
            ",".join(r.get("sectors_mapped") or []),
            "",  # target NULL preserved (no synthetic target)
            reason,
            r.get("confidence", ""),
            "UNMAPPABLE",
            "no",
            "none",
            "expansion_excluded",
            r.get("source_url", ""),
            "",
        ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        wtr = csv.writer(f)
        wtr.writerow(HEADER)
        wtr.writerows(rows)

    n_reg = len(v3)
    n_new = len(NEW_EVENTS)
    n_elig = sum(1 for row in rows if row[9] == "YES")
    print(f"wrote {OUT}")
    print(f"  rows: {len(rows)}  (registry={n_reg}, new={n_new}, excluded={n_excl})")
    print(f"  engine_eligible rows (YES): {n_elig}  "
          f"[expect 21 existing + 7 new = 28]")
    # corpus tallies
    cur = sum(1 for row in rows if "current" in row[10])
    prim = sum(1 for row in rows if "v4_primary" in row[10])
    mx = sum(1 for row in rows if "v4_max" in row[10])
    print(f"  corpus membership: current={cur}  v4_primary={prim}  v4_max={mx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
