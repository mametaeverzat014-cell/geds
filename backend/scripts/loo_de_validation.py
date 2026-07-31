"""Leave-one-out cross-validation with per-fold DE re-calibration.

The honest answer to "does the recalibrated SEIRS engine beat the linear-
diffusion baseline, or is the in-sample win an artifact of fitting?":

    for each event i in HISTORICAL_EVENTS:
        calibrate the 5 engine parameters on the other N-1 events (reduced DE)
        predict the held-out event with the fold-calibrated config
    pool the N out-of-sample predictions and score them exactly like the
    benchmark scores the (parameter-free) linear-diffusion baseline.

Linear diffusion has no fitted parameters, so its benchmark scores ARE
out-of-sample; GEDS must be scored this way for the comparison to be fair.

Run:  python -m scripts.loo_de_validation          (~30 min, writes JSON)
Output: data/calibration/loo_de_result.json
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.optimize import differential_evolution

import copy

from app.core.backtest import backtest_event
from app.core.benchmark import _score
from app.core.graph import compile_graph
from app.core.mcmc import PARAM_BOUNDS, PARAM_NAMES
from app.core.types import EngineConfig
from app.data.expanded_graph import to_v3_node
from app.data.seed import compiled_graph_for, load_graph
from app.data.seed_data import HISTORICAL_EVENTS

# Reduced DE settings: enough to converge near the full-run optimum (the
# 3-restart production run found a sharp basin), cheap enough for 21 folds.
DE_MAXITER = 12
DE_POPSIZE = 4          # per dimension → population 20
DE_SEED = 42

OBJ_WEIGHTS = {"loss": 0.5, "infl": 0.3, "recovery": 0.2}
OBJ_SIGMA = {"loss": 0.05, "infl": 0.01, "recovery": 0.20}

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "calibration" / "loo_de_result.json"


def _events_for_graph(version: str) -> list[dict]:
    """Event set for the requested graph version.

    v2 uses the events as authored. v3 (405-node ICIO) has no chokepoint nodes,
    so each event's shocks are remapped onto v3 node ids and events that map to
    nothing (chokepoint-only) are dropped — the same convention
    cascade_validation.compare_spatial_recall() uses.
    """
    if version == "v2":
        return list(HISTORICAL_EVENTS)
    out = []
    for ev in HISTORICAL_EVENTS:
        shocks = [{**s, "target_node_id": to_v3_node(s["target_node_id"])}
                  for s in ev["shocks"] if to_v3_node(s["target_node_id"])]
        if not shocks:
            continue
        remapped = copy.deepcopy(ev)
        remapped["shocks"] = shocks
        out.append(remapped)
    return out


def _config(theta: np.ndarray, overrides: dict | None = None) -> EngineConfig:
    kw = dict(zip(PARAM_NAMES, (float(x) for x in theta), strict=True))
    return EngineConfig(seed=0, stochastic_sigma=0.0, **kw, **(overrides or {}))


def _objective(theta: np.ndarray, graph, events: list[dict], overrides: dict | None = None) -> float:
    config = _config(theta, overrides)
    total = 0.0
    for event in events:
        try:
            r = backtest_event(event, graph, config)
        except Exception:
            return 1e12
        errs = {
            "loss":     r.industry_loss_predicted - r.industry_loss_observed,
            "infl":     r.inflation_predicted - r.inflation_observed,
            "recovery": (r.recovery_predicted - r.recovery_observed) / 52.0,
        }
        for k, e in errs.items():
            total += 0.5 * OBJ_WEIGHTS[k] * (e / OBJ_SIGMA[k]) ** 2
    return float(total)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="LOO-DE out-of-sample validation; optional fixed-config "
                    "overrides for mechanism experiments (e.g. --r-output-floor 0)",
    )
    ap.add_argument("--r-output-floor", type=float, default=None,
                    help="override the (non-calibrated) R-state output floor")
    ap.add_argument("--per-node-recovery", action="store_true",
                    help="enable the per-node recovery coupling (Batch 9b mechanism)")
    ap.add_argument("--out", type=Path, default=OUT_PATH,
                    help=f"output JSON path (default {OUT_PATH.name})")
    ap.add_argument("--graph", choices=("v2", "v3"), default="v2",
                    help="graph version to calibrate on (v3 = 405-node OECD ICIO; "
                         "chokepoint-only events are dropped, ~9x slower per run)")
    ap.add_argument("--resume", action="store_true",
                    help="reuse folds already recorded in the checkpoint file and "
                         "compute only the missing ones (a v3 run takes hours and "
                         "can be killed mid-way by a container restart)")
    ap.add_argument("--checkpoint", type=Path, default=None,
                    help="checkpoint path (default: <out>.checkpoint.json)")
    args = ap.parse_args()

    overrides: dict = {}
    if args.r_output_floor is not None:
        overrides["r_output_floor"] = args.r_output_floor
    if args.per_node_recovery:
        overrides["per_node_recovery"] = True
    out_path = args.out

    graph = (compile_graph(load_graph()) if args.graph == "v2"
             else compiled_graph_for("v3"))
    events = _events_for_graph(args.graph)
    print(f"graph={args.graph} ({graph.n} nodes), {len(events)} events", flush=True)
    bounds = [PARAM_BOUNDS[n] for n in PARAM_NAMES]

    ckpt_path = args.checkpoint or out_path.with_suffix(".checkpoint.json")
    done: dict[str, dict] = {}
    if args.resume and ckpt_path.exists():
        done = {f["slug"]: f for f in
                json.loads(ckpt_path.read_text(encoding="utf-8"))["folds"]}
        print(f"resuming: {len(done)} folds already in {ckpt_path.name}", flush=True)

    folds: list[dict] = []
    t0 = time.perf_counter()
    for i, held_out in enumerate(events):
        if held_out["slug"] in done:
            folds.append(done[held_out["slug"]])
            print(f"[{i+1:2d}/{len(events)}] {held_out['slug']}: cached", flush=True)
            continue
        train = [e for j, e in enumerate(events) if j != i]
        res = differential_evolution(
            _objective, bounds, args=(graph, train, overrides),
            strategy="best1bin", maxiter=DE_MAXITER, popsize=DE_POPSIZE,
            tol=1e-3, mutation=(0.5, 1.0), recombination=0.7,
            seed=DE_SEED, updating="deferred", workers=1, polish=False, init="sobol",
        )
        r = backtest_event(held_out, graph, _config(res.x, overrides))
        folds.append({
            "slug": held_out["slug"],
            "loss_predicted": r.industry_loss_predicted,
            "loss_observed": r.industry_loss_observed,
            "fold_params": dict(zip(PARAM_NAMES, [round(float(x), 4) for x in res.x], strict=True)),
            "fold_train_loss": round(float(res.fun), 3),
        })
        print(f"[{i+1:2d}/{len(events)}] {held_out['slug']}: "
              f"pred={r.industry_loss_predicted:.4f} obs={r.industry_loss_observed:.4f}",
              flush=True)
        # checkpoint after every fold so a container restart costs one fold, not the run
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        ckpt_path.write_text(json.dumps({"graph_version": args.graph,
                                         "folds": folds}, indent=2), encoding="utf-8")

    preds = [f["loss_predicted"] for f in folds]
    obs = [f["loss_observed"] for f in folds]
    score = _score("GEDS SEIRS (LOO-DE, out-of-sample)", np.array(preds), np.array(obs))
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "n_folds": len(folds),
        "de_settings": {"maxiter": DE_MAXITER, "popsize_per_dim": DE_POPSIZE, "seed": DE_SEED},
        "config_overrides": overrides,
        "graph_version": args.graph,
        "graph_nodes": int(graph.n),
        "runtime_seconds": round(time.perf_counter() - t0, 1),
        "out_of_sample_score": {
            "mae": score.mae, "rmse": score.rmse, "r_squared": score.r_squared,
            "pearson": score.pearson, "spearman": score.spearman,
        },
        "folds": folds,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nOut-of-sample: MAE={score.mae:.4f} RMSE={score.rmse:.4f} "
          f"Pearson={score.pearson:+.3f} Spearman={score.spearman:+.3f} R2={score.r_squared:+.3f}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
