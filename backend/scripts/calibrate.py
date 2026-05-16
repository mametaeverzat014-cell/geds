"""GEDS Bayesian Calibration — joint parameter optimization with Optuna.

Optimizes five free parameters against the 8-event historical suite using TPE
(Tree-structured Parzen Estimator) sampling.  Each trial runs the engine on
every historical event, computes a weighted RMSE, and adds a sanity penalty
plus a pass-rate penalty so the optimizer is pushed toward solutions that are
both accurate AND don't violate global GDP plausibility.

Search space
------------
    amplification_mu     [0.50, 4.00]    shared amplification slope
    bullwhip_factor      [1.00, 1.50]    E-state inbound multiplier
    recovery_rate        [0.02, 0.20]    weekly exponential recovery
    inventory_scale      [0.50, 1.50]    global multiplier on inventory_weeks
    distress_base        [0.25, 0.55]    base output-loss threshold for default risk

Objective
---------
    L = w_rmse · RMSE_weighted
        + w_pass · max(0, 0.75 − pass_rate)            # heavy push toward ≥75% pass rate
        + w_sanity · mean(per-event sanity penalty)    # global-GDP plausibility

Output
------
    data/calibration/study.db                          Optuna persistence (resumable)
    data/calibration/provenance.json                   {best_params, pass_rate, date, …}

Usage
-----
    python -m scripts.calibrate --n-trials 200 --study-name geds-v1
    python -m scripts.calibrate --n-trials 50  --resume

The backtest module (app/core/backtest.py) auto-loads the produced
provenance.json so the rest of the system uses the calibrated parameters.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Path setup so this can be invoked as `python -m scripts.calibrate` or directly.
THIS = Path(__file__).resolve()
sys.path.insert(0, str(THIS.parent.parent))

try:
    import optuna
    from optuna.samplers import TPESampler
    from optuna.pruners import MedianPruner
except ImportError:
    print("ERROR: Optuna is required.  Install with:  pip install optuna>=3.6", file=sys.stderr)
    sys.exit(2)

from app.core.backtest import backtest_event
from app.core.graph import compile_graph
from app.core.sanity import sanity_penalty
from app.core.types import EngineConfig
from app.data.seed import load_graph
from app.data.seed_data import HISTORICAL_EVENTS


# Weighted objective components — tune these if calibrator overshoots
# in the wrong direction (e.g., high sanity penalty but low RMSE).
W_RMSE   = 1.0
W_PASS   = 2.0     # heavy weight: we care about pass-rate
W_SANITY = 0.5

# Target pass rate above which no pass-penalty is applied.
TARGET_PASS_RATE = 0.75


def build_config(params: dict) -> EngineConfig:
    """Map an Optuna trial's sampled params into an EngineConfig."""
    return EngineConfig(
        propagation_decay=0.85,
        rerouting_efficiency=0.55,
        amplification_eps=0.06,
        amplification_mu=params["amplification_mu"],
        recovery_rate=params["recovery_rate"],
        bullwhip_factor=params["bullwhip_factor"],
        inventory_scale=params["inventory_scale"],
        distress_base=params["distress_base"],
        seis_enabled=True,
        adaptive_rerouting=True,
        stochastic_sigma=0.0,
    )


def evaluate_config(graph, config: EngineConfig) -> dict:
    """Run engine on all historical events; return aggregate metrics."""
    per_event_rmse = []
    per_event_sanity = []
    per_event_pass_25 = []
    weighted_squared = 0.0

    for event in HISTORICAL_EVENTS:
        r = backtest_event(event, graph, config)

        # Weighted squared error (loss=50%, inflation=30%, recovery=20%).
        loss_err = (r.industry_loss_predicted - r.industry_loss_observed) ** 2
        infl_err = (r.inflation_predicted - r.inflation_observed) ** 2
        rec_err  = ((r.recovery_predicted - r.recovery_observed) / 52.0) ** 2
        weighted_squared += 0.5 * loss_err + 0.3 * infl_err + 0.2 * rec_err

        per_event_rmse.append(r.rmse)
        per_event_pass_25.append(r.passes_25pct)
        per_event_sanity.append(
            sanity_penalty(r.total_loss_usd, event["horizon_weeks"])
        )

    n = max(1, len(HISTORICAL_EVENTS))
    weighted_rmse = float(np.sqrt(weighted_squared / n))
    pass_rate = sum(per_event_pass_25) / n
    mean_sanity = float(np.mean(per_event_sanity))

    return {
        "weighted_rmse": weighted_rmse,
        "pass_rate": pass_rate,
        "mean_sanity_penalty": mean_sanity,
        "per_event_rmse": per_event_rmse,
        "per_event_pass_25": per_event_pass_25,
    }


