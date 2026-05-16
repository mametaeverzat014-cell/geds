"""Sparse matrix and vector representation of a GraphSnapshot for fast propagation."""

from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
from scipy import sparse

from .seis import INDUSTRY_INVENTORY_WEEKS
from .types import EdgeKind, GraphSnapshot, Industry, NodeKind

# Industry-level coefficients used by the macro layer.
# pass_through  — how much shock translates to local inflation pressure (0..1)
# elasticity    — output loss per unit shock (0..1)
# labor         — labor intensity, controls unemployment risk (0..1)

INDUSTRY_COEFFICIENTS: dict[str | None, dict[str, float]] = {
    Industry.SEMICONDUCTORS.value: {"pass_through": 0.18, "elasticity": 0.72, "labor": 0.32},
    Industry.ELECTRONICS.value:    {"pass_through": 0.28, "elasticity": 0.66, "labor": 0.55},
    Industry.AUTOMOTIVE.value:     {"pass_through": 0.38, "elasticity": 0.76, "labor": 0.66},
    Industry.AEROSPACE.value:      {"pass_through": 0.12, "elasticity": 0.52, "labor": 0.48},
    Industry.CONSUMER_GOODS.value: {"pass_through": 0.42, "elasticity": 0.46, "labor": 0.60},
    Industry.ENERGY.value:         {"pass_through": 0.55, "elasticity": 0.42, "labor": 0.30},
    Industry.SHIPPING.value:       {"pass_through": 0.32, "elasticity": 0.55, "labor": 0.50},
    None:                          {"pass_through": 0.10, "elasticity": 0.20, "labor": 0.10},
}


