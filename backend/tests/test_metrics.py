"""Tests for CSI, ECV, country risk, and sector fragility."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.metrics import (
    compute_csi,
    compute_ecv,
    compute_ecv_geo,
)
from app.core.propagation import PropagationEngine
from app.core.scenarios import taiwan_semiconductor_shock


@dataclass
class _StubState:
    """Minimal state for compute_csi(): only `.shock` is read by the function.

    After the vectorized-engine refactor, BatchedEngineState requires 18 fields
    and uses 2D (I, N) shock arrays. compute_csi() is the legacy single-iter
    function and only reads `.shock` as 1D, so this stub is sufficient and
    keeps the test focused on the metric, not on engine plumbing.
    """
    shock: np.ndarray


def _zero_state(n: int) -> _StubState:
    return _StubState(shock=np.zeros(n))


def test_csi_is_zero_without_shock(graph):
    s = _zero_state(graph.n)
    assert compute_csi(s, graph) == 0.0


def test_csi_increases_with_shock_at_central_node(graph):
    s = _zero_state(graph.n)
    s.shock = np.zeros(graph.n)

    # Inject shock at the highest-centrality node.
    central_i = int(np.argmax(graph.centrality))
    s.shock[central_i] = 0.8
    csi_at_central = compute_csi(s, graph)

    # Now inject the same shock at the lowest-centrality node.
    s.shock = np.zeros(graph.n)
    low_i = int(np.argmin(graph.centrality))
    s.shock[low_i] = 0.8
    csi_at_low = compute_csi(s, graph)

    assert csi_at_central >= csi_at_low


def test_ecv_counts_new_affected(graph):
    n = graph.n
    prev = np.zeros(n, dtype=bool)
    now = np.zeros(n, dtype=bool)
    now[:5] = True
    ecv = compute_ecv(now, prev)
    assert abs(ecv - 5 / n) < 1e-12


def test_ecv_geo_zero_when_no_new(graph):
    n = graph.n
    affected_first_week = np.full(n, -1, dtype=np.int32)
    assert compute_ecv_geo(affected_first_week, t=3, shortest_path={}, g=graph) == 0.0


def test_summary_country_risk_taiwan_scenario(graph):
    engine = PropagationEngine(graph)
    result = engine.run(taiwan_semiconductor_shock(magnitude=0.75, duration_weeks=20, horizon_weeks=52))

    risks = result.summary.country_risk
    assert len(risks) > 0

    # Taiwan is the shock ORIGIN — its peak_shock should be high.
    twn = next(r for r in risks if r.iso3 == "TWN")
    assert twn.peak_shock > 0.5, f"TWN peak shock should be high (origin); got {twn.peak_shock}"

    # Top risk score should be a heavy-downstream country (auto / electronics economy).
    heavy_downstream = {"USA", "DEU", "MEX", "JPN", "CHN", "KOR", "THA", "MYS", "VNM", "TWN"}
    assert risks[0].iso3 in heavy_downstream, (
        f"top-1 risk should be a heavy downstream economy; got {risks[0].iso3}"
    )

    # Risk scores in [0, 1+]
    for r in risks:
        assert 0.0 <= r.risk_score <= 1.5


def test_sector_fragility_semiconductors_first(graph):
    engine = PropagationEngine(graph)
    result = engine.run(taiwan_semiconductor_shock(magnitude=0.75, duration_weeks=20, horizon_weeks=52))

    fragility = result.summary.sector_fragility
    assert len(fragility) > 0
    top_industries = [f.industry.value for f in fragility[:3]]
    assert "semiconductors" in top_industries, (
        f"semiconductors should be a top-3 fragility sector; got {top_industries}"
    )
