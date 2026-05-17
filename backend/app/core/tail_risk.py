"""Tail-risk engine — VaR, CVaR, fan-chart percentiles, black-swan estimation.

Phase 7 content.  Consumes the existing Monte Carlo output tensor and
produces the financial-risk language that insurance underwriters and
treasury teams actually use:

    VaR_α(L)   = inf { x : P(L ≤ x) ≥ α }        loss at α-confidence
    CVaR_α(L)  = E[ L | L > VaR_α ]              expected loss in worst tail
    BlackSwan  = P( L > μ + k·σ )                 prob of k-sigma tail
    FanChart   = weekly p1/p5/p10/p50/p90/p95/p99 trajectories

Why this matters
----------------
Monte Carlo p5/p95 bands are an *uncertainty range*.  VaR/CVaR are a
*risk measure*.  A trader or risk officer cares about the tail expectation,
not the median.  Without this layer the model can't be sold into financial
risk teams — which is the entire startup thesis.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .graph import CompiledGraph
from .monte_carlo import run_monte_carlo
from .propagation import PropagationEngine
from .types import EngineConfig, Scenario


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class TailRiskReport:
    scenario_id: str
    n_iterations: int
    # Tail measures on total output loss (USD)
    var_95: float
    var_99: float
    var_999: float
    cvar_95: float
    cvar_99: float
    cvar_999: float
    # Distribution moments
    mean: float
    std: float
    skewness: float
    kurtosis: float
    # Black-swan probabilities
    p_loss_above_2sigma: float
    p_loss_above_3sigma: float
    p_loss_above_5sigma: float
    # Fan chart weekly bands (length = horizon_weeks)
    fan_chart_p01: list[float]
    fan_chart_p05: list[float]
    fan_chart_p10: list[float]
    fan_chart_p50: list[float]
    fan_chart_p90: list[float]
    fan_chart_p95: list[float]
    fan_chart_p99: list[float]


# ─────────────────────────── core math ─────────────────────────────────────


def value_at_risk(losses: np.ndarray, alpha: float) -> float:
    """Loss-side VaR: the alpha-quantile.

    Convention: losses are non-negative; higher = worse.  VaR_α is the
    loss not exceeded with probability α.  Standard finance convention.
    """
    if losses.size == 0:
        return 0.0
    return float(np.percentile(losses, 100.0 * alpha))


def conditional_var(losses: np.ndarray, alpha: float) -> float:
    """Expected loss conditional on exceeding VaR_α."""
    if losses.size == 0:
        return 0.0
    threshold = np.percentile(losses, 100.0 * alpha)
    tail = losses[losses > threshold]
    return float(tail.mean()) if tail.size > 0 else float(threshold)


def black_swan_probability(losses: np.ndarray, k_sigma: float) -> float:
    """Empirical probability of k-sigma+ tail event."""
    if losses.size == 0:
        return 0.0
    mu, sigma = losses.mean(), losses.std()
    threshold = mu + k_sigma * sigma
    return float((losses > threshold).mean())


def _skewness(x: np.ndarray) -> float:
    if x.size < 3 or x.std() == 0:
        return 0.0
    z = (x - x.mean()) / x.std()
    return float((z ** 3).mean())


def _kurtosis(x: np.ndarray) -> float:
    """Excess kurtosis (kurtosis − 3, so Gaussian = 0)."""
    if x.size < 4 or x.std() == 0:
        return 0.0
    z = (x - x.mean()) / x.std()
    return float((z ** 4).mean() - 3.0)


# ─────────────────────────── full pipeline ─────────────────────────────────


def compute_tail_risk(
    scenario: Scenario,
    graph: CompiledGraph,
    n_iterations: int = 2000,
    param_noise_pct: float = 15.0,
    seed: int = 42,
) -> TailRiskReport:
    """Run a larger-N Monte Carlo and extract the full tail-risk panel.

    n_iterations defaults to 2000 (vs 1000 for the standard MC endpoint)
    because tail percentiles need more samples to be stable — p99 on 1000
    samples is just the 10 worst, which is unreliable.
    """
    # Run MC and capture per-iteration distributions.
    mc = run_monte_carlo(
        scenario=scenario, graph=graph,
        n_iterations=n_iterations,
        param_noise_pct=param_noise_pct,
        seed=seed, n_workers=1,
    )
    # Re-derive the per-iteration total-loss distribution from weekly_loss bands.
    # The MC result stores percentile bands, not raw per-iter values, so we
    # need to recompute with the engine's batch interface for proper tails.
    engine = PropagationEngine(graph, scenario.config)
    batch = engine.run_batch(
        scenario, n_iterations=n_iterations,
        param_noise_pct=param_noise_pct, seed=seed,
        keep_node_trajectories=False,
    )
    per_iter_total = batch.state.total_loss_traj.sum(axis=1)   # (I,)
    weekly_traj = batch.state.total_loss_traj                  # (I, T)

    return TailRiskReport(
        scenario_id=scenario.id,
        n_iterations=int(per_iter_total.size),
        var_95=value_at_risk(per_iter_total, 0.95),
        var_99=value_at_risk(per_iter_total, 0.99),
        var_999=value_at_risk(per_iter_total, 0.999),
        cvar_95=conditional_var(per_iter_total, 0.95),
        cvar_99=conditional_var(per_iter_total, 0.99),
        cvar_999=conditional_var(per_iter_total, 0.999),
        mean=float(per_iter_total.mean()),
        std=float(per_iter_total.std()),
        skewness=_skewness(per_iter_total),
        kurtosis=_kurtosis(per_iter_total),
        p_loss_above_2sigma=black_swan_probability(per_iter_total, 2.0),
        p_loss_above_3sigma=black_swan_probability(per_iter_total, 3.0),
        p_loss_above_5sigma=black_swan_probability(per_iter_total, 5.0),
        fan_chart_p01=np.percentile(weekly_traj, 1, axis=0).tolist(),
        fan_chart_p05=np.percentile(weekly_traj, 5, axis=0).tolist(),
        fan_chart_p10=np.percentile(weekly_traj, 10, axis=0).tolist(),
        fan_chart_p50=np.percentile(weekly_traj, 50, axis=0).tolist(),
        fan_chart_p90=np.percentile(weekly_traj, 90, axis=0).tolist(),
        fan_chart_p95=np.percentile(weekly_traj, 95, axis=0).tolist(),
        fan_chart_p99=np.percentile(weekly_traj, 99, axis=0).tolist(),
    )


def tail_risk_to_dict(r: TailRiskReport) -> dict:
    return asdict(r)


__all__ = [
    "TailRiskReport",
    "value_at_risk", "conditional_var", "black_swan_probability",
    "compute_tail_risk", "tail_risk_to_dict",
]
