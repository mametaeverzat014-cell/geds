"""Baseline propagation models for SEIRS benchmarking.

Implements two reference models so SEIRS can be compared rigorously rather
than asserted "good".  Both consume the same GraphSnapshot and return the
same output shape as the SEIRS engine for a single scenario.

(1) Leontief input-output model
    Classic Wassily Leontief framework: final demand shock × (I − A)^-1
    propagates through the dependency matrix as a one-shot equilibrium.
    Treats supply chains as linear and instantaneous — the textbook baseline
    that any non-trivial dynamic model has to beat.

(2) Linear diffusion model
    x(t+1) = x(t) + α · D_eff · x(t) − β · x(t)
    Simple network diffusion — no inventory buffer, no nonlinear amplification,
    no SEIRS states.  The "naive dynamic" baseline.

Both expose .predict_event(event) returning the same (loss, inflation, recovery)
triple as backtest_event() so the comparison is apples-to-apples.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

from .graph import CompiledGraph
from .types import Industry, ShockSpec


# ─────────────────────────── prediction container ──────────────────────────


@dataclass
class BaselinePrediction:
    industry_loss: float          # peak industry-weighted output loss (fraction)
    inflation: float              # peak inflation pressure × pass_through scale
    recovery_weeks: float         # weeks for shock to decay below 0.1
    total_output_loss_usd: float
    model: str


# ─────────────────────────── Leontief I-O ──────────────────────────────────


def leontief_predict(
    graph: CompiledGraph,
    shocks: list[ShockSpec],
    industry: Industry,
    horizon_weeks: int = 52,
) -> BaselinePrediction:
    """Classic Leontief input-output equilibrium response.

    Equation:   x = (I − A)^-1 · f
    where A is the technical-coefficient matrix derived from D_eff and f is
    the final demand shock vector.  Single equilibrium solve — no dynamics.

    Recovery time is computed via exponential decay assumption τ = recovery_delay.
    """
    N = graph.n
    # Final demand shock: max external shock per target node.
    f = np.zeros(N)
    for sh in shocks:
        idx = graph.index.get(sh.target_node_id)
        if idx is not None:
            f[idx] = max(f[idx], sh.magnitude)

    A = graph.D_eff_dense
    I_mat = np.eye(N)
    try:
        # Use scipy solve for (I - A) x = f
        x = np.linalg.solve(I_mat - 0.9 * A, f)  # 0.9 damping to keep spectral radius < 1
        x = np.clip(x, 0.0, 1.0)
    except np.linalg.LinAlgError:
        x = f  # fallback: no propagation

    # Industry aggregation (GDP-weighted)
    idxs = [i for i, n in enumerate(graph.snapshot.nodes) if n.industry == industry]
    if not idxs:
        return BaselinePrediction(0.0, 0.0, 0.0, 0.0, "leontief")
    weights = graph.gdp_usd[idxs]
    w = weights / max(weights.sum(), 1.0)

    industry_shock = float(np.average(x[idxs], weights=w))
    # Peak output loss = shock × elasticity × (1−resilience), averaged
    el = graph.elasticity[idxs]
    rs = graph.resilience[idxs]
    industry_loss = float(np.average(x[idxs] * el * (1.0 - rs), weights=w))
    # Inflation: shock × pass_through × 0.10 scaling to match backtest unit
    pt = graph.pass_through[idxs]
    inflation = float(np.average(x[idxs] * pt, weights=w)) * 0.10
    # Recovery weeks: weighted recovery_delay
    rd = graph.recovery_delay[idxs]
    recovery_weeks = float(np.average(rd, weights=w))

    total_loss = float((x * graph.elasticity * (1.0 - graph.resilience) * graph.gdp_usd).sum())

    return BaselinePrediction(
        industry_loss=industry_loss,
        inflation=inflation,
        recovery_weeks=recovery_weeks,
        total_output_loss_usd=total_loss,
        model="leontief",
    )


# ─────────────────────────── Linear diffusion ──────────────────────────────


def linear_diffusion_predict(
    graph: CompiledGraph,
    shocks: list[ShockSpec],
    industry: Industry,
    horizon_weeks: int = 52,
    alpha: float = 0.6,      # diffusion rate
    beta: float = 0.07,      # decay rate
) -> BaselinePrediction:
    """Dead-simple linear network diffusion.

    x(t+1) = x(t) + α·D_eff·x(t) − β·x(t), clipped to [0, 1].
    External shocks act as a per-week floor on x.

    No inventory buffer.  No bullwhip.  No SEIRS.  No nonlinearity.
    """
    N = graph.n
    A = graph.D_eff_dense
    x = np.zeros(N)
    series = np.zeros((horizon_weeks, N))

    for t in range(horizon_weeks):
        # External shocks
        ext = np.zeros(N)
        for sh in shocks:
            idx = graph.index.get(sh.target_node_id)
            if idx is None:
                continue
            ext[idx] = max(ext[idx], sh.magnitude * sh.factor(t))
        # Diffuse
        x = x + alpha * (A @ x) - beta * x
        x = np.maximum(x, ext)
        x = np.clip(x, 0.0, 1.0)
        series[t] = x

    # Industry aggregation
    idxs = [i for i, n in enumerate(graph.snapshot.nodes) if n.industry == industry]
    if not idxs:
        return BaselinePrediction(0.0, 0.0, 0.0, 0.0, "linear_diffusion")
    weights = graph.gdp_usd[idxs]
    w = weights / max(weights.sum(), 1.0)

    ind_series = np.average(series[:, idxs], axis=1, weights=w)
    peak_t = int(ind_series.argmax())
    el_avg = float(np.average(graph.elasticity[idxs], weights=w))
    rs_avg = float(np.average(graph.resilience[idxs], weights=w))
    pt_avg = float(np.average(graph.pass_through[idxs], weights=w))

    industry_loss = float(ind_series.max()) * el_avg * (1.0 - rs_avg)
    inflation = float(ind_series.max()) * pt_avg * 0.10
    below = np.where(ind_series[peak_t:] < 0.1)[0]
    recovery_weeks = float(below[0]) if below.size > 0 else float(horizon_weeks - peak_t)

    total_loss = float(
        (series.max(axis=0) * graph.elasticity * (1.0 - graph.resilience) * graph.gdp_usd).sum()
    )

    return BaselinePrediction(
        industry_loss=industry_loss,
        inflation=inflation,
        recovery_weeks=recovery_weeks,
        total_output_loss_usd=total_loss,
        model="linear_diffusion",
    )


__all__ = ["BaselinePrediction", "leontief_predict", "linear_diffusion_predict"]
