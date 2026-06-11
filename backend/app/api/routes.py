"""REST routes."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..core import scenarios as scenario_registry
from ..core.advisor import analyze as advise
from ..core.ablation import run_ablation_study, save_ablation
from ..core.backtest import run_track_record, track_record_to_dict
from ..core.benchmark import run_benchmark, save_benchmark
from ..core.cross_validation import loo_cross_validate_fast, save_cv
from ..core.mcmc import load_result as load_posterior
from ..core.postcalibration import loo_calibration_report
from ..core.research_metrics import (
    cascading_criticality_score, ert_summary, evaluate_metrics_against_history,
    evaluate_metrics_v2, recovery_elasticity_score, sac_summary,
    shock_absorption_capacity, systemic_fragility_index,
)
from ..core.tail_risk import compute_tail_risk, tail_risk_to_dict
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
from ..data.csv_loader import (
    load_datasets_csv, load_historical_events_csv,
    load_parameters_csv, out_of_graph_events,
)
from ..services.claude_advisor import ClaudeCrisisAdvisor
from ..services.event_logger import log_event
from ..services.grok import GrokPolicyAdvisor
from ..services.news import (
    NodeMatcher,
    apply_overlay_to_graph,
    live_keys_present,
    overlay_from_events,
    overlay_to_shocks,
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
    scenario = _with_overlay_shocks(scenario, overlay)
    engine = PropagationEngine(graph, scenario.config)
    return engine.run(scenario)


def _with_overlay_shocks(scenario: Scenario, overlay) -> Scenario:
    """Merge active-news disruptions into the scenario as extra active shocks.

    Returns a copy (never mutates the registry's cached Scenario). The engine
    takes the per-node max over shocks, so a news shock that overlaps a scenario
    shock can only strengthen it, never double-count.
    """
    extra = overlay_to_shocks(overlay) if overlay else []
    if not extra:
        return scenario
    extra_specs = [ShockSpec(**d) for d in extra]
    return scenario.model_copy(update={"shocks": list(scenario.shocks) + extra_specs})


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
    scenario = _with_overlay_shocks(scenario, overlay)

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

    # Honest live/demo selection: only run the real pipeline when a provider key
    # exists; otherwise fall back to clearly-labelled stub data instead of an
    # empty panel. `mode` tells the frontend which it got.
    want_stub = use_stub or not live_keys_present()
    if want_stub:
        matcher = NodeMatcher(node_ids, node_names)
        parsed = [parse_headline(h, matcher) for h in stub_headlines(lang=lang)]
        mode = "stub"
    else:
        parsed = run_pipeline(node_ids=node_ids, node_names=node_names, hours_back=hours_back)
        mode = "live"

    for ev in parsed:
        try:
            log_event(ev)
        except Exception:
            pass

    return {
        "n_events": len(parsed),
        "lang": lang,
        "mode": mode,
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

    want_stub = payload.use_stub or not live_keys_present()
    if want_stub:
        matcher = NodeMatcher(node_ids, node_names)
        parsed = [parse_headline(h, matcher) for h in stub_headlines(lang=payload.lang)]
        mode = "stub"
    else:
        parsed = run_pipeline(
            node_ids=node_ids, node_names=node_names, hours_back=payload.hours_back,
        )
        mode = "live"

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
        "mode": mode,
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


# ────────────────────────── posterior / cross-validation / metrics ──────────


@router.get("/posterior", tags=["validation"])
def posterior() -> dict:
    """MCMC-derived posterior distribution over engine parameters.

    Returns 404 if no posterior has been computed yet — run
    `python -m scripts.mcmc_calibrate --n-steps 600` to generate one.
    """
    result = load_posterior()
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No posterior found. Run `python -m scripts.mcmc_calibrate`.",
        )
    from dataclasses import asdict
    return asdict(result)


@router.get("/cv-report", tags=["validation"])
def cv_report() -> dict:
    """Leave-one-event-out cross-validation report with bootstrap CIs."""
    from dataclasses import asdict
    cv = loo_cross_validate_fast()
    save_cv(cv)
    return asdict(cv)


@router.get("/research-metrics", tags=["validation"])
def research_metrics(req: Request) -> dict:
    """Novel research metrics — SFI, RES, CCS, ERT, SAC — with stats.

    Returns:
        - SFI scalar (graph-level fragility)
        - RES scalar (graph-level recovery elasticity)
        - CCS top-5 nodes by cascading criticality
        - ERT summary (resilience over time)
        - SAC summary (per-node shock absorption capacity)
        - Statistical evaluation (Pearson, Spearman, p-value, Cohen's d) of
          the per-event metrics vs observed event severity.
    """
    g = _graph(req)
    sfi = systemic_fragility_index(g)
    res = recovery_elasticity_score(g)
    ccs_vec = cascading_criticality_score(g)
    evaluations = evaluate_metrics_against_history() + evaluate_metrics_v2()

    top_ccs = sorted(
        ((g.node_ids[i], float(ccs_vec[i])) for i in range(g.n)),
        key=lambda x: x[1], reverse=True,
    )[:5]

    from dataclasses import asdict
    return {
        "systemic_fragility_index": sfi,
        "recovery_elasticity_score": res,
        "top_cascading_criticality_nodes": [
            {"node_id": nid, "ccs": round(score, 4)} for nid, score in top_ccs
        ],
        "economic_resilience_tensor_summary": ert_summary(g),
        "shock_absorption_capacity_summary": sac_summary(g),
        "statistical_evaluation": [asdict(e) for e in evaluations],
    }


class CrisisRadarRequest(BaseModel):
    force_refresh: bool = False


@router.post("/crisis-radar", tags=["narrative"])
def crisis_radar(payload: CrisisRadarRequest, req: Request) -> dict:
    """Claude-powered bilingual "what could go wrong" analysis, grounded in GEDS signals.

    Gathers GEDS's own risk signals — most-fragile nodes (low shock-absorption
    capacity), top cascading-criticality nodes, and the active live-news overlay —
    and asks Claude to narrate plausible danger scenarios in EN + RU. Claude
    invents no numbers; quantitative magnitudes come from the engine, not from
    this analysis. Falls back to a labelled stub when ANTHROPIC_API_KEY is unset.
    """
    g = _graph(req)

    sac = sac_summary(g)
    ccs_vec = cascading_criticality_score(g)
    top_ccs = sorted(
        ((g.node_ids[i], float(ccs_vec[i])) for i in range(g.n)),
        key=lambda x: x[1], reverse=True,
    )[:6]
    sfi = systemic_fragility_index(g)

    overlay = getattr(req.app.state, "news_overlay", None)
    active_news: list[dict] = []
    if overlay is not None and overlay.is_active():
        for node_id, d in overlay.deltas.items():
            active_news.append({
                "node_id": node_id,
                "event_type": d.get("event_type"),
                "source": (d.get("source") or "")[:160],
            })

    signals = {
        "systemic_fragility_index": round(float(sfi), 4),
        "most_fragile_nodes": (sac.get("most_fragile_nodes") or [])[:6],
        "top_cascading_criticality_nodes": [
            {"node_id": nid, "ccs": round(s, 4)} for nid, s in top_ccs
        ],
        "active_news_disruptions": active_news,
        "all_nodes": list(g.node_ids),
    }

    advisor = ClaudeCrisisAdvisor()
    result = advisor.analyze(signals, force_refresh=payload.force_refresh)

    return {
        "overview_en": result.overview_en,
        "overview_ru": result.overview_ru,
        "scenarios": result.scenarios,
        "disclaimer_en": result.disclaimer_en,
        "disclaimer_ru": result.disclaimer_ru,
        "model": result.model,
        "cached": result.cached,
        "latency_ms": result.latency_ms,
        "mode": result.mode,
        "configured": advisor.is_configured(),
        "n_signals": result.n_signals,
        "active_news_count": len(active_news),
    }


@router.get("/ablation", tags=["validation"])
def ablation() -> dict:
    """Component-wise ablation study.  Which engine pieces earn their complexity?"""
    from dataclasses import asdict
    report = run_ablation_study()
    save_ablation(report)
    return {
        "timestamp": report.timestamp,
        "n_events": report.n_events,
        "best_variant": report.best_variant,
        "worst_variant": report.worst_variant,
        "rows": [asdict(r) for r in report.rows],
    }


@router.get("/loo-de-report", tags=["validation"])
def loo_de_report() -> dict:
    """Out-of-sample LOO-DE verdict: per-fold DE re-calibration, pooled score.

    Serves the artifact written by ``python -m scripts.loo_de_validation``
    (a ~30 min run, so it is precomputed rather than recomputed per request).
    The payload carries its own provenance — timestamp, DE settings, runtime
    and every per-fold prediction — so the UI can show exactly where the
    numbers come from and how to reproduce them.
    """
    path = Path(__file__).parent.parent.parent / "data" / "calibration" / "loo_de_result.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="loo_de_result.json not generated yet — run: python -m scripts.loo_de_validation",
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["reproduce_command"] = "python -m scripts.loo_de_validation"
    return payload


def _serve_calibration_artifact(filename: str, regenerate_hint: str) -> dict:
    path = Path(__file__).parent.parent.parent / "data" / "calibration" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not generated yet — run: {regenerate_hint}")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/portwatch-validation", tags=["validation"])
def portwatch_validation() -> dict:
    """Chokepoint shock specs vs MEASURED IMF PortWatch transit deficits,
    plus the Cape-of-Good-Hope rerouting cross-check."""
    return _serve_calibration_artifact(
        "portwatch_validation.json", "python -m scripts.portwatch_validation")


@router.get("/gscpi-validation", tags=["validation"])
def gscpi_validation() -> dict:
    """Predicted global severity vs the NY Fed GSCPI — an independent index
    the model was never calibrated on."""
    return _serve_calibration_artifact(
        "gscpi_validation.json", "python -m scripts.gscpi_validation")


@router.get("/benchmark", tags=["validation"])
def benchmark() -> dict:
    """Unified model leaderboard: SEIRS vs Leontief vs Diffusion vs naive."""
    from dataclasses import asdict
    report = run_benchmark()
    save_benchmark(report)
    return {
        "timestamp": report.timestamp,
        "n_events": report.n_events,
        "winner_by_mae": report.winner_by_mae,
        "winner_by_rmse": report.winner_by_rmse,
        "winner_by_r_squared": report.winner_by_r_squared,
        "winner_by_pearson": report.winner_by_pearson,
        "models": [asdict(m) for m in report.models],
    }


# ─────────────────────────── CSV data layer ──────────────────────────────


@router.get("/data/historical-events-csv", tags=["data"])
def historical_events_csv_endpoint() -> dict:
    """Return historical_events.csv contents as JSON.

    Includes BOTH in-graph (21 events backtestable now) and out-of-graph
    events (9/11, SARS, 2008, Russia-Ukraine — preserved for future
    graph-expansion validation).
    """
    from dataclasses import asdict
    events = load_historical_events_csv()
    return {
        "n_total": len(events),
        "n_in_graph": sum(1 for e in events if e.in_geds_graph),
        "n_out_of_graph": sum(1 for e in events if not e.in_geds_graph),
        "events": [asdict(e) for e in events],
    }


@router.get("/data/model-parameters-csv", tags=["data"])
def model_parameters_csv_endpoint() -> dict:
    from dataclasses import asdict
    params = load_parameters_csv()
    return {"n": len(params), "parameters": [asdict(p) for p in params]}


@router.get("/data/validation-datasets-csv", tags=["data"])
def validation_datasets_csv_endpoint() -> dict:
    from dataclasses import asdict
    ds = load_datasets_csv()
    return {"n": len(ds), "datasets": [asdict(d) for d in ds]}


@router.get("/data/last-refresh", tags=["data"])
def last_refresh_endpoint() -> dict:
    """Когда последний раз обновлялся Comtrade-граф через scheduled refresh.

    Источник истины: data/csv/last_refresh.json, который коммитится в репо
    GitHub Actions workflow .github/workflows/refresh-comtrade.yml.
    """
    import json
    from datetime import datetime, timezone
    p = Path(__file__).parent.parent.parent / "data" / "csv" / "last_refresh.json"
    if not p.exists():
        return {
            "last_refresh_utc": None,
            "age_hours": None,
            "source": "never",
            "workflow_run_url": None,
        }
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        ts = data.get("last_refresh_utc")
        if ts:
            last = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
            data["age_hours"] = round(age, 2)
        return data
    except (json.JSONDecodeError, ValueError):
        return {"last_refresh_utc": None, "age_hours": None, "source": "parse_error"}


@router.get("/calibration-report", tags=["validation"])
def calibration_report() -> dict:
    """Isotonic post-calibration report — out-of-sample leave-one-out.

    Returns before/after metrics demonstrating the magnitude correction.
    The frontend can display 'pass rate ±25% improved from X to Y after
    isotonic recalibration' as a real, computed result.
    """
    from dataclasses import asdict
    return asdict(loo_calibration_report())


class TailRiskRequest(BaseModel):
    scenario_id: str | None = None
    custom: CustomScenarioRequest | None = None
    n_iterations: int = Field(2000, ge=200, le=10000)
    param_noise_pct: float = Field(15.0, ge=1.0, le=50.0)
    seed: int = Field(42, ge=0)


@router.post("/tail-risk", tags=["risk"])
def tail_risk(payload: TailRiskRequest, req: Request) -> dict:
    """VaR / CVaR / black-swan probability + fan-chart percentiles.

    The financial-grade tail-risk panel.  Returns the loss distribution's
    higher moments plus weekly p1/p5/p10/p50/p90/p95/p99 trajectories.
    """
    sim_payload = SimulationRequest(scenario_id=payload.scenario_id, custom=payload.custom)
    scenario = _resolve_scenario(sim_payload)
    report = compute_tail_risk(
        scenario=scenario, graph=_graph(req),
        n_iterations=payload.n_iterations,
        param_noise_pct=payload.param_noise_pct,
        seed=payload.seed,
    )
    return tail_risk_to_dict(report)


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
