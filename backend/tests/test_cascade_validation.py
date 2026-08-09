"""Tests for the multi-output cascade-shape validation (Task #3).

Pins the harness contract: three scored dimensions (magnitude, weeks_to_peak,
recovery_weeks) read at the directly-shocked NODE (not the diluted industry
global average), scored only where a clean observed value exists.
"""

from __future__ import annotations

import pytest

from app.core.cascade_validation import (
    compare_spatial_recall,
    run_cascade_validation,
    run_spatial_validation,
)

_DIMS = {"magnitude", "weeks_to_peak", "recovery_weeks"}


def test_runs_and_dimension_coverage():
    rep = run_cascade_validation()
    assert rep.events, "no events scored"
    for r in rep.events:
        for d in r.dims:
            assert d.name in _DIMS
            assert d.abs_error >= 0.0
    # deterministic join counts against the current engine event set
    # 6 since 2026-08: japan, eu, thailand, shanghai, gfc-auto + ukraine-war-harness.
    # The sixth was already available as a measured direct target but was being
    # discarded because the event had no cascade_timing row — the harness used to
    # require timing before it would score magnitude at all.
    assert rep.n_by_dim["magnitude"] == 6
    assert rep.n_by_dim["weeks_to_peak"] == 15
    assert rep.n_by_dim["recovery_weeks"] == 11


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


# ── spatial axis ──


def test_spatial_validation_well_formed():
    rep = run_spatial_validation()
    assert 0.0 < rep.coverage <= 1.0
    assert 0.0 <= rep.spatial_recall <= 1.0
    assert -1.0 <= rep.onset_spearman <= 1.0
    assert rep.n_out_of_graph == 15  # documented coverage gaps in the 12-country graph
    for e in rep.events:
        assert e.reached <= e.observed_nodes


def test_spatial_recall_below_one_documents_sparse_graph():
    """The engine misses nodes history hit because the hand-authored graph lacks
    the edges — this is the quantified case for the ICIO expansion (Batch 11)."""
    rep = run_spatial_validation()
    assert rep.spatial_recall < 1.0
    # ordering of the nodes it does reach should still track observed onset
    assert rep.onset_spearman > 0.0


def test_dense_v3_graph_improves_spatial_recall():
    """Batch 16 headline: the dense ICIO 405-node graph should reach materially
    more historically-hit nodes than the sparse 36-node graph."""
    cmp = compare_spatial_recall()
    assert cmp.events_compared >= 8
    assert cmp.v3_recall > cmp.v2_recall, "ICIO expansion should lift spatial recall"
    # chokepoint events can't run on v3 (no chokepoint nodes) — must be excluded, not crash
    assert all("/" in e["v2"] and "/" in e["v3"] for e in cmp.per_event)


# ─────────────── recovery predictions must declare when they are bounds ──────
# Found 2026-08 by an adversarial review of the demo page. `_node_shape` returns
# the simulated window length when a node never recovers in-window, so 7 of the
# 11 scored "predictions" are right-censored lower bounds equal to a hand-set
# `horizon_weeks`. Ranking the events by that field ALONE — no engine — gives
# Spearman 0.8717 against the engine's 0.8828. Any consumer that presents these
# as predictions overstates the project's headline result badly, so the flag
# that lets them be told apart is locked here.


def test_censored_recoveries_are_flagged():
    """A prediction equal to the horizon is a bound and must say so."""
    from app.core.cascade_validation import run_cascade_validation

    rep = run_cascade_validation()
    for ev in rep.events:
        at_horizon = (
            ev.horizon_weeks > 0
            and abs(ev.predicted_recovery_weeks - ev.horizon_weeks) < 1e-9
        )
        assert ev.recovery_censored == at_horizon, (
            f"{ev.slug}: predicted={ev.predicted_recovery_weeks} "
            f"horizon={ev.horizon_weeks} but recovery_censored={ev.recovery_censored}"
        )


def test_recovery_is_scored_on_a_fixed_horizon_with_nothing_censored():
    """The censoring confound is removed by construction, and stays removed.

    History: recovery used to be scored on each event's own hand-set
    `horizon_weeks`, and `_node_shape` substitutes the window length when a node
    never recovers in-window. That made 7 of 11 "predictions" lower bounds equal
    to a field a human typed in, and since horizons were chosen to cover each
    event, ranking by that field ALONE scored 0.8717 against the engine's 0.8828
    (scripts/recovery_censoring_audit.py). The fix was to simulate every event on
    one fixed window, which makes the horizon a constant with zero variance.

    The earlier version of this test locked the SIZE of the problem so that
    removing it would fail the suite rather than silently improve the number.
    It did exactly that, and this is the rewritten lock on the fixed state.
    """
    import numpy as np

    from app.core.cascade_validation import (
        CASCADE_HORIZON_WEEKS,
        run_cascade_validation,
    )
    from app.core.metrics import spearman_rho

    rep = run_cascade_validation()
    scored = [e for e in rep.events if e.observed_recovery_weeks is not None]

    assert len(scored) == 11
    # nothing may be censored: 260 weeks is >3x the longest observed recovery
    assert sum(e.recovery_censored for e in scored) == 0
    # and every event must have been run on the SAME window, or the confound is back
    assert {e.horizon_weeks for e in scored} == {CASCADE_HORIZON_WEEKS}

    pred = np.array([e.predicted_recovery_weeks for e in scored])
    obs = np.array([e.observed_recovery_weeks for e in scored])
    # the clean value; materially below the 0.8828 that the confounded harness
    # reported, and that gap is the size of the artifact that was removed
    assert spearman_rho(pred, obs) == pytest.approx(0.7107, abs=5e-4)
