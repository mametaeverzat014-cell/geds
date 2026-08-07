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
    assert dims["magnitude"]["n"] == 6   # +ukraine-war-harness-2022 (see cascade_validation)
    assert dims["weeks_to_peak"]["n"] == 15
    assert dims["recovery_weeks"]["n"] == 11
    # the naive model must not carry rank metrics
    assert payload["models"]["NaivePersistence"]["spearman"] is None


# ─────────────────────────── Holm–Bonferroni ────────────────────────────────
# holm_adjust became load-bearing in 2026-08: the model leaderboard, the
# ablation table and the ML probe all decide significance from its output, so a
# silent bug here would corrupt every published significance claim at once.


def test_holm_matches_hand_computed_reference():
    """Textbook step-down: sorted p_(i) scaled by (m - i), then made monotone."""
    from app.core.significance import holm_adjust

    # m=4, sorted raw p: 0.005, 0.011, 0.02, 0.30
    #   0.005*4 = 0.020
    #   0.011*3 = 0.033
    #   0.020*2 = 0.040
    #   0.300*1 = 0.300
    out = holm_adjust({"a": 0.02, "b": 0.005, "c": 0.30, "d": 0.011})
    assert out["b"] == pytest.approx(0.020)
    assert out["d"] == pytest.approx(0.033)
    assert out["a"] == pytest.approx(0.040)
    assert out["c"] == pytest.approx(0.300)


def test_holm_enforces_monotonicity():
    """A later test may never receive a smaller adjusted p than an earlier one."""
    from app.core.significance import holm_adjust

    # Raw 0.04*3 = 0.12 but 0.03*2 = 0.06 < 0.12, so the step-down must carry
    # the running maximum forward rather than report 0.06.
    out = holm_adjust({"x": 0.04, "y": 0.03, "z": 0.02})
    ordered = [out["z"], out["y"], out["x"]]
    assert ordered == sorted(ordered), f"non-monotone Holm output: {ordered}"
    assert out["y"] >= out["z"]
    assert out["x"] >= out["y"]


def test_holm_clips_at_one_and_is_identity_for_single_test():
    from app.core.significance import holm_adjust

    assert holm_adjust({"only": 0.031})["only"] == pytest.approx(0.031)
    for v in holm_adjust({"a": 0.9, "b": 0.8, "c": 0.7}).values():
        assert v <= 1.0


def test_holm_never_reduces_a_p_value():
    """Correction may only make a claim harder to sustain, never easier."""
    from app.core.significance import holm_adjust

    raw = {"a": 0.001, "b": 0.049, "c": 0.2, "d": 0.5, "e": 0.9}
    adj = holm_adjust(raw)
    for k, p in raw.items():
        assert adj[k] >= p - 1e-12, f"{k}: Holm {adj[k]} < raw {p}"


def test_published_leaderboard_has_no_significant_pair_after_holm():
    """Regression lock on the paper's central negative claim.

    If a future change makes some pair significant after correction, that is a
    real finding and must be reviewed explicitly — not absorbed silently.
    """
    import json
    from pathlib import Path

    art = (Path(__file__).resolve().parents[1]
           / "data" / "calibration" / "significance.json")
    payload = json.loads(art.read_text(encoding="utf-8"))
    assert payload["n_pairwise_significant_after_holm"] == 0
    for key, entry in payload["pairwise"].items():
        assert entry["significant_at_05_holm"] is False, key
        assert entry["p_holm_mae_two_sided"] >= entry["p_perm_mae_two_sided"]
