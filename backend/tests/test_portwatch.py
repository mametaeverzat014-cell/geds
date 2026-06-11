"""Tests for the PortWatch chokepoint-transit validation layer.

Assertions are pinned to *measured facts* in the committed raw dataset
(backend/data/raw/external/portwatch_daily_chokepoints.csv), so they double
as a data-integrity check: if the file is replaced with a different export,
violations of these known events will be caught.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.portwatch import (
    CHOKEPOINT_EVENTS,
    check_event,
    deficit_profile,
    rerouting_cross_check,
    run_validation,
    weekly,
)


def test_weekly_series_sane():
    s = weekly("Suez Canal")
    assert len(s) > 300                       # 2019 → 2026, weekly
    assert s.median() > 200                   # Suez handles hundreds of transits/week
    with pytest.raises(KeyError):
        weekly("Strait of Nowhere")


def test_ever_given_blockage_is_in_the_data():
    deficits, base = deficit_profile("Suez Canal", "2021-03-23", 4)
    assert base > 250
    assert deficits.max() > 0.5               # the blockage week
    assert deficits.min() < -0.15             # the catch-up surge after clearing


def test_red_sea_deficit_persistent():
    deficits, _ = deficit_profile("Suez Canal", "2023-12-15", 52)
    # Long partial closure: most weeks of 2024 show a >25% transit deficit.
    assert (deficits[8:] > 0.25).mean() > 0.8


def test_event_specs_match_measured_deficits():
    for ev in CHOKEPOINT_EVENTS:
        chk = check_event(ev)
        assert "CONFIRMED" in chk.magnitude_verdict, (
            f"{ev['slug']}: {chk.magnitude_verdict} — either the event spec or "
            f"the dataset changed; reconcile before publishing."
        )


def test_rerouting_mirror():
    x = rerouting_cross_check()
    # Lost Suez transits must reappear at the Cape (the capacity-factor premise).
    assert x["weekly_correlation_suez_lost_vs_cape_gained"] > 0.6
    assert x["fraction_of_lost_suez_transits_reappearing_at_cape"] > 0.7


def test_run_validation_payload_shape():
    payload = run_validation()
    assert payload["event_checks"]
    assert "rerouting_cross_check" in payload
    for chk in payload["event_checks"]:
        assert np.isfinite(chk["observed_peak_weekly_deficit"])
