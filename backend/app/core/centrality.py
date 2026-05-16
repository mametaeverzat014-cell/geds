"""Cascading Impact Score (CIS) — trade-weighted PageRank and supply-chain metrics.

CIS answers: "If this node fails, how much economic damage propagates through it?"
It extends standard PageRank by weighting edges with UN Comtrade bilateral trade
values (flow_value_usd) and import penetration ratios (dependency_weight), so a
node's score reflects both its topological position and the economic magnitude of
the flows it mediates.

Algorithm
---------
1. Build N×N weight matrix  W[i,j] = flow_value_usd(j→i) × dependency_weight(j→i).
   ROUTES_THROUGH edges get a 2× amplification because a blocked chokepoint
   disrupts *all* flows on that route, not just one bilateral pair.
2. Column-normalise W (each source sums to 1).
3. Run power iteration: r ← (1−d)/N + d·W·r  until convergence (or n_iter steps).
4. Normalise to [0, 1].

Supplementary metrics
---------------------
* upstream_criticality   — weighted out-degree: Σ_i dep_weight(j→i) × GDP_i
* downstream_exposure    — economic throughput at risk: Σ_i flow_usd(j→i) × dep_weight
* chokepoint_exposure    — fraction of inbound dep_weight routed through CP nodes

Data sources
------------
* flow_value_usd  : UN Comtrade 2019 (bilateral, sector-allocated)
* dependency_weight: UN Comtrade 2019 import penetration ratios
* GDP shares      : World Bank 2019 + OECD STAN 2019
"""

from __future__ import annotations

import numpy as np

from .types import CentralityResult, EdgeKind, NodeCentrality, NodeKind, GraphSnapshot


def compute_cis(
    snapshot: GraphSnapshot,
    n_iter: int = 150,
    damping: float = 0.85,
) -> np.ndarray:
    """Return CIS score per node (same order as snapshot.nodes), normalised to [0, 1].

    Uses weighted PageRank on the dependency graph, where a high score means the
    node mediates large economic flows between many critical partners.
    """
    index = {n.id: i for i, n in enumerate(snapshot.nodes)}
    N = len(snapshot.nodes)

    W = np.zeros((N, N), dtype=np.float64)
    for e in snapshot.edges:
        j = index.get(e.source)
        i = index.get(e.target)
        if j is None or i is None or j == i:
            continue
        w = e.flow_value_usd * e.dependency_weight
        # Chokepoint-routed flows are amplified: one blocked strait disrupts all lanes.
        if e.kind == EdgeKind.ROUTES_THROUGH:
            w *= 2.0
        W[i, j] += w

    col_sums = W.sum(axis=0)
    col_sums[col_sums == 0] = 1.0
    W = W / col_sums[np.newaxis, :]

    cis = np.ones(N, dtype=np.float64) / N
    for _ in range(n_iter):
        cis = (1.0 - damping) / N + damping * (W @ cis)

    lo, hi = cis.min(), cis.max()
    if hi > lo:
        cis = (cis - lo) / (hi - lo)
    return cis


def compute_upstream_criticality(snapshot: GraphSnapshot) -> np.ndarray:
    """Weighted out-degree: how critical is each node as a supplier?

    Score_j = Σ_i  dependency_weight(j→i) × GDP_i(USD)
    Normalised to [0, 1].  High score → many large economies depend on this node.
    """
    index = {n.id: i for i, n in enumerate(snapshot.nodes)}
    N = len(snapshot.nodes)
    gdp = np.array([n.gdp_usd for n in snapshot.nodes], dtype=np.float64)
    score = np.zeros(N, dtype=np.float64)

    for e in snapshot.edges:
        j = index.get(e.source)
        i = index.get(e.target)
        if j is None or i is None:
            continue
        score[j] += e.dependency_weight * gdp[i]

    hi = score.max()
    return score / hi if hi > 0 else score


def compute_downstream_exposure(snapshot: GraphSnapshot) -> np.ndarray:
    """Economic throughput (USD) at risk if a node fails, normalised to [0, 1].

    Score_j = Σ_i  flow_value_usd(j→i) × dependency_weight(j→i)
    Captures both large flows (high trade value) and critical flows (high dep_weight).
    """
    index = {n.id: i for i, n in enumerate(snapshot.nodes)}
    N = len(snapshot.nodes)
    score = np.zeros(N, dtype=np.float64)

    for e in snapshot.edges:
        j = index.get(e.source)
        i = index.get(e.target)
        if j is None or i is None:
            continue
        score[j] += e.flow_value_usd * e.dependency_weight

    hi = score.max()
    return score / hi if hi > 0 else score


def compute_chokepoint_exposure(snapshot: GraphSnapshot) -> np.ndarray:
    """For each node: fraction of inbound dependency routed through chokepoints.

    A high score signals that the node is particularly vulnerable to maritime
    disruptions — its supply cannot easily shift to overland alternatives.
    """
    index = {n.id: i for i, n in enumerate(snapshot.nodes)}
    N = len(snapshot.nodes)
    cp_sources = {n.id for n in snapshot.nodes if n.kind == NodeKind.CHOKEPOINT}

    total_in = np.zeros(N, dtype=np.float64)
    cp_in = np.zeros(N, dtype=np.float64)

    for e in snapshot.edges:
        j = index.get(e.source)
        i = index.get(e.target)
        if j is None or i is None:
            continue
        total_in[i] += e.dependency_weight
        if e.source in cp_sources or e.kind == EdgeKind.ROUTES_THROUGH:
            cp_in[i] += e.dependency_weight

    return cp_in / np.maximum(total_in, 1e-9)


def full_centrality_report(snapshot: GraphSnapshot) -> CentralityResult:
    """Compute all four metrics and return a ranked CentralityResult."""
    cis  = compute_cis(snapshot)
    uc   = compute_upstream_criticality(snapshot)
    de   = compute_downstream_exposure(snapshot)
    ce   = compute_chokepoint_exposure(snapshot)

    ranked_idx = np.argsort(cis)[::-1]
    rank_map = np.empty(len(snapshot.nodes), dtype=int)
    rank_map[ranked_idx] = np.arange(1, len(snapshot.nodes) + 1)

    nodes = [
        NodeCentrality(
            node_id=n.id,
            name=n.name,
            cis=float(cis[i]),
            upstream_criticality=float(uc[i]),
            downstream_exposure=float(de[i]),
            chokepoint_exposure=float(ce[i]),
            rank=int(rank_map[i]),
        )
        for i, n in enumerate(snapshot.nodes)
    ]
    nodes.sort(key=lambda x: x.rank)

    return CentralityResult(
        nodes=nodes,
        method="weighted_pagerank_v2",
        data_sources=[
            "UN Comtrade 2019 (HS 8541/8542/8703)",
            "World Bank GDP 2019",
            "OECD STAN sector shares 2019",
            "GEDS trade dependency graph",
        ],
    )


__all__ = [
    "compute_cis",
    "compute_upstream_criticality",
    "compute_downstream_exposure",
    "compute_chokepoint_exposure",
    "full_centrality_report",
]
