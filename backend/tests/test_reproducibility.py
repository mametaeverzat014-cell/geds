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

# Frozen expected scores (clean N=21 hand-authored event set). Captured
# 2026-06-09 after the event-set expansion 8 → 21 (seed_data.HISTORICAL_EVENTS
# expansion batch). MAE is the headline metric; the GEDS Spearman value locks
# the tie-corrected rank correlation; persistence NDCG is None because a
# constant predictor has no ranking.
#
# Honest note on the expansion: on the old N=8 set GEDS scored Spearman 0.83;
# on N=21 it drops to 0.36 — the strong rank correlation was a small-sample
# artifact. Naive persistence now beats GEDS on MAE. This is locked here
# deliberately: any future improvement must show up as an explicit, reviewed
# change to these numbers.
GOLDEN = {
    "SEIRS-Bullwhip-Hysteresis (GEDS)": {"mae": 0.0191, "rmse": 0.0362, "spearman": 0.4212},
    "Leontief (input-output equilibrium)": {"mae": 0.0154, "rmse": 0.0301},
    "Linear Diffusion (network)": {"mae": 0.0112, "rmse": 0.0141, "spearman": 0.8001},
    "Naive Persistence (predict mean)": {"mae": 0.0168, "rmse": 0.0268},
}
# 2026-06-11: red-sea-crisis-2023 shock duration corrected 26 → 40 weeks
# based on MEASURED IMF PortWatch transit deficits (elevated 57+ weeks);
# see data/calibration/portwatch_validation.json. Tiny numeric drift in
# this snapshot comes from that single data-driven correction.
# 2026-06-10 graph-connectivity repair (same commit as these numbers):
# MYS:semiconductors gained its missing outbound edges, chokepoints gained
# carrier links with capacity-factor weights, Yantian event magnitude fixed
# to node-level convention. The repair improved EVERY model (linear diffusion
# MAE 0.0130 → 0.0111, GEDS 0.0216 → 0.0192) — evidence it is a genuine
# structural fix rather than GEDS-specific tuning.


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
    # Honest baseline result on the clean set (N=21): the simple network-
    # diffusion baseline wins every metric; GEDS does not beat it. This is
    # locked so a future "win" cannot appear without a deliberate, reviewed
    # change.
    report = run_benchmark()
    assert report.winner_by_mae == "Linear Diffusion (network)"
    assert report.winner_by_rmse == "Linear Diffusion (network)"
    assert report.winner_by_pearson == "Linear Diffusion (network)"
    assert report.winner_by_spearman == "Linear Diffusion (network)"
