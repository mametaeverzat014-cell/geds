"""Leave-one-event-out cross-validation with bootstrap confidence intervals.

The honest answer to "does this model work?" — train (calibrate) on N-1 events,
test on the held-out one, rotate.  Aggregates an out-of-sample skill score
that can't be inflated by in-sample fit.

Skill metrics reported per held-out event:
    - industry_loss_error     |pred − obs|
    - inflation_error
    - recovery_weeks_error
    - within_25pct_tolerance  bool
    - within_50pct_tolerance  bool

Aggregate metrics with 95% bootstrap CIs:
    - mean absolute error per metric
    - out-of-sample pass rate at ±25% and ±50%
    - mean RMSE across the three normalized metrics
    - mean correlation predicted-vs-observed (Pearson and Spearman)

A separate "fast" mode skips re-calibration and just runs all events with a
fixed config — useful when you already trust the calibrated parameters and
just want LOO test-set numbers.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .backtest import backtest_event
from .graph import compile_graph
from .types import EngineConfig
from ..data.seed import load_graph
from ..data.seed_data import HISTORICAL_EVENTS


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class LOOEventResult:
    slug: str
    name: str
    industry_loss_predicted: float
    industry_loss_observed: float
    inflation_predicted: float
    inflation_observed: float
    recovery_predicted: float
    recovery_observed: float
    abs_loss_err: float
    abs_inf_err: float
    abs_rec_err_weeks: float
    within_25pct: bool
    within_50pct: bool


@dataclass
class CVResult:
    method: str
    n_events: int
    runtime_seconds: float
    pass_rate_25pct: float
    pass_rate_25pct_ci95_lo: float
    pass_rate_25pct_ci95_hi: float
    pass_rate_50pct: float
    pass_rate_50pct_ci95_lo: float
    pass_rate_50pct_ci95_hi: float
    mae_industry_loss: float
    mae_inflation: float
    mae_recovery_weeks: float
    pearson_loss: float
    spearman_loss: float
    rmse_normalized: float
    per_event: list[LOOEventResult]
    timestamp: str


# ─────────────────────────── helpers ───────────────────────────────────────


def _bootstrap_ci(values: np.ndarray, n_boot: int = 5000, ci: float = 0.95,
                  seed: int = 17) -> tuple[float, float]:
    """Bootstrap percentile CI on the mean.  Returns (lo, hi)."""
    if values.size == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    boots = np.zeros(n_boot)
    for i in range(n_boot):
        sample = rng.choice(values, size=values.size, replace=True)
        boots[i] = sample.mean()
    alpha = (1.0 - ci) / 2.0
    return float(np.percentile(boots, 100 * alpha)), float(np.percentile(boots, 100 * (1 - alpha)))


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2:
        return float("nan")
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a @ a) * (b @ b)))
    if denom == 0:
        return float("nan")
    return float((a @ b) / denom)


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Rank correlation without scipy.stats import overhead."""
    if a.size < 2:
        return float("nan")
    ra = np.argsort(np.argsort(a)).astype(np.float64)
    rb = np.argsort(np.argsort(b)).astype(np.float64)
    return _pearson(ra, rb)


# ─────────────────────────── main routines ─────────────────────────────────


def loo_cross_validate_fast(config: EngineConfig | None = None) -> CVResult:
    """Fast LOO mode: use a single fixed config, evaluate every event on it.

    This is "test-set" performance under fixed params — what the model
    predicts WITHOUT having been calibrated on each individual event.
    Cheap (~1 sec) and the honest baseline for ISEF figures.
    """
    import time
    t0 = time.perf_counter()
    snapshot = load_graph()
    graph = compile_graph(snapshot)
    cfg = config or EngineConfig()

    per_event: list[LOOEventResult] = []
    for event in HISTORICAL_EVENTS:
        r = backtest_event(event, graph, cfg)
        per_event.append(LOOEventResult(
            slug=r.slug, name=r.name,
            industry_loss_predicted=r.industry_loss_predicted,
            industry_loss_observed=r.industry_loss_observed,
            inflation_predicted=r.inflation_predicted,
            inflation_observed=r.inflation_observed,
            recovery_predicted=r.recovery_predicted,
            recovery_observed=r.recovery_observed,
            abs_loss_err=abs(r.industry_loss_predicted - r.industry_loss_observed),
            abs_inf_err=abs(r.inflation_predicted - r.inflation_observed),
            abs_rec_err_weeks=abs(r.recovery_predicted - r.recovery_observed),
            within_25pct=r.passes_25pct,
            within_50pct=r.passes_50pct,
        ))
    runtime = time.perf_counter() - t0
    return _aggregate(per_event, method="fixed-config-LOO", runtime=runtime)


