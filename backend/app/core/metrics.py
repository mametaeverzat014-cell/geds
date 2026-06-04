"""Novel and standard metrics for the cascade propagation engine.

Two original contributions:

* **Cascade Severity Index (CSI)** — a graph-weighted scalar that combines per-node shock,
  centrality, dependency exposure, intrinsic sensitivity, and expected recovery delay:

        CSI(t) = (1/N) · Σ_i  shock_i(t) · centrality_i · dep_exposure_i
                        · vulnerability_i · (1 − resilience_i) · recovery_weight_i

* **Economic Contagion Velocity (ECV)** — the rate at which the cascade frontier expands
  over the network. Two variants:

        ECV(t)      = |new_affected(t)| / N                    ← node-count velocity
        ECV_geo(t)  = mean hop-distance from origin, over newly affected nodes at t

Financial intelligence layer (added with the vectorized engine refactor):

* **default_probability** — sigmoid risk score that climbs once a node has been
  above 40% output loss for more than 6 consecutive weeks (technical-default proxy).

* **projected_market_cap_loss_usd** — DCF-style equity hit per node, combining the
  direct earnings drag (output loss × margin × P/E multiple) and the inflation
  margin/discount-rate drag.  Calibrated coefficients: MARGIN=0.12, PE_MULTIPLE=18,
  INFLATION_MARGIN_HIT=0.30.  See compute_market_cap_loss().
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np

from .types import (
    CountryRisk,
    Frame,
    Industry,
    SectorFragility,
    SimulationSummary,
)

if TYPE_CHECKING:
    from .graph import CompiledGraph
    from .propagation import EngineState


def compute_csi(state: "EngineState", g: "CompiledGraph") -> float:
    """Cascade Severity Index at the current step. Always in [0, 1]-ish range,
    not strictly bounded but well-behaved for our parameter regime."""

    max_recovery = max(float(g.recovery_delay.max()), 1.0)
    recovery_w = g.recovery_delay / max_recovery
    sensitivity = g.vulnerability * (1.0 - g.resilience)

    per_node = (
        state.shock
        * g.centrality
        * g.inbound_dep_sum
        * sensitivity
        * recovery_w
    )
    # Scale by 10 because per-node terms are products of [0,1] values and would otherwise sit very low.
    return float(per_node.sum() / max(1, g.n) * 10.0)


def compute_ecv(affected_now: np.ndarray, affected_prev: np.ndarray) -> float:
    """Count-velocity: new affected nodes this step, normalized by network size."""

    new_affected = int(np.logical_and(affected_now, ~affected_prev).sum())
    return new_affected / max(1, affected_now.size)


def compute_ecv_geo(
    affected_first_week: np.ndarray,
    t: int,
    shortest_path: dict[str, int],
    g: "CompiledGraph",
) -> float:
    """Geodesic velocity: average hop distance reached this step from the primary origin.

    Returns 0 if no nodes were newly affected this step or if the shortest-path map is empty.
    Units: hops/week.
    """

    if not shortest_path:
        return 0.0
    newly_idx = np.where(affected_first_week == t)[0]
    if newly_idx.size == 0:
        return 0.0
    hops = [shortest_path.get(g.node_ids[i], 0) for i in newly_idx]
    return float(np.mean(hops)) if hops else 0.0


def country_risk_scores(frames: list[Frame], g: "CompiledGraph") -> list[CountryRisk]:
    """Aggregate per-country risk scores from the full frame trajectory."""

    snapshot = g.snapshot
    country_nodes: dict[str, list[int]] = defaultdict(list)
    for i, node in enumerate(snapshot.nodes):
        if node.country:
            country_nodes[node.country].append(i)

    # Build (N, T) arrays for fast aggregation.
    T = len(frames)
    N = g.n
    shock_arr = np.zeros((N, T))
    infl_arr = np.zeros((N, T))
    unemp_arr = np.zeros((N, T))
    output_arr = np.zeros((N, T))

    for t, f in enumerate(frames):
        for nf in f.nodes:
            i = g.index[nf.id]
            shock_arr[i, t] = nf.shock
            infl_arr[i, t] = nf.inflation_pressure
            unemp_arr[i, t] = nf.unemployment_risk
            output_arr[i, t] = nf.output_loss

    results: list[CountryRisk] = []
    for iso3, idxs in country_nodes.items():
        gdp_w = g.gdp_usd[idxs]
        gdp_total = gdp_w.sum()
        weights = gdp_w / gdp_total if gdp_total > 0 else np.ones(len(idxs)) / len(idxs)

        country_shock = np.average(shock_arr[idxs], axis=0, weights=weights)
        country_infl = np.average(infl_arr[idxs], axis=0, weights=weights)
        country_unemp = np.average(unemp_arr[idxs], axis=0, weights=weights)
        country_output = np.average(output_arr[idxs], axis=0, weights=weights)

        peak_shock = float(country_shock.max())
        peak_infl = float(country_infl.max())
        peak_unemp = float(country_unemp.max())

        # Expected recovery: weeks from peak shock until shock falls below 0.1.
        if peak_shock < 0.1:
            recovery_weeks = 0.0
        else:
            peak_idx = int(country_shock.argmax())
            below = np.where(country_shock[peak_idx:] < 0.1)[0]
            recovery_weeks = float(below[0]) if below.size > 0 else float(T - peak_idx)

        risk_score = float(
            0.45 * peak_shock
            + 0.25 * peak_infl
            + 0.20 * peak_unemp
            + 0.10 * np.mean(country_output)
        )
        results.append(
            CountryRisk(
                iso3=iso3,
                risk_score=round(risk_score, 4),
                peak_shock=round(peak_shock, 4),
                peak_inflation=round(peak_infl, 4),
                peak_unemployment=round(peak_unemp, 4),
                expected_recovery_weeks=round(recovery_weeks, 1),
            )
        )

    results.sort(key=lambda r: r.risk_score, reverse=True)
    return results


def sector_fragility_scores(frames: list[Frame], g: "CompiledGraph") -> list[SectorFragility]:
    """Aggregate per-industry fragility from peak shock × centrality × elasticity."""

    snapshot = g.snapshot
    industry_nodes: dict[Industry, list[int]] = defaultdict(list)
    for i, node in enumerate(snapshot.nodes):
        if node.industry:
            industry_nodes[node.industry].append(i)

    # Peak shock per node across the run.
    peak_shock_per_node = np.zeros(g.n)
    for f in frames:
        for nf in f.nodes:
            i = g.index[nf.id]
            peak_shock_per_node[i] = max(peak_shock_per_node[i], nf.shock)

    results: list[SectorFragility] = []
    for industry, idxs in industry_nodes.items():
        idxs_arr = np.array(idxs, dtype=int)
        peaks = peak_shock_per_node[idxs_arr]
        cent = g.centrality[idxs_arr]
        elas = g.elasticity[idxs_arr]

        fragility = float((peaks * cent * elas).mean()) if idxs else 0.0
        most_exposed_idx = int(idxs_arr[int(peaks.argmax())])
        most_exposed_country = snapshot.nodes[most_exposed_idx].country or "—"
        expected_disruption = float((peaks * elas).mean()) if idxs else 0.0

        results.append(
            SectorFragility(
                industry=industry,
                fragility_score=round(fragility, 4),
                most_exposed_country=most_exposed_country,
                expected_disruption=round(expected_disruption, 4),
            )
        )

    results.sort(key=lambda r: r.fragility_score, reverse=True)
    return results


def build_summary(
    frames: list[Frame], state: "EngineState", g: "CompiledGraph"
) -> SimulationSummary:
    """Build a SimulationSummary from a finished simulation."""

    if not frames:
        raise ValueError("Cannot build summary from zero frames")

    csis = np.array([f.csi for f in frames])
    ecvs = np.array([f.ecv for f in frames])

    # Country-aggregated peak inflation and peak GDP impact.
    peak_infl_country: tuple[str, float] = ("—", 0.0)
    peak_gdp_country: tuple[str, float] = ("—", 0.0)

    country_idx: dict[str, list[int]] = defaultdict(list)
    for i, node in enumerate(g.snapshot.nodes):
        if node.country:
            country_idx[node.country].append(i)

    for iso3, idxs in country_idx.items():
        gdp_w = g.gdp_usd[np.array(idxs)]
        gdp_total = gdp_w.sum()
        if gdp_total <= 0:
            continue
        peak_infl = 0.0
        peak_gdp = 0.0
        for f in frames:
            infl = 0.0
            output_loss = 0.0
            for i in idxs:
                nf = f.nodes[i]
                infl += nf.inflation_pressure * g.gdp_usd[i]
                output_loss += nf.output_loss * g.gdp_usd[i]
            infl /= gdp_total
            output_loss /= gdp_total
            peak_infl = max(peak_infl, infl)
            peak_gdp = max(peak_gdp, output_loss)
        if peak_infl > peak_infl_country[1]:
            peak_infl_country = (iso3, float(peak_infl))
        if peak_gdp > peak_gdp_country[1]:
            peak_gdp_country = (iso3, float(peak_gdp))

    affected_country_count = sum(
        1
        for iso3, idxs in country_idx.items()
        if any(state.shock[i] > 0.1 for i in idxs)
    )

    # Global recovery weeks: how long after peak CSI did CSI return below 0.1·peak.
    if csis.max() > 0:
        peak_t = int(csis.argmax())
        threshold = 0.1 * csis.max()
        below = np.where(csis[peak_t:] < threshold)[0]
        global_recovery = float(below[0]) if below.size > 0 else float(len(frames) - peak_t)
    else:
        global_recovery = 0.0

    total_loss = float(sum(f.total_output_loss for f in frames))

    return SimulationSummary(
        peak_csi=round(float(csis.max()), 4),
        peak_ecv=round(float(ecvs.max()), 4),
        final_csi=round(float(csis[-1]), 4),
        total_output_loss_usd=round(total_loss, 2),
        max_inflation_country=peak_infl_country,
        max_gdp_impact_country=peak_gdp_country,
        affected_country_count=affected_country_count,
        global_recovery_weeks=round(global_recovery, 1),
        country_risk=country_risk_scores(frames, g),
        sector_fragility=sector_fragility_scores(frames, g),
    )


# ───────────────────────── financial intelligence ───────────────────────────


# Calibration constants for the equity-valuation model.
# MARGIN: blended industrial EBIT margin (~12%).
# INFLATION_MARGIN_HIT: each unit of cumulative inflation_pressure erodes
#   margins by ~30% (input cost squeeze + discount-rate drag).
# PE_MULTIPLE: typical equity multiple on lost earnings (~18×).
FIN_MARGIN              = 0.12
FIN_INFLATION_MARGIN_HIT = 0.30
FIN_PE_MULTIPLE         = 18.0

# Technical-default thresholds.
DISTRESS_OUTPUT_LOSS_PCT = 0.40    # output_loss above this counts as distress
DISTRESS_WEEK_THRESHOLD  = 6       # weeks of sustained distress before sharp risk spike
DEFAULT_SIGMOID_SCALE    = 2.0     # how steep the risk curve climbs past the threshold


def compute_default_probability(
    weeks_above_distress: np.ndarray,
    week_threshold: int = DISTRESS_WEEK_THRESHOLD,
) -> np.ndarray:
    """Vectorized technical-default probability.

    Sigmoid centred on `week_threshold` consecutive weeks of sustained distress.
    Per-node thresholds (endogenous, based on inventory + vulnerability) are
    applied upstream when computing `weeks_above_distress`.
    """
    excess = weeks_above_distress.astype(np.float64) - week_threshold
    return 1.0 / (1.0 + np.exp(-excess / DEFAULT_SIGMOID_SCALE))


def compute_market_cap_loss(
    cumulative_output_loss_usd: np.ndarray,    # (I, N) or (N,) — sum of output_loss × (gdp/52)
    cumulative_inflation_usd: np.ndarray,      # (I, N) or (N,) — sum of inflation_pressure × (gdp/52)
) -> np.ndarray:
    """Projected market-cap impact per node, in USD.

    Two-component DCF approximation:
        direct  = cumulative_output_loss_usd × MARGIN × PE_MULTIPLE
        infl    = cumulative_inflation_usd  × INFLATION_MARGIN_HIT × PE_MULTIPLE
        total   = direct + infl

    Result shape matches inputs.  Broadcasts cleanly across an iteration axis.
    """
    direct = cumulative_output_loss_usd * (FIN_MARGIN * FIN_PE_MULTIPLE)
    infl   = cumulative_inflation_usd  * (FIN_INFLATION_MARGIN_HIT * FIN_PE_MULTIPLE)
    return direct + infl


# ───────────────────────── vectorized CSI ───────────────────────────────────


def compute_csi_batch(
    shock_batch: np.ndarray,        # (I, N)
    g: "CompiledGraph",
) -> np.ndarray:
    """Vectorized CSI across an iteration batch.  Returns shape (I,)."""
    max_recovery = max(float(g.recovery_delay.max()), 1.0)
    recovery_w = g.recovery_delay / max_recovery
    sensitivity = g.vulnerability * (1.0 - g.resilience)
    # node weight vector, shape (N,)
    node_w = g.centrality * g.inbound_dep_sum * sensitivity * recovery_w
    # per-iteration weighted sum, shape (I,)
    return (shock_batch * node_w[np.newaxis, :]).sum(axis=1) / max(1, g.n) * 10.0


def compute_ecv_batch(
    affected_now: np.ndarray,        # (I, N) bool
    affected_prev: np.ndarray,       # (I, N) bool
) -> np.ndarray:
    """Vectorized count-ECV per iteration.  Returns shape (I,)."""
    new_affected = (affected_now & ~affected_prev).sum(axis=1)
    return new_affected / max(1, affected_now.shape[1])


# ───────────────────────── ranking-aware evaluation metrics ──────────────────
#
# Standard, citable rank/retrieval metrics for benchmark evaluation. These are
# textbook definitions (NOT novel contributions): Spearman (1904), Kendall
# tau-b (1945), NDCG (Järvelin & Kekäläinen 2002), Precision@k and Jaccard
# overlap (standard IR). They complement the error metrics (MAE/RMSE/R²) by
# scoring whether a model ranks events in the correct order — the relevant
# question when absolute magnitudes are noisy but relative severity matters.
#
# Convention throughout: `pred` and `obs` are 1-D array-likes of equal length;
# higher value = more severe / higher rank. All functions return float("nan")
# for degenerate inputs (n < 2, zero variance, empty top-k) rather than raising.


def _pearson_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation with NaN on degenerate input. Local copy so this
    module has no dependency on benchmark.py."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.size < 2 or np.std(a) == 0.0 or np.std(b) == 0.0:
        return float("nan")
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a @ a) * (b @ b)))
    return float((a @ b) / denom) if denom > 0 else float("nan")


def _average_ranks(x: np.ndarray) -> np.ndarray:
    """Fractional (tie-averaged) ranks, 0-indexed. Tied values share the mean
    of the positions they span — the correct convention for Spearman/tau-b."""
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    order = np.argsort(x, kind="mergesort")
    sx = x[order]
    ranks_sorted = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sx[j + 1] == sx[i]:
            j += 1
        ranks_sorted[i : j + 1] = (i + j) / 2.0
        i = j + 1
    ranks = np.empty(n, dtype=np.float64)
    ranks[order] = ranks_sorted
    return ranks


def _tie_pairs(x: np.ndarray) -> int:
    """Number of tied pairs Σ t(t-1)/2 over equal-value groups."""
    _, counts = np.unique(np.asarray(x), return_counts=True)
    return int(np.sum(counts * (counts - 1) // 2))


def spearman_rho(pred, obs) -> float:
    """Spearman rank correlation ρ ∈ [-1, 1], tie-corrected via average ranks.

    Equivalent to the Pearson correlation of the fractional ranks. Returns NaN
    if fewer than 2 points or either ranking has zero variance (all tied).
    """
    pred = np.asarray(pred, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)
    if pred.size != obs.size:
        raise ValueError("pred and obs must have equal length")
    if pred.size < 2:
        return float("nan")
    return _pearson_corr(_average_ranks(pred), _average_ranks(obs))


def kendall_tau(pred, obs) -> float:
    """Kendall's tau-b ∈ [-1, 1], the tie-adjusted rank-correlation coefficient.

        tau_b = (C - D) / sqrt((n0 - n1) * (n0 - n2))

    where C/D are concordant/discordant pairs, n0 = n(n-1)/2, and n1/n2 are the
    tied-pair counts in pred/obs respectively. Matches scipy.stats.kendalltau
    (variant 'b'). Returns NaN for n < 2 or a zero denominator.
    """
    pred = np.asarray(pred, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)
    if pred.size != obs.size:
        raise ValueError("pred and obs must have equal length")
    n = pred.size
    if n < 2:
        return float("nan")
    concordant = 0
    discordant = 0
    for i in range(n):
        da = pred[i] - pred[i + 1 :]
        db = obs[i] - obs[i + 1 :]
        prod = da * db
        concordant += int(np.count_nonzero(prod > 0))
        discordant += int(np.count_nonzero(prod < 0))
    n0 = n * (n - 1) // 2
    n1 = _tie_pairs(pred)
    n2 = _tie_pairs(obs)
    denom = float(np.sqrt((n0 - n1) * (n0 - n2)))
    return float((concordant - discordant) / denom) if denom > 0 else float("nan")


def ndcg_at_k(pred, obs, k: int) -> float:
    """Normalized Discounted Cumulative Gain at rank k, in [0, 1].

    Items are ranked by `pred`; the gain accrued at each position is the
    corresponding `obs` value, discounted by 1/log2(position+1). Normalized by
    the ideal DCG (ranking by `obs`). Relevance/gains (`obs`) must be
    non-negative — true for output-loss fractions. Returns NaN if k <= 0,
    inputs are empty, or the ideal DCG is 0 (all gains zero).
    """
    pred = np.asarray(pred, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)
    if pred.size != obs.size:
        raise ValueError("pred and obs must have equal length")
    n = pred.size
    if n == 0 or k <= 0:
        return float("nan")
    if np.any(obs < 0):
        raise ValueError("ndcg_at_k requires non-negative obs (gains)")
    k = min(k, n)
    discounts = 1.0 / np.log2(np.arange(2, k + 2))
    pred_order = np.argsort(-pred, kind="mergesort")[:k]
    dcg = float(np.sum(obs[pred_order] * discounts))
    ideal_order = np.argsort(-obs, kind="mergesort")[:k]
    idcg = float(np.sum(obs[ideal_order] * discounts))
    return dcg / idcg if idcg > 0 else float("nan")


def precision_at_k(pred, obs, k: int) -> float:
    """Precision@k: fraction of the top-k predicted items that are also among
    the top-k items by observed severity, in [0, 1].

    Returns NaN if k <= 0 or inputs are empty. k is clamped to n.
    """
    pred = np.asarray(pred, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)
    if pred.size != obs.size:
        raise ValueError("pred and obs must have equal length")
    n = pred.size
    if n == 0 or k <= 0:
        return float("nan")
    k = min(k, n)
    top_pred = set(np.argsort(-pred, kind="mergesort")[:k].tolist())
    top_obs = set(np.argsort(-obs, kind="mergesort")[:k].tolist())
    return len(top_pred & top_obs) / k


def top_k_overlap(pred, obs, k: int) -> float:
    """Jaccard overlap of the top-k predicted and top-k observed sets, in
    [0, 1]: |A ∩ B| / |A ∪ B|.

    Returns NaN if k <= 0 or inputs are empty. k is clamped to n.
    """
    pred = np.asarray(pred, dtype=np.float64)
    obs = np.asarray(obs, dtype=np.float64)
    if pred.size != obs.size:
        raise ValueError("pred and obs must have equal length")
    n = pred.size
    if n == 0 or k <= 0:
        return float("nan")
    k = min(k, n)
    top_pred = set(np.argsort(-pred, kind="mergesort")[:k].tolist())
    top_obs = set(np.argsort(-obs, kind="mergesort")[:k].tolist())
    union = top_pred | top_obs
    return len(top_pred & top_obs) / len(union) if union else float("nan")
