"""Tests for per-scenario baseline comparison (Task #4) and LOO band (Task #5)."""

from __future__ import annotations

from app.core.forecast_ensemble import baseline_compare, loo_forecast_band
from app.core.types import EngineConfig, Scenario, ShockSpec


def _semi_scenario() -> Scenario:
    return Scenario(
        id="t", name="t", horizon_weeks=40,
        shocks=[ShockSpec(target_node_id="TWN:semiconductors", magnitude=0.75,
                          start_week=0, duration_weeks=8, decay_curve="step")],
        config=EngineConfig(),
    )


def _chokepoint_scenario() -> Scenario:
    return Scenario(
        id="cp", name="cp", horizon_weeks=16,
        shocks=[ShockSpec(target_node_id="CP:Suez", magnitude=0.9,
                          start_week=0, duration_weeks=2, decay_curve="step")],
        config=EngineConfig(),
    )


def test_baseline_compare_has_three_models(graph):
    out = baseline_compare(_semi_scenario(), graph)
    models = {m["model"]: m for m in out["models"]}
    assert set(models) == {"SEIRS (GEDS)", "Linear diffusion", "Leontief"}
    assert models["SEIRS (GEDS)"]["parameters"] == 5
    assert models["Linear diffusion"]["parameters"] == 0
    for m in out["models"]:
        assert m["industry_loss"] >= 0.0
        assert m["recovery_weeks"] >= 0.0


def test_baseline_compare_chokepoint_industry_fallback(graph):
    # chokepoint scenarios have no source industry → must not crash
    out = baseline_compare(_chokepoint_scenario(), graph)
    assert len(out["models"]) == 3


def test_loo_forecast_band_well_ordered(graph):
    band = loo_forecast_band(_semi_scenario(), graph)
    assert band["available"] is True
    assert band["n_folds"] == 27  # LOO-DE refreshed at N=27 (2026-07-18, +GFC fold)
    assert band["min"] <= band["p10"] <= band["median"] <= band["p90"] <= band["max"]
    assert band["rel_width"] >= 0.0
