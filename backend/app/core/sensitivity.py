"""Sobol global sensitivity analysis on the engine's free parameters.

Sobol decomposes the variance of the model output into contributions from
each input parameter:

    Var(Y) = Σ_i S_i · Var(Y) + Σ_{i<j} S_ij · Var(Y) + …

Two indices per parameter:
    S_i   (first-order)  — fraction of Y-variance explained by varying x_i alone
    S_T_i (total-effect) — fraction including all interactions involving x_i

Interpretation:
    S_i ≈ S_T_i             → x_i acts independently, no important interactions
    S_T_i > S_i              → x_i interacts with other parameters
    S_T_i ≈ 0               → x_i is non-influential, can be fixed
    Σ S_i ≈ 1                → additive model (no interactions)

This is the gold-standard sensitivity analysis cited in IPCC, EPA, IEA
modeling guidelines.  Anchored by Saltelli et al. (2010) and Sobol (1993).

Implementation uses SALib's Sobol sampler (Saltelli scheme).  N_base = 1024
samples gives (2k+2)·N = 14k engine evaluations for k=5 parameters — about
3-5 minutes wall time at the smoke setting.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    from SALib.analyze.sobol import analyze as sobol_analyze
    from SALib.sample.sobol import sample as sobol_sample
    _SALIB_OK = True
except ImportError:
    _SALIB_OK = False
    sobol_analyze = None
    sobol_sample = None

from .backtest import backtest_event
from .graph import compile_graph
from .mcmc import PARAM_BOUNDS, PARAM_NAMES
from .types import EngineConfig
from ..data.seed import load_graph
from ..data.seed_data import HISTORICAL_EVENTS


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class ParamSensitivity:
    name: str
    first_order_S1: float
    first_order_S1_ci95: float
    total_effect_ST: float
    total_effect_ST_ci95: float
    rank_by_total_effect: int
    interpretation: str


@dataclass
class SobolReport:
    timestamp: str
    method: str
    n_base_samples: int
    n_engine_evals: int
    runtime_seconds: float
    output_variable: str
    output_mean: float
    output_std: float
    sum_S1: float           # ≈ 1.0 → additive model; <1 → interactions matter
    parameters: list[ParamSensitivity]


# ─────────────────────────── target function ───────────────────────────────


def _target_function(theta: np.ndarray, graph) -> float:
    """The scalar output Sobol decomposes — total industry-loss MAE across history.

    Higher = worse fit. Sobol measures how sensitive THIS scalar is to the
    inputs, so we're asking: 'which parameter, when varied, most affects
    how well the model fits history?'
    """
    config = EngineConfig(
        propagation_decay=0.85,
        rerouting_efficiency=0.55,
        amplification_eps=0.06,
        amplification_mu=float(theta[0]),
        recovery_rate=float(theta[2]),
        bullwhip_factor=float(theta[1]),
        inventory_scale=float(theta[3]),
        distress_base=float(theta[4]),
        seis_enabled=True, adaptive_rerouting=True,
        stochastic_sigma=0.0,
    )
    errs = []
    for ev in HISTORICAL_EVENTS:
        try:
            r = backtest_event(ev, graph, config)
        except Exception:
            return 1e6
        errs.append(abs(r.industry_loss_predicted - r.industry_loss_observed))
    return float(np.mean(errs))


# ─────────────────────────── runner ────────────────────────────────────────


def run_sobol(n_base_samples: int = 512, seed: int = 42) -> SobolReport:
    """Run Sobol sensitivity analysis.

    n_base_samples controls the Saltelli-scheme base; total engine evaluations
    will be (2k + 2) * n_base = 12 * n_base for k=5 params.
    Default 512 → ~6k evaluations → ~1 min at 10ms per event-sweep.

    For publication-grade results use n_base_samples=2048 (24k evals, ~5 min).
    """
    if not _SALIB_OK:
        raise ImportError("SALib required: pip install SALib")

    import time
    snapshot = load_graph()
    graph = compile_graph(snapshot)

    # SALib problem definition.
    problem = {
        "num_vars": len(PARAM_NAMES),
        "names": list(PARAM_NAMES),
        "bounds": [list(PARAM_BOUNDS[n]) for n in PARAM_NAMES],
    }

    samples = sobol_sample(problem, n_base_samples, seed=seed)
    n_evals = samples.shape[0]

    t0 = time.perf_counter()
    y = np.zeros(n_evals, dtype=np.float64)
    for i in range(n_evals):
        y[i] = _target_function(samples[i], graph)
    runtime = time.perf_counter() - t0

    # SALib's analyze handles all the bookkeeping (CI via bootstrap).
    result = sobol_analyze(problem, y, print_to_console=False)

    # Pull per-parameter S1 / ST and their CIs.
    S1 = np.asarray(result["S1"])
    S1c = np.asarray(result["S1_conf"])
    ST = np.asarray(result["ST"])
    STc = np.asarray(result["ST_conf"])

    # Rank by total-effect descending.
    ranks = np.argsort(-ST)
    rank_map = np.empty(len(PARAM_NAMES), dtype=int)
    rank_map[ranks] = np.arange(1, len(PARAM_NAMES) + 1)

    params: list[ParamSensitivity] = []
    for i, name in enumerate(PARAM_NAMES):
        s_i, st_i = float(S1[i]), float(ST[i])
        if st_i < 0.01:
            interp = "negligible — parameter can be fixed without affecting model output"
        elif st_i - s_i > 0.10:
            interp = "interacts strongly with other parameters"
        elif st_i - s_i < 0.02:
            interp = "acts independently of other parameters"
        else:
            interp = "moderate independent + interaction effect"
        params.append(ParamSensitivity(
            name=name,
            first_order_S1=round(s_i, 4),
            first_order_S1_ci95=round(float(S1c[i]), 4),
            total_effect_ST=round(st_i, 4),
            total_effect_ST_ci95=round(float(STc[i]), 4),
            rank_by_total_effect=int(rank_map[i]),
            interpretation=interp,
        ))

    return SobolReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        method="sobol_saltelli_scheme",
        n_base_samples=n_base_samples,
        n_engine_evals=n_evals,
        runtime_seconds=round(runtime, 2),
        output_variable="mean_industry_loss_MAE",
        output_mean=round(float(y.mean()), 4),
        output_std=round(float(y.std()), 4),
        sum_S1=round(float(S1.sum()), 4),
        parameters=params,
    )


def save_sobol(report: SobolReport, path: Path | None = None) -> Path:
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "sobol.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": report.timestamp,
        "method": report.method,
        "n_base_samples": report.n_base_samples,
        "n_engine_evals": report.n_engine_evals,
        "runtime_seconds": report.runtime_seconds,
        "output_variable": report.output_variable,
        "output_mean": report.output_mean,
        "output_std": report.output_std,
        "sum_S1": report.sum_S1,
        "parameters": [asdict(p) for p in report.parameters],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


__all__ = ["ParamSensitivity", "SobolReport", "run_sobol", "save_sobol"]
