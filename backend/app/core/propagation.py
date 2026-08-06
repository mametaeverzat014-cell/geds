"""Cascade Propagation Engine — vectorized across an iteration axis.

The engine runs N Monte Carlo iterations as a single broadcast NumPy computation.
A "single deterministic run" is just I=1 with zero parameter noise.

State tensors during the simulation:
    shock, output_loss, inflation, …   shape (I, N)        — current week
    *_traj                              shape (I, T, N)     — full trajectory
    csi_traj, ecv_traj, total_loss_traj shape (I, T)        — per-week scalars per iter

Per-step update (vectorized form of the spec formula):
    inbound[I, i]  = Σ_j  D_eff_batch[I, i, j] · shock_eff[I, j]      ← einsum 'Iij,Ij->Ii'
    inbound      *= bullwhip_factor[I, i]                              ← E-state +25% (panic buy)
    impact        = decay · inbound · V · A_amp · (1−R) · (1−shock)
    impact        = apply_adaptive_rerouting(impact, shock)            ← CP cost surcharge
    shock(t+1)    = clip(max(external, shock+impact−recovery+noise),0,1)

Hysteresis: SEIRS introduces an R (Recovering) state; nodes leaving I move into
R for `recovery_delay_weeks` before returning to S, with output capped at 70%.

Financial intelligence:
    weeks_above_distress tracks consecutive weeks with output_loss > 40%.
    default_probability  = sigmoid((weeks_above_distress − 6) / 2).
    cumulative_loss_usd  += output_loss × (gdp_usd / 52)
    cumulative_infl_usd  += inflation_pressure × (gdp_usd / 52)
    projected_market_cap_loss = MARGIN·PE·cum_loss + INFL_DRAG·PE·cum_infl
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from .graph import CompiledGraph
from .metrics import (
    build_summary,
    compute_csi_batch,
    compute_default_probability,
    compute_ecv_batch,
    compute_market_cap_loss,
)
from .graph import compute_distress_thresholds
from .seis import (
    E_STATE,
    REROUTING_TRIGGER,
    SEISState,
    build_seis_state,
    update_seis,
)
from .types import (
    EngineConfig,
    Frame,
    MarketCapImpact,
    NodeFrame,
    Scenario,
    SimulationResult,
    SimulationSummary,
)


# ─────────────────────────── state container ────────────────────────────────


@dataclass(slots=True)
class BatchedEngineState:
    """Vectorized engine state. Trajectory arrays have leading iteration axis."""

    week: int

    # Current-week per-iter, per-node state — shape (I, N)
    shock: np.ndarray
    inflation_pressure: np.ndarray
    output_loss: np.ndarray
    shortage_prob: np.ndarray
    unemployment_risk: np.ndarray
    persistence: np.ndarray

    affected_mask_prev: np.ndarray         # bool
    affected_first_week: np.ndarray        # int32, -1 if never crossed threshold

    # Financial state — per-iter, per-node
    weeks_above_distress: np.ndarray       # int16
    default_probability: np.ndarray        # float64
    cum_output_loss_usd: np.ndarray        # float64
    cum_inflation_usd: np.ndarray          # float64

    seis: SEISState | None

    # Per-iteration parameters (perturbed in MC, broadcast otherwise)
    D_eff_batch: np.ndarray                # (I, N, N)
    vulnerability_b: np.ndarray            # (I, N)
    amplification_b: np.ndarray            # (I, N)

    # Endogenous distress thresholds per node, recomputed if calibrator
    # adjusts distress_base.  Shape (N,) — broadcasts against (I, N) state.
    distress_threshold: np.ndarray

    # Trajectory tensors — kept_trajectories=True populates these
    shock_traj: np.ndarray | None = None              # (I, T, N)
    output_loss_traj: np.ndarray | None = None
    inflation_traj: np.ndarray | None = None
    shortage_traj: np.ndarray | None = None
    unemployment_traj: np.ndarray | None = None
    seis_traj: np.ndarray | None = None               # int8
    default_prob_traj: np.ndarray | None = None

    # Always-populated per-iter time series
    csi_traj: np.ndarray = field(default_factory=lambda: np.zeros(0))     # (I, T)
    ecv_traj: np.ndarray = field(default_factory=lambda: np.zeros(0))
    ecv_geo_traj: np.ndarray = field(default_factory=lambda: np.zeros(0))
    total_loss_traj: np.ndarray = field(default_factory=lambda: np.zeros(0))
    affected_count_traj: np.ndarray = field(default_factory=lambda: np.zeros(0))


# ─────────────────────────── result container ───────────────────────────────


@dataclass(slots=True)
class BatchedSimulationResult:
    """Output of run_batch.  Exposes both materializers."""

    scenario_id: str
    horizon_weeks: int
    graph_version: str
    n_iterations: int
    state: BatchedEngineState
    graph: CompiledGraph

    def to_simulation_result(self, iter_idx: int = 0) -> SimulationResult:
        """Materialize one iteration as a SimulationResult (Frames + Summary)."""
        return _build_simulation_result(self, iter_idx)


# ─────────────────────────── engine ─────────────────────────────────────────


def _sigmoid(x: np.ndarray) -> np.ndarray:
    out = np.empty_like(x)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    out[~pos] = np.exp(x[~pos]) / (1.0 + np.exp(x[~pos]))
    return out


class PropagationEngine:
    """Vectorized cascade propagation engine.

    Single deterministic runs (I=1, noise=0) reproduce the original engine's
    output exactly modulo the new SEIRS R-state.  Monte Carlo runs use the
    same code path with I>1 and dep_noise>0.
    """

    AFFECTED_THRESHOLD = 0.10

    # recovery_rate is defined as the weekly decay of a node at this delay
    # (the historical uniform default), so per-node coupling changes nothing
    # for 8-week nodes and the calibrated global parameter keeps its meaning.
    REFERENCE_RECOVERY_DELAY_WEEKS = 8.0

    def __init__(self, graph: CompiledGraph, config: EngineConfig | None = None) -> None:
        self.g = graph
        # Kept as None when not supplied so `run_batch` can tell "caller specified an
        # engine config" from "fall back to whatever the scenario carries". Storing
        # `config or EngineConfig()` here would make the two indistinguishable.
        # Mappings are coerced: callers used to pass plain dicts and relied on
        # Scenario's pydantic validation to convert them, which no longer happens
        # now that an explicit engine config takes precedence over the scenario's.
        if isinstance(config, Mapping):
            config = EngineConfig(**config)
        self.config = config

    # ─────────────────────── public API ──────────────────────────────────

    def run(self, scenario: Scenario) -> SimulationResult:
        """Single deterministic run.  Internally I=1, noise=0."""
        batch = self.run_batch(
            scenario,
            n_iterations=1,
            param_noise_pct=0.0,
            seed=scenario.config.seed if scenario.config else None,
            keep_node_trajectories=True,
        )
        return batch.to_simulation_result(iter_idx=0)

    def run_batch(
        self,
        scenario: Scenario,
        n_iterations: int = 1,
        param_noise_pct: float = 0.0,
        seed: int | None = None,
        keep_node_trajectories: bool = True,
    ) -> BatchedSimulationResult:
        """Run N iterations in a single vectorized pass.

        Parameters
        ----------
        n_iterations : int
            Size of the iteration axis.  I=1 reproduces the deterministic engine.
        param_noise_pct : float
            Log-normal scale (×100) applied to D_eff non-zeros; Gaussian noise at
            (2/3)·this on vulnerability and (1/3)·this on amplification.
        seed : int | None
            Master RNG seed.  None → fresh entropy each call.
        keep_node_trajectories : bool
            If False, the (I, T, N) tensors are not allocated — useful for MC
            where only aggregate stats are kept and we want to save memory.
        """
        # An explicitly-supplied engine config wins. `Scenario.config` has a
        # default_factory, so it is *never* falsy — the previous
        # `scenario.config or self.config` made `self.config` unreachable and
        # silently discarded any config passed to the constructor. Every analysis
        # path threads the same object into both, so precedence is a no-op there;
        # this only fixes callers that set the engine config alone.
        cfg = self.config or scenario.config
        T = scenario.horizon_weeks
        I = max(1, n_iterations)
        N = self.g.n

        rng = np.random.default_rng(seed)
        dep_noise = param_noise_pct / 100.0

        state = self._init_state(cfg, I, T, N, rng, dep_noise, keep_node_trajectories)

        # Pre-index scenario shocks by node index for fast per-step lookup.
        shocks_by_node: dict[int, list] = {}
        for shock in scenario.shocks:
            i = self.g.index.get(shock.target_node_id)
            if i is None:
                continue
            shocks_by_node.setdefault(i, []).append(shock)

        # ECV-geo shortest paths from primary origin (same for all iterations).
        primary = max(scenario.shocks, key=lambda s: s.magnitude, default=None)
        sp_from_origin = (
            self.g.snapshot.shortest_path.get(primary.target_node_id, {})
            if primary else {}
        )
        sp_arr = np.array(
            [sp_from_origin.get(nid, 0) for nid in self.g.node_ids],
            dtype=np.float64,
        )

        weekly_gdp = self.g.gdp_usd / 52.0   # (N,) — broadcast against (I, N)

        # Per-node recovery rates (Batch 9b): shock decay coupled to the node's
        # recovery_delay_weeks. A 2-week node (TSMC-class priority restoration)
        # heals 4× faster than the 8-week reference; a 16-week node 2× slower.
        # Capped at 0.95/week; the global recovery_rate remains the calibrated
        # scale. cfg.per_node_recovery=False restores the uniform rate.
        if cfg.per_node_recovery:
            node_recovery_rate = np.clip(
                cfg.recovery_rate
                * (self.REFERENCE_RECOVERY_DELAY_WEEKS / np.maximum(self.g.recovery_delay, 0.5)),
                0.0, 0.95,
            )
        else:
            node_recovery_rate = np.full(N, cfg.recovery_rate)

        for t in range(T):
            state.week = t

            # 1. External shocks (same value for every iteration; broadcasts to (I, N)).
            external_1d = self._apply_external_shocks(shocks_by_node, t, N)
            external = np.broadcast_to(external_1d, (I, N))
            active_external = external > 0.0

            # 2. SEIS-damped outbound signal.
            shock_eff = state.shock * state.seis.outbound_mask

            # 3. Propagation step — vectorized over the iteration axis.
            impact, inbound = self._propagation_step_batch(
                shock_eff, state.shock, state.D_eff_batch,
                state.vulnerability_b, state.amplification_b, cfg,
            )

            # 4. Bullwhip effect: E-state nodes amplify their *receiving* inbound by 25%.
            impact = impact * state.seis.bullwhip_factor

            # 5. Adaptive rerouting: blocked chokepoints add a cost surcharge.
            if cfg.adaptive_rerouting and self.g.reroute_map:
                impact = self._apply_adaptive_rerouting_batch(impact, state.shock)

            # 6. Recovery (only when no external forcing), per-node rate.
            recovery = node_recovery_rate[np.newaxis, :] * state.shock * (~active_external).astype(np.float64)

            # 7. Optional stochastic noise (independent per iter and node).
            if cfg.stochastic_sigma > 0:
                noise = rng.normal(0.0, cfg.stochastic_sigma, (I, N))
            else:
                noise = 0.0

            # 8. State update.
            new_shock = state.shock + impact - recovery + noise
            new_shock = np.maximum(new_shock, external)
            new_shock = np.clip(new_shock, 0.0, 1.0)
            state.shock = new_shock
            state.persistence = 0.85 * state.persistence + 0.15 * state.shock

            # 9. SEIRS transitions (uses inbound *before* bullwhip — pure exposure signal).
            #    Guarded by cfg.seis_enabled: _init_state neutralizes the three state
            #    modifiers (outbound_mask=1, bullwhip=1, output_floor=0) when the flag is
            #    off, but that only holds if the state machine never re-arms them. Before
            #    2026-08 this call ran unconditionally, so seis_enabled=False was a no-op
            #    and the `no_seis` ablation row silently duplicated `full`.
            if cfg.seis_enabled:
                update_seis(
                    state.seis, inbound, state.shock, active_external,
                    bullwhip_factor=cfg.bullwhip_factor,
                    r_output_floor=cfg.r_output_floor,
                )

            # 10. Derived per-node macro state (with R-state output floor).
            self._update_derived(state)

            # 11. Financial intelligence: distress tracking + cumulative USD damage.
            #     Uses endogenous per-node thresholds (function of inventory + vulnerability).
            distressed = state.output_loss > state.distress_threshold[np.newaxis, :]
            state.weeks_above_distress = np.where(
                distressed,
                state.weeks_above_distress + 1,
                np.zeros_like(state.weeks_above_distress),
            )
            state.default_probability = compute_default_probability(
                state.weeks_above_distress,
                week_threshold=cfg.distress_week_threshold,
            )
            state.cum_output_loss_usd += state.output_loss * weekly_gdp[np.newaxis, :]
            state.cum_inflation_usd   += state.inflation_pressure * weekly_gdp[np.newaxis, :]

            # 12. Affected-frontier metrics.
            affected_now = state.shock > self.AFFECTED_THRESHOLD
            newly = affected_now & ~state.affected_mask_prev
            update_mask = newly & (state.affected_first_week < 0)
            state.affected_first_week[update_mask] = t

            # 13. Per-week scalar metrics.
            state.csi_traj[:, t]            = compute_csi_batch(state.shock, self.g)
            state.ecv_traj[:, t]            = compute_ecv_batch(affected_now, state.affected_mask_prev)
            state.ecv_geo_traj[:, t]        = self._ecv_geo_batch(state.affected_first_week, t, sp_arr)
            state.affected_count_traj[:, t] = affected_now.sum(axis=1)
            state.total_loss_traj[:, t]     = (state.output_loss * self.g.gdp_usd[np.newaxis, :]).sum(axis=1)

            # 14. Trajectory tensors (only if requested).
            if state.shock_traj is not None:
                state.shock_traj[:, t, :]        = state.shock
                state.output_loss_traj[:, t, :]  = state.output_loss
                state.inflation_traj[:, t, :]    = state.inflation_pressure
                state.shortage_traj[:, t, :]     = state.shortage_prob
                state.unemployment_traj[:, t, :] = state.unemployment_risk
                state.seis_traj[:, t, :]         = state.seis.state
                state.default_prob_traj[:, t, :] = state.default_probability

            state.affected_mask_prev = affected_now

        return BatchedSimulationResult(
            scenario_id=scenario.id,
            horizon_weeks=T,
            graph_version=self.g.snapshot.version,
            n_iterations=I,
            state=state,
            graph=self.g,
        )

    # ─────────────────────── internals ──────────────────────────────────

    def _init_state(
        self,
        cfg: EngineConfig,
        I: int,
        T: int,
        N: int,
        rng: np.random.Generator,
        dep_noise: float,
        keep_trajectories: bool,
    ) -> BatchedEngineState:
        D_eff_batch, vuln_b, amp_b = self.g.make_batched_params(I, dep_noise, rng)

        # Recompute distress thresholds if calibrator passed a non-default base.
        if cfg.distress_base != 0.40:
            distress_threshold = compute_distress_thresholds(
                self.g.inventory_weeks, self.g.vulnerability, base=cfg.distress_base,
            )
        else:
            distress_threshold = self.g.distress_threshold

        seis = build_seis_state(
            self.g.snapshot.nodes, I, N, inventory_scale=cfg.inventory_scale
        ) if cfg.seis_enabled else None
        if seis is None:
            seis = build_seis_state(
                self.g.snapshot.nodes, I, N, inventory_scale=cfg.inventory_scale
            )
            seis.outbound_mask[:] = 1.0
            seis.bullwhip_factor[:] = 1.0
            seis.output_floor[:] = 0.0

        return BatchedEngineState(
            week=0,
            shock=np.zeros((I, N)),
            inflation_pressure=np.zeros((I, N)),
            output_loss=np.zeros((I, N)),
            shortage_prob=np.zeros((I, N)),
            unemployment_risk=np.zeros((I, N)),
            persistence=np.zeros((I, N)),
            affected_mask_prev=np.zeros((I, N), dtype=bool),
            affected_first_week=np.full((I, N), -1, dtype=np.int32),
            weeks_above_distress=np.zeros((I, N), dtype=np.int16),
            default_probability=np.zeros((I, N)),
            cum_output_loss_usd=np.zeros((I, N)),
            cum_inflation_usd=np.zeros((I, N)),
            seis=seis,
            D_eff_batch=D_eff_batch,
            vulnerability_b=vuln_b,
            amplification_b=amp_b,
            distress_threshold=distress_threshold,
            shock_traj=np.zeros((I, T, N)) if keep_trajectories else None,
            output_loss_traj=np.zeros((I, T, N)) if keep_trajectories else None,
            inflation_traj=np.zeros((I, T, N)) if keep_trajectories else None,
            shortage_traj=np.zeros((I, T, N)) if keep_trajectories else None,
            unemployment_traj=np.zeros((I, T, N)) if keep_trajectories else None,
            seis_traj=np.zeros((I, T, N), dtype=np.int8) if keep_trajectories else None,
            default_prob_traj=np.zeros((I, T, N)) if keep_trajectories else None,
            csi_traj=np.zeros((I, T)),
            ecv_traj=np.zeros((I, T)),
            ecv_geo_traj=np.zeros((I, T)),
            total_loss_traj=np.zeros((I, T)),
            affected_count_traj=np.zeros((I, T), dtype=np.int32),
        )

    def _apply_external_shocks(self, shocks_by_node: dict[int, list], t: int, N: int) -> np.ndarray:
        ext = np.zeros(N)
        for i, shocks in shocks_by_node.items():
            for s in shocks:
                ext[i] = max(ext[i], s.magnitude * s.factor(t))
        return ext

    def _propagation_step_batch(
        self,
        shock_eff: np.ndarray,       # (I, N)
        shock_actual: np.ndarray,    # (I, N)
        D_eff_batch: np.ndarray,     # (I, N, N)
        vulnerability_b: np.ndarray, # (I, N)
        amplification_b: np.ndarray, # (I, N)
        cfg: EngineConfig,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Vectorized propagation.  Returns (impact, inbound) — both (I, N)."""
        # Batched matmul: inbound[I, i] = Σ_j D_eff[I, i, j] · shock_eff[I, j]
        inbound = np.einsum("Iij,Ij->Ii", D_eff_batch, shock_eff)

        amp_kicker = _sigmoid((shock_actual - self.g.threshold[np.newaxis, :]) / cfg.amplification_eps)
        A_amp = amplification_b * (1.0 + cfg.amplification_mu * amp_kicker)

        impact = (
            cfg.propagation_decay
            * inbound
            * vulnerability_b
            * A_amp
            * (1.0 - self.g.resilience[np.newaxis, :])
            * (1.0 - shock_actual)
        )
        return impact, inbound

    def _apply_adaptive_rerouting_batch(
        self,
        impact: np.ndarray,       # (I, N)
        shock: np.ndarray,        # (I, N)
    ) -> np.ndarray:
        """Apply chokepoint rerouting cost surcharge, vectorized over iterations."""
        result = impact.copy()
        for cp_idx, (targets, cost_mult) in self.g.reroute_map.items():
            cp_shock = shock[:, cp_idx]                              # (I,)
            block_frac = np.maximum(0.0, (cp_shock - REROUTING_TRIGGER) / (1.0 - REROUTING_TRIGGER))
            effective_mult = 1.0 + (cost_mult - 1.0) * block_frac    # (I,)
            tgt_arr = np.asarray(targets, dtype=np.intp)
            # broadcast multiplier across the target slice
            result[:, tgt_arr] *= effective_mult[:, np.newaxis]
        return result

    def _update_derived(self, state: BatchedEngineState) -> None:
        pt = self.g.pass_through[np.newaxis, :]
        el = self.g.elasticity[np.newaxis, :]
        rs = self.g.resilience[np.newaxis, :]
        li = self.g.labor_intensity[np.newaxis, :]

        state.inflation_pressure = state.shock * pt * (1.0 + 0.3 * state.persistence)
        # R-state hysteresis: output_loss can't fall below the floor (70% production cap).
        raw_loss = state.shock * el * (1.0 - rs)
        state.output_loss = np.maximum(raw_loss, state.seis.output_floor)
        state.shortage_prob = 1.0 / (1.0 + np.exp(-(6.0 * state.shock - 3.0)))
        state.unemployment_risk = state.output_loss * li * 0.85

    def _ecv_geo_batch(
        self,
        affected_first_week: np.ndarray,  # (I, N)
        t: int,
        sp: np.ndarray,                   # (N,)
    ) -> np.ndarray:
        """Per-iteration mean hop-distance for nodes that first crossed threshold this week."""
        I, N = affected_first_week.shape
        out = np.zeros(I, dtype=np.float64)
        if sp.sum() == 0:
            return out
        for it in range(I):
            newly = np.where(affected_first_week[it] == t)[0]
            if newly.size > 0:
                out[it] = float(sp[newly].mean())
        return out


