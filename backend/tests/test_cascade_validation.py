"""Tests for the multi-output cascade-shape validation (Task #3).

Pins the harness contract: three scored dimensions (magnitude, weeks_to_peak,
recovery_weeks) read at the directly-shocked NODE (not the diluted industry
global average), scored only where a clean observed value exists.
"""

from __future__ import annotations

from app.core.cascade_validation import run_cascade_validation

_DIMS = {"magnitude", "weeks_to_peak", "recovery_weeks"}


def test_runs_and_dimension_coverage():
    rep = run_cascade_validation()
    assert rep.events, "no events scored"
    for r in rep.events:
        for d in r.dims:
            assert d.name in _DIMS
            assert d.abs_error >= 0.0
    # deterministic join counts against the current engine event set
    assert rep.n_by_dim["magnitude"] == 4       # japan, eu, thailand, shanghai (direct)
    assert rep.n_by_dim["weeks_to_peak"] == 14
    assert rep.n_by_dim["recovery_weeks"] == 10


def test_node_level_not_diluted():
    """The fix that matters: magnitude is read at the shocked node, so a real
    shock shows a real loss — not the ~0.02 industry-global average."""
    rep = run_cascade_validation()
    japan = next(r for r in rep.events if r.slug == "japan-triple-disaster-2011")
    mag = next(d for d in japan.dims if d.name == "magnitude")
    assert mag.predicted > 0.05, "node-level magnitude collapsed to industry-global dilution"


def test_spearman_in_range_and_engine_ranks_shape():
    rep = run_cascade_validation()
    for dim, s in rep.spearman_by_dim.items():
        assert -1.0 <= s <= 1.0, f"{dim} spearman out of range"
    # The positive finding: the engine ranks at least one shape dimension well.
    assert max(rep.spearman_by_dim.values()) > 0.5


def test_structural_separation_fields_present():
    rep = run_cascade_validation()
    # both observed and predicted separation flags are computed (booleans)
    assert isinstance(rep.structural_separation_observed, bool)
    assert isinstance(rep.structural_separation_predicted, bool)
