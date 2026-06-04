"""
GEDS MCMC / Bayesian Calibration — Pseudocode & Implementation Template

Publication-grade calibration methodology for ~1128-node OECD ICIO graph.

This is a skeleton; you must plug in your actual data loading and simulator.
"""

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from scipy import stats as sp_stats
# Optional: CMA-ES, PyMC, NumPyro, ArviZ, pymoo, etc.


# ============================================================
# STEP 1 — Load OECD ICIO Leontief coefficients A_ij (FIXED)
# ============================================================

def load_oecd_icio(path: str) -> np.ndarray:
    """
    Load OECD ICIO 2021 Leontief technical coefficient matrix A.

    A_ij = fraction of sector j's output used by sector i per unit i output.
    Shape: (N_nodes, N_nodes) where nodes = country × sector.
    """
    # TODO: implement using your ICIO CSV/parquet files
    raise NotImplementedError("Implement with actual OECD ICIO data.")


# ============================================================
# STEP 2 — Parameter vector structure
# ============================================================

# Free parameters:
#   θ = [β, γ,
#        δ_1..δ_19,
#        λ_1..λ_19,
#        n_1..n_19,
#        τ_1..τ_19,
#        α_BW, ψ, σ_obs]
# Total dimension = 81

SECTOR_COUNT = 19
SECTOR_PARAMS = ["δ", "λ", "n", "τ"]   # 4 * 19 = 76
GLOBAL_PARAMS = ["β", "γ", "α_BW", "ψ", "σ_obs"]
TOTAL_DIM = 4 * SECTOR_COUNT + len(GLOBAL_PARAMS)  # 81


def unpack_theta(theta: np.ndarray):
    """Unpack flat theta vector into named blocks."""
    β = theta[0]
    γ = theta[1]
    δ = theta[2:2 + SECTOR_COUNT]
    λ = theta[2 + SECTOR_COUNT:2 + 2 * SECTOR_COUNT]
    n = theta[2 + 2 * SECTOR_COUNT:2 + 3 * SECTOR_COUNT]
    τ = theta[2 + 3 * SECTOR_COUNT:2 + 4 * SECTOR_COUNT]
    α_BW = theta[2 + 4 * SECTOR_COUNT]
    ψ = theta[3 + 4 * SECTOR_COUNT]
    σ_obs = theta[4 + 4 * SECTOR_COUNT]
    return β, γ, δ, λ, n, τ, α_BW, ψ, σ_obs


# ============================================================
# STEP 3 — GEDS forward simulator wrapper
# ============================================================

def geds_forward(theta: np.ndarray, A: np.ndarray, shock_event: dict) -> float:
    """
    Run GEDS simulation and return GDP impact scalar for a single event.

    Parameters
    ----------
    theta : np.ndarray
        81-dim parameter vector.
    A : np.ndarray
        Fixed OECD ICIO Leontief matrix.
    shock_event : dict
        Contains event configuration: affected nodes/sectors, initial shock, horizon, etc.

    Returns
    -------
    float
        Simulated GDP impact (e.g. % deviation from baseline).
    """
    # TODO: call your actual GEDS engine here.
    raise NotImplementedError("Connect to existing GEDS simulator.")


# ============================================================
# STEP 4 — Log-likelihood
# ============================================================

def log_likelihood(theta: np.ndarray, A: np.ndarray,
                   events_train: list, y_obs: np.ndarray) -> float:
    """
    Gaussian observation model:
      y_i ~ N(f(theta, event_i), σ_obs^2)

    log L(θ) = -0.5 * Σ_i [ (y_i - f(θ, event_i))^2 / σ_obs^2 + log(2π σ_obs^2) ]
    """
    _, _, _, _, _, _, _, _, σ_obs = unpack_theta(theta)
    if σ_obs <= 0:
        return -np.inf

    ll = 0.0
    for i, event in enumerate(events_train):
        y_hat = geds_forward(theta, A, event)
        resid = (y_obs[i] - y_hat) / σ_obs
        ll += -0.5 * (resid ** 2 + 2.0 * np.log(σ_obs))
    return ll


