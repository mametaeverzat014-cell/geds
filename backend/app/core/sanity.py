"""Sanity caps on simulation outputs.

A 12-week localized chokepoint shock should NOT produce a $15T global loss.
This module enforces realistic bounds and exposes a penalty function for the
Bayesian calibrator's objective.

Anchors (all in 2019 USD):
    GLOBAL_GDP_2019        87.6 T   World Bank
    GLOBAL_GOODS_TRADE     19.5 T   WTO World Trade Statistical Review 2020
    SEMI_INDUSTRY_VALUE     0.45 T  SEMI annual report 2020
    AUTO_INDUSTRY_VALUE     2.86 T  OICA 2019 production × avg unit price
"""

from __future__ import annotations

import numpy as np

# Global anchors (2019)
GLOBAL_GDP_USD            = 87.6e12
GLOBAL_GOODS_TRADE_USD    = 19.5e12
SEMICONDUCTOR_INDUSTRY_USD = 0.45e12
AUTOMOTIVE_INDUSTRY_USD    = 2.86e12
ELECTRONICS_INDUSTRY_USD   = 4.40e12

# Calibrated rule-of-thumb caps (fraction of horizon-prorated global GDP)
DEFAULT_MAX_EVENT_LOSS_FRACTION = 0.15   # no single event > 15% of horizon-prorated global GDP
DEFAULT_MAX_PER_COUNTRY_FRACTION = 0.60  # no country loses > 60% of its horizon GDP
DEFAULT_MAX_PER_SECTOR_FRACTION  = 0.40  # no sector loses > 40% of its global value-add


def horizon_global_gdp(horizon_weeks: int) -> float:
    """Pro-rate global GDP by simulation horizon length."""
    return GLOBAL_GDP_USD * (horizon_weeks / 52.0)


def sanity_penalty(
    total_loss_usd: float,
    horizon_weeks: int,
    max_fraction: float = DEFAULT_MAX_EVENT_LOSS_FRACTION,
) -> float:
    """Smooth penalty term for the calibrator objective.

    Returns 0 if the loss is within sanity bounds, scales quadratically when
    the cap is exceeded so the optimizer feels the gradient and steers away.
    """
    cap = horizon_global_gdp(horizon_weeks) * max_fraction
    if total_loss_usd <= cap:
        return 0.0
    overshoot = (total_loss_usd - cap) / cap
    return overshoot * overshoot


def apply_per_node_caps(
    per_node_cumulative_loss_usd: np.ndarray,    # (I, N) or (N,)
    gdp_usd: np.ndarray,                         # (N,)
    horizon_weeks: int,
    max_fraction: float = DEFAULT_MAX_PER_COUNTRY_FRACTION,
) -> np.ndarray:
    """Cap per-node cumulative loss at max_fraction of node's horizon-prorated GDP.

    Returns a new array with the cap applied; the original is not mutated.
    Useful for post-simulation reporting when raw model output exceeds plausibility.
    """
    horizon_fraction = horizon_weeks / 52.0
    cap_per_node = gdp_usd * horizon_fraction * max_fraction
    return np.minimum(per_node_cumulative_loss_usd, cap_per_node)


def is_within_sanity(
    total_loss_usd: float,
    horizon_weeks: int,
    max_fraction: float = DEFAULT_MAX_EVENT_LOSS_FRACTION,
) -> tuple[bool, float, float]:
    """Returns (within_bounds, loss, cap) — for the backtest/track-record report."""
    cap = horizon_global_gdp(horizon_weeks) * max_fraction
    return total_loss_usd <= cap, total_loss_usd, cap


__all__ = [
    "GLOBAL_GDP_USD",
    "GLOBAL_GOODS_TRADE_USD",
    "SEMICONDUCTOR_INDUSTRY_USD",
    "AUTOMOTIVE_INDUSTRY_USD",
    "ELECTRONICS_INDUSTRY_USD",
    "horizon_global_gdp",
    "sanity_penalty",
    "apply_per_node_caps",
    "is_within_sanity",
]
