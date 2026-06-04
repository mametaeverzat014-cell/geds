"""Tests for the ranking-aware evaluation metrics in app.core.metrics.

These are standard rank/retrieval metrics, so where a reference implementation
exists in SciPy (Spearman, Kendall tau-b) we assert numerical agreement with
it. NDCG, Precision@k and Top-K overlap are checked against hand-computed
values and their defining edge cases.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats

from app.core.metrics import (
    kendall_tau,
    ndcg_at_k,
    precision_at_k,
    spearman_rho,
    top_k_overlap,
)


# ─────────────────────────── Spearman rho ───────────────────────────────────


def test_spearman_perfect_monotonic():
    pred = [1.0, 2.0, 3.0, 4.0, 5.0]
    obs = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert spearman_rho(pred, obs) == pytest.approx(1.0)


def test_spearman_perfect_anti_monotonic():
    pred = [1.0, 2.0, 3.0, 4.0, 5.0]
    obs = [50.0, 40.0, 30.0, 20.0, 10.0]
    assert spearman_rho(pred, obs) == pytest.approx(-1.0)


def test_spearman_matches_scipy_random():
    rng = np.random.default_rng(0)
    for _ in range(20):
        a = rng.normal(size=15)
        b = rng.normal(size=15)
        assert spearman_rho(a, b) == pytest.approx(float(stats.spearmanr(a, b).statistic))


def test_spearman_matches_scipy_with_ties():
    a = [1.0, 1.0, 2.0, 3.0, 3.0, 3.0, 4.0]
    b = [5.0, 6.0, 6.0, 7.0, 7.0, 8.0, 9.0]
    assert spearman_rho(a, b) == pytest.approx(float(stats.spearmanr(a, b).statistic))


def test_spearman_degenerate_returns_nan():
    assert math.isnan(spearman_rho([1.0], [2.0]))          # n < 2
    assert math.isnan(spearman_rho([3.0, 3.0, 3.0], [1.0, 2.0, 3.0]))  # zero variance


def test_spearman_length_mismatch_raises():
    with pytest.raises(ValueError):
        spearman_rho([1.0, 2.0], [1.0])


# ─────────────────────────── Kendall tau-b ──────────────────────────────────


def test_kendall_perfect_concordant():
    assert kendall_tau([1.0, 2.0, 3.0, 4.0], [9.0, 8.5, 8.0, 1.0]) == pytest.approx(-1.0)
    assert kendall_tau([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]) == pytest.approx(1.0)


def test_kendall_matches_scipy_random():
    rng = np.random.default_rng(1)
    for _ in range(20):
        a = rng.normal(size=12)
        b = rng.normal(size=12)
        assert kendall_tau(a, b) == pytest.approx(float(stats.kendalltau(a, b).statistic))


def test_kendall_matches_scipy_with_ties():
    a = [1.0, 1.0, 2.0, 2.0, 3.0, 4.0, 4.0]
    b = [2.0, 3.0, 3.0, 3.0, 1.0, 5.0, 5.0]
    assert kendall_tau(a, b) == pytest.approx(float(stats.kendalltau(a, b).statistic))


def test_kendall_degenerate_returns_nan():
    assert math.isnan(kendall_tau([1.0], [2.0]))
    assert math.isnan(kendall_tau([2.0, 2.0, 2.0], [1.0, 2.0, 3.0]))  # all tied -> denom 0


# ─────────────────────────── NDCG@k ─────────────────────────────────────────


def test_ndcg_perfect_ranking_is_one():
    obs = [3.0, 2.0, 1.0, 0.0]
    pred = [0.9, 0.8, 0.7, 0.6]  # same order as obs
    assert ndcg_at_k(pred, obs, k=4) == pytest.approx(1.0)


def test_ndcg_hand_computed_reversed():
    # obs gains, predicted ranking exactly reverses the ideal order.
    obs = np.array([3.0, 2.0, 1.0, 0.0])
    pred = np.array([0.1, 0.2, 0.3, 0.4])  # ranks worst-first
    discounts = 1.0 / np.log2(np.arange(2, 6))
    # pred order picks indices [3,2,1,0] -> gains [0,1,2,3]
    dcg = float(np.sum(np.array([0.0, 1.0, 2.0, 3.0]) * discounts))
    idcg = float(np.sum(np.array([3.0, 2.0, 1.0, 0.0]) * discounts))
    assert ndcg_at_k(pred, obs, k=4) == pytest.approx(dcg / idcg)


def test_ndcg_k_clamped_and_truncated():
    obs = [10.0, 5.0, 1.0]
    pred = [3.0, 2.0, 1.0]
    assert ndcg_at_k(pred, obs, k=99) == pytest.approx(1.0)  # k clamps to n
    # k=1: dcg = obs[argmax pred] = 10; idcg = max obs = 10 -> 1.0
    assert ndcg_at_k(pred, obs, k=1) == pytest.approx(1.0)


def test_ndcg_all_zero_gain_is_nan():
    assert math.isnan(ndcg_at_k([3.0, 2.0, 1.0], [0.0, 0.0, 0.0], k=3))


def test_ndcg_invalid_args():
    assert math.isnan(ndcg_at_k([1.0, 2.0], [1.0, 2.0], k=0))
    assert math.isnan(ndcg_at_k([], [], k=3))
    with pytest.raises(ValueError):
        ndcg_at_k([1.0, 2.0], [-1.0, 2.0], k=2)  # negative gain


# ─────────────────────────── Precision@k ────────────────────────────────────


def test_precision_perfect():
    pred = [5.0, 4.0, 3.0, 2.0, 1.0]
    obs = [9.0, 8.0, 7.0, 0.0, 0.0]  # top-2 by both = {0,1}
    assert precision_at_k(pred, obs, k=2) == pytest.approx(1.0)


def test_precision_partial():
    pred = [5.0, 4.0, 3.0, 2.0, 1.0]   # top-2 pred = {0,1}
    obs = [0.0, 9.0, 8.0, 1.0, 2.0]    # top-2 obs  = {1,2}
    assert precision_at_k(pred, obs, k=2) == pytest.approx(0.5)


def test_precision_invalid_args():
    assert math.isnan(precision_at_k([1.0], [1.0], k=0))
    assert math.isnan(precision_at_k([], [], k=2))


# ─────────────────────────── Top-K overlap (Jaccard) ────────────────────────


def test_top_k_overlap_identical():
    pred = [5.0, 4.0, 3.0, 2.0, 1.0]
    obs = [50.0, 40.0, 30.0, 20.0, 10.0]
    assert top_k_overlap(pred, obs, k=3) == pytest.approx(1.0)


def test_top_k_overlap_disjoint():
    pred = [5.0, 4.0, 0.0, 0.0]   # top-2 = {0,1}
    obs = [0.0, 0.0, 5.0, 4.0]    # top-2 = {2,3}
    assert top_k_overlap(pred, obs, k=2) == pytest.approx(0.0)


def test_top_k_overlap_partial_jaccard():
    pred = [5.0, 4.0, 3.0, 2.0, 1.0]  # top-2 = {0,1}
    obs = [0.0, 9.0, 8.0, 1.0, 2.0]   # top-2 = {1,2}
    # intersection {1} = 1, union {0,1,2} = 3 -> 1/3
    assert top_k_overlap(pred, obs, k=2) == pytest.approx(1.0 / 3.0)


def test_top_k_overlap_invalid_args():
    assert math.isnan(top_k_overlap([1.0], [1.0], k=0))
    assert math.isnan(top_k_overlap([], [], k=2))