# ============================================================
# STEP 5 — Log-prior from literature-informed bounds
# ============================================================

def log_prior(theta: np.ndarray) -> float:
    """
    Literature-informed priors (see parameter_table.csv).

    β  ~ LogNormal(μ=ln(0.15), σ=0.5)
    γ  ~ LogNormal(μ=ln(0.10), σ=0.6)
    δ_k ~ Beta(2,5)
    λ_k ~ Gamma(2,0.05)
    n_k ~ LogNormal(μ=ln(4), σ=0.5)
    τ_k ~ Gamma(3,0.5)
    α_BW ~ 1 + HalfNormal(σ=1.0)
    ψ  ~ Beta(2,3)
    σ_obs ~ HalfNormal(σ=0.1)
    """
    β, γ, δ, λ, n, τ, α_BW, ψ, σ_obs = unpack_theta(theta)
    lp = 0.0

    # Global parameters
    lp += sp_stats.lognorm(s=0.5, scale=np.exp(np.log(0.15))).logpdf(β)
    lp += sp_stats.lognorm(s=0.6, scale=np.exp(np.log(0.10))).logpdf(γ)

    # Sector parameters
    lp += np.sum(sp_stats.beta(2, 5).logpdf(δ))
    lp += np.sum(sp_stats.gamma(a=2, scale=0.05).logpdf(λ))
    lp += np.sum(sp_stats.lognorm(s=0.5, scale=np.exp(np.log(4.0))).logpdf(n))
    lp += np.sum(sp_stats.gamma(a=3, scale=0.5).logpdf(τ))

    # Bullwhip amplification (shifted half-normal, α_BW ≥ 1)
    lp += sp_stats.halfnorm(scale=1.0).logpdf(α_BW - 1.0)

    # Hysteresis
    lp += sp_stats.beta(2, 3).logpdf(ψ)

    # Observation noise
    lp += sp_stats.halfnorm(scale=0.1).logpdf(σ_obs)

    return lp


# ============================================================
# STEP 6 — Negative log-posterior with L2 regularization
# ============================================================

def negative_log_posterior(theta: np.ndarray, A: np.ndarray,
                           events_train: list, y_obs: np.ndarray,
                           lambda_L2: float = 0.01) -> float:
    """
    Full objective for MAP:

      L(θ) = -log p(θ) - log L(θ) + λ_L2 * ||θ||^2 / dim(θ)

    λ_L2 in [0.005, 0.02] recommended; tune via LOEO-CV.
    """
    lp = log_prior(theta)
    if not np.isfinite(lp):
        return 1e10

    ll = log_likelihood(theta, A, events_train, y_obs)
    if not np.isfinite(ll):
        return 1e10

    reg = lambda_L2 * np.sum(theta ** 2) / len(theta)
    return -(lp + ll) + reg


# ============================================================
# STEP 7 — CMA-ES MAP (Phase 1)
# ============================================================

def init_from_prior_mean() -> np.ndarray:
    """Prior-mean initialization for θ."""
    theta = np.zeros(TOTAL_DIM)
    theta[0] = 0.15                # β
    theta[1] = 0.10                # γ
    theta[2:2 + SECTOR_COUNT] = 0.30   # δ
    theta[2 + SECTOR_COUNT:2 + 2 * SECTOR_COUNT] = 0.10   # λ
    theta[2 + 2 * SECTOR_COUNT:2 + 3 * SECTOR_COUNT] = 4.0   # n
    theta[2 + 3 * SECTOR_COUNT:2 + 4 * SECTOR_COUNT] = 1.5   # τ
    theta[2 + 4 * SECTOR_COUNT] = 2.0    # α_BW
    theta[3 + 4 * SECTOR_COUNT] = 0.40   # ψ
    theta[4 + 4 * SECTOR_COUNT] = 0.10   # σ_obs
    return theta