@dataclass(slots=True)
class CompiledGraph:
    """Numerical projection of a GraphSnapshot ready for the engine."""

    node_ids: list[str]
    index: dict[str, int]

    # node-level vectors, all shape (N,)
    vulnerability: np.ndarray
    resilience: np.ndarray
    amplification: np.ndarray
    threshold: np.ndarray
    recovery_delay: np.ndarray
    centrality: np.ndarray
    gdp_usd: np.ndarray
    inventory_weeks: np.ndarray    # SEIS buffer depth per node (int16)
    distress_threshold: np.ndarray # per-node endogenous default trigger (float64)

    # macro-coefficient vectors
    pass_through: np.ndarray
    elasticity: np.ndarray
    labor_intensity: np.ndarray

    # sparse effective dependency matrix D_eff[i, j] (CSR, N×N)
    # rows = target nodes (i); cols = source nodes (j)
    D_eff: sparse.csr_matrix

    # dense projection of D_eff for batched einsum (N×N float64).
    # With N≈40 this is 12.5 KB; with N=1000 it'd be 8 MB — still fine.
    D_eff_dense: np.ndarray

    # per-node sum of inbound effective dependencies (for normalization / metrics)
    inbound_dep_sum: np.ndarray

    # adaptive rerouting: maps chokepoint_node_idx → (list[target_idx], cost_multiplier)
    # Built from ROUTES_THROUGH edges + reroute_cost_multiplier in node.meta.
    reroute_map: dict[int, tuple[list[int], float]]

    # graph snapshot kept for metadata
    snapshot: GraphSnapshot

    @property
    def n(self) -> int:
        return len(self.node_ids)

    def perturb(self, rng: np.random.Generator, dep_noise: float = 0.15) -> "CompiledGraph":
        """Return a shallow copy with single-iteration Monte Carlo perturbation.

        Kept for backward compatibility and unit tests.  The vectorized engine
        uses make_batched_params() instead.
        """
        new = copy.copy(self)
        scale = np.clip(rng.lognormal(0.0, dep_noise, self.D_eff.nnz), 0.60, 1.67)
        new_data = self.D_eff.data * scale
        new.D_eff = sparse.csr_matrix(
            (new_data, self.D_eff.indices.copy(), self.D_eff.indptr.copy()),
            shape=self.D_eff.shape, dtype=np.float64,
        )
        # Rebuild dense projection from the perturbed sparse matrix.
        new.D_eff_dense = new.D_eff.toarray()

        v_noise = rng.normal(0.0, dep_noise * 0.67, self.n)
        new.vulnerability = np.clip(self.vulnerability + v_noise, 0.05, 0.98)
        a_noise = rng.normal(0.0, dep_noise * 0.33, self.n)
        new.amplification = np.clip(self.amplification + a_noise, 0.80, 1.80)
        return new

    def make_batched_params(
        self,
        n_iterations: int,
        dep_noise: float,
        rng: np.random.Generator,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build (D_eff_batch, vulnerability_batch, amplification_batch) tensors.

        Shapes:
            D_eff_batch       : (I, N, N)
            vulnerability_batch / amplification_batch : (I, N)

        With dep_noise=0 (or I=1 and no MC), all batch tensors are exact copies
        of the deterministic parameters — broadcasting preserves identity.
        """
        I, N = n_iterations, self.n

        if dep_noise <= 0.0:
            # No perturbation — broadcast deterministic params.  Single contiguous copy so
            # the engine doesn't have to special-case read-only broadcast views.
            D_eff_batch = np.broadcast_to(self.D_eff_dense, (I, N, N)).copy()
            vuln_batch = np.broadcast_to(self.vulnerability, (I, N)).copy()
            amp_batch = np.broadcast_to(self.amplification, (I, N)).copy()
            return D_eff_batch, vuln_batch, amp_batch

        # D_eff: log-normal multiplicative noise, clamped to ±67% (matches single-iter perturb).
        d_noise = np.clip(rng.lognormal(0.0, dep_noise, (I, N, N)), 0.60, 1.67)
        D_eff_batch = self.D_eff_dense[np.newaxis, :, :] * d_noise

        # Vulnerability: Gaussian, ±(2/3 × dep_noise).
        v_noise = rng.normal(0.0, dep_noise * 0.67, (I, N))
        vuln_batch = np.clip(self.vulnerability[np.newaxis, :] + v_noise, 0.05, 0.98)

        # Amplification: Gaussian, ±(1/3 × dep_noise).
        a_noise = rng.normal(0.0, dep_noise * 0.33, (I, N))
        amp_batch = np.clip(self.amplification[np.newaxis, :] + a_noise, 0.80, 1.80)

        return D_eff_batch, vuln_batch, amp_batch


def compute_distress_thresholds(
    inventory_weeks: np.ndarray,
    vulnerability: np.ndarray,
    base: float = 0.40,
) -> np.ndarray:
    """Endogenous per-node default trigger.

    threshold_i = base + 0.20·norm_inventory_i − 0.20·vulnerability_i
    Clamped to [0.15, 0.65]. A semiconductor fab with 10w inventory and
    vulnerability 0.5 → threshold ≈ 0.45 (forgiving). A JIT-supplied auto plant
    with 3w inventory and vulnerability 0.8 → threshold ≈ 0.27 (fragile).
    """
    inv_factor = np.clip(inventory_weeks.astype(np.float64) / 13.0, 0.0, 1.0)
    thr = base + 0.20 * inv_factor - 0.20 * vulnerability
    return np.clip(thr, 0.15, 0.65)


def compile_graph(snapshot: GraphSnapshot, rerouting_efficiency: float = 0.55) -> CompiledGraph:
    """Convert a GraphSnapshot into the numerical structures the engine needs."""

    node_ids = [n.id for n in snapshot.nodes]
    index = {nid: i for i, nid in enumerate(node_ids)}
    N = len(node_ids)

    vulnerability = np.array([n.vulnerability for n in snapshot.nodes], dtype=np.float64)
    resilience = np.array([n.resilience for n in snapshot.nodes], dtype=np.float64)
    amplification = np.array([n.amplification for n in snapshot.nodes], dtype=np.float64)
    threshold = np.array([n.threshold for n in snapshot.nodes], dtype=np.float64)
    recovery_delay = np.array([n.recovery_delay_weeks for n in snapshot.nodes], dtype=np.float64)
    centrality = np.array(
        [snapshot.centrality.get(n.id, 0.0) for n in snapshot.nodes], dtype=np.float64
    )
    gdp = np.array([n.gdp_usd for n in snapshot.nodes], dtype=np.float64)

    # SEIS inventory buffer depth per node.
    def _inv_weeks(node) -> int:
        if node.inventory_weeks is not None:
            return int(node.inventory_weeks)
        if node.industry is not None:
            return INDUSTRY_INVENTORY_WEEKS.get(node.industry.value, 8)
        return 0  # chokepoints / resource nodes

    inventory_weeks = np.array([_inv_weeks(n) for n in snapshot.nodes], dtype=np.int16)
    distress_threshold = compute_distress_thresholds(inventory_weeks, vulnerability)

    pass_through = np.array(
        [INDUSTRY_COEFFICIENTS[n.industry.value if n.industry else None]["pass_through"]
         for n in snapshot.nodes], dtype=np.float64,
    )
    elasticity = np.array(
        [INDUSTRY_COEFFICIENTS[n.industry.value if n.industry else None]["elasticity"]
         for n in snapshot.nodes], dtype=np.float64,
    )
    labor = np.array(
        [INDUSTRY_COEFFICIENTS[n.industry.value if n.industry else None]["labor"]
         for n in snapshot.nodes], dtype=np.float64,
    )

    # Build effective dependency matrix.
    #
    #   D_eff[i, j] = dep_weight × (0.5 + 0.5·sub_difficulty)             ← cascade strength
    #                × (1 − rerouting_capability × η)                       ← static rerouting
    #                × (1 − 0.5·resilience_coefficient)                     ← edge-level damping
    #
    # Edges originating from chokepoints (ROUTES_THROUGH) skip the rerouting reduction:
    # a closed strait is by definition unreroutable in the short term.
    rows, cols, vals = [], [], []
    for e in snapshot.edges:
        i = index.get(e.target)
        j = index.get(e.source)
        if i is None or j is None:
            continue
        reroute_factor = (
            1.0
            if e.kind == EdgeKind.ROUTES_THROUGH
            else (1.0 - e.rerouting_capability * rerouting_efficiency)
        )
        eff = (
            e.dependency_weight
            * (0.5 + 0.5 * e.substitution_difficulty)
            * reroute_factor
            * (1.0 - 0.5 * e.resilience_coefficient)
        )
        rows.append(i)
        cols.append(j)
        vals.append(float(eff))

    D_eff = sparse.csr_matrix(
        (vals, (rows, cols)), shape=(N, N), dtype=np.float64
    )

    # Row-normalize cap: prevent any single row from summing above 1.2 (stability guarantee
    # plus a soft cap on "more than 100% dependent on imports"). Edges remain proportional.
    inbound_sum = np.asarray(D_eff.sum(axis=1)).flatten()
    scale = np.where(inbound_sum > 1.2, 1.2 / np.maximum(inbound_sum, 1e-9), 1.0)
    D_eff = sparse.diags(scale) @ D_eff
    inbound_dep_sum = np.asarray(D_eff.sum(axis=1)).flatten()

    # Adaptive rerouting map: chokepoint_idx → (target_indices, cost_multiplier).
    # cost_multiplier sourced from node.meta["reroute_cost_multiplier"]:
    #   Suez  1.35 (Cape of Good Hope detour: +35% voyage cost per Lloyd's/IEA)
    #   Hormuz 2.00 (no viable alternative; LNG/crude price spike)
    #   Malacca 1.10 (Sunda Strait minor detour)
    #   TaiwanStrait 1.15 (Northern/Southern Pacific lane rerouting)
    reroute_map: dict[int, tuple[list[int], float]] = {}
    for e in snapshot.edges:
        if e.kind != EdgeKind.ROUTES_THROUGH:
            continue
        j = index.get(e.source)
        i = index.get(e.target)
        if j is None or i is None:
            continue
        cp_node = snapshot.nodes[j]
        cost_mult = float(cp_node.meta.get("reroute_cost_multiplier", 1.0))
        if j not in reroute_map:
            reroute_map[j] = ([], cost_mult)
        reroute_map[j][0].append(i)

    return CompiledGraph(
        node_ids=node_ids,
        index=index,
        vulnerability=vulnerability,
        resilience=resilience,
        amplification=amplification,
        threshold=threshold,
        recovery_delay=recovery_delay,
        centrality=centrality,
        gdp_usd=gdp,
        inventory_weeks=inventory_weeks,
        distress_threshold=distress_threshold,
        pass_through=pass_through,
        elasticity=elasticity,
        labor_intensity=labor,
        D_eff=D_eff,
        D_eff_dense=D_eff.toarray(),
        inbound_dep_sum=inbound_dep_sum,
        reroute_map=reroute_map,
        snapshot=snapshot,
    )


def chokepoint_indices(g: CompiledGraph) -> list[int]:
    return [i for i, node in enumerate(g.snapshot.nodes) if node.kind == NodeKind.CHOKEPOINT]


def country_indices(g: CompiledGraph) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for i, node in enumerate(g.snapshot.nodes):
        if node.country is None:
            continue
        out.setdefault(node.country, []).append(i)
    return out


def industry_indices(g: CompiledGraph) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for i, node in enumerate(g.snapshot.nodes):
        if node.industry is None:
            continue
        out.setdefault(node.industry.value, []).append(i)
    return out
