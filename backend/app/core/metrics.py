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
