"""Unified model benchmark suite — Phase 5 closure.

Runs every implemented propagation model on every historical event and
produces a leaderboard with the full panel of metrics:

    MAE     mean absolute error
    RMSE    root mean squared error
    MAPE    mean absolute percentage error (only for nonzero observations)
    R²      coefficient of determination
    Pearson r
    Spearman ρ
    Bias    mean(pred − obs) — positive = over-prediction
    Skill   1 − MSE_model / MSE_persistence  (Murphy's skill score vs naive)

Models compared:
    SEIRS-bullwhip            (the full GEDS engine)
    Leontief                  (closed-form input-output equilibrium)
    Linear diffusion          (textbook network diffusion baseline)
    Naive persistence         (always predicts mean observed loss)

The naive-persistence row anchors the Murphy skill score: any model that
scores below it is failing to beat "predict the average."  ISEF rigor
demands this anchor.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .backtest import backtest_event
from .baselines import leontief_predict, linear_diffusion_predict
from .graph import compile_graph
from .types import EngineConfig, Industry, ShockSpec
from ..data.seed import load_graph
from ..data.seed_data import HISTORICAL_EVENTS


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class ModelScore:
    model: str
    n_events: int
    mae: float
    rmse: float
    mape: float          # mean absolute percentage error (skipping obs=0)
    r_squared: float
    pearson: float
    spearman: float
    bias: float
    skill_score_vs_persistence: float


@dataclass
class BenchmarkReport:
    timestamp: str
    n_events: int
    models: list[ModelScore]
    winner_by_mae: str
    winner_by_rmse: str
    winner_by_r_squared: str
    winner_by_pearson: str


# ─────────────────────────── metric helpers ────────────────────────────────


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    a = a - a.mean(); b = b - b.mean()
    d = float(np.sqrt((a @ a) * (b @ b)))
    return float((a @ b) / d) if d > 0 else float("nan")


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = np.argsort(np.argsort(a)).astype(np.float64)
    rb = np.argsort(np.argsort(b)).astype(np.float64)
    return _pearson(ra, rb)


def _r2(pred: np.ndarray, obs: np.ndarray) -> float:
    ss_res = float(((obs - pred) ** 2).sum())
    ss_tot = float(((obs - obs.mean()) ** 2).sum())
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def _mape(pred: np.ndarray, obs: np.ndarray) -> float:
    mask = obs != 0
    if mask.sum() == 0:
        return float("nan")
    return float(np.abs((pred[mask] - obs[mask]) / obs[mask]).mean()) * 100


def _murphy_skill(pred: np.ndarray, obs: np.ndarray) -> float:
    """Murphy skill score vs the naive 'always predict the mean' forecast."""
    naive = np.full_like(obs, obs.mean())
    mse_model = float(((pred - obs) ** 2).mean())
    mse_naive = float(((naive - obs) ** 2).mean())
    if mse_naive == 0:
        return float("nan")
    return 1.0 - mse_model / mse_naive


def _score(model: str, pred: np.ndarray, obs: np.ndarray) -> ModelScore:
    return ModelScore(
        model=model,
        n_events=int(obs.size),
        mae=round(float(np.abs(pred - obs).mean()), 4),
        rmse=round(float(np.sqrt(((pred - obs) ** 2).mean())), 4),
        mape=round(_mape(pred, obs), 2),
        r_squared=round(_r2(pred, obs), 4),
        pearson=round(_pearson(pred, obs), 4) if not np.isnan(_pearson(pred, obs)) else 0.0,
        spearman=round(_spearman(pred, obs), 4) if not np.isnan(_spearman(pred, obs)) else 0.0,
        bias=round(float((pred - obs).mean()), 4),
        skill_score_vs_persistence=round(_murphy_skill(pred, obs), 4),
    )


# ─────────────────────────── model evaluators ──────────────────────────────


def _eval_seirs(graph, cfg: EngineConfig | None = None) -> tuple[np.ndarray, np.ndarray]:
    config = cfg or EngineConfig()
    pred = np.zeros(len(HISTORICAL_EVENTS))
    obs = np.zeros(len(HISTORICAL_EVENTS))
    for i, ev in enumerate(HISTORICAL_EVENTS):
        r = backtest_event(ev, graph, config)
        pred[i] = r.industry_loss_predicted
        obs[i]  = r.industry_loss_observed
    return pred, obs


def _eval_leontief(graph) -> tuple[np.ndarray, np.ndarray]:
    pred = np.zeros(len(HISTORICAL_EVENTS))
    obs = np.zeros(len(HISTORICAL_EVENTS))
    for i, ev in enumerate(HISTORICAL_EVENTS):
        industry = Industry(ev["observed"]["most_impacted_industry"])
        shocks = [ShockSpec(**s) for s in ev["shocks"]]
        p = leontief_predict(graph, shocks, industry, ev["horizon_weeks"])
        pred[i] = p.industry_loss
        obs[i] = ev["observed"].get("auto_production_loss_pct", 0.0)
    return pred, obs


def _eval_diffusion(graph) -> tuple[np.ndarray, np.ndarray]:
    pred = np.zeros(len(HISTORICAL_EVENTS))
    obs = np.zeros(len(HISTORICAL_EVENTS))
    for i, ev in enumerate(HISTORICAL_EVENTS):
        industry = Industry(ev["observed"]["most_impacted_industry"])
        shocks = [ShockSpec(**s) for s in ev["shocks"]]
        p = linear_diffusion_predict(graph, shocks, industry, ev["horizon_weeks"])
        pred[i] = p.industry_loss
        obs[i] = ev["observed"].get("auto_production_loss_pct", 0.0)
    return pred, obs


def _eval_persistence(graph) -> tuple[np.ndarray, np.ndarray]:
    """Naive: predict the mean observed loss for every event."""
    obs = np.array([ev["observed"].get("auto_production_loss_pct", 0.0)
                    for ev in HISTORICAL_EVENTS])
    pred = np.full_like(obs, obs.mean())
    return pred, obs


# ─────────────────────────── main entry ────────────────────────────────────


def run_benchmark() -> BenchmarkReport:
    snapshot = load_graph()
    graph = compile_graph(snapshot)

    scores: list[ModelScore] = []
    pred, obs = _eval_seirs(graph); scores.append(_score("SEIRS-Bullwhip-Hysteresis (GEDS)", pred, obs))
    pred, obs = _eval_leontief(graph); scores.append(_score("Leontief (input-output equilibrium)", pred, obs))
    pred, obs = _eval_diffusion(graph); scores.append(_score("Linear Diffusion (network)", pred, obs))
    pred, obs = _eval_persistence(graph); scores.append(_score("Naive Persistence (predict mean)", pred, obs))

    return BenchmarkReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        n_events=len(HISTORICAL_EVENTS),
        models=scores,
        winner_by_mae=min(scores, key=lambda s: s.mae).model,
        winner_by_rmse=min(scores, key=lambda s: s.rmse).model,
        winner_by_r_squared=max(scores, key=lambda s: s.r_squared if not np.isnan(s.r_squared) else -1e9).model,
        winner_by_pearson=max(scores, key=lambda s: s.pearson if not np.isnan(s.pearson) else -1e9).model,
    )


def save_benchmark(report: BenchmarkReport, path: Path | None = None) -> Path:
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "benchmark.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": report.timestamp,
        "n_events": report.n_events,
        "models": [asdict(m) for m in report.models],
        "winner_by_mae": report.winner_by_mae,
        "winner_by_rmse": report.winner_by_rmse,
        "winner_by_r_squared": report.winner_by_r_squared,
        "winner_by_pearson": report.winner_by_pearson,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


__all__ = ["ModelScore", "BenchmarkReport", "run_benchmark", "save_benchmark"]
