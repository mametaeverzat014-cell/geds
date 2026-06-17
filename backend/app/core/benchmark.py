"""Unified model benchmark suite — deterministic, rank-aware harness.

Runs every implemented propagation model on every historical event and
produces a leaderboard with both error metrics and ranking metrics:

    error      MAE, RMSE, MAPE, R², bias, Murphy skill vs persistence
    ranking    Pearson r, Spearman ρ, Kendall τ-b, NDCG@k

Models compared:
    SEIRS-bullwhip            (the full GEDS engine)
    Leontief                  (closed-form input-output equilibrium)
    Linear diffusion          (textbook network diffusion baseline)
    Naive persistence         (always predicts the mean observed loss)

The naive-persistence row anchors the Murphy skill score: any model that
scores below it is failing to beat "predict the average."

Reproducibility
---------------
The run is deterministic. The SEIRS engine is configured from the pinned
``BENCHMARK_CONFIG`` (``stochastic_sigma = 0`` ⇒ no RNG draws; ``seed`` fixed
so even a future stochastic term would be reproducible). The only nondeterm-
inistic field is the ISO ``timestamp`` on the report, which is excluded from
the scored payload. Run ``python -m app.core.benchmark --check`` to assert two
back-to-back runs produce byte-identical scores.

Single-command execution
------------------------
    python -m app.core.benchmark            # write reports/benchmark/{json,md}
    python -m app.core.benchmark --check    # determinism self-test (no writes)
    python -m app.core.benchmark --out DIR  # custom output directory
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .backtest import backtest_event
from .baselines import leontief_predict, linear_diffusion_predict
from .graph import compile_graph
from .metrics import kendall_tau, ndcg_at_k, spearman_rho
from .types import EngineConfig, Industry, ShockSpec
from ..data.seed import load_graph
from ..data.seed_data import HISTORICAL_EVENTS


# ─────────────────────────── pinned configuration ──────────────────────────

# NDCG cutoff for the ranking score (top-k events by predicted severity).
NDCG_K = 5

# Pinned engine configuration for the benchmark. stochastic_sigma=0.0 makes the
# SEIRS cascade fully deterministic; seed is fixed for belt-and-suspenders
# reproducibility. These equal the historical EngineConfig() defaults, so
# pinning them does NOT change previously published numbers.
BENCHMARK_CONFIG = EngineConfig(seed=0, stochastic_sigma=0.0)

# reports/benchmark/ at the repository root (…/GEDS/reports/benchmark).
REPORT_DIR = Path(__file__).resolve().parents[3] / "reports" / "benchmark"


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class ModelScore:
    model: str
    n_events: int
    mae: float
    rmse: float
    mape: float                 # mean absolute percentage error (skipping obs=0)
    r_squared: float
    pearson: float
    spearman: float
    kendall: float
    ndcg_at_k: float | None     # None when ranking is undefined (constant predictor)
    bias: float
    skill_score_vs_persistence: float


@dataclass
class BenchmarkReport:
    timestamp: str
    n_events: int
    ndcg_k: int
    config: dict
    models: list[ModelScore]
    winner_by_mae: str
    winner_by_rmse: str
    winner_by_r_squared: str
    winner_by_pearson: str
    winner_by_spearman: str


# ─────────────────────────── metric helpers ────────────────────────────────


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    a = a - a.mean(); b = b - b.mean()
    d = float(np.sqrt((a @ a) * (b @ b)))
    return float((a @ b) / d) if d > 0 else float("nan")


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


def _round_or_zero(x: float) -> float:
    """Legacy convention for correlation fields: undefined ⇒ 0.0 (no correlation)."""
    return round(float(x), 4) if not math.isnan(x) else 0.0


def _score(model: str, pred: np.ndarray, obs: np.ndarray, ndcg_k: int = NDCG_K) -> ModelScore:
    # A constant predictor (e.g. naive persistence) has no rank ordering, so its
    # ranking metrics are undefined rather than literally zero/worst. We report
    # 0.0 for correlation coefficients (no rank correlation) and None for NDCG
    # (which is bounded [0,1] where 0 would wrongly read as "worst ranking").
    # Tolerance (not > 0.0) because np.full_like(obs, obs.mean()) is a bit-identical
    # constant array, but np.std()'s internal mean recomputation can introduce
    # ~1e-17 floating-point noise that otherwise flips this for specific N.
    has_ranking = float(np.std(pred)) > 1e-9
    ndcg = round(float(ndcg_at_k(pred, obs, ndcg_k)), 4) if has_ranking else None
    return ModelScore(
        model=model,
        n_events=int(obs.size),
        mae=round(float(np.abs(pred - obs).mean()), 4),
        rmse=round(float(np.sqrt(((pred - obs) ** 2).mean())), 4),
        mape=round(_mape(pred, obs), 2),
        r_squared=round(_r2(pred, obs), 4),
        pearson=_round_or_zero(_pearson(pred, obs)),
        spearman=_round_or_zero(spearman_rho(pred, obs)),
        kendall=_round_or_zero(kendall_tau(pred, obs)),
        ndcg_at_k=ndcg,
        bias=round(float((pred - obs).mean()), 4),
        skill_score_vs_persistence=round(_murphy_skill(pred, obs), 4),
    )


# ─────────────────────────── model evaluators ──────────────────────────────


def _eval_seirs(graph, cfg: EngineConfig | None = None) -> tuple[np.ndarray, np.ndarray]:
    config = cfg or BENCHMARK_CONFIG
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


# ─────────────────────────── config provenance ─────────────────────────────


def _config_to_dict(cfg: EngineConfig) -> dict:
    """Best-effort serialization of the pinned engine config for provenance."""
    for attr in ("model_dump", "dict"):
        fn = getattr(cfg, attr, None)
        if callable(fn):
            try:
                return {k: _json_safe(v) for k, v in fn().items()}
            except Exception:
                pass
    try:
        return {k: _json_safe(v) for k, v in asdict(cfg).items()}  # type: ignore[call-overload]
    except Exception:
        return {k: _json_safe(v) for k, v in vars(cfg).items()}


# ─────────────────────────── main entry ────────────────────────────────────


def run_benchmark(config: EngineConfig | None = None, ndcg_k: int = NDCG_K) -> BenchmarkReport:
    """Run the full leaderboard. Deterministic given the pinned config."""
    cfg = config or BENCHMARK_CONFIG
    snapshot = load_graph()
    graph = compile_graph(snapshot)

    scores: list[ModelScore] = []
    pred, obs = _eval_seirs(graph, cfg); scores.append(_score("SEIRS-Bullwhip-Hysteresis (GEDS)", pred, obs, ndcg_k))
    pred, obs = _eval_leontief(graph); scores.append(_score("Leontief (input-output equilibrium)", pred, obs, ndcg_k))
    pred, obs = _eval_diffusion(graph); scores.append(_score("Linear Diffusion (network)", pred, obs, ndcg_k))
    pred, obs = _eval_persistence(graph); scores.append(_score("Naive Persistence (predict mean)", pred, obs, ndcg_k))

    def _best(key, *, maximize):
        vals = [(getattr(s, key), s.model) for s in scores]
        vals = [(v, m) for v, m in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
        if not vals:
            return "—"
        return (max if maximize else min)(vals, key=lambda t: t[0])[1]

    return BenchmarkReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        n_events=len(HISTORICAL_EVENTS),
        ndcg_k=ndcg_k,
        config=_config_to_dict(cfg),
        models=scores,
        winner_by_mae=_best("mae", maximize=False),
        winner_by_rmse=_best("rmse", maximize=False),
        winner_by_r_squared=_best("r_squared", maximize=True),
        winner_by_pearson=_best("pearson", maximize=True),
        winner_by_spearman=_best("spearman", maximize=True),
    )


# ─────────────────────────── serialization / reporting ─────────────────────


def _json_safe(obj):
    """Recursively replace NaN/inf floats with None so output is valid JSON."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _report_payload(report: BenchmarkReport) -> dict:
    return {
        "timestamp": report.timestamp,
        "n_events": report.n_events,
        "ndcg_k": report.ndcg_k,
        "config": report.config,
        "models": [_json_safe(asdict(m)) for m in report.models],
        "winner_by_mae": report.winner_by_mae,
        "winner_by_rmse": report.winner_by_rmse,
        "winner_by_r_squared": report.winner_by_r_squared,
        "winner_by_pearson": report.winner_by_pearson,
        "winner_by_spearman": report.winner_by_spearman,
    }


