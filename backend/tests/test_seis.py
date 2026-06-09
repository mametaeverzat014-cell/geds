"""Unit tests for the SEIRS state machine (core/seis.py).

The SEIRS layer is the novel part of the engine, so every transition rule in
the update_seis docstring is locked down individually:

    S → E : inbound > EXPOSURE_TRIGGER  AND  shock < 0.15
    E → I : buffer_weeks ≥ max_buffer   OR   shock ≥ 0.70
    I → R : shock < RECOVERY_THRESHOLD  AND  no active external forcing
    R → S : recovery_weeks ≥ recovery_delay  AND  shock < RECOVERY_THRESHOLD
    R → I : shock spikes back ≥ REENTRY_SHOCK

plus the state-modifier arrays (outbound_mask / bullwhip_factor / output_floor)
and the chokepoint rerouting surcharge in the propagation engine.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.seis import (
    E_BULLWHIP_FACTOR,
    E_OUTBOUND_LEAK,
    E_STATE,
    EXPOSURE_TRIGGER,
    I_STATE,
    R_OUTBOUND_FACTOR,
    R_OUTPUT_FLOOR,
    R_STATE,
    REENTRY_SHOCK,
    S_STATE,
    SEISState,
    build_seis_state,
    update_seis,
)


# ─────────────────────────── helpers ────────────────────────────────────────


def _make_state(n_nodes: int = 3, max_buffer: int = 4, recovery_delay: int = 3) -> SEISState:
    """Single-iteration SEIRS state with uniform buffer/recovery caps."""
    I, N = 1, n_nodes
    return SEISState(
        state=np.zeros((I, N), dtype=np.int8),
        buffer_weeks=np.zeros((I, N), dtype=np.int16),
        recovery_weeks=np.zeros((I, N), dtype=np.int16),
        max_buffer=np.full(N, max_buffer, dtype=np.int16),
        recovery_delay=np.full(N, recovery_delay, dtype=np.int16),
        outbound_mask=np.ones((I, N), dtype=np.float64),
        bullwhip_factor=np.ones((I, N), dtype=np.float64),
        output_floor=np.zeros((I, N), dtype=np.float64),
    )


def _step(seis, inbound, shock, active=False):
    I, N = seis.state.shape
    update_seis(
        seis,
        inbound=np.full((I, N), inbound, dtype=np.float64),
        shock=np.full((I, N), shock, dtype=np.float64),
        active_external=np.full((I, N), active, dtype=bool),
    )


# ─────────────────────────── transitions ────────────────────────────────────


def test_s_to_e_requires_inbound_pressure_and_low_shock():
    seis = _make_state()
    # Inbound above trigger, shock low → exposed.
    _step(seis, inbound=EXPOSURE_TRIGGER + 0.01, shock=0.05)
    assert (seis.state == E_STATE).all()


def test_s_stays_s_below_exposure_trigger():
    seis = _make_state()
    _step(seis, inbound=EXPOSURE_TRIGGER - 0.01, shock=0.05)
    assert (seis.state == S_STATE).all()


def test_s_with_high_shock_does_not_enter_e():
    # shock ≥ 0.15 blocks the S→E rule (node is already visibly disrupted,
    # not merely "exposed" through upstream pressure).
    seis = _make_state()
    _step(seis, inbound=0.5, shock=0.20)
    assert (seis.state == S_STATE).all()


def test_e_to_i_on_buffer_exhaustion():
    # buffer_weeks increments on the entry week too, so a node survives exactly
    # max_buffer weeks in E counting the week it entered.
    seis = _make_state(max_buffer=3)
    _step(seis, inbound=0.2, shock=0.05)          # S → E (buffer_weeks=1)
    assert (seis.state == E_STATE).all()
    _step(seis, inbound=0.2, shock=0.05)          # buffer_weeks=2, still absorbing
    assert (seis.state == E_STATE).all()
    _step(seis, inbound=0.2, shock=0.05)          # buffer_weeks=3 ≥ max → I
    assert (seis.state == I_STATE).all()


def test_e_to_i_hard_override_on_severe_shock():
    seis = _make_state(max_buffer=50)             # deep buffer — only the override can fire
    _step(seis, inbound=0.2, shock=0.05)          # S → E
    _step(seis, inbound=0.2, shock=0.75)          # shock ≥ 0.70 overrides the buffer
    assert (seis.state == I_STATE).all()


def test_i_to_r_requires_low_shock_and_no_external_forcing():
    seis = _make_state()
    seis.state[:] = I_STATE
    # Still externally forced → stays I even though shock has receded.
    _step(seis, inbound=0.0, shock=0.01, active=True)
    assert (seis.state == I_STATE).all()
    # Forcing gone → enters recovery.
    _step(seis, inbound=0.0, shock=0.01, active=False)
    assert (seis.state == R_STATE).all()


def test_r_to_s_after_recovery_delay():
    seis = _make_state(recovery_delay=3)
    seis.state[:] = R_STATE
    for _ in range(2):
        _step(seis, inbound=0.0, shock=0.01)
        assert (seis.state == R_STATE).all()
    _step(seis, inbound=0.0, shock=0.01)          # recovery_weeks reaches delay
    assert (seis.state == S_STATE).all()
    assert (seis.recovery_weeks == 0).all()
    assert (seis.buffer_weeks == 0).all()


def test_r_to_i_on_reentry_shock():
    seis = _make_state()
    seis.state[:] = R_STATE
    _step(seis, inbound=0.0, shock=REENTRY_SHOCK + 0.01)
    assert (seis.state == I_STATE).all()
    assert (seis.recovery_weeks == 0).all()


def test_transitions_are_per_node_independent():
    seis = _make_state(n_nodes=3)
    inbound = np.array([[0.2, 0.0, 0.2]])
    shock = np.array([[0.05, 0.05, 0.20]])
    update_seis(seis, inbound=inbound, shock=shock,
                active_external=np.zeros((1, 3), dtype=bool))
    # node0: exposed; node1: no inbound → S; node2: shock too high for E → S.
    assert seis.state[0, 0] == E_STATE
    assert seis.state[0, 1] == S_STATE
    assert seis.state[0, 2] == S_STATE


# ─────────────────────────── modifier arrays ─────────────────────────────────


def test_modifiers_match_states():
    seis = _make_state(n_nodes=4)
    seis.state[0] = [S_STATE, E_STATE, I_STATE, R_STATE]
    # A no-op step (no transitions fire) just refreshes the modifier arrays...
    # except E accumulates buffer; use a deep buffer so E stays E.
    seis.max_buffer[:] = 50
    _step(seis, inbound=0.0, shock=0.20)
    assert seis.outbound_mask[0, 0] == 1.0                  # S: undamped
    assert seis.outbound_mask[0, 1] == E_OUTBOUND_LEAK      # E: buffer absorbs outbound
    assert seis.outbound_mask[0, 2] == 1.0                  # I: full propagation
    assert seis.outbound_mask[0, 3] == R_OUTBOUND_FACTOR    # R: mostly recovered
    assert seis.bullwhip_factor[0, 1] == E_BULLWHIP_FACTOR  # E: panic-buying
    assert (seis.bullwhip_factor[0, [0, 2, 3]] == 1.0).all()
    assert seis.output_floor[0, 3] == R_OUTPUT_FLOOR        # R: hysteresis cap
    assert (seis.output_floor[0, :3] == 0.0).all()


def test_custom_bullwhip_and_floor_are_respected():
    seis = _make_state(n_nodes=2, max_buffer=50)
    seis.state[0] = [E_STATE, R_STATE]
    update_seis(
        seis,
        inbound=np.zeros((1, 2)),
        shock=np.full((1, 2), 0.20),
        active_external=np.zeros((1, 2), dtype=bool),
        bullwhip_factor=1.8,
        r_output_floor=0.55,
    )
    assert seis.bullwhip_factor[0, 0] == 1.8
    assert seis.output_floor[0, 1] == 0.55


# ─────────────────────────── build_seis_state ───────────────────────────────


def test_build_seis_state_uses_industry_inventory_and_scale(snapshot):
    nodes = snapshot.nodes
    base = build_seis_state(nodes, n_iterations=2, n_nodes=len(nodes), inventory_scale=1.0)
    doubled = build_seis_state(nodes, n_iterations=2, n_nodes=len(nodes), inventory_scale=2.0)
    assert base.state.shape == (2, len(nodes))
    assert (doubled.max_buffer >= base.max_buffer).all()
    # Scaling must affect at least one node with a non-zero buffer.
    assert (doubled.max_buffer > base.max_buffer).any()
    # Recovery delay is at least 1 week everywhere (clamped).
    assert (base.recovery_delay >= 1).all()


# ─────────────────────────── full-engine SEIRS behaviour ────────────────────


def test_seis_states_appear_in_cascade(graph):
    """A large real shock must drive downstream nodes through E and the source to I."""
    from app.core.propagation import PropagationEngine
    from app.core.types import EngineConfig, Scenario, ShockSpec

    cfg = EngineConfig(seed=0, stochastic_sigma=0.0)
    sc = Scenario(
        id="seis-cascade-test", name="seis cascade", horizon_weeks=30,
        shocks=[ShockSpec(target_node_id="TWN:semiconductors", magnitude=0.85,
                          start_week=0, duration_weeks=10, decay_curve="step")],
    )
    engine = PropagationEngine(graph, cfg)
    result = engine.run(sc)
    states = np.array([[nf.seis_state for nf in f.nodes] for f in result.frames])
    assert (states == E_STATE).any(), "no node ever entered the Exposed state"
    assert (states == I_STATE).any(), "no node ever entered the Infected state"
    assert (states == R_STATE).any(), "no node ever entered the Recovering state"


# ─────────────────────────── chokepoint rerouting ───────────────────────────


def test_rerouting_surcharge_amplifies_chokepoint_targets(graph):
    """Blocking a chokepoint must multiply impact on its dependent nodes only."""
    from app.core.propagation import PropagationEngine

    engine = PropagationEngine(graph)
    assert graph.reroute_map, "compiled graph has no chokepoint reroute map"

    n = len(graph.snapshot.nodes)
    impact = np.ones((1, n))
    shock = np.zeros((1, n))
    cp_idx, (targets, cost_mult) = next(iter(graph.reroute_map.items()))
    assert cost_mult > 1.0

    # Below the trigger: no surcharge anywhere.
    shock[0, cp_idx] = 0.10
    out = engine._apply_adaptive_rerouting_batch(impact, shock)
    np.testing.assert_allclose(out, impact)

    # Fully blocked chokepoint: targets multiplied by the full reroute cost.
    shock[0, cp_idx] = 1.0
    out = engine._apply_adaptive_rerouting_batch(impact, shock)
    for t in targets:
        assert out[0, t] == pytest.approx(cost_mult)
    untouched = [i for i in range(n) if i not in targets]
    np.testing.assert_allclose(out[0, untouched], impact[0, untouched])


def test_rerouting_surcharge_scales_with_block_fraction(graph):
    from app.core.propagation import PropagationEngine
    from app.core.seis import REROUTING_TRIGGER

    engine = PropagationEngine(graph)
    n = len(graph.snapshot.nodes)
    cp_idx, (targets, cost_mult) = next(iter(graph.reroute_map.items()))

    impact = np.ones((1, n))
    shock = np.zeros((1, n))
    half_block = REROUTING_TRIGGER + 0.5 * (1.0 - REROUTING_TRIGGER)
    shock[0, cp_idx] = half_block
    out = engine._apply_adaptive_rerouting_batch(impact, shock)
    expected = 1.0 + (cost_mult - 1.0) * 0.5
    for t in targets:
        assert out[0, t] == pytest.approx(expected)
