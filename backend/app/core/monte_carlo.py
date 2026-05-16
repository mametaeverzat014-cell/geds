"""Monte Carlo uncertainty quantification — single vectorized pass.

All N iterations run in one NumPy broadcast over a (I, T, N) state tensor.
For our 40-node MVP graph, 1000 iterations × 52 weeks finishes in ~0.5 s on a
laptop — about an order of magnitude faster than the previous threaded version.

Each iteration perturbs:
    * D_eff non-zeros     — log-normal, scale = dep_noise, clamped to [0.60, 1.67]
    * vulnerability       — Gaussian, scale = dep_noise × 0.67
    * amplification       — Gaussian, scale = dep_noise × 0.33

The financial-intelligence layer (default_probability, market_cap_loss) is
included automatically because it lives inside the engine's per-step update.
"""

from __future__ import annotations

import time

import numpy as np

from .graph import CompiledGraph
from .metrics import compute_market_cap_loss
from .propagation import PropagationEngine
from .types import MonteCarloResult, Scenario


def run_monte_carlo(
    scenario: Scenario,
    graph: CompiledGraph,
    n_iterations: int = 1000,
    param_noise_pct: float = 15.0,
    seed: int = 42,
    n_workers: int = 1,    # accepted for API compatibility; ignored by vectorized path
) -> MonteCarloResult:
    """Run *n_iterations* perturbed simulations in a single vectorized call.

    Returns p5/p50/p95 confidence bands for weekly GDP loss, peak CSI, total
    output loss, and projected market-cap loss.  Default: 1,000 iterations at
    ±15% dependency-weight noise.
    """
    engine = PropagationEngine(graph, scenario.config)

    t0 = time.perf_counter()
    batch = engine.run_batch(
        scenario,
        n_iterations=n_iterations,
        param_noise_pct=param_noise_pct,
        seed=seed,
        keep_node_trajectories=False,   # MC only needs aggregate stats
    )
    runtime = time.perf_counter() - t0

    s = batch.state

    # Per-iteration aggregates
    weekly_loss      = s.total_loss_traj                              # (I, T)
    peak_csi_per_iter = s.csi_traj.max(axis=1)                        # (I,)
    total_loss_per_iter = weekly_loss.sum(axis=1)                     # (I,)

    # Financial: market cap loss per iter, summed across nodes.
    mcap_per_node = compute_market_cap_loss(
        s.cum_output_loss_usd, s.cum_inflation_usd
    )                                                                 # (I, N)
    mcap_per_iter = mcap_per_node.sum(axis=1)                         # (I,)
    high_risk_count_per_iter = (s.default_probability > 0.5).sum(axis=1)  # (I,)

    def pct(arr: np.ndarray, q: float) -> float:
        return float(np.percentile(arr, q))

    return MonteCarloResult(
        scenario_id=scenario.id,
        n_iterations=n_iterations,
        param_noise_pct=param_noise_pct,
        weekly_loss_p5=np.percentile(weekly_loss,  5, axis=0).tolist(),
        weekly_loss_p50=np.percentile(weekly_loss, 50, axis=0).tolist(),
        weekly_loss_p95=np.percentile(weekly_loss, 95, axis=0).tolist(),
        peak_csi_p5=pct(peak_csi_per_iter,  5),
        peak_csi_p50=pct(peak_csi_per_iter, 50),
        peak_csi_p95=pct(peak_csi_per_iter, 95),
        total_loss_p5=pct(total_loss_per_iter,  5),
        total_loss_p50=pct(total_loss_per_iter, 50),
        total_loss_p95=pct(total_loss_per_iter, 95),
        total_loss_mean=float(total_loss_per_iter.mean()),
        total_loss_std=float(total_loss_per_iter.std()),
        market_cap_loss_p5=pct(mcap_per_iter, 5),
        market_cap_loss_p50=pct(mcap_per_iter, 50),
        market_cap_loss_p95=pct(mcap_per_iter, 95),
        high_default_risk_count_p50=int(np.percentile(high_risk_count_per_iter, 50)),
        runtime_seconds=round(runtime, 3),
    )


__all__ = ["run_monte_carlo"]
