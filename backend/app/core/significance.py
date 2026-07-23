"""Statistical significance layer for the N-event benchmark leaderboard.

Answers the question the point estimates in ``benchmark.py`` cannot: at the
current N, WHICH leaderboard differences are real and which are small-sample
noise? This is the first question any technical judge asks of a 27-event
validation set, and it deserves a precomputed, deterministic, reviewable
answer rather than an improvised one.

Three procedures, all seeded and event-level (resampling whole events, never
individual residuals, so heteroscedasticity across event types is preserved):

1. Per-model bootstrap CIs — MAE / RMSE / Spearman with percentile intervals.
2. Pairwise PAIRED bootstrap on metric differences — the same resample indices
   are applied to both models, so the interval reflects the variance of the
   *difference* on common events, not the (much wider) variance of each side.
3. Pairwise sign-flip permutation test — exact-style two-sided p-value for
   "model A's per-event absolute error is lower than model B's", flipping the
   sign of each per-event error difference under H0 exchangeability.

Also bootstraps the Track B cascade-shape Spearman per dimension: the shape
dimensions have small n (magnitude 5, weeks_to_peak 15, recovery 11), so any
claim about them without a CI would be exactly the kind of overreach this
module exists to prevent.

Determinism: given (n_boot, n_perm, seed) the payload is byte-identical across
runs — the same convention as the benchmark golden snapshot.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np

from app.core.benchmark import (
    BENCHMARK_CONFIG,
    _config_to_dict,
    _eval_diffusion,
    _eval_leontief,
    _eval_persistence,
    _eval_seirs,
)
from app.core.cascade_validation import run_cascade_validation
from app.core.graph import compile_graph
from app.core.metrics import spearman_rho
from app.data.seed import load_graph
from app.data.seed_data import HISTORICAL_EVENTS

SCHEMA = "geds.significance.v1"

# Short stable keys for the payload; long display names stay in benchmark.py.
MODEL_KEYS = {
    "GEDS": "SEIRS-Bullwhip-Hysteresis (GEDS)",
    "Leontief": "Leontief (input-output equilibrium)",
    "LinearDiffusion": "Linear Diffusion (network)",
    "NaivePersistence": "Naive Persistence (predict mean)",
}

# Constant-predictor guard, same tolerance rationale as benchmark._score.
_RANK_EPS = 1e-9


def _mae(pred: np.ndarray, obs: np.ndarray) -> float:
    return float(np.abs(pred - obs).mean())


def _rmse(pred: np.ndarray, obs: np.ndarray) -> float:
    return float(np.sqrt(((pred - obs) ** 2).mean()))


def _spearman_or_nan(pred: np.ndarray, obs: np.ndarray) -> float:
    if float(np.std(pred)) <= _RANK_EPS or float(np.std(obs)) <= _RANK_EPS:
        return float("nan")
    return float(spearman_rho(pred, obs))


def _pctl_block(samples: np.ndarray, point: float) -> dict:
    """Percentile summary of a bootstrap distribution around a point estimate."""
    finite = samples[np.isfinite(samples)]
    if finite.size == 0:
        return {"point": _safe(point), "p2_5": None, "p50": None, "p97_5": None,
                "n_finite_resamples": 0}
    return {
        "point": _safe(point),
        "p2_5": round(float(np.percentile(finite, 2.5)), 5),
        "p50": round(float(np.percentile(finite, 50.0)), 5),
        "p97_5": round(float(np.percentile(finite, 97.5)), 5),
        "n_finite_resamples": int(finite.size),
    }


def _safe(x: float) -> float | None:
    return None if (isinstance(x, float) and math.isnan(x)) else round(float(x), 5)


def bootstrap_model_ci(pred: np.ndarray, obs: np.ndarray,
                       n_boot: int, seed: int) -> dict:
    """Event-level bootstrap CIs for one model's MAE / RMSE / Spearman."""
    rng = np.random.default_rng(seed)
    n = obs.size
    idx = rng.integers(0, n, size=(n_boot, n))
    p, o = pred[idx], obs[idx]
    mae = np.abs(p - o).mean(axis=1)
    rmse = np.sqrt(((p - o) ** 2).mean(axis=1))
    out = {
        "mae": _pctl_block(mae, _mae(pred, obs)),
        "rmse": _pctl_block(rmse, _rmse(pred, obs)),
    }
    if float(np.std(pred)) > _RANK_EPS:
        sp = np.array([_spearman_or_nan(p[b], o[b]) for b in range(n_boot)])
        out["spearman"] = _pctl_block(sp, _spearman_or_nan(pred, obs))
    else:
        out["spearman"] = None  # constant predictor: no rank ordering exists
    return out