def loo_cross_validate_full(
    n_walkers: int = 12,
    n_steps: int = 60,
    n_burnin: int = 20,
    seed: int = 42,
) -> CVResult:
    """Full LOO: for each held-out event, re-calibrate via MCMC on the other 7.

    Slow (≈ 5 min for 8 events at these defaults) — the gold-standard skill
    estimate.  Reduces in-sample bias entirely.
    """
    import time
    from . import mcmc as mcmc_mod   # avoid circular import on warm startup

    t0 = time.perf_counter()
    snapshot = load_graph()
    graph = compile_graph(snapshot)
    rng = np.random.default_rng(seed)

    per_event: list[LOOEventResult] = []
    all_events = list(HISTORICAL_EVENTS)

    for held_idx, held in enumerate(all_events):
        # Train set = all events EXCEPT held; we patch the module-level list temporarily.
        train_events = [e for j, e in enumerate(all_events) if j != held_idx]
        original = mcmc_mod.HISTORICAL_EVENTS
        mcmc_mod.HISTORICAL_EVENTS = train_events
        try:
            posterior = mcmc_mod.run_mcmc(
                n_walkers=n_walkers, n_steps=n_steps, n_burnin=n_burnin,
                seed=int(rng.integers(1, 2**31)),
            )
        finally:
            mcmc_mod.HISTORICAL_EVENTS = original

        # Use posterior mean as the test-config.
        config = EngineConfig(
            propagation_decay=0.85, rerouting_efficiency=0.55, amplification_eps=0.06,
            amplification_mu=next(p.mean for p in posterior.parameters if p.name == "amplification_mu"),
            recovery_rate=next(p.mean for p in posterior.parameters if p.name == "recovery_rate"),
            bullwhip_factor=next(p.mean for p in posterior.parameters if p.name == "bullwhip_factor"),
            inventory_scale=next(p.mean for p in posterior.parameters if p.name == "inventory_scale"),
            distress_base=next(p.mean for p in posterior.parameters if p.name == "distress_base"),
            seis_enabled=True, adaptive_rerouting=True, stochastic_sigma=0.0,
        )
        r = backtest_event(held, graph, config)
        per_event.append(LOOEventResult(
            slug=r.slug, name=r.name,
            industry_loss_predicted=r.industry_loss_predicted,
            industry_loss_observed=r.industry_loss_observed,
            inflation_predicted=r.inflation_predicted,
            inflation_observed=r.inflation_observed,
            recovery_predicted=r.recovery_predicted,
            recovery_observed=r.recovery_observed,
            abs_loss_err=abs(r.industry_loss_predicted - r.industry_loss_observed),
            abs_inf_err=abs(r.inflation_predicted - r.inflation_observed),
            abs_rec_err_weeks=abs(r.recovery_predicted - r.recovery_observed),
            within_25pct=r.passes_25pct,
            within_50pct=r.passes_50pct,
        ))

    runtime = time.perf_counter() - t0
    return _aggregate(per_event, method="LOO-MCMC", runtime=runtime)


# ─────────────────────────── aggregation ───────────────────────────────────


def _aggregate(per_event: list[LOOEventResult], method: str, runtime: float) -> CVResult:
    n = len(per_event)
    pass25 = np.array([1.0 if e.within_25pct else 0.0 for e in per_event])
    pass50 = np.array([1.0 if e.within_50pct else 0.0 for e in per_event])
    loss_err = np.array([e.abs_loss_err for e in per_event])
    inf_err = np.array([e.abs_inf_err for e in per_event])
    rec_err = np.array([e.abs_rec_err_weeks for e in per_event])

    pred_loss = np.array([e.industry_loss_predicted for e in per_event])
    obs_loss = np.array([e.industry_loss_observed for e in per_event])

    # Normalized RMSE — each metric divided by characteristic scale before summing.
    normalized = np.sqrt(
        ((loss_err / 0.05) ** 2 + (inf_err / 0.01) ** 2 + (rec_err / 52.0 / 0.20) ** 2) / 3.0
    ).mean()

    ci25_lo, ci25_hi = _bootstrap_ci(pass25)
    ci50_lo, ci50_hi = _bootstrap_ci(pass50)

    return CVResult(
        method=method,
        n_events=n,
        runtime_seconds=round(runtime, 2),
        pass_rate_25pct=round(float(pass25.mean()), 4),
        pass_rate_25pct_ci95_lo=round(ci25_lo, 4),
        pass_rate_25pct_ci95_hi=round(ci25_hi, 4),
        pass_rate_50pct=round(float(pass50.mean()), 4),
        pass_rate_50pct_ci95_lo=round(ci50_lo, 4),
        pass_rate_50pct_ci95_hi=round(ci50_hi, 4),
        mae_industry_loss=round(float(loss_err.mean()), 4),
        mae_inflation=round(float(inf_err.mean()), 4),
        mae_recovery_weeks=round(float(rec_err.mean()), 2),
        pearson_loss=round(_pearson(pred_loss, obs_loss), 4),
        spearman_loss=round(_spearman(pred_loss, obs_loss), 4),
        rmse_normalized=round(float(normalized), 4),
        per_event=per_event,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ─────────────────────────── persistence ───────────────────────────────────


def save_cv(result: CVResult, path: Path | None = None) -> Path:
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "cv_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return path


__all__ = ["LOOEventResult", "CVResult",
           "loo_cross_validate_fast", "loo_cross_validate_full",
           "save_cv"]
