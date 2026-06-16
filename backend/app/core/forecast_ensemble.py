"""Per-scenario baseline comparison (Task #4) and LOO forecast band (Task #5).

Two things the validation dashboard's aggregate leaderboard can't show inline
with an actual run:

  baseline_compare(scenario)  — runs SEIRS, linear diffusion and Leontief on the
      SAME scenario and returns their peak industry-loss side by side, so the
      cost (and benefit) of SEIRS's machinery is visible for the run in front of
      you. Linear diffusion is the honest zero-free-parameter reference and, on
      out-of-sample ranking, the engine's toughest competitor (see Batch 4).

  loo_forecast_band(scenario) — re-runs the scenario under each of the 26
      leave-one-out fold parameter sets (data/calibration/loo_de_result.json) and
      returns the median + 10/90 percentile band of peak CSI. With N=26 every
      point estimate carries large parametric uncertainty; this surfaces it
      honestly instead of pretending the calibrated point is exact.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .backtest import _aggregate_industry
from .baselines import leontief_predict, linear_diffusion_predict
from .graph import CompiledGraph
from .propagation import PropagationEngine
from .types import EngineConfig, Industry, Scenario

_LOO_PATH = Path(__file__).parent.parent.parent / "data" / "calibration" / "loo_de_result.json"


def _primary_industry(scenario: Scenario, graph: CompiledGraph) -> Industry:
    """Industry of the first shock target that has one; AUTOMOTIVE as fallback
    (chokepoint-only scenarios have no source industry)."""
    for sh in scenario.shocks:
        idx = graph.index.get(sh.target_node_id)
        if idx is not None and graph.snapshot.nodes[idx].industry is not None:
            return graph.snapshot.nodes[idx].industry
    return Industry.AUTOMOTIVE


def baseline_compare(scenario: Scenario, graph: CompiledGraph) -> dict:
    """SEIRS vs linear-diffusion vs Leontief peak industry-loss for one scenario."""
    industry = _primary_industry(scenario, graph)

    sim = PropagationEngine(graph, scenario.config).run(scenario)
    seirs = _aggregate_industry(sim, graph, industry)
    ld = linear_diffusion_predict(graph, list(scenario.shocks), industry, scenario.horizon_weeks)
    le = leontief_predict(graph, list(scenario.shocks), industry, scenario.horizon_weeks)

    models = [
        {"model": "SEIRS (GEDS)", "industry_loss": round(seirs["loss"], 4),
         "recovery_weeks": round(seirs["recovery"], 1), "parameters": 5},
        {"model": "Linear diffusion", "industry_loss": round(ld.industry_loss, 4),
         "recovery_weeks": round(ld.recovery_weeks, 1), "parameters": 0},
        {"model": "Leontief", "industry_loss": round(le.industry_loss, 4),
         "recovery_weeks": round(le.recovery_weeks, 1), "parameters": 0},
    ]
    return {"industry": industry.value, "models": models}


def loo_forecast_band(scenario: Scenario, graph: CompiledGraph) -> dict:
    """Peak-CSI band from re-running the scenario under all 26 LOO fold params."""
    try:
        folds = json.loads(_LOO_PATH.read_text(encoding="utf-8")).get("folds", [])
    except (OSError, json.JSONDecodeError):
        folds = []

    valid = set(EngineConfig.model_fields.keys())
    base = scenario.config.model_dump()

    peaks: list[float] = []
    for f in folds:
        params = {k: v for k, v in f.get("fold_params", {}).items() if k in valid}
        if not params:
            continue
        cfg = EngineConfig(**{**base, **params})
        scen_f = scenario.model_copy(update={"config": cfg})
        sim = PropagationEngine(graph, cfg).run(scen_f)
        peaks.append(max((fr.csi for fr in sim.frames), default=0.0))

    if not peaks:
        return {"n_folds": 0, "metric": "peak_csi", "available": False}

    arr = np.array(peaks, dtype=float)
    return {
        "n_folds": len(peaks),
        "metric": "peak_csi",
        "available": True,
        "median": round(float(np.median(arr)), 4),
        "p10": round(float(np.percentile(arr, 10)), 4),
        "p90": round(float(np.percentile(arr, 90)), 4),
        "min": round(float(arr.min()), 4),
        "max": round(float(arr.max()), 4),
        "rel_width": round(float((np.percentile(arr, 90) - np.percentile(arr, 10))
                                 / max(np.median(arr), 1e-9)), 3),
    }
