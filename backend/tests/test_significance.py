"""Tests for the benchmark significance layer (app.core.significance).

Pins the contract: deterministic seeded resampling, honest handling of the
constant predictor, and agreement between the significance layer's point
estimates and the golden benchmark snapshot (same evaluators, same events).
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.significance import (
    bootstrap_model_ci,
    paired_delta_bootstrap,
    run_significance,
    sign_flip_p,
)


def test_sign_flip_p_detects_clear_difference():
    a = np.zeros(20)          # model a: perfect
    b = np.ones(20)           # model b: constant error of 1
    p = sign_flip_p(a, b, n_perm=2000, seed=7)
    assert p < 0.01


def test_sign_flip_p_is_one_for_identical_errors():
    e = np.linspace(0.1, 0.5, 12)
    assert sign_flip_p(e, e.copy(), n_perm=500, seed=7) == 1.0


def test_sign_flip_p_deterministic_and_bounded():
    rng = np.random.default_rng(3)
    a, b = rng.random(15), rng.random(15)
    p1 = sign_flip_p(a, b, n_perm=1000, seed=42)
    p2 = sign_flip_p(a, b, n_perm=1000, seed=42)
    assert p1 == p2
    assert 0.0 < p1 <= 1.0


def test_bootstrap_ci_ordering_and_constant_predictor():
    rng = np.random.default_rng(5)
    obs = rng.random(20)
    pred = obs + rng.normal(0, 0.05, size=20)
    ci = bootstrap_model_ci(pred, obs, n_boot=500, seed=1)
    for metric in ("mae", "rmse", "spearman"):
        block = ci[metric]
        assert block["p2_5"] <= block["p50"] <= block["p97_5"]
    # a constant predictor has no rank ordering → spearman is None, not 0
    const = bootstrap_model_ci(np.full(20, obs.mean()), obs, n_boot=200, seed=1)
    assert const["spearman"] is None
    assert const["mae"]["point"] is not None


def test_paired_delta_point_matches_direct_computation():
    rng = np.random.default_rng(9)
    obs = rng.random(18)
    a = obs + rng.normal(0, 0.02, 18)
    b = obs + rng.normal(0, 0.10, 18)
    d = paired_delta_bootstrap(a, b, obs, n_boot=400, seed=2)
    direct = float(np.abs(a - obs).mean() - np.abs(b - obs).mean())
    assert d["delta_mae_a_minus_b"]["point"] == pytest.approx(direct, abs=1e-5)
    # a is clearly better here, so most resamples should agree
    assert d["frac_a_better_mae"] > 0.9


def test_bootstrap_deterministic_given_seed():
    rng = np.random.default_rng(11)
    obs = rng.random(16)
    pred = obs + rng.normal(0, 0.05, 16)
    assert (bootstrap_model_ci(pred, obs, 300, seed=4)
            == bootstrap_model_ci(pred, obs, 300, seed=4))


def test_run_significance_agrees_with_golden_benchmark():
    """Integration: the layer must reproduce the golden point estimates
    (same evaluators as run_benchmark) and cover all pairs and dims."""
    payload = run_significance(n_boot=300, n_perm=500, seed=1)
    assert payload["n_events"] == 27
    golden_mae = {  # 2026-07-23: Batch 19 ramp adoption (see test_reproducibility GOLDEN)
        "GEDS": 0.0242,
        "Leontief": 0.0168,
        "LinearDiffusion": 0.0171,
        "NaivePersistence": 0.0208,
    }
    for name, expected in golden_mae.items():
        got = payload["models"][name]["mae"]["point"]
        assert got == pytest.approx(expected, abs=1e-4), (name, got)
    # 4 models → 6 unordered pairs, each with a valid p-value
    assert len(payload["pairwise"]) == 6
    for pair in payload["pairwise"].values():
        assert 0.0 < pair["p_perm_mae_two_sided"] <= 1.0
    # shape dims join counts pinned by test_cascade_validation
    dims = payload["cascade_shape_spearman"]
    assert dims["magnitude"]["n"] == 5
    assert dims["weeks_to_peak"]["n"] == 15
    assert dims["recovery_weeks"]["n"] == 11
    # the naive model must not carry rank metrics
    assert payload["models"]["NaivePersistence"]["spearman"] is None
