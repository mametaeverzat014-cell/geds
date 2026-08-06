"""Is the v2 -> v3 spatial-recall result an artifact of the reach threshold?

The paper's strongest positive claim is structural: swapping the hand-authored
36-node graph for the 405-node OECD ICIO graph lifts pooled spatial recall from
0.29 to 0.79 with no parameter change. That number is computed at a single
reach threshold (output loss >= 0.01), and there is an obvious confound:

    v3 runs roughly 4x hot in magnitude (raw MAE 0.068 against a target scale of
    ~0.023; see v3_scale_experiment.json). If every v3 trajectory is uniformly
    larger, more nodes clear a FIXED threshold for reasons that have nothing to
    do with network structure.

If that were the explanation, the v3 advantage would evaporate once the
threshold is raised to compensate for the scale offset. This script tests that
directly by sweeping the threshold across two orders of magnitude, including the
scale-corrected point 0.01 / k where k = 0.2578 is the LOO-fitted v3 scale
factor from v3_calibration_result.json.

A structural result should survive; a scale artifact should not.

Run:  python -m scripts.spatial_recall_robustness
Output: data/calibration/spatial_recall_robustness.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.core.cascade_validation import compare_spatial_recall

CAL = Path(__file__).resolve().parents[1] / "data" / "calibration"
OUT = CAL / "spatial_recall_robustness.json"

# LOO-fitted v3 scale factor; 0.01 / K is the threshold at which a scale-corrected
# v3 trajectory clears the same bar the paper applies to v2.
K_V3_SCALE = 0.2578
PUBLISHED_THRESHOLD = 0.01

THRESHOLDS = [0.001, 0.005, 0.01, 0.02,
              round(PUBLISHED_THRESHOLD / K_V3_SCALE, 4),   # scale-corrected
              0.05, 0.10]


def main() -> int:
    rows = []
    for th in sorted(set(THRESHOLDS)):
        c = compare_spatial_recall(reach_threshold=th)
        rows.append({
            "threshold": th,
            "v2_recall": c.v2_recall,
            "v2_reached": c.v2_reached,
            "v2_nodes": c.v2_nodes,
            "v3_recall": c.v3_recall,
            "v3_reached": c.v3_reached,
            "v3_nodes": c.v3_nodes,
            "v3_minus_v2": round(c.v3_recall - c.v2_recall, 4),
            "v3_over_v2": (round(c.v3_recall / c.v2_recall, 3)
                           if c.v2_recall else None),
            "events_compared": c.events_compared,
            "is_published_threshold": th == PUBLISHED_THRESHOLD,
            "is_scale_corrected_threshold": th == round(
                PUBLISHED_THRESHOLD / K_V3_SCALE, 4),
        })

    v3_always_higher = all(r["v3_minus_v2"] > 0 for r in rows)
    corrected = next(r for r in rows if r["is_scale_corrected_threshold"])
    published = next(r for r in rows if r["is_published_threshold"])

    payload = {
        "schema": "geds.spatial_robustness.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "k_v3_scale": K_V3_SCALE,
        "published_threshold": PUBLISHED_THRESHOLD,
        "scale_corrected_threshold": corrected["threshold"],
        "rows": rows,
        "v3_higher_at_every_threshold": v3_always_higher,
        "verdict": (
            "The v3 advantage is NOT a threshold or scale artifact: v3 recall "
            f"exceeds v2 at every threshold tested, including the scale-corrected "
            f"point {corrected['threshold']} where v3 still leads "
            f"{corrected['v3_recall']} vs {corrected['v2_recall']} "
            f"({corrected['v3_over_v2']}x). The published threshold "
            f"{published['threshold']} gives {published['v3_recall']} vs "
            f"{published['v2_recall']}."
            if v3_always_higher else
            "The v3 advantage REVERSES at one or more thresholds — the published "
            "single-threshold number is not robust and must not be reported "
            "without this sweep."
        ),
        "reading": (
            "Recall denominators differ by design (v2 cannot represent some "
            "observed nodes at all, so they are excluded from its denominator "
            "rather than counted against it). That convention favours v2, which "
            "makes the surviving v3 advantage conservative."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"{'threshold':>10s} {'v2 recall':>18s} {'v3 recall':>18s} "
          f"{'v3-v2':>7s} {'v3/v2':>6s}")
    for r in rows:
        tag = ("  <- published" if r["is_published_threshold"]
               else "  <- scale-corrected" if r["is_scale_corrected_threshold"]
               else "")
        v2s = f"{r['v2_recall']:.3f} ({r['v2_reached']}/{r['v2_nodes']})"
        v3s = f"{r['v3_recall']:.3f} ({r['v3_reached']}/{r['v3_nodes']})"
        ratio = f"{r['v3_over_v2']:.2f}" if r["v3_over_v2"] else "—"
        print(f"{r['threshold']:>10} {v2s:>18s} {v3s:>18s} "
              f"{r['v3_minus_v2']:+7.3f} {ratio:>6s}{tag}")
    print(f"\nverdict: {payload['verdict']}\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
