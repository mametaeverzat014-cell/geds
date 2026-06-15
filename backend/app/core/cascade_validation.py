"""Multi-output cascade-shape validation (Task #3).

The single-scalar backtest (core/backtest.py) scores only peak magnitude. This
module scores the engine against the *shape* of each cascade — three dimensions
per event:

    magnitude            peak output loss at the directly-shocked sector
    weeks_to_peak        how long until that trough
    recovery_weeks       how long until ~90% recovery

Observed values come from the standardized, primary-source research:
  - magnitude   : data/csv/standardized_targets.csv  (Batch 12)
  - timing      : data/csv/cascade_timing.csv         (Batch 13)

Each dimension is scored only where a clean observed value exists, and magnitude
is scored only for `direct` source-sector-output events (for chokepoint events
the published number is throughput, not output loss — a different quantity, see
Batch 12). The harness also tests the qualitative structural prediction from the
research review: chokepoint disruptions recover faster than production shocks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..data.csv_loader import (
    load_cascade_timing_csv,
    load_standardized_targets_csv,
)
from ..data.seed import load_graph
from .backtest import _scenario_from_event
from .graph import compile_graph
from .propagation import PropagationEngine
from .types import EngineConfig


@dataclass
class DimScore:
    name: str
    predicted: float
    observed: float
    abs_error: float


@dataclass
class CascadeEventResult:
    slug: str
    is_chokepoint: bool
    predicted_recovery_weeks: float
    observed_recovery_weeks: float | None
    dims: list[DimScore]


@dataclass
class CascadeReport:
    events: list[CascadeEventResult]
    mae_by_dim: dict[str, float]
    spearman_by_dim: dict[str, float]
    n_by_dim: dict[str, int]
    # structural separation: do chokepoints recover faster than production shocks?
    chokepoint_recovery_observed: float
    production_recovery_observed: float
    chokepoint_recovery_predicted: float
    production_recovery_predicted: float
    structural_separation_observed: bool
    structural_separation_predicted: bool


def _spearman(pred: list[float], obs: list[float]) -> float:
    """Rank correlation (Pearson on ranks). 0.0 when n < 2."""
    if len(pred) < 2:
        return 0.0
    pr = np.argsort(np.argsort(pred)).astype(float)
    orr = np.argsort(np.argsort(obs)).astype(float)
    pm, om = pr.mean(), orr.mean()
    dp, do = pr - pm, orr - om
    denom = float(np.sqrt((dp @ dp) * (do @ do)))
    return float(dp @ do) / denom if denom > 0 else 0.0


def _node_shape(sim, node_idx: int) -> tuple[float, int, float]:
    """(peak_loss, weeks_to_peak, recovery_week) of one node's output-loss trajectory.

    recovery_week is weeks-from-start until output loss falls back to <=10% of the
    peak (matching the observed 'recovery_to_90%' definition); the horizon length
    if it never recovers within the simulated window.
    """
    traj = np.array([f.nodes[node_idx].output_loss for f in sim.frames], dtype=float)
    peak_week = int(traj.argmax())
    peak_loss = float(traj[peak_week])
    rec_threshold = max(0.10 * peak_loss, 0.02)
    recovered = np.where(traj[peak_week:] <= rec_threshold)[0]
    recovery_week = float(peak_week + recovered[0]) if recovered.size else float(len(traj))
    return peak_loss, peak_week, recovery_week


def run_cascade_validation(config: EngineConfig | None = None) -> CascadeReport:
    """Score the engine's cascade shape against standardized + timing research."""
    from ..data.seed_data import HISTORICAL_EVENTS

    cfg = config or EngineConfig()
    graph = compile_graph(load_graph())
    engine_events = {e["slug"]: e for e in HISTORICAL_EVENTS}

    timing = {t.engine_slug: t for t in load_cascade_timing_csv()}
    magnitude = {
        t.engine_slug: t
        for t in load_standardized_targets_csv()
        if t.status == "measured" and t.usability == "direct" and t.value_pct is not None
    }
    chokepoint_slugs = {
        t.engine_slug
        for t in load_standardized_targets_csv()
        if t.target_class == "chokepoint_throughput"
    }

    results: list[CascadeEventResult] = []
    for slug, ev in engine_events.items():
        tm = timing.get(slug)
        if tm is None:
            continue  # no timing research for this event

        # Read the directly-shocked NODE's trajectory (node-level), not the
        # GDP-weighted industry-global average — the standardized targets are
        # node-level (e.g. JPN:automotive), so industry-global would dilute the
        # source-country peak to near zero.
        node_id = ev["shocks"][0]["target_node_id"]
        node_idx = graph.index.get(node_id)
        if node_idx is None:
            continue

        sc = _scenario_from_event(ev, cfg)
        sim = PropagationEngine(graph, cfg).run(sc)
        peak_loss, peak_week, recovery_week = _node_shape(sim, node_idx)

        dims: list[DimScore] = []
        if slug in magnitude:
            obs_mag = magnitude[slug].value_pct
            dims.append(DimScore("magnitude", round(peak_loss, 4), obs_mag,
                                 round(abs(peak_loss - obs_mag), 4)))
        if tm.weeks_to_peak is not None:
            dims.append(DimScore("weeks_to_peak", float(peak_week),
                                 float(tm.weeks_to_peak),
                                 abs(peak_week - tm.weeks_to_peak)))
        if tm.recovery_weeks_to_90 is not None:
            dims.append(DimScore("recovery_weeks", round(recovery_week, 1),
                                 float(tm.recovery_weeks_to_90),
                                 round(abs(recovery_week - tm.recovery_weeks_to_90), 1)))

        results.append(CascadeEventResult(
            slug=slug,
            is_chokepoint=slug in chokepoint_slugs,
            predicted_recovery_weeks=round(recovery_week, 1),
            observed_recovery_weeks=(
                float(tm.recovery_weeks_to_90) if tm.recovery_weeks_to_90 is not None else None
            ),
            dims=dims,
        ))

    # ── aggregate per-dimension ──
    mae_by_dim: dict[str, float] = {}
    spearman_by_dim: dict[str, float] = {}
    n_by_dim: dict[str, int] = {}
    for dim in ("magnitude", "weeks_to_peak", "recovery_weeks"):
        pred = [d.predicted for r in results for d in r.dims if d.name == dim]
        obs = [d.observed for r in results for d in r.dims if d.name == dim]
        if pred:
            mae_by_dim[dim] = round(float(np.mean([abs(p - o) for p, o in zip(pred, obs, strict=True)])), 4)
            spearman_by_dim[dim] = round(_spearman(pred, obs), 4)
            n_by_dim[dim] = len(pred)

    # ── structural separation: chokepoint vs production recovery ──
    cp_obs = [r.observed_recovery_weeks for r in results
              if r.is_chokepoint and r.observed_recovery_weeks is not None]
    pr_obs = [r.observed_recovery_weeks for r in results
              if not r.is_chokepoint and r.observed_recovery_weeks is not None]
    cp_pred = [r.predicted_recovery_weeks for r in results if r.is_chokepoint]
    pr_pred = [r.predicted_recovery_weeks for r in results if not r.is_chokepoint]

    cp_obs_m = float(np.mean(cp_obs)) if cp_obs else float("nan")
    pr_obs_m = float(np.mean(pr_obs)) if pr_obs else float("nan")
    cp_pred_m = float(np.mean(cp_pred)) if cp_pred else float("nan")
    pr_pred_m = float(np.mean(pr_pred)) if pr_pred else float("nan")

    return CascadeReport(
        events=results,
        mae_by_dim=mae_by_dim,
        spearman_by_dim=spearman_by_dim,
        n_by_dim=n_by_dim,
        chokepoint_recovery_observed=round(cp_obs_m, 1),
        production_recovery_observed=round(pr_obs_m, 1),
        chokepoint_recovery_predicted=round(cp_pred_m, 1),
        production_recovery_predicted=round(pr_pred_m, 1),
        structural_separation_observed=bool(cp_obs and pr_obs and cp_obs_m < pr_obs_m),
        structural_separation_predicted=bool(cp_pred and pr_pred and cp_pred_m < pr_pred_m),
    )
