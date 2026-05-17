"""Compare REAL Comtrade-derived dep_weights vs hardcoded values in seed_data.py.

Reads:
    backend/data/csv/comtrade_edges.csv  ← real, fetched
    backend/app/data/seed_data.py        ← hardcoded MVP values

Outputs:
    backend/data/csv/comtrade_vs_seed.csv  ← side-by-side comparison
    stdout: top discrepancies, calibration quality report

This is the **honest validation** of how good our hardcoded MVP was.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.seed_data import EDGES_RAW


def parse_node(node_id: str) -> tuple[str, str]:
    """'TWN:semiconductors' → ('TWN', 'semiconductors')"""
    parts = node_id.split(":", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("?", "?")


def load_real_edges(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    comtrade_path = repo / "data" / "csv" / "comtrade_edges.csv"
    out_path = repo / "data" / "csv" / "comtrade_vs_seed.csv"

    if not comtrade_path.exists():
        print(f"ERROR: {comtrade_path} not found. Run scripts.fetch_comtrade first.")
        return 1

    real_rows = load_real_edges(comtrade_path)
    print(f"Loaded {len(real_rows)} real Comtrade edges from {comtrade_path.name}")

    # Index real edges by (source_iso3, source_industry, target_iso3, target_industry)
    real_idx: dict[tuple[str, str, str, str], dict] = {}
    for r in real_rows:
        key = (r["source_iso3"], r["source_industry"], r["target_iso3"], r["target_industry"])
        real_idx[key] = r

    # Hardcoded edges from seed_data — EDGES_RAW format:
    # (src_node_id, tgt_node_id, dep, sub, route, res, recov, flow_b)
    hardcoded: list[tuple[str, str, str, str, float, float]] = []
    for src, tgt, dep, sub, route, res, recov, flow_b in EDGES_RAW:
        src_c, src_i = parse_node(src)
        tgt_c, tgt_i = parse_node(tgt)
        hardcoded.append((src_c, src_i, tgt_c, tgt_i, dep, flow_b))

    print(f"Loaded {len(hardcoded)} hardcoded edges from seed_data.EDGES_RAW")
    print()

    # Compare: for each hardcoded edge, find matching real edge
    comparison: list[dict] = []
    matched = 0
    for src_c, src_i, tgt_c, tgt_i, hc_dep, hc_flow_b in hardcoded:
        key = (src_c, src_i, tgt_c, tgt_i)
        real = real_idx.get(key)
        # Also try cross-industry match (we model TWN:semi → JPN:auto but real
        # Comtrade is TWN:semi → JPN:semi — different concept, mark separately)
        cross_industry = src_i != tgt_i
        match_status = "missing"
        real_dep = None
        real_flow_b = None
        diff = None
        ratio = None
        if real is not None:
            match_status = "exact_match"
            real_dep = float(real["dependency_weight"])
            real_flow_b = float(real["flow_value_usd"]) / 1e9
            diff = real_dep - hc_dep
            ratio = real_dep / hc_dep if hc_dep > 0 else None
            matched += 1
        elif cross_industry:
            # Try same-source-industry match for the cross-industry hardcoded edge
            alt_key = (src_c, src_i, tgt_c, src_i)
            alt = real_idx.get(alt_key)
            if alt is not None:
                match_status = "cross_industry_proxy"
                real_dep = float(alt["dependency_weight"])
                real_flow_b = float(alt["flow_value_usd"]) / 1e9
                diff = real_dep - hc_dep
                ratio = real_dep / hc_dep if hc_dep > 0 else None

        comparison.append({
            "source": f"{src_c}:{src_i}",
            "target": f"{tgt_c}:{tgt_i}",
            "match_status": match_status,
            "hardcoded_dep_weight": round(hc_dep, 4),
            "real_dep_weight": round(real_dep, 4) if real_dep is not None else None,
            "diff_real_minus_hc": round(diff, 4) if diff is not None else None,
            "ratio_real_over_hc": round(ratio, 3) if ratio is not None else None,
            "hardcoded_flow_b_usd": round(hc_flow_b, 2),
            "real_flow_b_usd": round(real_flow_b, 2) if real_flow_b is not None else None,
        })

    # Write CSV
    if comparison:
        with out_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=comparison[0].keys())
            w.writeheader()
            for row in comparison:
                w.writerow(row)
        print(f"Wrote {out_path}")

    # Stats
    exact = [c for c in comparison if c["match_status"] == "exact_match"]
    cross = [c for c in comparison if c["match_status"] == "cross_industry_proxy"]
    missing = [c for c in comparison if c["match_status"] == "missing"]

    print()
    print(f"=== MATCH SUMMARY ===")
    print(f"  exact matches:           {len(exact):3d} / {len(hardcoded)}")
    print(f"  cross-industry proxies:  {len(cross):3d}")
    print(f"  no Comtrade data:        {len(missing):3d}")

    if exact:
        diffs = np.array([c["diff_real_minus_hc"] for c in exact])
        ratios = np.array([c["ratio_real_over_hc"] for c in exact if c["ratio_real_over_hc"] is not None])
        print()
        print(f"=== CALIBRATION QUALITY (exact matches) ===")
        print(f"  mean diff (real - hardcoded):  {diffs.mean():+.4f}")
        print(f"  median absolute diff:          {np.median(np.abs(diffs)):.4f}")
        print(f"  RMSE:                          {np.sqrt((diffs**2).mean()):.4f}")
        if len(ratios) > 0:
            print(f"  median ratio (real/hc):        {np.median(ratios):.2f}x")
            print(f"  ratio range:                   {ratios.min():.2f}x .. {ratios.max():.2f}x")

    # Top under/over estimates
    print()
    print(f"=== TOP 10 OVER-ESTIMATES (hardcoded > real) ===")
    over = sorted([c for c in exact if c["diff_real_minus_hc"] is not None],
                  key=lambda x: x["diff_real_minus_hc"])[:10]
    for c in over:
        print(f"  {c['source']:<22s} -> {c['target']:<22s}  "
              f"hc={c['hardcoded_dep_weight']:.3f}  real={c['real_dep_weight']:.3f}  "
              f"diff={c['diff_real_minus_hc']:+.3f}")

    print()
    print(f"=== TOP 10 UNDER-ESTIMATES (hardcoded < real) ===")
    under = sorted([c for c in exact if c["diff_real_minus_hc"] is not None],
                   key=lambda x: -x["diff_real_minus_hc"])[:10]
    for c in under:
        print(f"  {c['source']:<22s} -> {c['target']:<22s}  "
              f"hc={c['hardcoded_dep_weight']:.3f}  real={c['real_dep_weight']:.3f}  "
              f"diff={c['diff_real_minus_hc']:+.3f}")

    print()
    print(f"=== TOP 10 LARGEST REAL EDGES NOT IN HARDCODED MODEL ===")
    real_keys_in_hc = {(c["source"].split(":")[0], c["source"].split(":")[1],
                       c["target"].split(":")[0], c["target"].split(":")[1])
                      for c in comparison}
    new_edges = []
    for r in real_rows:
        k = (r["source_iso3"], r["source_industry"], r["target_iso3"], r["target_industry"])
        if k not in real_keys_in_hc:
            new_edges.append(r)
    new_edges.sort(key=lambda x: float(x["dependency_weight"]), reverse=True)
    for r in new_edges[:10]:
        print(f"  {r['source_iso3']}:{r['source_industry']:<18s} -> "
              f"{r['target_iso3']}:{r['target_industry']:<18s}  "
              f"dep={float(r['dependency_weight']):.3f}  "
              f"flow={float(r['flow_value_usd'])/1e9:.2f}B")

    return 0


if __name__ == "__main__":
    sys.exit(main())
