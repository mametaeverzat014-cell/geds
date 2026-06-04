"""Reproducibility lockdown for the benchmark harness (WP1).

These tests are the automated guard that the benchmark is deterministic and
that its published numbers do not drift silently. They assert three things:

1. The engine config used by the benchmark is pinned (no RNG path active).
2. Two back-to-back runs produce byte-identical scores (determinism).
3. The scored numbers match a frozen golden snapshot (regression lock). If a
   code change legitimately changes the results, update GOLDEN below in the
   same commit — that makes every numeric change explicit and reviewable.
"""

from __future__ import annotations

import pytest

from app.core.benchmark import (
    BENCHMARK_CONFIG,
    run_benchmark,
    scored_payload,
)

# Frozen expected scores (clean N=8 hand-authored event set). Captured
# 2026-06-04 from the deterministic harness. MAE is the headline metric; the
# GEDS Spearman value locks the tie-corrected rank correlation; persistence
# NDCG is None because a constant predictor has no ranking.
GOLDEN = {
    "SEIRS-Bullwhip-Hysteresis (GEDS)": {"mae": 0.0248, "rmse": 0.0361, "spearman": 0.8264},
    "Leontief (input-output equilibrium)": {"mae": 0.0301, "rmse": 0.0478},
    "Linear Diffusion (network)": {"mae": 0.0152, "rmse": 0.0179, "spearman": 0.8503},
    "Naive Persistence (predict mean)": {"mae": 0.0305, "rmse": 0.0370},
}


def test_benchmark_config_is_pinned():
    # stochastic_sigma == 0 means the SEIRS engine takes no RNG draws.
    assert BENCHMARK_CONFIG.stochastic_sigma == 0.0
    assert BENCHMARK_CONFIG.seed == 0


def test_benchmark_is_deterministic():
    a = scored_payload(run_benchmark())
    b = scored_payload(run_benchmark())
    assert a == b, "two benchmark runs produced different scores"


def test_benchmark_matches_golden_snapshot():
    models = {m.model: m for m in run_benchmark().models}
    assert set(models) == set(GOLDEN), "model roster changed; update GOLDEN"
    for name, expected in GOLDEN.items():
        m = models[name]
        for field, value in expected.items():
            assert getattr(m, field) == pytest.approx(value, abs=1e-4), (
                f"{name}.{field} drifted: got {getattr(m, field)}, expected {value}"
            )


def test_persistence_has_no_ranking_metrics():
    models = {m.model: m for m in run_benchmark().models}
    persistence = models["Naive Persistence (predict mean)"]
    # A constant predictor cannot rank: correlations are 0, NDCG is undefined.
    assert persistence.spearman == 0.0
    assert persistence.kendall == 0.0
    assert persistence.ndcg_at_k is None


def test_winner_is_linear_diffusion():
    # Honest baseline result on the clean set: the simple network-diffusion
    # baseline wins every metric; GEDS does not beat it. This is locked so a
    # future "win" cannot appear without a deliberate, reviewed change.
    report = run_benchmark()
    assert report.winner_by_mae == "Linear Diffusion (network)"
    assert report.winner_by_rmse == "Linear Diffusion (network)"
    assert report.winner_by_pearson == "Linear Diffusion (network)"
