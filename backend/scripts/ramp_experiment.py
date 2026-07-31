"""Pre-registered experiment: ramp forcing for slow-accumulation events (Batch 19).

MOTIVATION (the forensics this follows from). The engine predicts
weeks_to_peak = 0 for 12 of 15 scored events; the entire predicted support is
{0, 11, 22} against an observed range of 1-52, which fully explains the
chance-level Spearman 0.07 [-0.43, +0.53] in significance.json. Cause, located
in code: all three existing decay curves peak at onset (linear/exp DECAY from
t=0), and the ratchet update `state = max(external, state + impact - recovery)`
renders any declining forcing as a rectangular pulse at the shocked node. The
two nonzero predictions (11, 22) are argmax picks on near-flat plateau creep
(0.088->0.096, 0.012->0.013), not genuine late dynamics. The engine simply has
no rising forcing shape, while the slowest observed builders (congestion 52w,
drought 20w, demand collapse 20w) are exactly rising-stress events.

TREATMENT (selected by real-world MECHANISM, declared before running — never
by which flips would score best): events whose historical forcing accumulated
over months rather than arriving at onset get decay_curve="ramp":

    us-west-coast-ports-2021    congestion accumulation (obs peak week 52)
    panama-canal-drought-2023   hydrological drought, draft limits tightened
                                progressively (obs peak week 20)
    gfc-auto-collapse-2008-2009 demand collapse over ~2 quarters (obs 20)
    eu-energy-crisis-2021       energy-price escalation over months (obs 13)

Sharp-onset events (earthquakes, fires, lockdowns, canal blockage, Red Sea
attack onset - PortWatch shows the transit collapse within days, obs peak 4w)
keep their existing curves.

PRE-REGISTERED GATE (all four must hold to adopt ramp specs into seed_data):
    G1  weeks_to_peak Spearman (n=15) >= 0.40          (baseline 0.0683)
    G2  magnitude and recovery_weeks Spearman each drop by <= 0.05
    G3  benchmark GEDS MAE worsens by <= 0.001         (golden 0.0241)
    G4  events NOT in the treatment set have bit-identical cascade dims
        (no side effects through shared state)

Negative result => same disposition as Batches 8/9b/9d: keep the ramp
capability, do NOT flip the specs, document honestly.

Run:  python -m scripts.ramp_experiment          (~2-3 min, writes JSON)
Output: data/calibration/ramp_experiment.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.core.benchmark import run_benchmark
from app.core.cascade_validation import run_cascade_validation
from app.data.seed_data import HISTORICAL_EVENTS

OUT_PATH = (Path(__file__).resolve().parents[1]
            / "data" / "calibration" / "ramp_experiment.json")

TREATMENT = {
    "us-west-coast-ports-2021": "congestion accumulation",
    "panama-canal-drought-2023": "hydrological drought, progressive draft limits",
    "gfc-auto-collapse-2008-2009": "demand collapse over ~2 quarters",
    "eu-energy-crisis-2021": "energy-price escalation over months",
}

GATE = {
    "G1_weeks_to_peak_spearman_min": 0.40,
    "G2_other_dims_max_drop": 0.05,
    "G3_benchmark_mae_max_worsening": 0.001,
}


def _cascade_summary(rep) -> dict:
    return {
        "spearman_by_dim": dict(rep.spearman_by_dim),
        "mae_by_dim": dict(rep.mae_by_dim),
        "n_by_dim": dict(rep.n_by_dim),
        "per_event": {
            ev.slug: {d.name: {"pred": d.predicted, "obs": d.observed}
                      for d in ev.dims}
            for ev in rep.events
        },
    }


def _geds_mae(report) -> float:
    return next(m.mae for m in report.models
                if m.model.startswith("SEIRS-Bullwhip"))


def main() -> int:
    originals: dict[str, list[str]] = {}
    treated_events = []
    for ev in HISTORICAL_EVENTS:
        if ev["slug"] in TREATMENT:
            originals[ev["slug"]] = [s["decay_curve"] for s in ev["shocks"]]
            treated_events.append(ev)
    missing = set(TREATMENT) - set(originals)
    if missing:
        print(f"ERROR: treatment events not found: {missing}", file=sys.stderr)
        return 1

    print("Baseline (current specs)...")
    base_cascade = _cascade_summary(run_cascade_validation())
    base_bench = _geds_mae(run_benchmark())
    print(f"  weeks_to_peak spearman = {base_cascade['spearman_by_dim']['weeks_to_peak']}"
          f"   GEDS MAE = {base_bench}")

    print("Treatment (ramp on mechanism-selected events)...")
    try:
        for ev in treated_events:
            for s in ev["shocks"]:
                s["decay_curve"] = "ramp"
        ramp_cascade = _cascade_summary(run_cascade_validation())
        ramp_bench = _geds_mae(run_benchmark())
    finally:
        for ev in treated_events:
            for s, orig in zip(ev["shocks"], originals[ev["slug"]], strict=True):
                s["decay_curve"] = orig
    print(f"  weeks_to_peak spearman = {ramp_cascade['spearman_by_dim']['weeks_to_peak']}"
          f"   GEDS MAE = {ramp_bench}")

    # ── gate evaluation ──
    g1 = ramp_cascade["spearman_by_dim"]["weeks_to_peak"] >= GATE["G1_weeks_to_peak_spearman_min"]
    drops = {
        dim: base_cascade["spearman_by_dim"][dim] - ramp_cascade["spearman_by_dim"][dim]
        for dim in ("magnitude", "recovery_weeks")
    }
    g2 = all(d <= GATE["G2_other_dims_max_drop"] for d in drops.values())
    mae_delta = ramp_bench - base_bench
    g3 = mae_delta <= GATE["G3_benchmark_mae_max_worsening"]
    untouched_diffs = {
        slug: {"before": base_cascade["per_event"][slug],
               "after": ramp_cascade["per_event"][slug]}
        for slug in base_cascade["per_event"]
        if slug not in TREATMENT
        and base_cascade["per_event"][slug] != ramp_cascade["per_event"][slug]
    }
    g4 = not untouched_diffs

    verdict = "ADOPT" if (g1 and g2 and g3 and g4) else "REJECT"
    print(f"\nGate: G1={g1} G2={g2} (drops {drops}) G3={g3} (dMAE {mae_delta:+.4f}) "
          f"G4={g4} -> {verdict}")

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experiment": "ramp forcing for slow-accumulation events",
        "treatment": TREATMENT,
        "gate": GATE,
        "gate_results": {"G1": g1, "G2": g2, "G2_drops": drops,
                         "G3": g3, "G3_mae_delta": round(mae_delta, 5),
                         "G4": g4, "G4_untouched_diffs": untouched_diffs},
        "verdict": verdict,
        "baseline": {"cascade": base_cascade, "geds_benchmark_mae": base_bench},
        "ramp": {"cascade": ramp_cascade, "geds_benchmark_mae": ramp_bench},
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
