"""Unit tests for the propagation engine.

Properties verified:
* No-shock invariant: zero shock in, zero shock out.
* Bounded state: shock ∈ [0, 1] for all nodes, all times.
* Single shock at TWN propagates to its direct neighbors after the first propagation step.
* Recovery: after the shock window ends, the global shock decays toward zero.
* Determinism: same scenario + same seed produces identical frames.
"""

from __future__ import annotations

import numpy as np

from app.core.propagation import PropagationEngine
from app.core.scenarios import taiwan_semiconductor_shock
from app.core.types import EngineConfig, Industry, Scenario, ShockSpec


def _id(country: str, industry: Industry) -> str:
    return f"{country}:{industry.value}"


def test_zero_shock_stays_zero(graph):
    engine = PropagationEngine(graph)
    scenario = Scenario(
        id="null",
        name="Null",
        horizon_weeks=10,
        shocks=[],
    )
    result = engine.run(scenario)
    for f in result.frames:
        assert all(nf.shock == 0.0 for nf in f.nodes)
        assert f.csi == 0.0
        assert f.ecv == 0.0


def test_shock_state_is_bounded(graph, taiwan_scenario):
    engine = PropagationEngine(graph)
    result = engine.run(taiwan_scenario)
    for f in result.frames:
        for nf in f.nodes:
            assert 0.0 <= nf.shock <= 1.0, f"week {f.week} {nf.id} = {nf.shock}"


def test_first_neighbors_react_quickly(graph):
    """After the first propagation step, downstream importers should show non-zero shock."""

    engine = PropagationEngine(graph, EngineConfig(propagation_decay=0.85))
    scenario = Scenario(
        id="t",
        name="Direct Taiwan shock",
        horizon_weeks=6,
        shocks=[
            ShockSpec(
                target_node_id=_id("TWN", Industry.SEMICONDUCTORS),
                magnitude=0.80,
                start_week=0,
                duration_weeks=6,
                decay_curve="step",
            )
        ],
    )
    result = engine.run(scenario)

    # Pick downstream importers that have a direct edge from TWN:semiconductors.
    importers = [_id("USA", Industry.ELECTRONICS), _id("DEU", Industry.AUTOMOTIVE)]
    by_id = {nf.id: nf for nf in result.frames[2].nodes}
    for imp in importers:
        assert by_id[imp].shock > 0.0, f"{imp} should have non-zero shock by week 2"


def test_taiwan_shock_cascades_globally(graph, taiwan_scenario):
    """The Taiwan-semi shock should reach ≥8 distinct countries at PEAK.

    summary.affected_country_count is a final-state metric (countries still
    above threshold at the end of horizon).  With SEIRS recovery, many
    countries drop back below 0.10 by week 52 even though they were
    affected mid-cascade.  We assert on the peak crossing instead,
    which is the more meaningful "cascade is global" check.
    """
    engine = PropagationEngine(graph)
    result = engine.run(taiwan_scenario)

    # Peak per-node shock across all frames.
    n_nodes = len(result.frames[0].nodes)
    peak_per_node = [0.0] * n_nodes
    for f in result.frames:
        for i, nf in enumerate(f.nodes):
            if nf.shock > peak_per_node[i]:
                peak_per_node[i] = nf.shock

    # Count distinct country-prefix IDs whose peak_shock exceeded 0.10.
    affected_countries: set[str] = set()
    for i, nf in enumerate(result.frames[0].nodes):
        if peak_per_node[i] > 0.10 and ":" in nf.id and not nf.id.startswith("CP:"):
            affected_countries.add(nf.id.split(":", 1)[0])

    assert len(affected_countries) >= 8, (
        f"Expected peak cascade to ≥8 countries, got {len(affected_countries)} "
        f"({sorted(affected_countries)}). Final-state count was "
        f"{result.summary.affected_country_count}."
    )
    assert result.summary.peak_csi > 0.0
    assert result.summary.peak_ecv > 0.0


