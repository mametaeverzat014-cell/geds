"""Re-score recovery on ONE fixed horizon, removing the censoring confound.

`recovery_censoring_audit.py` established that the project's recovery-ordering
result cannot be attributed to the engine: 7 of 11 reported predictions are
right-censored at a hand-set `horizon_weeks`, and ranking the events by that
field alone reproduces the headline to within 0.011.

That audit named its own fix, and this script executes it. Every event is re-run
on a single long horizon identical across events. Two things follow:

  * Nothing is censored (or, where it still is, it is censored at the SAME value
    for every event, which carries no ordering information at all).
  * The horizon becomes a constant, so it has zero variance and cannot correlate
    with anything. The confound is removed by construction rather than adjusted
    for.

Whatever Spearman survives that is a property of the engine.

This is a fair test and not a rescue attempt: the result is reported in either
direction. If the correlation holds, the retraction narrows to "the original
harness was confounded, the underlying claim survives a clean re-run". If it
collapses, the retraction stands in full and is strengthened, because the
alternative explanation will have been tested rather than assumed.

Validity check performed before running: `ShockSpec.factor` depends only on
`start_week` and `duration_weeks`, never on the horizon, so lengthening the
window does not alter the forcing. The events are identical; only the length of
the simulation changes.

Run:  python -m scripts.fixed_horizon_recovery
Output: data/calibration/fixed_horizon_recovery.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.core.backtest import _scenario_from_event
from app.core.cascade_validation import _node_shape
from app.core.graph import compile_graph
from app.core.metrics import spearman_rho
from app.core.propagation import PropagationEngine
from app.core.types import EngineConfig
from app.data.csv_loader import load_cascade_timing_csv
from app.data.seed import load_graph
from app.data.seed_data import HISTORICAL_EVENTS

OUT = (Path(__file__).resolve().parents[1]
       / "data" / "calibration" / "fixed_horizon_recovery.json")

# 5 years. The longest observed recovery in the benchmark is 78 weeks (the 2008
# auto collapse), so this leaves better than 3x headroom for every event.
FIXED_HORIZON_WEEKS = 260


def main() -> int:
    cfg = EngineConfig(stochastic_sigma=0.0, seed=0)
    graph = compile_graph(load_graph())
    timing = {t.engine_slug: t for t in load_cascade_timing_csv()}

    rows = []
    for ev in HISTORICAL_EVENTS:
        tm = timing.get(ev["slug"])
        if tm is None or tm.recovery_weeks_to_90 is None:
            continue
        node_idx = graph.index.get(ev["shocks"][0]["target_node_id"])
        if node_idx is None:
            continue

        # identical event, identical shocks — only the window length changes
        long_ev = {**ev, "horizon_weeks": FIXED_HORIZON_WEEKS}
        sim = PropagationEngine(graph, cfg).run(_scenario_from_event(long_ev, cfg))
        _, _, rec_long = _node_shape(sim, node_idx)

        orig = PropagationEngine(graph, cfg).run(_scenario_from_event(ev, cfg))
        _, _, rec_orig = _node_shape(orig, node_idx)

        rows.append({
            "slug": ev["slug"],
            "name": ev["name"],
            "observed": float(tm.recovery_weeks_to_90),
            "original_horizon": int(ev["horizon_weeks"]),
            "predicted_original": rec_orig,
            "predicted_fixed_horizon": rec_long,
            "was_censored_originally": bool(
                abs(rec_orig - float(ev["horizon_weeks"])) < 1e-9),
            "still_censored_at_fixed": bool(
                abs(rec_long - FIXED_HORIZON_WEEKS) < 1e-9),
        })

    rows.sort(key=lambda r: r["observed"])
    obs = np.array([r["observed"] for r in rows])
    p_orig = np.array([r["predicted_original"] for r in rows])
    p_fixed = np.array([r["predicted_fixed_horizon"] for r in rows])
    hor_orig = np.array([r["original_horizon"] for r in rows], dtype=float)

    n_cens_before = sum(r["was_censored_originally"] for r in rows)
    n_cens_after = sum(r["still_censored_at_fixed"] for r in rows)

    rho_orig = float(spearman_rho(p_orig, obs))
    rho_fixed = float(spearman_rho(p_fixed, obs))
    rho_horizon = float(spearman_rho(hor_orig, obs))

    # On a fixed horizon the window is a constant, so it cannot carry ordering
    # information. Stated explicitly rather than left for the reader to infer.
    payload = {
        "schema": "geds.fixed_horizon_recovery.v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fixed_horizon_weeks": FIXED_HORIZON_WEEKS,
        "n_events": len(rows),
        "rows": rows,
        "censoring": {
            "censored_under_original_horizons": int(n_cens_before),
            "still_censored_at_fixed_horizon": int(n_cens_after),
        },
        "spearman": {
            "original_censored_predictions_vs_observed": round(rho_orig, 4),
            "hand_set_horizon_alone_vs_observed": round(rho_horizon, 4),
            "fixed_horizon_predictions_vs_observed": round(rho_fixed, 4),
        },
        "reading": (
            "Under the original per-event horizons the reported correlation was "
            f"{rho_orig:.4f}, but a hand-set field reproduced {rho_horizon:.4f} of it "
            "with no engine at all. On one fixed horizon the window is constant "
            "across events, so it carries no ordering information by construction, "
            f"and the engine's own correlation is {rho_fixed:.4f}."
        ),
        "verdict": (
            f"The recovery ordering SURVIVES a clean re-run: {rho_fixed:.4f} with the "
            "confound removed by construction. The original harness was confounded; "
            "the underlying claim holds."
            if rho_fixed >= 0.7 else
            f"The recovery ordering does NOT survive a clean re-run: {rho_fixed:.4f} "
            "once the horizon confound is removed. The retraction stands in full, and "
            "the alternative explanation has now been tested rather than assumed."
            if rho_fixed < 0.5 else
            f"Partial: {rho_fixed:.4f} once the confound is removed — materially weaker "
            f"than the {rho_orig:.4f} originally published, and too weak at this n to "
            "carry a headline claim."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"fixed horizon: {FIXED_HORIZON_WEEKS} weeks, {len(rows)} events\n")
    print(f"{'event':34s} {'obs':>5s} {'orig':>7s} {'fixed':>7s}  was/still censored")
    for r in rows:
        print(f"{r['slug']:34s} {r['observed']:5.0f} {r['predicted_original']:7.0f} "
              f"{r['predicted_fixed_horizon']:7.0f}  "
              f"{'YES' if r['was_censored_originally'] else ' — '} / "
              f"{'YES' if r['still_censored_at_fixed'] else ' — '}")
    print(f"\ncensored: {n_cens_before} originally -> {n_cens_after} at fixed horizon")
    print(f"\n  Spearman, original (censored)      = {rho_orig:+.4f}")
    print(f"  Spearman, hand-set horizon alone   = {rho_horizon:+.4f}")
    print(f"  Spearman, FIXED horizon (clean)    = {rho_fixed:+.4f}")
    print(f"\nverdict: {payload['verdict']}\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
