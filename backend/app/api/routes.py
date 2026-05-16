"""REST routes."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..core import scenarios as scenario_registry
from ..core.advisor import analyze as advise
from ..core.backtest import run_track_record, track_record_to_dict
from ..core.centrality import full_centrality_report
from ..core.graph import CompiledGraph
from ..core.monte_carlo import run_monte_carlo
from ..core.propagation import PropagationEngine
from ..core.types import (
    AdvisorResult,
    CentralityResult,
    GraphSnapshot,
    MonteCarloResult,
    Scenario,
    ShockSpec,
    SimulationResult,
)
from ..core.validation import run_all as validate_all
from ..services.event_logger import log_event
from ..services.grok import GrokPolicyAdvisor
from ..services.news import (
    NodeMatcher,
    apply_overlay_to_graph,
    overlay_from_events,
    parse_headline,
    run_pipeline,
    stub_headlines,
)

router = APIRouter()

_PROVENANCE_PATH = Path(__file__).parent.parent.parent / "data" / "provenance.json"


def _graph(req: Request) -> CompiledGraph:
    return req.app.state.compiled_graph


def _snapshot(req: Request) -> GraphSnapshot:
    return req.app.state.graph_snapshot


# ────────────────────────── graph ──────────────────────────


@router.get("/graph", tags=["graph"])
def get_graph(req: Request) -> GraphSnapshot:
    return _snapshot(req)


@router.get("/graph/stats", tags=["graph"])
def graph_stats(req: Request) -> dict:
    g = _graph(req)
    snapshot = _snapshot(req)
    return {
        "version": snapshot.version,
        "node_count": g.n,
        "edge_count": len(snapshot.edges),
        "countries": sorted({n.country for n in snapshot.nodes if n.country}),
        "industries": sorted({n.industry.value for n in snapshot.nodes if n.industry}),
        "chokepoints": [n.id for n in snapshot.nodes if n.kind.value == "chokepoint"],
        "max_centrality": max(snapshot.centrality.values(), default=0.0),
    }


# ────────────────────────── scenarios ──────────────────────────


class ShockInput(BaseModel):
    target_node_id: str
    magnitude: float = Field(..., ge=0, le=1)
    start_week: int = Field(0, ge=0)
    duration_weeks: int = Field(8, ge=1)
    decay_curve: str = "step"


class CustomScenarioRequest(BaseModel):
    name: str = "Custom scenario"
    horizon_weeks: int = Field(52, ge=1, le=520)
    shocks: list[ShockInput]


@router.get("/scenarios", tags=["scenarios"])
def list_scenarios() -> list[Scenario]:
    return scenario_registry.list_scenarios()


@router.get("/scenarios/{scenario_id}", tags=["scenarios"])
def get_scenario(scenario_id: str) -> Scenario:
    try:
        return scenario_registry.by_id(scenario_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ────────────────────────── simulation ──────────────────────────


class SimulationRequest(BaseModel):
    scenario_id: str | None = None
    custom: CustomScenarioRequest | None = None


@router.post("/simulate", tags=["simulation"], response_model=SimulationResult)
def simulate(payload: SimulationRequest, req: Request) -> SimulationResult:
    """Synchronously run a simulation and return the full frame trajectory.

    If a news overlay is active (set via /news/apply), its vulnerability and
    D_eff deltas are applied to the compiled graph before this run.
    """
    scenario = _resolve_scenario(payload)
    base_graph = _graph(req)
    overlay = getattr(req.app.state, "news_overlay", None)
    graph = apply_overlay_to_graph(base_graph, overlay) if overlay else base_graph
    engine = PropagationEngine(graph, scenario.config)
    return engine.run(scenario)


def _resolve_scenario(payload: SimulationRequest) -> Scenario:
    if payload.scenario_id:
        try:
            return scenario_registry.by_id(payload.scenario_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
    if payload.custom:
        shocks = [ShockSpec(**s.model_dump()) for s in payload.custom.shocks]
        return Scenario(
            id="custom",
            name=payload.custom.name,
            horizon_weeks=payload.custom.horizon_weeks,
            shocks=shocks,
        )
    raise HTTPException(status_code=400, detail="Provide either scenario_id or custom")


# ────────────────────────── policy advisor ──────────────────────────


class PolicyRequest(BaseModel):
    scenario_id: str | None = None
    custom: CustomScenarioRequest | None = None


@router.post("/policy", tags=["policy"], response_model=AdvisorResult)
def policy_advisor(payload: PolicyRequest, req: Request) -> AdvisorResult:
    """Run a simulation and return AI-generated policy recommendations."""

    # Reuse the same scenario resolution logic.
    sim_payload = SimulationRequest(
        scenario_id=payload.scenario_id,
        custom=payload.custom,
    )
    scenario = _resolve_scenario(sim_payload)
    g = _graph(req)
    engine = PropagationEngine(g, scenario.config)
    result = engine.run(scenario)
    return advise(result, g)


# ────────────────────────── data provenance ──────────────────────────


@router.get("/data/provenance", tags=["data"])
def data_provenance() -> dict:
    """Return the full data provenance manifest for all graph parameters."""
    if not _PROVENANCE_PATH.exists():
        raise HTTPException(status_code=404, detail="provenance.json not found")
    return json.loads(_PROVENANCE_PATH.read_text(encoding="utf-8"))


@router.get("/data/sources", tags=["data"])
def data_sources() -> list[dict]:
    """Return a summary list of data sources (id, source name, period, quality)."""
    if not _PROVENANCE_PATH.exists():
        raise HTTPException(status_code=404, detail="provenance.json not found")
    prov = json.loads(_PROVENANCE_PATH.read_text(encoding="utf-8"))
    return [
        {
            "id": s["id"],
            "source": s["source"],
            "period": s.get("period", ""),
            "variables_derived": s.get("variables_derived", []),
            "quality": s.get("quality", "real"),
        }
        for s in prov.get("sources", [])
    ]


# ────────────────────────── monte carlo ──────────────────────────


class MonteCarloRequest(BaseModel):
    scenario_id: str | None = None
    custom: CustomScenarioRequest | None = None
    n_iterations: int = Field(1000, ge=10, le=5000)
    param_noise_pct: float = Field(15.0, ge=1.0, le=50.0)
    seed: int = Field(42, ge=0)
    n_workers: int = Field(4, ge=1, le=16)


@router.post("/monte-carlo", tags=["simulation"], response_model=MonteCarloResult)
def monte_carlo(payload: MonteCarloRequest, req: Request) -> MonteCarloResult:
    """Run N Monte Carlo iterations with perturbed graph parameters.

    Returns p5/p50/p95 confidence bands for weekly GDP loss, peak CSI, and
    total output loss.  Default: 1,000 iterations, ±15% dependency-weight noise.
    Typical wall time: 3–8 s on a 4-core machine.
    """
    sim_payload = SimulationRequest(
        scenario_id=payload.scenario_id,
        custom=payload.custom,
    )
    scenario = _resolve_scenario(sim_payload)
    return run_monte_carlo(
        scenario=scenario,
        graph=_graph(req),
        n_iterations=payload.n_iterations,
        param_noise_pct=payload.param_noise_pct,
        seed=payload.seed,
        n_workers=payload.n_workers,
    )


# ────────────────────────── centrality ──────────────────────────


@router.get("/centrality", tags=["data"], response_model=CentralityResult)
def node_centrality(req: Request) -> CentralityResult:
    """Return the Cascading Impact Score and supply-chain metrics for every node.

    CIS is a trade-weighted PageRank (damping=0.85, 150 iterations) where edge
    weight = UN Comtrade flow_value_usd × import penetration ratio.  Also returns
    upstream_criticality (supplier importance), downstream_exposure (economic
    throughput at risk), and chokepoint_exposure (fraction of supply through CPs).
    """
    return full_centrality_report(_snapshot(req))


# ────────────────────────── narrative (Grok) ──────────────────────────


class NarrativeRequest(BaseModel):
    scenario_id: str | None = None
    custom: CustomScenarioRequest | None = None
    force_refresh: bool = False
    lang: str = Field("en", pattern="^(en|ru)$")


@router.post("/narrative", tags=["narrative"])
def narrative(payload: NarrativeRequest, req: Request) -> dict:
    """Run the scenario (with news overlay applied if active) and ask Grok for
    a structured policy narrative in the requested language."""
    sim_payload = SimulationRequest(scenario_id=payload.scenario_id, custom=payload.custom)
    scenario = _resolve_scenario(sim_payload)
    base_graph = _graph(req)
    overlay = getattr(req.app.state, "news_overlay", None)
    graph = apply_overlay_to_graph(base_graph, overlay) if overlay else base_graph

    engine = PropagationEngine(graph, scenario.config)
    result = engine.run(scenario)
    summary_dict = result.summary.model_dump(mode="json")

    advisor = GrokPolicyAdvisor()
    narrative = advisor.analyze(
        scenario_id=scenario.id,
        sim_summary=summary_dict,
        force_refresh=payload.force_refresh,
        lang=payload.lang,
    )
    return {
        "scenario_id": scenario.id,
        "lang": payload.lang,
        "model": narrative.model,
        "cached": narrative.cached,
        "latency_ms": narrative.latency_ms,
        "confidence": narrative.confidence,
        "executive_summary": narrative.executive_summary,
        "cascade_mechanism": narrative.cascade_mechanism,
        "immediate_risks": narrative.immediate_risks,
        "structural_vulnerabilities": narrative.structural_vulnerabilities,
        "policy_recommendations": narrative.policy_recommendations,
        "overlay_active": bool(overlay and overlay.is_active()),
        "overlay_node_count": len(overlay.deltas) if overlay and overlay.is_active() else 0,
    }


# ────────────────────────── news pipeline ──────────────────────────


@router.get("/news/recent", tags=["news"])
def news_recent(
    req: Request,
    hours_back: int = 24,
    use_stub: bool = False,
    lang: str = "en",
) -> dict:
    """Pull recent news, NER, fuzzy-match to graph nodes, propose parameter deltas.

    Stub mode (`use_stub=true` or no API keys) returns synthetic bilingual
    headlines so the pipeline can be demoed offline.  Pass `lang=ru` for Russian.
    """
    snap = _snapshot(req)
    node_ids = [n.id for n in snap.nodes]
    node_names = [n.name for n in snap.nodes]

    if use_stub:
        matcher = NodeMatcher(node_ids, node_names)
        parsed = [parse_headline(h, matcher) for h in stub_headlines(lang=lang)]
    else:
        parsed = run_pipeline(node_ids=node_ids, node_names=node_names, hours_back=hours_back)

    for ev in parsed:
        try:
            log_event(ev)
        except Exception:
            pass

    return {
        "n_events": len(parsed),
        "lang": lang,
        "events": [
            {
                "headline": {
                    "title": ev.headline.title,
                    "description": ev.headline.description,
                    "source": ev.headline.source,
                    "url": ev.headline.url,
                    "published_at": ev.headline.published_at,
                },
                "event_type": ev.event_type,
                "matched_nodes": ev.matched_nodes,
                "entities": ev.entities[:8],
                "deltas": [
                    {
                        "node_id": d.node_id,
                        "vulnerability_delta": round(d.vulnerability_delta, 3),
                        "d_eff_multiplier": round(d.d_eff_multiplier, 3),
                        "decay_weeks": d.decay_weeks,
                        "confidence": round(d.confidence, 3),
                    }
                    for d in ev.deltas
                ],
            }
            for ev in parsed
        ],
    }


# ────────────────────────── news overlay management ──────────────────────────


class NewsOverlayApplyRequest(BaseModel):
    """Apply the current parsed events (or stub) as an active overlay on the graph.

    Once applied, subsequent /simulate and /narrative calls will use the
    overlay-adjusted vulnerability and D_eff until cleared or expired.
    """
    use_stub: bool = False
    hours_back: int = 24
    decay_hours: int = Field(168, ge=1, le=720)
    confidence_floor: float = Field(0.5, ge=0.0, le=1.0)
    lang: str = Field("en", pattern="^(en|ru)$")


@router.post("/news/apply", tags=["news"])
def news_apply(payload: NewsOverlayApplyRequest, req: Request) -> dict:
    """Refetch headlines, build an overlay, store it on app.state."""
    snap = _snapshot(req)
    node_ids = [n.id for n in snap.nodes]
    node_names = [n.name for n in snap.nodes]

    if payload.use_stub:
        matcher = NodeMatcher(node_ids, node_names)
        parsed = [parse_headline(h, matcher) for h in stub_headlines(lang=payload.lang)]
    else:
        parsed = run_pipeline(
            node_ids=node_ids, node_names=node_names, hours_back=payload.hours_back,
        )

    overlay = overlay_from_events(
        parsed,
        decay_hours=payload.decay_hours,
        confidence_floor=payload.confidence_floor,
    )
    req.app.state.news_overlay = overlay

    return {
        "applied_at": overlay.applied_at,
        "active_until": overlay.active_until,
        "n_nodes_affected": len(overlay.deltas),
        "deltas": overlay.deltas,
    }


@router.get("/news/overlay", tags=["news"])
def news_overlay(req: Request) -> dict:
    overlay = getattr(req.app.state, "news_overlay", None)
    if overlay is None:
        return {"active": False, "deltas": {}, "n_nodes_affected": 0}
    return {
        "active": overlay.is_active(),
        "applied_at": overlay.applied_at,
        "active_until": overlay.active_until,
        "n_nodes_affected": len(overlay.deltas),
        "deltas": overlay.deltas,
    }


@router.delete("/news/overlay", tags=["news"])
def news_overlay_clear(req: Request) -> dict:
    req.app.state.news_overlay = None
    return {"cleared": True}


# ────────────────────────── backtest / track record ──────────────────────────


@router.get("/backtest", tags=["validation"])
def backtest() -> dict:
    """Frozen-parameter historical replay.  Loads calibrated params if available."""
    tr = run_track_record()
    return track_record_to_dict(tr)


# ────────────────────────── validation ──────────────────────────


@router.get("/validate", tags=["validation"])
def validate() -> dict:
    results = validate_all()
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.pass_),
        "failed": sum(1 for r in results if not r.pass_),
        "events": [r.__dict__ for r in results],
    }
