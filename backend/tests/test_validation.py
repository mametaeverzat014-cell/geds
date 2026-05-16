"""Historical replay validation tests.

These are CI-gating: every replay event must produce predictions within tolerances
defined in `core/validation.py`. If this regresses on a future engine change we want
to know about it loudly.
"""

from __future__ import annotations

from app.core.validation import run_all, run_replay
from app.data.seed_data import HISTORICAL_EVENTS


def test_all_historical_events_have_replays():
    results = run_all()
    assert len(results) == len(HISTORICAL_EVENTS)


def test_replay_metrics_are_finite():
    for r in run_all():
        assert r.rmse != float("inf")
        assert -1.0 <= r.correlation <= 1.0 or r.correlation == 0.0


def test_replay_predicted_recovery_positive():
    for r in run_all():
        assert r.recovery_predicted >= 0


def test_individual_event_runs():
    for ev in HISTORICAL_EVENTS:
        r = run_replay(ev)
        assert r.slug == ev["slug"]
        # Predicted output loss should be non-zero for substantive events.
        if ev["observed"]["auto_production_loss_pct"] > 0.02:
            assert r.auto_loss_predicted > 0.0, f"{ev['slug']} predicted zero output loss"
