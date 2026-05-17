"""Bayesian parameter inference via affine-invariant MCMC (emcee).

Replaces Optuna's point-estimate calibration with a full posterior distribution
over the five free engine parameters.  The posterior is what an ISEF judge
will actually ask for: "what's your uncertainty on amplification_mu?"

Model
-----
For each historical event i with observed metrics o_i (industry loss, inflation,
recovery weeks), the engine produces a prediction p_i(θ).  Treating prediction
error as Gaussian with per-metric scale σ_m gives the log-likelihood:

    log L(θ | data) = -½ ∑_i ∑_m w_m · (p_{i,m}(θ) − o_{i,m})² / σ_m²
                       + constant

Priors: independent uniform on the calibrated parameter bounds (uninformative,
lets the data speak).  Hard-clipped to the bounds, so any prior-violating
walker gets −∞ log-prob and is rejected.

Diagnostics
-----------
- Posterior mean, std, 5%/50%/95% credible intervals per parameter
- Gelman-Rubin R̂ (across walker chains as proxy chains)
- Autocorrelation time per parameter (effective sample size estimate)
- Sensitivity scores: 1 − Var(posterior) / Var(prior)
- Pairwise posterior correlations

Output JSON consumed by /api/v1/posterior endpoint and by ISEF figures.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

try:
    import emcee
except ImportError as e:
    raise ImportError("emcee>=3.1 is required.  pip install emcee") from e

from .backtest import backtest_event
from .graph import compile_graph
from .types import EngineConfig
from ..data.seed import load_graph
from ..data.seed_data import HISTORICAL_EVENTS


# ─────────────────────────── search-space priors ───────────────────────────


PARAM_NAMES = [
    "amplification_mu",
    "bullwhip_factor",
    "recovery_rate",
    "inventory_scale",
    "distress_base",
]
# Widened 2026-05-17 after batch-2 DE diagnostic showed three of five parameters
# pinned at the previous bounds — meaning the optimizer wanted to leave the box.
# New bounds are explicitly defensible: amplification_mu up to 8 covers
# epidemiological R0 values for high-contagion supply chains; bullwhip up to 2.0
# matches Lee/Padmanabhan/Whang (1997) extremes; recovery_rate to 0.30 covers
# 3-week half-life recoveries.
PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "amplification_mu": (0.10, 8.00),
    "bullwhip_factor":  (1.00, 2.00),
    "recovery_rate":    (0.01, 0.30),
    "inventory_scale":  (0.30, 2.00),
    "distress_base":    (0.20, 0.70),
}

# Observation-noise scales (units = same as observed metric).
# These are deliberately conservative; calibrated from rough literature std-dev.
METRIC_SIGMA = {
    "industry_loss": 0.05,   # 5pp std for industry production loss
    "inflation":     0.01,   # 1pp std for inflation contribution
    "recovery_yr":   0.20,   # ~10 weeks std on recovery time
}
METRIC_WEIGHT = {"industry_loss": 0.50, "inflation": 0.30, "recovery_yr": 0.20}


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class ParamPosterior:
    name: str
    mean: float
    std: float
    p05: float
    p50: float
    p95: float
    prior_low: float
    prior_high: float
    sensitivity: float        # 1 − posterior_var / prior_var; 0 = no info, 1 = perfectly identified


@dataclass
class MCMCResult:
    calibration_date: str
    n_walkers: int
    n_steps: int
    n_burnin: int
    n_effective_samples: int
    log_evidence_proxy: float           # max log-posterior achieved
    acceptance_fraction_mean: float
    autocorr_time_max: float
    r_hat_max: float                    # split-walker proxy for Gelman-Rubin
    converged: bool
    runtime_seconds: float
    parameters: list[ParamPosterior]
    pairwise_corr: dict[str, dict[str, float]]


# ─────────────────────────── likelihood ────────────────────────────────────


def _log_prior(theta: np.ndarray) -> float:
    """Uniform prior on the calibration box."""
    for name, val in zip(PARAM_NAMES, theta, strict=True):
        lo, hi = PARAM_BOUNDS[name]
        if not (lo <= val <= hi):
            return -np.inf
    return 0.0   # uniform → constant log-prob inside the box


def _engine_config(theta: np.ndarray) -> EngineConfig:
    params = dict(zip(PARAM_NAMES, theta, strict=True))
    return EngineConfig(
        propagation_decay=0.85,
        rerouting_efficiency=0.55,
        amplification_eps=0.06,
        amplification_mu=float(params["amplification_mu"]),
        recovery_rate=float(params["recovery_rate"]),
        bullwhip_factor=float(params["bullwhip_factor"]),
        inventory_scale=float(params["inventory_scale"]),
        distress_base=float(params["distress_base"]),
        seis_enabled=True,
        adaptive_rerouting=True,
        stochastic_sigma=0.0,
    )


def _log_likelihood(theta: np.ndarray, graph) -> float:
    """Gaussian log-likelihood over the historical event suite."""
    if not np.isfinite(_log_prior(theta)):
        return -np.inf
    config = _engine_config(theta)

    lnL = 0.0
    for event in HISTORICAL_EVENTS:
        try:
            r = backtest_event(event, graph, config)
        except Exception:
            return -np.inf
        # Three metrics per event, Gaussian likelihood.
        terms = [
            ("industry_loss", r.industry_loss_predicted - r.industry_loss_observed),
            ("inflation",     r.inflation_predicted      - r.inflation_observed),
            ("recovery_yr",   (r.recovery_predicted      - r.recovery_observed) / 52.0),
        ]
        for key, err in terms:
            sigma = METRIC_SIGMA[key]
            w = METRIC_WEIGHT[key]
            lnL += -0.5 * w * (err / sigma) ** 2
    return float(lnL)


def _log_probability(theta: np.ndarray, graph) -> float:
    lp = _log_prior(theta)
    if not np.isfinite(lp):
        return -np.inf
    return lp + _log_likelihood(theta, graph)


# ─────────────────────────── sampler ───────────────────────────────────────


def _initial_walkers(n_walkers: int, rng: np.random.Generator) -> np.ndarray:
    """Latin-hypercube-ish uniform draw from the prior box for each walker."""
    out = np.zeros((n_walkers, len(PARAM_NAMES)))
    for i, name in enumerate(PARAM_NAMES):
        lo, hi = PARAM_BOUNDS[name]
        out[:, i] = rng.uniform(lo, hi, n_walkers)
    return out


def run_mcmc(
    n_walkers: int = 32,
    n_steps: int = 600,
    n_burnin: int = 200,
    seed: int = 42,
    progress: bool = False,
) -> MCMCResult:
    """Run affine-invariant MCMC and return a structured posterior.

    Defaults: 32 walkers × 600 steps × 8 events ≈ 90 sec on a laptop.
    For production posteriors targeting ISEF figures, use n_steps≥2000.
    """
    rng = np.random.default_rng(seed)
    snapshot = load_graph()
    graph = compile_graph(snapshot)

    n_dim = len(PARAM_NAMES)
    p0 = _initial_walkers(n_walkers, rng)

    sampler = emcee.EnsembleSampler(
        nwalkers=n_walkers, ndim=n_dim,
        log_prob_fn=_log_probability, args=(graph,),
    )

    t0 = time.perf_counter()
    sampler.run_mcmc(p0, n_steps, progress=progress)
    runtime = time.perf_counter() - t0

    # Diagnostics ----------------------------------------------------------
    chain = sampler.get_chain()                    # (n_steps, n_walkers, n_dim)
    post = chain[n_burnin:].reshape(-1, n_dim)     # (n_eff, n_dim)
    log_probs = sampler.get_log_prob()

    try:
        tau = sampler.get_autocorr_time(tol=0)
        tau_max = float(np.nanmax(tau))
    except emcee.autocorr.AutocorrError:
        tau = np.full(n_dim, np.nan)
        tau_max = float("nan")

    r_hat_max = _split_walker_r_hat(chain[n_burnin:])
    accept_frac = float(np.mean(sampler.acceptance_fraction))
    log_evidence_proxy = float(np.nanmax(log_probs))
    converged = bool((accept_frac > 0.20) and (r_hat_max < 1.10 or np.isnan(r_hat_max)))

    # Posterior summaries --------------------------------------------------
    params = []
    for i, name in enumerate(PARAM_NAMES):
        lo, hi = PARAM_BOUNDS[name]
        samples = post[:, i]
        prior_var = ((hi - lo) ** 2) / 12.0     # variance of Uniform(lo, hi)
        post_var = float(np.var(samples))
        sens = max(0.0, min(1.0, 1.0 - post_var / max(prior_var, 1e-12)))
        params.append(ParamPosterior(
            name=name,
            mean=float(np.mean(samples)),
            std=float(np.std(samples)),
            p05=float(np.percentile(samples, 5)),
            p50=float(np.percentile(samples, 50)),
            p95=float(np.percentile(samples, 95)),
            prior_low=lo, prior_high=hi,
            sensitivity=sens,
        ))

    # Pairwise correlation matrix (Pearson)
    corr_mat = np.corrcoef(post.T)
    pairwise: dict[str, dict[str, float]] = {}
    for i, ni in enumerate(PARAM_NAMES):
        pairwise[ni] = {nj: float(corr_mat[i, j]) for j, nj in enumerate(PARAM_NAMES)}

    return MCMCResult(
        calibration_date=datetime.now(timezone.utc).isoformat(),
        n_walkers=n_walkers, n_steps=n_steps, n_burnin=n_burnin,
        n_effective_samples=int(post.shape[0]),
        log_evidence_proxy=log_evidence_proxy,
        acceptance_fraction_mean=accept_frac,
        autocorr_time_max=tau_max,
        r_hat_max=float(r_hat_max),
        converged=converged,
        runtime_seconds=round(runtime, 2),
        parameters=params,
        pairwise_corr=pairwise,
    )


# ─────────────────────────── Gelman-Rubin proxy ────────────────────────────


def _split_walker_r_hat(chain_burned: np.ndarray) -> float:
    """Split each walker into halves and treat each as a chain — proxy for R̂.

    Standard Gelman-Rubin wants ≥2 independent chains; emcee's ensemble of
    walkers are correlated.  Splitting each walker in half is a reasonable
    proxy that catches non-convergence.  Reports max R̂ across parameters.
    """
    n_steps, n_walkers, n_dim = chain_burned.shape
    if n_steps < 4 or n_walkers < 2:
        return float("nan")
    half = n_steps // 2
    a = chain_burned[:half]
    b = chain_burned[half : 2 * half]
    # Treat each walker-half as one chain.  m = 2 × n_walkers chains, length = half.
    chains = np.concatenate([a, b], axis=1)        # (half, 2*n_walkers, n_dim)
    m = chains.shape[1]
    n = chains.shape[0]

    means = chains.mean(axis=0)                    # (m, n_dim)
    grand_mean = means.mean(axis=0)                # (n_dim,)
    B = n / (m - 1) * np.sum((means - grand_mean) ** 2, axis=0)
    W = np.mean(chains.var(axis=0, ddof=1), axis=0)
    var_hat = (n - 1) / n * W + B / n
    r_hat = np.sqrt(var_hat / np.maximum(W, 1e-12))
    return float(np.nanmax(r_hat))


# ─────────────────────────── persistence ───────────────────────────────────


def save_result(result: MCMCResult, path: Path | None = None) -> Path:
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "posterior.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable: dict[str, Any] = asdict(result)
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    return path


def load_result(path: Path | None = None) -> MCMCResult | None:
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "posterior.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    params = [ParamPosterior(**p) for p in raw.pop("parameters")]
    return MCMCResult(parameters=params, **raw)


__all__ = [
    "PARAM_NAMES", "PARAM_BOUNDS",
    "ParamPosterior", "MCMCResult",
    "run_mcmc", "save_result", "load_result",
]
