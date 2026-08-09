"""Is the recovery-ordering result a property of the model, or of the horizon?

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
            f"{n_cens} of {len(rows)} reported 'predictions' are right-censored: the "
            f"node never recovered inside its window, so the harness substituted the "
            f"window length, which is a hand-set field. Ranking the events by that "
            f"field alone — with no engine at all — reproduces the headline to "
            f"{rho_horizon:.4f} against the engine's {rho_model:.4f}. The engine adds "
            f"{rho_model - rho_horizon:+.4f}. On the {len(unc)} events where it "
            f"genuinely reached recovery in-window, Spearman is "
            f"{'n/a' if rho_unc is None else f'{rho_unc:.4f}'} at n={len(unc)}, which "
            f"supports nothing. The recovery-ordering result CANNOT be claimed as "
            f"evidence of model skill in its present form."
            if n_cens else
            "No prediction is censored at its horizon; the recovery result is a clean "
            "property of the engine."
        ),
        "what_would_fix_it": (
            "Re-run every event on one long fixed horizon so no prediction is censored, "
            "then re-score. Until then the honest statements are (a) the horizon-only "
            "null, and (b) the uncensored-subset correlation with its n."
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