def test_recovery_after_shock_window(graph):
    engine = PropagationEngine(graph, EngineConfig(propagation_decay=0.8, recovery_rate=0.15))
    scenario = Scenario(
        id="recovery",
        name="Brief shock then recovery",
        horizon_weeks=60,
        shocks=[
            ShockSpec(
                target_node_id=_id("TWN", Industry.SEMICONDUCTORS),
                magnitude=0.7,
                start_week=0,
                duration_weeks=6,
                decay_curve="step",
            )
        ],
    )
    result = engine.run(scenario)
    peak_csi = max(f.csi for f in result.frames)
    final_csi = result.frames[-1].csi
    assert final_csi < 0.4 * peak_csi, (
        f"CSI should have decayed at least 60% by horizon (peak={peak_csi:.3f}, final={final_csi:.3f})"
    )


def test_determinism_with_seed(graph):
    cfg = EngineConfig(stochastic_sigma=0.01, seed=42)
    scenario = taiwan_semiconductor_shock(magnitude=0.75, duration_weeks=12, horizon_weeks=24)
    scenario.config = cfg

    r1 = PropagationEngine(graph, cfg).run(scenario)
    r2 = PropagationEngine(graph, cfg).run(scenario)

    for f1, f2 in zip(r1.frames, r2.frames, strict=True):
        for n1, n2 in zip(f1.nodes, f2.nodes, strict=True):
            assert abs(n1.shock - n2.shock) < 1e-12


def test_amplification_activates_above_threshold(graph):
    """Sanity: with high amplification, transmission past threshold is non-trivially larger
    than transmission below threshold."""

    snapshot = graph.snapshot
    # Use the chokepoint with deepest dependencies (Taiwan Strait).
    cp_id = "CP:TaiwanStrait"
    assert cp_id in graph.index

    low_cfg = EngineConfig(propagation_decay=0.85, amplification_mu=0.0)
    high_cfg = EngineConfig(propagation_decay=0.85, amplification_mu=2.4)

    scenario_low = Scenario(
        id="lo",
        name="Low amp",
        horizon_weeks=12,
        shocks=[ShockSpec(target_node_id=cp_id, magnitude=0.9, start_week=0, duration_weeks=6)],
        config=low_cfg,
    )
    scenario_high = scenario_low.model_copy(update={"id": "hi", "config": high_cfg})

    r_lo = PropagationEngine(graph, low_cfg).run(scenario_low)
    r_hi = PropagationEngine(graph, high_cfg).run(scenario_high)

    assert r_hi.summary.peak_csi > r_lo.summary.peak_csi


def test_per_node_recovery_couples_to_delay(graph):
    """Batch 9b: a node's post-forcing shock decay follows its recovery_delay_weeks.

    TWN:semiconductors carries a grounded 2-week delay (TSMC Chi-Chi restoration
    timeline) → 4× the reference decay rate; with the coupling disabled it must
    decay exactly at the uniform global rate.
    """
    scenario = Scenario(
        id="impulse",
        name="One-week impulse at TWN semis",
        horizon_weeks=12,
        shocks=[
            ShockSpec(
                target_node_id=_id("TWN", Industry.SEMICONDUCTORS),
                magnitude=0.9,
                start_week=0,
                duration_weeks=1,
                decay_curve="step",
            )
        ],
    )
    i = graph.index[_id("TWN", Industry.SEMICONDUCTORS)]
    assert graph.recovery_delay[i] == 2.0

    shocks = {}
    for flag in (True, False):
        cfg = EngineConfig(per_node_recovery=flag, stochastic_sigma=0.0, seed=0)
        result = PropagationEngine(graph, cfg).run(
            Scenario(**{**scenario.model_dump(), "config": cfg})
        )
        shocks[flag] = np.array([f.nodes[i].shock for f in result.frames])

    # Coupled: the 2-week node sheds shock 4x faster than the global rate.
    assert shocks[True][6] < 0.5 * shocks[False][6], (
        f"coupled decay too slow: week-6 shock {shocks[True][6]:.3f} vs "
        f"uniform {shocks[False][6]:.3f}"
    )
    # Both runs see the same forcing peak.
    assert shocks[True][0] == shocks[False][0] > 0.8
