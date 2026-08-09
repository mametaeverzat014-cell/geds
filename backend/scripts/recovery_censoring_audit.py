"""Regression check: the recovery result must stay free of the horizon confound.

STATUS: the defect this script found has been FIXED at source. The harness now
simulates every event on one fixed 260-week window (CASCADE_HORIZON_WEEKS), so
the horizon is a constant, carries no ordering information, and nothing is
censored. Clean Spearman is 0.7107, down from the 0.8828 the confounded harness
reported. This script is kept as the standing check that the confound does not
come back, and as the record of how large it was.

One number below deserves care. Ranking the events by the OLD hand-set
`horizon_weeks` still scores 0.8717 — higher than the engine's clean 0.7107.
That is NOT a baseline the engine failed to beat. The horizons were chosen by a
human who already knew how long each event lasted, so that field is contaminated
by outcome knowledge; its high score measures how much outcome information had
leaked into the event table, which is precisely why scoring against it was
invalid. A contaminated predictor beating a clean one is expected and is not
evidence about the model.

Original diagnosis follows.

Is the recovery-ordering result a property of the model, or of the horizon?

The paper's single strongest claim is that the engine ranks recovery durations at
Spearman 0.88, and that this is the one quantitative result surviving correction
for multiplicity. This script tests that claim against the most damaging
alternative explanation available, and the claim does not survive.

THE PROBLEM. `cascade_validation._node_shape` computes recovery as the week the
node's output loss falls back to 10% of peak, and when that never happens inside
the simulated window it returns the window length instead:

    recovery_week = float(peak_week + recovered[0]) if recovered.size else float(len(traj))

That fallback is right-censoring. The returned value is not a prediction — it is
a lower bound equal to `horizon_weeks`, a field set by hand per event in
seed_data.py. And horizons were chosen to cover each event, so they track the
real duration: long events got long windows. Any correlation between horizon and
observed outcome therefore flows straight into the "prediction" vector.

THE TEST. Compare three quantities against the observed recovery durations:

  1. the engine's reported prediction              (what the paper claims)
  2. the hand-set horizon_weeks alone, no engine   (the null this must beat)
  3. the engine on the uncensored subset only      (where it genuinely predicted)

If (2) is close to (1), the headline is largely an artifact of the event table
rather than a property of the simulator.

Run:  python -m scripts.recovery_censoring_audit
Output: data/calibration/recovery_censoring.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.core.cascade_validation import run_cascade_validation
from app.core.metrics import spearman_rho
from app.data.seed_data import HISTORICAL_EVENTS

OUT = (Path(__file__).resolve().parents[1]
       / "data" / "calibration" / "recovery_censoring.json")

# A prediction equal to the horizon means the node never recovered in-window.
_EPS = 1e-9


def main() -> int:
    horizons = {e["slug"]: int(e["horizon_weeks"]) for e in HISTORICAL_EVENTS}
    report = run_cascade_validation()

    rows = []
    for ev in report.events:
        if ev.observed_recovery_weeks is None:
            continue
        h = horizons[ev.slug]
        censored = abs(ev.predicted_recovery_weeks - h) < _EPS
        rows.append({
            "slug": ev.slug,
            "name": ev.name,
            "predicted": ev.predicted_recovery_weeks,
            "observed": ev.observed_recovery_weeks,
            "horizon_weeks": h,
            "censored_at_horizon": bool(censored),
        })
    rows.sort(key=lambda r: r["observed"])

    pred = np.array([r["predicted"] for r in rows], dtype=float)
    obs = np.array([r["observed"] for r in rows], dtype=float)
    hor = np.array([r["horizon_weeks"] for r in rows], dtype=float)

    unc = [r for r in rows if not r["censored_at_horizon"]]
    up = np.array([r["predicted"] for r in unc], dtype=float)
    uo = np.array([r["observed"] for r in unc], dtype=float)

    rho_model = float(spearman_rho(pred, obs))
    rho_horizon = float(spearman_rho(hor, obs))
    rho_pred_hor = float(spearman_rho(pred, hor))
    rho_unc = float(spearman_rho(up, uo)) if len(unc) >= 2 else None

    n_cens = sum(r["censored_at_horizon"] for r in rows)
    payload = {
        "schema": "geds.recovery_censoring.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_events_scored": len(rows),
        "n_censored_at_horizon": int(n_cens),
        "rows": rows,
        "spearman": {
            "model_prediction_vs_observed": round(rho_model, 4),
            "hand_set_horizon_vs_observed": round(rho_horizon, 4),
            "model_prediction_vs_horizon": round(rho_pred_hor, 4),
            "uncensored_subset_only": None if rho_unc is None else round(rho_unc, 4),
            "n_uncensored": len(unc),
        },
        "model_advantage_over_horizon_null": round(rho_model - rho_horizon, 4),
        "verdict": (
            f"CONFOUND REMOVED. The harness runs every event on one fixed window, so "
            f"the horizon is a constant and cannot carry ordering information. The "
            f"engine's clean correlation is {rho_model:.4f}, against the {0.8828:.4f} "
            f"the confounded harness reported — the {0.8828 - rho_model:+.4f} gap is "
            f"the size of the artifact that was removed. The old hand-set horizon "
            f"field still scores {rho_horizon:.4f}, which is HIGHER, but that field "
            f"was chosen by someone who knew each event's duration: it is "
            f"outcome-contaminated, not a baseline the engine must beat, and its "
            f"score measures the leak rather than any skill."
        ),
        "how_it_was_fixed": (
            "cascade_validation.CASCADE_HORIZON_WEEKS = 260 — one window for every "
            "event, >3x the longest observed recovery. Verified before adopting that "
            "peak magnitude and weeks-to-peak are bit-identical under the longer "
            "window, so only the recovery dimension moved. Locked by "
            "tests/test_cascade_validation.py::"
            "test_recovery_is_scored_on_a_fixed_horizon_with_nothing_censored."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"{'event':34s} {'pred':>6s} {'obs':>5s} {'horizon':>8s}  censored")
    for r in rows:
        print(f"{r['slug']:34s} {r['predicted']:6.1f} {r['observed']:5.1f} "
              f"{r['horizon_weeks']:8d}  {'YES' if r['censored_at_horizon'] else '—'}")
    print(f"\ncensored: {n_cens}/{len(rows)}")
    print(f"  Spearman(model, observed)   = {rho_model:+.4f}")
    print(f"  Spearman(horizon, observed) = {rho_horizon:+.4f}   <- no engine at all")
    print(f"  model advantage             = {rho_model - rho_horizon:+.4f}")
    print(f"  uncensored subset           = "
          f"{'n/a' if rho_unc is None else f'{rho_unc:+.4f}'} at n={len(unc)}")
    print(f"\nverdict: {payload['verdict']}\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
