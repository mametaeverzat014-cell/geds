"""Tests for the policy advisor module."""

from __future__ import annotations

import pytest

from app.core.advisor import analyze
from app.core.propagation import PropagationEngine
from app.core.scenarios import (
    suez_2021_replay,
    taiwan_semiconductor_shock,
)
from app.core.types import PolicyCategory, PolicyPriority


@pytest.fixture(scope="module")
def taiwan_result(graph):
    engine = PropagationEngine(graph)
    scenario = taiwan_semiconductor_shock(magnitude=0.75, duration_weeks=20, horizon_weeks=52)
    return engine.run(scenario), graph


@pytest.fixture(scope="module")
def suez_result(graph):
    engine = PropagationEngine(graph)
    return engine.run(suez_2021_replay()), graph


# ─────────────────────────── structural tests ───────────────────────────────


def test_advisor_returns_result(taiwan_result):
    result, g = taiwan_result
    advisor = analyze(result, g)
    assert advisor.scenario_id == result.scenario_id
    assert len(advisor.recommendations) > 0


def test_recommendations_are_sorted_by_priority(taiwan_result):
    result, g = taiwan_result
    advisor = analyze(result, g)
    order = {PolicyPriority.CRITICAL: 0, PolicyPriority.HIGH: 1,
             PolicyPriority.MEDIUM: 2, PolicyPriority.LOW: 3}
    priorities = [order[r.priority] for r in advisor.recommendations]
    assert priorities == sorted(priorities), "Recommendations not sorted by priority"


def test_recommendation_ids_are_unique(taiwan_result):
    result, g = taiwan_result
    advisor = analyze(result, g)
    ids = [r.id for r in advisor.recommendations]
    assert len(ids) == len(set(ids)), "Duplicate recommendation IDs"


def test_taiwan_generates_critical_emergency_rec(taiwan_result):
    result, g = taiwan_result
    advisor = analyze(result, g)
    critical = [r for r in advisor.recommendations if r.priority == PolicyPriority.CRITICAL]
    assert len(critical) >= 1, "Taiwan shock should generate at least one CRITICAL recommendation"


def test_taiwan_has_semiconductor_rec(taiwan_result):
    result, g = taiwan_result
    advisor = analyze(result, g)
    semi_recs = [r for r in advisor.recommendations if "semiconductors" in r.target_industries]
    assert len(semi_recs) >= 1


def test_estimated_impact_in_range(taiwan_result):
    result, g = taiwan_result
    advisor = analyze(result, g)
    for r in advisor.recommendations:
        assert 0.0 <= r.estimated_impact <= 1.0, f"impact out of range for {r.id}"
        assert 0.0 <= r.implementation_difficulty <= 1.0, f"difficulty out of range for {r.id}"
        assert r.horizon_weeks >= 1


def test_critical_nodes_sorted_by_priority(taiwan_result):
    result, g = taiwan_result
    advisor = analyze(result, g)
    # All critical nodes should have had peak_shock ≥ 0.35.
    assert len(advisor.critical_nodes) >= 1


def test_intervention_window_positive(taiwan_result):
    result, g = taiwan_result
    advisor = analyze(result, g)
    assert advisor.intervention_window_weeks >= 0


def test_suez_generates_chokepoint_alert(suez_result):
    result, g = suez_result
    advisor = analyze(result, g)
    assert "CP:Suez" in advisor.chokepoint_alerts, (
        f"Suez blockage should trigger CP:Suez alert; alerts={advisor.chokepoint_alerts}"
    )


def test_suez_has_diplomatic_rec(suez_result):
    result, g = suez_result
    advisor = analyze(result, g)
    diplomatic = [r for r in advisor.recommendations if r.category == PolicyCategory.DIPLOMATIC]
    assert len(diplomatic) >= 1, "Suez scenario should generate at least one diplomatic recommendation"


def test_no_duplicate_recommendations_across_runs(graph):
    """Multiple engine runs should not inflate recommendation counts."""
    engine = PropagationEngine(graph)
    scenario = taiwan_semiconductor_shock(magnitude=0.75, duration_weeks=20, horizon_weeks=52)
    r1 = analyze(engine.run(scenario), graph)
    r2 = analyze(engine.run(scenario), graph)
    assert len(r1.recommendations) == len(r2.recommendations)
    assert {r.id for r in r1.recommendations} == {r.id for r in r2.recommendations}
