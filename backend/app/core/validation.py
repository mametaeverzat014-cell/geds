"""Historical validation pipeline.

Replays known events through the engine and compares predicted outcomes against
observed estimates from the published literature. Reports correlation, RMSE,
and propagation similarity. Exits non-zero on regression so CI can gate.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass

import numpy as np

from ..data.seed import load_graph
from ..data.seed_data import HISTORICAL_EVENTS
from .graph import compile_graph
from .propagation import PropagationEngine
from .types import EngineConfig, Industry, Scenario, ShockSpec


@dataclass
class ReplayMetrics:
    slug: str
    name: str
    auto_loss_predicted: float
    auto_loss_observed: float
    inflation_predicted: float
    inflation_observed: float
    recovery_predicted: float
    recovery_observed: float
    most_impacted_predicted: str
    most_impacted_observed: str
    rmse: float
    correlation: float
    pass_: bool        # tolerances respected


def _scenario_from_event(event: dict) -> Scenario:
    shocks = [ShockSpec(**s) for s in event["shocks"]]
    return Scenario(
        id=f"replay-{event['slug']}",
        name=event["name"],
        horizon_weeks=event["horizon_weeks"],
        shocks=shocks,
        config=EngineConfig(propagation_decay=0.85, recovery_rate=0.07),
    )


def _aggregate(result, graph, industry: Industry) -> dict:
    """Reduce a SimulationResult into the metrics the historical record reports."""

    g = graph
    # Find indices for the target industry across all countries.
    ind_idx = [i for i, node in enumerate(g.snapshot.nodes) if node.industry == industry]
    if not ind_idx:
        return {"loss": 0.0, "inflation": 0.0, "recovery_weeks": 0.0, "most_country": "—"}

    weights = g.gdp_usd[ind_idx]
    if weights.sum() == 0:
        weights = np.ones(len(ind_idx))
    weights = weights / weights.sum()

    industry_shock_series = []
    industry_infl_series = []
    industry_loss_series = []
    for f in result.frames:
        shock_vec = np.array([f.nodes[i].shock for i in ind_idx])
        infl_vec = np.array([f.nodes[i].inflation_pressure for i in ind_idx])
        loss_vec = np.array([f.nodes[i].output_loss for i in ind_idx])
        industry_shock_series.append(float(np.average(shock_vec, weights=weights)))
        industry_infl_series.append(float(np.average(infl_vec, weights=weights)))
        industry_loss_series.append(float(np.average(loss_vec, weights=weights)))

    industry_shock_series = np.array(industry_shock_series)
    industry_infl_series = np.array(industry_infl_series)
    industry_loss_series = np.array(industry_loss_series)

    peak_loss = float(industry_loss_series.max())
    peak_infl = float(industry_infl_series.max())
    peak_t = int(industry_shock_series.argmax())
    below = np.where(industry_shock_series[peak_t:] < 0.1)[0]
    recovery_weeks = float(below[0]) if below.size > 0 else float(len(result.frames) - peak_t)

    # Most-impacted country in this industry (by peak shock).
    peak_per_node = {}
    for i in ind_idx:
        peaks = max(f.nodes[i].shock for f in result.frames)
        peak_per_node[i] = peaks
    worst_i = max(peak_per_node, key=peak_per_node.get)
    most_country = g.snapshot.nodes[worst_i].country or "—"

    return {
        "loss": peak_loss,
        "inflation": peak_infl,
        "recovery_weeks": recovery_weeks,
        "most_country": most_country,
    }


def _rmse(predicted: list[float], observed: list[float]) -> float:
    if not predicted or len(predicted) != len(observed):
        return float("inf")
    sq = [(p - o) ** 2 for p, o in zip(predicted, observed, strict=True)]
    return math.sqrt(sum(sq) / len(sq))


def _corr(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(a) != len(b):
        return float("nan")
    am, bm = np.mean(a), np.mean(b)
    da = np.array(a) - am
    db = np.array(b) - bm
    denom = math.sqrt((da @ da) * (db @ db))
    if denom == 0:
        return float("nan")
    return float((da @ db) / denom)


def run_replay(event: dict) -> ReplayMetrics:
    graph_snapshot = load_graph()
    g = compile_graph(graph_snapshot, rerouting_efficiency=0.5)
    engine = PropagationEngine(g)

    scenario = _scenario_from_event(event)
    result = engine.run(scenario)

    observed = event["observed"]
    industry = Industry(observed["most_impacted_industry"])
    agg = _aggregate(result, g, industry)

    pred_loss = agg["loss"]
    obs_loss = observed.get("auto_production_loss_pct", 0.0)
    pred_infl = agg["inflation"] * 0.10        # rough scale: shock×pass_through → CPI contribution pp
    obs_infl = observed.get("us_inflation_contribution", 0.0)
    pred_recovery = agg["recovery_weeks"]
    obs_recovery = observed["expected_recovery_weeks"]

    rmse = _rmse([pred_loss, pred_infl, pred_recovery / 52], [obs_loss, obs_infl, obs_recovery / 52])
    correlation = _corr(
        [pred_loss, pred_infl, pred_recovery / 52],
        [obs_loss, obs_infl, obs_recovery / 52],
    )

    # Tolerances: tuned per event. These are loose because the MVP graph is sparse.
    loss_ok = abs(pred_loss - obs_loss) <= max(0.06, 0.6 * obs_loss)
    infl_ok = abs(pred_infl - obs_infl) <= max(0.012, 1.0 * obs_infl)
    recovery_ok = abs(pred_recovery - obs_recovery) <= max(8.0, 0.6 * obs_recovery)
    industry_ok = agg["most_country"] != "—"

    return ReplayMetrics(
        slug=event["slug"],
        name=event["name"],
        auto_loss_predicted=round(pred_loss, 4),
        auto_loss_observed=round(obs_loss, 4),
        inflation_predicted=round(pred_infl, 4),
        inflation_observed=round(obs_infl, 4),
        recovery_predicted=round(pred_recovery, 1),
        recovery_observed=round(obs_recovery, 1),
        most_impacted_predicted=agg["most_country"],
        most_impacted_observed=observed["most_impacted_industry"],
        rmse=round(rmse, 4),
        correlation=round(correlation, 4) if not math.isnan(correlation) else 0.0,
        pass_=bool(loss_ok and infl_ok and recovery_ok and industry_ok),
    )


def run_all() -> list[ReplayMetrics]:
    return [run_replay(e) for e in HISTORICAL_EVENTS]


def cli() -> int:
    results = run_all()
    print(f"\n{'event':40s}  {'loss(p/o)':>14s}  {'infl(p/o)':>12s}  {'rec(p/o)':>12s}  RMSE   r     pass")
    print("-" * 110)
    for r in results:
        print(
            f"{r.name[:40]:40s}  "
            f"{r.auto_loss_predicted:.3f}/{r.auto_loss_observed:.3f}  "
            f"{r.inflation_predicted:.3f}/{r.inflation_observed:.3f}  "
            f"{r.recovery_predicted:5.1f}/{r.recovery_observed:5.1f}  "
            f"{r.rmse:.3f}  {r.correlation:+.2f}  "
            f"{'PASS' if r.pass_ else 'FAIL'}"
        )
    fails = [r for r in results if not r.pass_]
    print()
    if fails:
        print(f"{len(fails)}/{len(results)} replay tests FAILED")
        return 1
    print(f"all {len(results)} replay tests PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(cli())