def objective_factory(graph):
    """Return an Optuna-compatible objective closure bound to a compiled graph."""

    def objective(trial: optuna.Trial) -> float:
        params = {
            "amplification_mu": trial.suggest_float("amplification_mu", 0.5, 4.0),
            "bullwhip_factor":  trial.suggest_float("bullwhip_factor",  1.00, 1.50),
            "recovery_rate":    trial.suggest_float("recovery_rate",    0.02, 0.20),
            "inventory_scale":  trial.suggest_float("inventory_scale",  0.50, 1.50),
            "distress_base":    trial.suggest_float("distress_base",    0.25, 0.55),
        }
        config = build_config(params)
        try:
            metrics = evaluate_config(graph, config)
        except Exception as exc:
            # Any engine failure during this trial → penalty + skip.
            trial.set_user_attr("error", str(exc))
            return float("inf")

        rmse  = metrics["weighted_rmse"]
        sanity = metrics["mean_sanity_penalty"]
        pass_rate = metrics["pass_rate"]
        pass_penalty = max(0.0, TARGET_PASS_RATE - pass_rate)

        # Record diagnostics so we can inspect the Pareto frontier post-hoc.
        trial.set_user_attr("pass_rate", pass_rate)
        trial.set_user_attr("weighted_rmse", rmse)
        trial.set_user_attr("mean_sanity_penalty", sanity)

        return W_RMSE * rmse + W_PASS * pass_penalty + W_SANITY * sanity

    return objective


def run_calibration(
    n_trials: int = 200,
    study_name: str = "geds-cal-v1",
    storage: str | None = None,
    seed: int = 42,
    verbose: bool = True,
) -> dict:
    """Execute the full calibration sweep and write provenance.json."""
    snap = load_graph()
    graph = compile_graph(snap)

    sampler = TPESampler(seed=seed)
    pruner = MedianPruner(n_warmup_steps=15)
    study = optuna.create_study(
        direction="minimize",
        study_name=study_name,
        sampler=sampler,
        pruner=pruner,
        storage=storage,
        load_if_exists=True,
    )

    objective = objective_factory(graph)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=verbose)

    # Final re-evaluation with best params (to record clean metrics).
    best_config = build_config(study.best_params)
    final_metrics = evaluate_config(graph, best_config)

    provenance = {
        "calibration_date": datetime.now(timezone.utc).isoformat(),
        "study_name": study_name,
        "n_trials": n_trials,
        "n_completed_trials": len([t for t in study.trials if t.state.name == "COMPLETE"]),
        "best_value": float(study.best_value),
        "best_params": {k: float(v) for k, v in study.best_params.items()},
        "best_config": best_config.model_dump(),
        "final_validation": {
            "weighted_rmse": final_metrics["weighted_rmse"],
            "pass_rate_25pct": final_metrics["pass_rate"],
            "mean_sanity_penalty": final_metrics["mean_sanity_penalty"],
            "n_passed_25pct": sum(final_metrics["per_event_pass_25"]),
            "n_events": len(HISTORICAL_EVENTS),
        },
        "search_space": {
            "amplification_mu": [0.5, 4.0],
            "bullwhip_factor":  [1.00, 1.50],
            "recovery_rate":    [0.02, 0.20],
            "inventory_scale":  [0.50, 1.50],
            "distress_base":    [0.25, 0.55],
        },
        "objective_weights": {"rmse": W_RMSE, "pass": W_PASS, "sanity": W_SANITY},
        "target_pass_rate": TARGET_PASS_RATE,
    }

    out_dir = Path(__file__).parent.parent / "data" / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)
    prov_path = out_dir / "provenance.json"
    prov_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    if verbose:
        print()
        print(f"Best value:          {study.best_value:.4f}")
        print(f"Best params:         {study.best_params}")
        print(f"Final pass rate:     {final_metrics['pass_rate']:.2%}")
        print(f"Weighted RMSE:       {final_metrics['weighted_rmse']:.4f}")
        print(f"Mean sanity penalty: {final_metrics['mean_sanity_penalty']:.4f}")
        print(f"Wrote provenance:    {prov_path}")

    return provenance


def main() -> int:
    ap = argparse.ArgumentParser(description="GEDS joint Bayesian calibration")
    ap.add_argument("--n-trials", type=int, default=200, help="Number of Optuna trials")
    ap.add_argument("--study-name", default="geds-cal-v1", help="Optuna study name")
    ap.add_argument("--resume", action="store_true",
                    help="Resume previous study from SQLite (data/calibration/study.db)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    storage = None
    if args.resume:
        db_path = Path(__file__).parent.parent / "data" / "calibration" / "study.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        storage = f"sqlite:///{db_path}"

    run_calibration(
        n_trials=args.n_trials,
        study_name=args.study_name,
        storage=storage,
        seed=args.seed,
        verbose=not args.quiet,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
