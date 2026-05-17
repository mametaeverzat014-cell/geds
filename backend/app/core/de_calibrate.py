"""Differential Evolution parameter calibration.

Phase-2 completion: with this module GEDS now offers three independent
calibration backends — `Optuna` (Bayesian Optimization, point estimate),
`emcee` (MCMC, posterior distribution), `scipy.optimize.differential_evolution`
(global GA-style optimizer, point estimate with optional CI via restarts).

Why three?
    Triangulation.  When all three converge to similar parameter values,
    that's evidence the optimum is real.  When they disagree, the disagreement
    itself is information — it suggests multi-modal posteriors or weakly
    identifiable parameters.

DE specifics
    - Population-based, no gradient needed (good for the discontinuous engine)
    - `scipy.optimize.differential_evolution` is battle-tested
    - "best1bin" strategy with population=30 × n_params and tol=1e-5
    - Output includes the converged minimum + per-parameter CI estimated
      via restart bootstrap (n_restarts random seeds → empirical std)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import differential_evolution

from .backtest import backtest_event
from .graph import compile_graph
from .mcmc import PARAM_BOUNDS, PARAM_NAMES
from .types import EngineConfig
from ..data.seed import load_graph
from ..data.seed_data import HISTORICAL_EVENTS


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class DEParamEstimate:
    name: str
    point: float
    restart_std: float
    restart_p05: float
    restart_p95: float
    prior_low: float
    prior_high: float


@dataclass
class DEResult:
    calibration_date: str
    method: str
    n_restarts: int
    pop_size: int
    converged_fraction: float
    best_loss: float
    runtime_seconds: float
    parameters: list[DEParamEstimate]


# ─────────────────────────── objective ─────────────────────────────────────


_OBJ_WEIGHTS = {"loss": 0.5, "infl": 0.3, "recovery": 0.2}
# Match the MCMC log-likelihood scales for apples-to-apples comparison.
_OBJ_SIGMA = {"loss": 0.05, "infl": 0.01, "recovery": 0.20}


def _objective(theta: np.ndarray, graph) -> float:
    """Negative log-likelihood — DE minimizes, so we return positive loss."""
    config = EngineConfig(
        propagation_decay=0.85,
        rerouting_efficiency=0.55,
        amplification_eps=0.06,
        amplification_mu=float(theta[0]),
        recovery_rate=float(theta[2]),
        bullwhip_factor=float(theta[1]),
        inventory_scale=float(theta[3]),
        distress_base=float(theta[4]),
        seis_enabled=True,
        adaptive_rerouting=True,
        stochastic_sigma=0.0,
    )
    total = 0.0
    for event in HISTORICAL_EVENTS:
        try:
            r = backtest_event(event, graph, config)
        except Exception:
            return 1e12
        errs = {
            "loss":     r.industry_loss_predicted - r.industry_loss_observed,
            "infl":     r.inflation_predicted      - r.inflation_observed,
            "recovery": (r.recovery_predicted      - r.recovery_observed) / 52.0,
        }
        for k, e in errs.items():
            total += 0.5 * _OBJ_WEIGHTS[k] * (e / _OBJ_SIGMA[k]) ** 2
    return float(total)


# ─────────────────────────── runner ────────────────────────────────────────


def run_de_calibration(
    n_restarts: int = 8,
    pop_size_per_dim: int = 25,
    max_iter: int = 200,
    tol: float = 1e-5,
    seed: int = 42,
) -> DEResult:
    """Run Differential Evolution n_restarts times with different seeds.

    The restart spread gives an empirical estimate of optimizer uncertainty
    that complements MCMC's posterior uncertainty.  If DE restarts converge
    to wildly different points, the optimization landscape is multi-modal
    — important diagnostic for the audit.
    """
    import time
    snapshot = load_graph()
    graph = compile_graph(snapshot)

    bounds = [PARAM_BOUNDS[n] for n in PARAM_NAMES]
    n_dim = len(bounds)
    pop = pop_size_per_dim * n_dim

    rng = np.random.default_rng(seed)
    restart_seeds = rng.integers(1, 2**31, size=n_restarts).tolist()

    t0 = time.perf_counter()
    bests: list[np.ndarray] = []
    losses: list[float] = []
    converged_count = 0
    for rs in restart_seeds:
        result = differential_evolution(
            _objective, bounds, args=(graph,),
            strategy="best1bin", maxiter=max_iter, popsize=pop_size_per_dim,
            tol=tol, mutation=(0.5, 1.0), recombination=0.7,
            seed=int(rs), updating="deferred", workers=1, polish=True, init="sobol",
        )
        bests.append(result.x.copy())
        losses.append(float(result.fun))
        if result.success:
            converged_count += 1
    runtime = time.perf_counter() - t0

    bests_arr = np.array(bests)
    best_idx = int(np.argmin(losses))
    best_x = bests_arr[best_idx]

    params: list[DEParamEstimate] = []
    for i, name in enumerate(PARAM_NAMES):
        samples = bests_arr[:, i]
        params.append(DEParamEstimate(
            name=name,
            point=float(best_x[i]),
            restart_std=float(samples.std()),
            restart_p05=float(np.percentile(samples, 5)),
            restart_p95=float(np.percentile(samples, 95)),
            prior_low=PARAM_BOUNDS[name][0],
            prior_high=PARAM_BOUNDS[name][1],
        ))

    return DEResult(
        calibration_date=datetime.now(timezone.utc).isoformat(),
        method="differential_evolution_multi_restart",
        n_restarts=n_restarts,
        pop_size=pop,
        converged_fraction=converged_count / n_restarts,
        best_loss=float(min(losses)),
        runtime_seconds=round(runtime, 2),
        parameters=params,
    )


# ─────────────────────────── triangulation comparator ──────────────────────


def triangulate_calibrators(de_result: DEResult, mcmc_result, optuna_result: dict | None = None) -> dict:
    """Compare DE, MCMC, and (optionally) Optuna estimates side by side.

    Returns a structured comparison that the calibration dashboard renders.
    Disagreement between methods → flag for further investigation.
    """
    out: dict[str, Any] = {"parameters": {}}
    for de_p, mc_p in zip(de_result.parameters, mcmc_result.parameters, strict=True):
        name = de_p.name
        de_point = de_p.point
        mc_mean = mc_p.mean
        # Disagreement: |DE - MCMC| / prior_range
        prior_range = de_p.prior_high - de_p.prior_low
        disagreement = abs(de_point - mc_mean) / max(prior_range, 1e-9)
        out["parameters"][name] = {
            "de_point":          round(de_point, 4),
            "de_restart_std":    round(de_p.restart_std, 4),
            "mcmc_mean":         round(mc_mean, 4),
            "mcmc_std":          round(mc_p.std, 4),
            "agreement_index":   round(1.0 - disagreement, 4),
            "consensus_estimate": round((de_point + mc_mean) / 2.0, 4),
        }
        if optuna_result and name in optuna_result:
            out["parameters"][name]["optuna_point"] = optuna_result[name]
    out["overall_agreement"] = round(
        float(np.mean([p["agreement_index"] for p in out["parameters"].values()])),
        4,
    )
    return out


# ─────────────────────────── persistence ───────────────────────────────────


def save_de_result(result: DEResult, path: Path | None = None) -> Path:
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "de_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return path


__all__ = ["DEResult", "DEParamEstimate", "run_de_calibration",
           "triangulate_calibrators", "save_de_result"]