def phase1_cma_es_map(A, events_train, y_obs, n_restarts: int = 5):
    """
    Phase 1: CMA-ES MAP optimization (pycma).

    Returns θ_MAP (best found).
    """
    import cma

    theta0 = init_from_prior_mean()
    sigma0 = 0.3
    opts = cma.CMAOptions()
    opts["maxiter"] = 5000
    opts["tolx"] = 1e-6
    opts["tolfun"] = 1e-6
    opts["verbose"] = -9

    best_result = None
    for _ in range(n_restarts):
        theta_init = theta0 * (1.0 + 0.1 * np.random.randn(theta0.size))
        es = cma.CMAEvolutionStrategy(theta_init, sigma0, opts)
        es.optimize(negative_log_posterior, args=(A, events_train, y_obs))
        if best_result is None or es.result.fbest < best_result.fbest:
            best_result = es.result

    return best_result.xbest


# ============================================================
# STEP 8 — LOEO cross-validation
# ============================================================

def loeo_cross_validation(events_all: list, y_all: np.ndarray, A: np.ndarray):
    """
    Leave-One-Event-Out CV over N events.

    Returns dict with mean/std MAE and RMSE, plus per-event MAE.
    """
    N = len(events_all)
    mae_list = []
    rmse_list = []

    for k in range(N):
        train_events = [e for i, e in enumerate(events_all) if i != k]
        train_y = np.delete(y_all, k)
        test_event = events_all[k]
        test_y = y_all[k]

        theta_hat = phase1_cma_es_map(A, train_events, train_y, n_restarts=3)
        y_pred = geds_forward(theta_hat, A, test_event)

        mae_list.append(abs(test_y - y_pred))
        rmse_list.append((test_y - y_pred) ** 2)

    mae_arr = np.array(mae_list)
    rmse_arr = np.array(rmse_list)

    return {
        "loeo_mae_mean": float(mae_arr.mean()),
        "loeo_mae_std": float(mae_arr.std()),
        "loeo_rmse": float(np.sqrt(rmse_arr.mean())),
        "mae_per_event": mae_list,
    }


# ============================================================
# STEP 9 — Bootstrap uncertainty on metrics
# ============================================================

def bootstrap_metrics(events_train, y_obs, A, theta_hat,
                      B: int = 1000, seed: int = 42):
    """
    Parametric bootstrap for MAE, Pearson, and R² uncertainty.

    Resamples events with replacement and recomputes metrics.
    """
    rng = np.random.default_rng(seed)
    n = len(events_train)

    y_pred_all = np.array([geds_forward(theta_hat, A, e) for e in events_train])
    mae_boot, pearson_boot, r2_boot = [], [], []

    for _ in range(B):
        idx = rng.integers(0, n, size=n)
        y_b = y_obs[idx]
        yp_b = y_pred_all[idx]

        mae_boot.append(np.mean(np.abs(y_b - yp_b)))

        if np.std(y_b) > 0 and np.std(yp_b) > 0:
            pearson_boot.append(pearsonr(y_b, yp_b)[0])

        ss_res = np.sum((y_b - yp_b) ** 2)
        ss_tot = np.sum((y_b - y_b.mean()) ** 2)
        r2_boot.append(1 - ss_res / ss_tot if ss_tot > 0 else -np.inf)

    return {
        "MAE_95CI": (np.percentile(mae_boot, 2.5), np.percentile(mae_boot, 97.5)),
        "Pearson_95CI": (np.percentile(pearson_boot, 2.5), np.percentile(pearson_boot, 97.5))
            if pearson_boot else (None, None),
        "R2_95CI": (np.percentile(r2_boot, 2.5), np.percentile(r2_boot, 97.5)),
    }