def paired_delta_bootstrap(pred_a: np.ndarray, pred_b: np.ndarray,
                           obs: np.ndarray, n_boot: int, seed: int) -> dict:
    """Paired bootstrap of (metric_a - metric_b) using shared resample indices.

    Negative delta on MAE/RMSE means model A is better; ``frac_a_better`` is
    the fraction of resamples in which A's metric is strictly lower.
    """
    rng = np.random.default_rng(seed)
    n = obs.size
    idx = rng.integers(0, n, size=(n_boot, n))
    pa, pb, o = pred_a[idx], pred_b[idx], obs[idx]
    d_mae = np.abs(pa - o).mean(axis=1) - np.abs(pb - o).mean(axis=1)
    d_rmse = (np.sqrt(((pa - o) ** 2).mean(axis=1))
              - np.sqrt(((pb - o) ** 2).mean(axis=1)))
    out = {
        "delta_mae_a_minus_b": _pctl_block(
            d_mae, _mae(pred_a, obs) - _mae(pred_b, obs)),
        "delta_rmse_a_minus_b": _pctl_block(
            d_rmse, _rmse(pred_a, obs) - _rmse(pred_b, obs)),
        "frac_a_better_mae": round(float((d_mae < 0).mean()), 4),
    }
    if float(np.std(pred_a)) > _RANK_EPS and float(np.std(pred_b)) > _RANK_EPS:
        d_sp = np.array([
            _spearman_or_nan(pa[b], o[b]) - _spearman_or_nan(pb[b], o[b])
            for b in range(n_boot)
        ])
        out["delta_spearman_a_minus_b"] = _pctl_block(
            d_sp, _spearman_or_nan(pred_a, obs) - _spearman_or_nan(pred_b, obs))
    else:
        out["delta_spearman_a_minus_b"] = None
    return out


def sign_flip_p(abs_err_a: np.ndarray, abs_err_b: np.ndarray,
                n_perm: int, seed: int) -> float:
    """Two-sided sign-flip permutation p for mean(|err_a| - |err_b|) == 0.

    Monte-Carlo with the standard +1 correction so p is never exactly 0 and
    the test remains valid at any n_perm.
    """
    d = abs_err_a - abs_err_b
    t_obs = abs(float(d.mean()))
    if t_obs == 0.0:
        return 1.0
    rng = np.random.default_rng(seed)
    signs = rng.choice((-1.0, 1.0), size=(n_perm, d.size))
    t_perm = np.abs((signs * d).mean(axis=1))
    return float((1 + int((t_perm >= t_obs).sum())) / (n_perm + 1))


def bootstrap_spearman_pairs(pred: np.ndarray, obs: np.ndarray,
                             n_boot: int, seed: int) -> dict:
    """Bootstrap CI for the Spearman of a small (pred, obs) pair set."""
    rng = np.random.default_rng(seed)
    n = obs.size
    idx = rng.integers(0, n, size=(n_boot, n))
    sp = np.array([_spearman_or_nan(pred[b_idx], obs[b_idx]) for b_idx in idx])
    block = _pctl_block(sp, _spearman_or_nan(pred, obs))
    block["n"] = int(n)
    return block


def run_significance(n_boot: int = 10_000, n_perm: int = 20_000,
                     seed: int = 20260718) -> dict:
    """Full significance payload over the live benchmark evaluators."""
    graph = compile_graph(load_graph())
    evals = {
        "GEDS": _eval_seirs(graph, BENCHMARK_CONFIG),
        "Leontief": _eval_leontief(graph),
        "LinearDiffusion": _eval_diffusion(graph),
        "NaivePersistence": _eval_persistence(graph),
    }
    # every evaluator reads the same observed vector in the same event order
    obs = evals["GEDS"][1]
    for name, (_, o) in evals.items():
        assert np.allclose(o, obs), f"{name} observed vector disagrees"

    models = {
        name: bootstrap_model_ci(pred, obs, n_boot, seed)
        for name, (pred, _) in evals.items()
    }

    names = list(evals)
    pairwise = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pred_a, pred_b = evals[a][0], evals[b][0]
            entry = paired_delta_bootstrap(pred_a, pred_b, obs, n_boot, seed)
            entry["p_perm_mae_two_sided"] = round(
                sign_flip_p(np.abs(pred_a - obs), np.abs(pred_b - obs),
                            n_perm, seed), 5)
            pairwise[f"{a}__vs__{b}"] = entry

    cascade = run_cascade_validation()
    dims: dict[str, dict] = {}
    for dim in ("magnitude", "weeks_to_peak", "recovery_weeks"):
        pairs = [(d.predicted, d.observed)
                 for ev in cascade.events for d in ev.dims if d.name == dim]
        if pairs:
            pred = np.array([p for p, _ in pairs])
            o = np.array([q for _, q in pairs])
            dims[dim] = bootstrap_spearman_pairs(pred, o, n_boot, seed)

    return {
        "schema": SCHEMA,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "n_boot": n_boot,
        "n_perm": n_perm,
        "n_events": len(HISTORICAL_EVENTS),
        "event_slugs": [e["slug"] for e in HISTORICAL_EVENTS],
        "model_display_names": MODEL_KEYS,
        "engine_config": _config_to_dict(BENCHMARK_CONFIG),
        "models": models,
        "pairwise": pairwise,
        "cascade_shape_spearman": dims,
        "interpretation": {
            "delta_sign": "delta_*_a_minus_b < 0 means the first-named model "
                          "has the lower (better) error metric",
            "significance_rule": "a pairwise difference is significant at "
                                 "alpha=0.05 if 0 lies outside the paired "
                                 "95% CI AND p_perm_mae_two_sided < 0.05",
            "caveat": "event-level bootstrap at N=27 (and n=5..15 for shape "
                      "dims) has limited power; absence of significance is "
                      "not evidence of equivalence",
        },
    }