def scored_payload(report: BenchmarkReport) -> list[dict]:
    """The deterministic part of a run (everything except the timestamp).

    Two runs with the same code, config and data must produce identical output
    here. Used by the determinism self-check and the reproducibility test.
    """
    return [_json_safe(asdict(m)) for m in report.models]


def _fmt(x) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:.4f}" if isinstance(x, float) else str(x)


def format_markdown(report: BenchmarkReport) -> str:
    cols = ["Model", "N", "MAE", "RMSE", "R²", "Pearson", "Spearman", "Kendall", f"NDCG@{report.ndcg_k}", "Skill"]
    lines = [
        "# GEDS Benchmark Leaderboard",
        "",
        f"- Generated: {report.timestamp}",
        f"- Events: {report.n_events}  |  NDCG cutoff: k={report.ndcg_k}",
        f"- Pinned config: seed={report.config.get('seed')}, stochastic_sigma={report.config.get('stochastic_sigma')}",
        "",
        "Error metrics: lower MAE/RMSE is better. Ranking metrics (Pearson/Spearman/"
        "Kendall/NDCG): higher is better. Skill = Murphy skill vs naive persistence "
        "(>0 beats the mean).",
        "",
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for m in report.models:
        row = [
            m.model, str(m.n_events), _fmt(m.mae), _fmt(m.rmse), _fmt(m.r_squared),
            _fmt(m.pearson), _fmt(m.spearman), _fmt(m.kendall), _fmt(m.ndcg_at_k),
            _fmt(m.skill_score_vs_persistence),
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines += [
        "",
        "## Winners",
        "",
        f"- Lowest MAE: **{report.winner_by_mae}**",
        f"- Lowest RMSE: **{report.winner_by_rmse}**",
        f"- Highest R²: **{report.winner_by_r_squared}**",
        f"- Highest Pearson: **{report.winner_by_pearson}**",
        f"- Highest Spearman: **{report.winner_by_spearman}**",
        "",
    ]
    return "\n".join(lines)


def write_report(report: BenchmarkReport, out_dir: Path | None = None) -> tuple[Path, Path]:
    """Write benchmark.json + summary.md to reports/benchmark/. Returns paths."""
    out = out_dir or REPORT_DIR
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "benchmark.json"
    md_path = out / "summary.md"
    json_path.write_text(json.dumps(_report_payload(report), indent=2), encoding="utf-8")
    md_path.write_text(format_markdown(report), encoding="utf-8")
    return json_path, md_path


def save_benchmark(report: BenchmarkReport, path: Path | None = None) -> Path:
    """Legacy writer: emit the served benchmark.json under data/calibration/.

    Kept for the FastAPI ``/benchmark`` endpoint (routes.py). New, reproducible
    artifacts go to reports/benchmark/ via ``write_report``.
    """
    if path is None:
        path = Path(__file__).parent.parent.parent / "data" / "calibration" / "benchmark.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(_report_payload(report)), indent=2), encoding="utf-8")
    return path


def _check_determinism(ndcg_k: int = NDCG_K) -> bool:
    a = scored_payload(run_benchmark(ndcg_k=ndcg_k))
    b = scored_payload(run_benchmark(ndcg_k=ndcg_k))
    return a == b


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GEDS deterministic benchmark harness")
    parser.add_argument("--out", type=Path, default=None, help="output directory (default reports/benchmark/)")
    parser.add_argument("--ndcg-k", type=int, default=NDCG_K, help=f"NDCG cutoff k (default {NDCG_K})")
    parser.add_argument("--check", action="store_true", help="run twice and assert identical scores; no files written")
    parser.add_argument("--quiet", action="store_true", help="suppress the stdout leaderboard")
    args = parser.parse_args(argv)

    # Windows consoles may use a legacy codepage (cp1251) that can't encode the
    # report's unicode (², ρ, τ). Reports are always written UTF-8; only stdout
    # needs hardening so the harness never crashes on its own console output.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

    if args.check:
        ok = _check_determinism(args.ndcg_k)
        print("DETERMINISM CHECK:", "PASS — two runs produced identical scores" if ok
              else "FAIL — scores differ between runs")
        return 0 if ok else 1

    report = run_benchmark(ndcg_k=args.ndcg_k)
    json_path, md_path = write_report(report, args.out)
    if not args.quiet:
        print(format_markdown(report))
        print(f"\nWrote: {json_path}\nWrote: {md_path}")
    return 0


__all__ = [
    "ModelScore",
    "BenchmarkReport",
    "BENCHMARK_CONFIG",
    "NDCG_K",
    "run_benchmark",
    "save_benchmark",
    "write_report",
    "format_markdown",
    "scored_payload",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
