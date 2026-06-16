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
    load_cascade_spatial_csv,
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


# ─────────────────── spatial axis: did the cascade reach the right nodes? ───


@dataclass
class SpatialEventResult:
    slug: str
    observed_nodes: int          # unique downstream nodes that map to the graph
    reached: int                 # of those, how many the engine's cascade reaches
    out_of_graph: int            # observed nodes the 12-country graph cannot represent


@dataclass
class SpatialReport:
    events: list[SpatialEventResult]
    reach_threshold: float
    coverage: float              # in-graph observed rows / all observed rows
    spatial_recall: float        # reached / in-graph observed nodes (pooled)
    onset_spearman: float        # observed vs predicted onset week, over reached nodes
    onset_mae_weeks: float
    n_reached: int
    n_out_of_graph: int


def run_spatial_validation(config: EngineConfig | None = None, reach_threshold: float = 0.01) -> SpatialReport:
    """Does the engine's cascade reach the nodes history actually hit, and in order?

    For each event with a documented downstream cascade, map the observed
    affected nodes to graph nodes, run the engine, and check (a) reach — does the
    node's output loss cross `reach_threshold` within the horizon — and (b) timing
    — does the engine's onset-week ordering track the observed ordering.
    """
    from ..data.seed_data import HISTORICAL_EVENTS

    cfg = config or EngineConfig()
    graph = compile_graph(load_graph())
    engine_events = {e["slug"]: e for e in HISTORICAL_EVENTS}
    perp_to_engine = {t.perplexity_slug: t.engine_slug for t in load_standardized_targets_csv()}

    # group spatial rows: (engine_slug, node_id) -> earliest observed onset
    observed: dict[str, dict[str, int]] = {}
    out_of_graph: dict[str, int] = {}
    total_rows = in_graph_rows = 0
    for r in load_cascade_spatial_csv():
        total_rows += 1
        eng = perp_to_engine.get(r.slug, r.slug)
        nid = r.node_id()
        if nid not in graph.index:
            out_of_graph[eng] = out_of_graph.get(eng, 0) + 1
            continue
        in_graph_rows += 1
        onset = r.onset_week if r.onset_week is not None else 0
        bucket = observed.setdefault(eng, {})
        bucket[nid] = min(bucket.get(nid, onset), onset)

    events: list[SpatialEventResult] = []
    obs_onsets: list[float] = []
    pred_onsets: list[float] = []
    total_reached = 0
    total_in_graph_nodes = 0

    for slug, nodes in observed.items():
        ev = engine_events.get(slug)
        if ev is None:
            continue
        sim = PropagationEngine(graph, cfg).run(_scenario_from_event(ev, cfg))
        reached = 0
        for nid, obs_onset in nodes.items():
            idx = graph.index[nid]
            traj = np.array([f.nodes[idx].output_loss for f in sim.frames], dtype=float)
            crossings = np.where(traj >= reach_threshold)[0]
            if crossings.size:
                reached += 1
                obs_onsets.append(float(obs_onset))
                pred_onsets.append(float(crossings[0]))
        total_reached += reached
        total_in_graph_nodes += len(nodes)
        events.append(SpatialEventResult(
            slug=slug,
            observed_nodes=len(nodes),
            reached=reached,
            out_of_graph=out_of_graph.get(slug, 0),
        ))

    onset_mae = (
        float(np.mean([abs(o - p) for o, p in zip(obs_onsets, pred_onsets, strict=True)]))
        if obs_onsets else float("nan")
    )
    return SpatialReport(
        events=sorted(events, key=lambda e: e.slug),
        reach_threshold=reach_threshold,
        coverage=round(in_graph_rows / total_rows, 3) if total_rows else 0.0,
        spatial_recall=round(total_reached / total_in_graph_nodes, 3) if total_in_graph_nodes else 0.0,
        onset_spearman=round(_spearman(pred_onsets, obs_onsets), 3),
        onset_mae_weeks=round(onset_mae, 2),
        n_reached=total_reached,
        n_out_of_graph=sum(out_of_graph.values()),
    )


# ───────── does the dense ICIO v3 graph fix the reach problem? (Batch 16) ─────

# v2 sector → v3 ICIO sector. semiconductors+electronics collapse into the merged
# C26 bucket (ICIO cannot split them); chemicals/energy/agriculture have no v3 node.
_V2_TO_V3_SECTOR = {
    "semiconductors": "electronics_c26",
    "electronics": "electronics_c26",
    "automotive": "automotive",
    "consumer_goods": "consumer_goods",
    "shipping": "shipping",
    "aerospace": "aerospace",
}