# ─────────────────────────── result materialisation ──────────────────────────


def _build_simulation_result(batch: BatchedSimulationResult, iter_idx: int) -> SimulationResult:
    """Extract one iteration as a SimulationResult.  Requires trajectories kept."""
    s = batch.state
    g = batch.graph

    if s.shock_traj is None:
        raise RuntimeError(
            "Cannot materialize SimulationResult — run with keep_node_trajectories=True."
        )

    T = batch.horizon_weeks
    N = g.n

    frames: list[Frame] = []
    for t in range(T):
        nodes_t = [
            NodeFrame(
                id=g.node_ids[i],
                shock=float(s.shock_traj[iter_idx, t, i]),
                inflation_pressure=float(s.inflation_traj[iter_idx, t, i]),
                output_loss=float(s.output_loss_traj[iter_idx, t, i]),
                shortage_prob=float(s.shortage_traj[iter_idx, t, i]),
                unemployment_risk=float(s.unemployment_traj[iter_idx, t, i]),
                seis_state=int(s.seis_traj[iter_idx, t, i]),
                default_probability=float(s.default_prob_traj[iter_idx, t, i]),
            )
            for i in range(N)
        ]
        affected = int(s.affected_count_traj[iter_idx, t])
        frames.append(
            Frame(
                week=t,
                nodes=nodes_t,
                csi=float(s.csi_traj[iter_idx, t]),
                ecv=float(s.ecv_traj[iter_idx, t]),
                ecv_geo=float(s.ecv_geo_traj[iter_idx, t]),
                affected_count=affected,
                total_output_loss=float(s.total_loss_traj[iter_idx, t]),
            )
        )

    # Build summary with original metrics path (needs frames + a stub EngineState).
    summary = build_summary(frames, _stub_engine_state(s, iter_idx), g)

    # Augment with financial intelligence.
    final_default = s.default_probability[iter_idx]                   # (N,)
    market_cap_loss_per_node = compute_market_cap_loss(
        s.cum_output_loss_usd[iter_idx],
        s.cum_inflation_usd[iter_idx],
    )                                                                 # (N,)
    high_default_risk = int((final_default > 0.5).sum())
    total_mcap_loss = float(market_cap_loss_per_node.sum())

    # Top-5 market cap impacts.
    top_idx = np.argsort(market_cap_loss_per_node)[::-1][:5]
    top_impacts = [
        MarketCapImpact(
            node_id=g.node_ids[i],
            market_cap_loss_usd=float(market_cap_loss_per_node[i]),
            default_probability=float(final_default[i]),
        )
        for i in top_idx
        if market_cap_loss_per_node[i] > 0
    ]

    summary.total_market_cap_loss_usd = round(total_mcap_loss, 2)
    summary.high_default_risk_count   = high_default_risk
    summary.top_market_cap_impacts    = top_impacts

    return SimulationResult(
        scenario_id=batch.scenario_id,
        horizon_weeks=batch.horizon_weeks,
        graph_version=batch.graph_version,
        frames=frames,
        summary=summary,
    )


class _StubEngineState:
    """Minimal duck-typed adapter for build_summary, which only reads .shock."""
    __slots__ = ("shock",)
    def __init__(self, shock: np.ndarray) -> None:
        self.shock = shock


def _stub_engine_state(s: BatchedEngineState, iter_idx: int) -> _StubEngineState:
    return _StubEngineState(shock=s.shock[iter_idx])


# Convenience entry point (kept for legacy callers).
def simulate(scenario: Scenario, graph: CompiledGraph) -> SimulationResult:
    return PropagationEngine(graph, scenario.config).run(scenario)


# Backward-compat alias: a few modules import EngineState from this file.
EngineState = BatchedEngineState


__all__ = [
    "BatchedEngineState",
    "BatchedSimulationResult",
    "EngineState",
    "PropagationEngine",
    "simulate",
]
