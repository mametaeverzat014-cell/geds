"""Shape contract for ShockSpec.factor(), including the ramp curve (Batch 19).

The weeks_to_peak forensics showed the engine's ratchet update renders any
DECLINING forcing as a rectangular pulse (peak at onset), so step/linear/exp
are all onset-peaked at the shocked node. ramp is the one rising shape and
must be monotone, reach full force in the window's last week, and never be a
silent no-op for short windows.
"""

from __future__ import annotations

import pytest

from app.core.types import ShockSpec


def _spec(curve: str, duration: int = 10, start: int = 0) -> ShockSpec:
    return ShockSpec(target_node_id="USA:automotive", magnitude=1.0,
                     start_week=start, duration_weeks=duration,
                     decay_curve=curve)


def test_all_curves_zero_outside_window():
    for curve in ("step", "linear", "exp", "ramp"):
        s = _spec(curve, duration=5, start=2)
        assert s.factor(1) == 0.0
        assert s.factor(7) == 0.0


def test_step_linear_exp_peak_at_onset():
    for curve in ("step", "linear", "exp"):
        s = _spec(curve)
        onset = s.factor(0)
        assert onset == 1.0
        assert all(s.factor(t) <= onset for t in range(10))


def test_ramp_is_monotone_rising_to_full_force():
    s = _spec("ramp", duration=10)
    vals = [s.factor(t) for t in range(10)]
    assert vals == sorted(vals)
    assert vals[0] == pytest.approx(0.1)   # 1/D — small but a real shock
    assert vals[-1] == pytest.approx(1.0)  # full force in the last window week


def test_ramp_degenerate_one_week_window_is_full_force():
    s = _spec("ramp", duration=1)
    assert s.factor(0) == pytest.approx(1.0)


def test_ramp_respects_start_week_offset():
    s = _spec("ramp", duration=4, start=3)
    assert s.factor(2) == 0.0
    assert s.factor(3) == pytest.approx(0.25)
    assert s.factor(6) == pytest.approx(1.0)