def _to_v3_node(node_id: str) -> str | None:
    """Map a v2 'COUNTRY:sector' id to its v3 equivalent, or None if unrepresentable
    (chokepoints, or chemicals/energy/agriculture sectors absent from the 5-sector v3)."""
    if ":" not in node_id:
        return None
    country, sector = node_id.split(":", 1)
    v3_sector = _V2_TO_V3_SECTOR.get(sector)
    return f"{country}:{v3_sector}" if v3_sector else None


@dataclass
class SpatialRecallComparison:
    events_compared: int
    reach_threshold: float
    v2_recall: float
    v3_recall: float
    v2_reached: int
    v2_nodes: int
    v3_reached: int
    v3_nodes: int
    per_event: list[dict]                 # {slug, v2, v3} reach strings
    chokepoint_events_v2_only: list[str]  # events that can't run on v3 (no chokepoint nodes)


def _reach_count(graph, scenario, observed_nodes: dict[str, int], cfg, threshold: float) -> tuple[int, int]:
    """(# observed nodes the cascade reaches, # observed nodes representable in this graph)."""
    sim = PropagationEngine(graph, cfg).run(scenario)
    reached = representable = 0
    for nid in observed_nodes:
        idx = graph.index.get(nid)
        if idx is None:
            continue
        representable += 1
        traj = [f.nodes[idx].output_loss for f in sim.frames]
        if max(traj) >= threshold:
            reached += 1
    return reached, representable


def compare_spatial_recall(config: EngineConfig | None = None, reach_threshold: float = 0.01) -> SpatialRecallComparison:
    """Headline test of the ICIO expansion: does the dense 405-node v3 graph reach
    more of the nodes history actually hit than the sparse 36-node v2 graph?

    Compared only on production-shock events (chokepoint events shock CP:* nodes,
    which v3 has no equivalent for) so the comparison is apples-to-apples.
    """
    from ..data.expanded_graph import build_expanded_snapshot
    from ..data.seed_data import HISTORICAL_EVENTS

    cfg = config or EngineConfig()
    g2 = compile_graph(load_graph())
    g3 = compile_graph(build_expanded_snapshot())
    engine_events = {e["slug"]: e for e in HISTORICAL_EVENTS}
    perp_to_engine = {t.perplexity_slug: t.engine_slug for t in load_standardized_targets_csv()}

    observed: dict[str, dict[str, int]] = {}
    for r in load_cascade_spatial_csv():
        eng = perp_to_engine.get(r.slug, r.slug)
        onset = r.onset_week if r.onset_week is not None else 0
        bucket = observed.setdefault(eng, {})
        bucket[r.node_id()] = min(bucket.get(r.node_id(), onset), onset)

    per_event: list[dict] = []
    chokepoint_only: list[str] = []
    v2r = v2n = v3r = v3n = 0
    compared = 0

    for slug, nodes in observed.items():
        ev = engine_events.get(slug)
        if ev is None:
            continue

        # remap shocks to v3; skip the event if any shock has no v3 node (chokepoint)
        v3_shocks = []
        mappable = True
        for sh in ev["shocks"]:
            t3 = _to_v3_node(sh["target_node_id"])
            if t3 is None or t3 not in g3.index:
                mappable = False
                break
            v3_shocks.append({**sh, "target_node_id": t3})
        if not mappable:
            chokepoint_only.append(slug)
            continue

        r2, n2 = _reach_count(g2, _scenario_from_event(ev, cfg), nodes, cfg, reach_threshold)
        ev3 = {**ev, "shocks": v3_shocks}
        nodes3 = {n3id: o for nid, o in nodes.items() if (n3id := _to_v3_node(nid))}
        r3, n3 = _reach_count(g3, _scenario_from_event(ev3, cfg), nodes3, cfg, reach_threshold)

        v2r += r2
        v2n += n2
        v3r += r3
        v3n += n3
        compared += 1
        per_event.append({"slug": slug, "v2": f"{r2}/{n2}", "v3": f"{r3}/{n3}"})

    return SpatialRecallComparison(
        events_compared=compared,
        reach_threshold=reach_threshold,
        v2_recall=round(v2r / v2n, 3) if v2n else 0.0,
        v3_recall=round(v3r / v3n, 3) if v3n else 0.0,
        v2_reached=v2r, v2_nodes=v2n,
        v3_reached=v3r, v3_nodes=v3n,
        per_event=sorted(per_event, key=lambda e: e["slug"]),
        chokepoint_events_v2_only=sorted(chokepoint_only),
    )
