"""SEIRS state machine with hysteresis and bullwhip — vectorized over an iteration axis.

States
------
    S = 0  Susceptible    — normal operation
    E = 1  Exposed        — inventory buffer absorbing shock, panic-buying upstream
    I = 2  Infected       — buffer exhausted, full disruption propagating
    R = 3  Recovering     — shock has receded but output capped at 70% (hysteresis)

Transitions (per week, applied AFTER the propagation step)
----------------------------------------------------------
    S → E : inbound > EXPOSURE_TRIGGER  AND  shock < 0.15
    E → I : buffer_weeks ≥ max_buffer   OR   shock ≥ 0.70  (hard override)
    I → R : shock < RECOVERY_THRESHOLD  AND  no active external forcing
    R → S : recovery_weeks ≥ recovery_delay  AND  shock < RECOVERY_THRESHOLD
    R → I : shock spikes back ≥ 0.50         (re-disrupted before recovery completes)

State modifiers (applied to the next propagation step)
------------------------------------------------------
    E: outbound_mask    = 0.10   (90% of outbound signal absorbed by buffer)
       bullwhip_factor  = 1.25   (panic-buying amplifies inbound 25%)
    R: outbound_mask    = 0.85   (returned mostly to normal supply)
       output_floor     = 0.30   (production capped at 70%; loss can't fall below 30%)

All public state arrays carry a leading iteration axis (I, N) so the engine can
broadcast the full Monte Carlo batch through a single vectorized loop.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ─────────────────────────── state codes ────────────────────────────────────
S_STATE = 0
E_STATE = 1
I_STATE = 2
R_STATE = 3

# ─────────────────────────── transition thresholds ──────────────────────────
EXPOSURE_TRIGGER   = 0.05
RECOVERY_THRESHOLD = 0.05
REROUTING_TRIGGER  = 0.30      # chokepoint shock above which rerouting surcharge kicks in
REENTRY_SHOCK      = 0.50      # R→I if shock spikes back above this

# ─────────────────────────── state modifiers ────────────────────────────────
E_OUTBOUND_LEAK   = 0.10
R_OUTBOUND_FACTOR = 0.85
R_OUTPUT_FLOOR    = 0.30        # 70% production cap → at least 30% output loss during R
E_BULLWHIP_FACTOR = 1.25        # +25% inbound dependency_weight for panic-buying

# ─────────────────────────── industry inventory defaults (weeks) ────────────
# Sources: IHS Markit (auto), SEMI/IPC (semi), Boeing/Airbus annual reports (aerospace).
INDUSTRY_INVENTORY_WEEKS: dict[str, int] = {
    "semiconductors": 10,
    "electronics":     7,
    "automotive":      5,
    "aerospace":      13,
    "shipping":        0,
    "energy":          3,
    "consumer_goods":  5,
}


@dataclass(slots=True)
class SEISState:
    """Vectorized SEIRS state for a batch of (iterations × nodes).

    All trajectory arrays have shape (I, N).  Static per-node arrays are (N,)
    and broadcast against the iteration axis on use.
    """

    # mutable trajectory state, shape (I, N)
    state: np.ndarray            # int8: 0=S, 1=E, 2=I, 3=R
    buffer_weeks: np.ndarray     # int16: weeks spent in E
    recovery_weeks: np.ndarray   # int16: weeks spent in R

    # static per-node caps, shape (N,)
    max_buffer: np.ndarray       # int16: inventory buffer depth
    recovery_delay: np.ndarray   # int16: weeks node must spend in R before returning to S

    # modifier arrays refreshed each week, shape (I, N)
    outbound_mask: np.ndarray    # float64: damping on this node's outbound shock signal
    bullwhip_factor: np.ndarray  # float64: amplification on this node's INBOUND impact
    output_floor: np.ndarray     # float64: lower bound on output_loss (R-state hysteresis)


def build_seis_state(
    nodes: list,
    n_iterations: int,
    n_nodes: int,
    inventory_scale: float = 1.0,
) -> SEISState:
    """Initialise SEIRS state for I iterations × N nodes.

    `inventory_scale` is a global multiplier on per-node inventory_weeks,
    exposed to the Bayesian calibrator so industry buffer depth can be tuned.
    """
    max_buffer = np.zeros(n_nodes, dtype=np.int16)
    recovery_delay = np.zeros(n_nodes, dtype=np.int16)

    for i, node in enumerate(nodes):
        if node.inventory_weeks is not None:
            raw = int(node.inventory_weeks)
        elif node.industry is not None:
            raw = INDUSTRY_INVENTORY_WEEKS.get(node.industry.value, 8)
        else:
            raw = 0
        max_buffer[i] = max(0, int(round(raw * inventory_scale)))

        recovery_delay[i] = max(1, int(round(node.recovery_delay_weeks)))

    I, N = n_iterations, n_nodes
    return SEISState(
        state=np.zeros((I, N), dtype=np.int8),
        buffer_weeks=np.zeros((I, N), dtype=np.int16),
        recovery_weeks=np.zeros((I, N), dtype=np.int16),
        max_buffer=max_buffer,
        recovery_delay=recovery_delay,
        outbound_mask=np.ones((I, N), dtype=np.float64),
        bullwhip_factor=np.ones((I, N), dtype=np.float64),
        output_floor=np.zeros((I, N), dtype=np.float64),
    )


def update_seis(
    seis: SEISState,
    inbound: np.ndarray,           # (I, N) — this step's inbound pressure
    shock: np.ndarray,             # (I, N) — post-update shock
    active_external: np.ndarray,   # (I, N) bool — external shock active this step
    bullwhip_factor: float = E_BULLWHIP_FACTOR,
    r_output_floor: float = R_OUTPUT_FLOOR,
) -> None:
    """Apply one week of SEIRS transitions, broadcast over the iteration axis.

    Mutates `seis` in-place.  Call after the propagation step so transitions
    react to the freshly computed inbound pressure and updated shock.
    """

    # Snapshot pre-transition state masks so each rule fires off a clean view.
    s_mask = seis.state == S_STATE

    # S → E ───────────────────────────────────────────────────────────────────
    s_to_e = s_mask & (inbound > EXPOSURE_TRIGGER) & (shock < 0.15)
    seis.state[s_to_e] = E_STATE
    seis.buffer_weeks[s_to_e] = 0

    # E: accumulate buffer counter (refresh mask after S→E)
    e_mask = seis.state == E_STATE
    seis.buffer_weeks[e_mask] += 1

    # E → I: buffer exhausted OR shock overrides ──────────────────────────────
    max_buf_2d = seis.max_buffer[np.newaxis, :]   # (1, N) broadcasts to (I, N)
    e_to_i = e_mask & ((seis.buffer_weeks >= max_buf_2d) | (shock >= 0.70))
    seis.state[e_to_i] = I_STATE
    seis.buffer_weeks[e_to_i] = 0

    # I → R: hysteresis — shock has fallen, no active external ────────────────
    i_mask = seis.state == I_STATE
    i_to_r = i_mask & (shock < RECOVERY_THRESHOLD) & ~active_external
    seis.state[i_to_r] = R_STATE
    seis.recovery_weeks[i_to_r] = 0

    # R: accumulate recovery counter
    r_mask = seis.state == R_STATE
    seis.recovery_weeks[r_mask] += 1

    # R → I: re-disrupted before recovery completes
    r_to_i = r_mask & (shock >= REENTRY_SHOCK)
    seis.state[r_to_i] = I_STATE
    seis.recovery_weeks[r_to_i] = 0

    # R → S: recovery delay elapsed AND shock stayed low
    r_mask = seis.state == R_STATE  # refresh after R→I
    rec_delay_2d = seis.recovery_delay[np.newaxis, :]
    r_to_s = r_mask & (seis.recovery_weeks >= rec_delay_2d) & (shock < RECOVERY_THRESHOLD)
    seis.state[r_to_s] = S_STATE
    seis.recovery_weeks[r_to_s] = 0
    seis.buffer_weeks[r_to_s] = 0

    # Refresh modifier arrays ────────────────────────────────────────────────
    seis.outbound_mask[:] = 1.0
    seis.outbound_mask[seis.state == E_STATE] = E_OUTBOUND_LEAK
    seis.outbound_mask[seis.state == R_STATE] = R_OUTBOUND_FACTOR

    seis.bullwhip_factor[:] = 1.0
    seis.bullwhip_factor[seis.state == E_STATE] = bullwhip_factor

    seis.output_floor[:] = 0.0
    seis.output_floor[seis.state == R_STATE] = r_output_floor


__all__ = [
    "SEISState", "build_seis_state", "update_seis",
    "INDUSTRY_INVENTORY_WEEKS",
    "S_STATE", "E_STATE", "I_STATE", "R_STATE",
    "EXPOSURE_TRIGGER", "RECOVERY_THRESHOLD", "REROUTING_TRIGGER", "REENTRY_SHOCK",
    "E_OUTBOUND_LEAK", "R_OUTBOUND_FACTOR", "R_OUTPUT_FLOOR", "E_BULLWHIP_FACTOR",
]
