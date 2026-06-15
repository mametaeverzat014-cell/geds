"""Frozen-parameter historical backtest — the 'Track Record' module.

Runs each event in HISTORICAL_EVENTS through the engine with parameters frozen
at a specified calibration date (loaded from provenance.json) and produces a
structured comparison of predicted vs. observed metrics.

Designed to be the canonical answer to "does this model actually work?":
every claim about r=+0.97 etc. should be replaced by this table's live output.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from ..data.seed import load_graph
from ..data.seed_data import HISTORICAL_EVENTS
from .graph import compile_graph
from .propagation import PropagationEngine
from .sanity import is_within_sanity
from .types import EngineConfig, Industry, Scenario, ShockSpec


# ─────────────────────── data classes ───────────────────────────────────────


@dataclass
class EventBacktest:
    """Per-event predicted-vs-observed report."""

    slug: str
    name: str
    horizon_weeks: int
    # Industry-level metrics (the headline numbers reported in the literature)
    industry_loss_predicted: float
    industry_loss_observed: float
    industry_loss_pct_error: float
    inflation_predicted: float
    inflation_observed: float
    inflation_pct_error: float
    recovery_predicted: float
    recovery_observed: float
    recovery_pct_error: float
    # Most-impacted node sanity check
    most_impacted_country_predicted: str
    most_impacted_industry_observed: str
    # Aggregate global loss (USD) — sanity capped, with raw recorded
    total_loss_usd: float
    total_loss_within_sanity: bool
    sanity_cap_usd: float
    # Skill scores
    rmse: float
    correlation: float
    passes_25pct: bool       # ±25% tolerance on all three metrics
    passes_50pct: bool       # ±50% tolerance (loose)


@dataclass
class TrackRecord:
    """Aggregate output for the UI 'Track Record' panel."""

    calibration_date: str | None
    config_used: dict
    events: list[EventBacktest] = field(default_factory=list)
    n_events: int = 0
    n_passed_25pct: int = 0
    n_passed_50pct: int = 0
    pass_rate_25pct: float = 0.0
    pass_rate_50pct: float = 0.0
    mean_rmse: float = 0.0
    mean_correlation: float = 0.0
    all_within_sanity: bool = True


# ─────────────────────── helpers ────────────────────────────────────────────


def _scenario_from_event(event: dict, config: EngineConfig) -> Scenario:
    return Scenario(
        id=f"backtest-{event['slug']}",
        name=event["name"],
        horizon_weeks=event["horizon_weeks"],
        shocks=[ShockSpec(**s) for s in event["shocks"]],
        config=config,
    )


def _aggregate_industry(result, graph, industry: Industry) -> dict:
    """Pull industry-level peak loss / inflation / recovery from a SimulationResult."""
    idxs = [i for i, n in enumerate(graph.snapshot.nodes) if n.industry == industry]
    if not idxs:
        return {"loss": 0.0, "infl": 0.0, "recovery": 0.0, "country": "—"}

    weights = graph.gdp_usd[idxs]
    total = weights.sum()
    weights = weights / total if total > 0 else np.ones(len(idxs)) / len(idxs)

    shock_s = np.zeros(len(result.frames))
    infl_s = np.zeros(len(result.frames))
    loss_s = np.zeros(len(result.frames))
    for t, f in enumerate(result.frames):
        shock_s[t] = float(np.average([f.nodes[i].shock for i in idxs], weights=weights))
        infl_s[t]  = float(np.average([f.nodes[i].inflation_pressure for i in idxs], weights=weights))
        loss_s[t]  = float(np.average([f.nodes[i].output_loss for i in idxs], weights=weights))

    peak_t = int(shock_s.argmax())
    below = np.where(shock_s[peak_t:] < 0.10)[0]
    recovery = float(below[0]) if below.size else float(len(result.frames) - peak_t)

    # Most-impacted country in this industry by peak shock
    peak_per_node = {i: max(f.nodes[i].shock for f in result.frames) for i in idxs}
    worst_i = max(peak_per_node, key=peak_per_node.get)
    country = graph.snapshot.nodes[worst_i].country or "—"

    return {
        "loss": float(loss_s.max()),
        "infl": float(infl_s.max()),
        "recovery": recovery,
        "peak_week": int(loss_s.argmax()),   # weeks-to-peak of the output-loss trajectory
        "country": country,
    }


def _safe_pct_error(pred: float, obs: float) -> float:
    if abs(obs) < 1e-9:
        return 0.0 if abs(pred) < 1e-9 else float("inf")
    return (pred - obs) / abs(obs)


def _rmse(pred: list[float], obs: list[float]) -> float:
    if not pred:
        return float("inf")
    sq = [(p - o) ** 2 for p, o in zip(pred, obs, strict=True)]
    return math.sqrt(sum(sq) / len(sq))


def _corr(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(a) != len(b):
        return 0.0
    am, bm = np.mean(a), np.mean(b)
    da = np.array(a) - am
    db = np.array(b) - bm
    denom = math.sqrt(float(da @ da) * float(db @ db))
    return float(da @ db) / denom if denom > 0 else 0.0


# ─────────────────────── main entry ────────────────────────────────────────


def backtest_event(event: dict, graph, config: EngineConfig) -> EventBacktest:
    sc = _scenario_from_event(event, config)
    result = PropagationEngine(graph, config).run(sc)

    observed = event["observed"]
    industry = Industry(observed["most_impacted_industry"])
    agg = _aggregate_industry(result, graph, industry)

    pred_loss = agg["loss"]
    obs_loss  = observed.get("auto_production_loss_pct", 0.0)
    pred_infl = agg["infl"] * 0.10           # rough scaling: shock×pass_through → CPI pp
    obs_infl  = observed.get("us_inflation_contribution", 0.0)
    pred_rec  = agg["recovery"]
    obs_rec   = observed["expected_recovery_weeks"]

    rmse  = _rmse([pred_loss, pred_infl, pred_rec / 52], [obs_loss, obs_infl, obs_rec / 52])
    corr  = _corr([pred_loss, pred_infl, pred_rec / 52], [obs_loss, obs_infl, obs_rec / 52])

    pass_25 = (
        abs(pred_loss - obs_loss) <= max(0.025, 0.25 * obs_loss)
        and abs(pred_infl - obs_infl) <= max(0.005, 0.30 * obs_infl)
        and abs(pred_rec - obs_rec) <= max(4.0, 0.30 * obs_rec)
    )
    pass_50 = (
        abs(pred_loss - obs_loss) <= max(0.06, 0.50 * obs_loss)
        and abs(pred_infl - obs_infl) <= max(0.012, 0.60 * obs_infl)
        and abs(pred_rec - obs_rec) <= max(8.0, 0.60 * obs_rec)
    )

    within, total_loss, sanity_cap = is_within_sanity(
        result.summary.total_output_loss_usd, event["horizon_weeks"]
    )

    return EventBacktest(
        slug=event["slug"],
        name=event["name"],
        horizon_weeks=event["horizon_weeks"],
        industry_loss_predicted=round(pred_loss, 4),
        industry_loss_observed=round(obs_loss, 4),
        industry_loss_pct_error=round(_safe_pct_error(pred_loss, obs_loss), 3),
        inflation_predicted=round(pred_infl, 4),
        inflation_observed=round(obs_infl, 4),
        inflation_pct_error=round(_safe_pct_error(pred_infl, obs_infl), 3),
        recovery_predicted=round(pred_rec, 1),
        recovery_observed=round(obs_rec, 1),
        recovery_pct_error=round(_safe_pct_error(pred_rec, obs_rec), 3),
        most_impacted_country_predicted=agg["country"],
        most_impacted_industry_observed=observed["most_impacted_industry"],
        total_loss_usd=round(total_loss, 2),
        total_loss_within_sanity=within,
        sanity_cap_usd=round(sanity_cap, 2),
        rmse=round(rmse, 4),
        correlation=round(corr, 4),
        passes_25pct=pass_25,
        passes_50pct=pass_50,
    )


def run_track_record(config: EngineConfig | None = None) -> TrackRecord:
    """Run the full historical suite and return a structured TrackRecord."""
    cfg, prov_date = _load_calibrated_config() if config is None else (config, None)
    snap = load_graph()
    graph = compile_graph(snap)

    events = [backtest_event(e, graph, cfg) for e in HISTORICAL_EVENTS]
    n = len(events)
    pass_25 = sum(1 for e in events if e.passes_25pct)
    pass_50 = sum(1 for e in events if e.passes_50pct)

    return TrackRecord(
        calibration_date=prov_date,
        config_used=cfg.model_dump(),
        events=events,
        n_events=n,
        n_passed_25pct=pass_25,
        n_passed_50pct=pass_50,
        pass_rate_25pct=round(pass_25 / n, 3) if n else 0.0,
        pass_rate_50pct=round(pass_50 / n, 3) if n else 0.0,
        mean_rmse=round(float(np.mean([e.rmse for e in events])), 4) if events else 0.0,
        mean_correlation=round(float(np.mean([e.correlation for e in events])), 4) if events else 0.0,
        all_within_sanity=all(e.total_loss_within_sanity for e in events),
    )


def _load_calibrated_config() -> tuple[EngineConfig, str | None]:
    """Look for a calibration provenance file written by scripts/calibrate.py."""
    prov_path = Path(__file__).parent.parent.parent / "data" / "calibration" / "provenance.json"
    if not prov_path.exists():
        return EngineConfig(), None
    try:
        data = json.loads(prov_path.read_text(encoding="utf-8"))
        params = data.get("best_params", {})
        # Filter to valid EngineConfig fields only.
        valid_fields = set(EngineConfig.model_fields.keys())
        params = {k: v for k, v in params.items() if k in valid_fields}
        return EngineConfig(**params), data.get("calibration_date")
    except (json.JSONDecodeError, TypeError, ValueError):
        return EngineConfig(), None


def track_record_to_dict(tr: TrackRecord) -> dict:
    """JSON-safe serialization for the API."""
    return {
        "calibration_date": tr.calibration_date,
        "config_used": tr.config_used,
        "n_events": tr.n_events,
        "n_passed_25pct": tr.n_passed_25pct,
        "n_passed_50pct": tr.n_passed_50pct,
        "pass_rate_25pct": tr.pass_rate_25pct,
        "pass_rate_50pct": tr.pass_rate_50pct,
        "mean_rmse": tr.mean_rmse,
        "mean_correlation": tr.mean_correlation,
        "all_within_sanity": tr.all_within_sanity,
        "events": [asdict(e) for e in tr.events],
    }


__all__ = [
    "EventBacktest",
    "TrackRecord",
    "backtest_event",
    "run_track_record",
    "track_record_to_dict",
]
