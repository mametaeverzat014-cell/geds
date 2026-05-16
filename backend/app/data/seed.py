"""Build a GraphSnapshot from the seed dataset, with centrality precomputed."""

from __future__ import annotations

from functools import lru_cache

import networkx as nx

from ..core.types import GraphSnapshot
from . import seed_data


def _build_nx(snapshot_nodes: list, snapshot_edges: list) -> nx.DiGraph:
    g = nx.DiGraph()
    for n in snapshot_nodes:
        g.add_node(n.id, **n.model_dump())
    for e in snapshot_edges:
        # Edge weight = dependency_weight × substitution_difficulty (effective transmission strength)
        weight = e.dependency_weight * (0.5 + 0.5 * e.substitution_difficulty)
        g.add_edge(e.source, e.target, weight=weight, **e.model_dump())
    return g


@lru_cache(maxsize=1)
def load_graph() -> GraphSnapshot:
    """Materialize the MVP graph snapshot, with centrality and shortest paths precomputed."""

    nodes = seed_data.build_nodes()
    edges = seed_data.build_edges()

    g = _build_nx(nodes, edges)

    # Centrality: PageRank on the reversed graph. A node is central if many downstream
    # nodes depend on it (directly and transitively). PageRank is robust and always
    # converges; it captures higher-order effects that simple weighted out-degree misses.
    rev = g.reverse(copy=False)
    try:
        pr = nx.pagerank(rev, alpha=0.85, weight="weight", max_iter=500, tol=1e-8)
    except (nx.PowerIterationFailedConvergence, nx.NetworkXException):
        pr = {n: 1.0 / max(1, g.number_of_nodes()) for n in g.nodes()}

    # We also fold in raw weighted out-degree (on the original graph) so that pure
    # suppliers with no inbound dependencies still register as important.
    out_deg = {n: 0.0 for n in g.nodes()}
    for u, _, data in g.edges(data=True):
        out_deg[u] = out_deg.get(u, 0.0) + float(data.get("weight", 0.0))
    max_out = max(out_deg.values()) if out_deg else 1.0
    if max_out == 0:
        max_out = 1.0

    blended = {n: 0.6 * pr.get(n, 0.0) + 0.4 * (out_deg.get(n, 0.0) / max_out) for n in g.nodes()}
    max_c = max(blended.values()) if blended else 1.0
    if max_c == 0:
        max_c = 1.0
    centrality = {k: v / max_c for k, v in blended.items()}

    # Shortest hop distances from likely shock origins (precompute for ECV-geo)
    origins = [n.id for n in nodes if n.industry and n.industry.value == "semiconductors"] + [
        n.id for n in nodes if n.kind.value == "chokepoint"
    ]
    shortest_path: dict[str, dict[str, int]] = {}
    for o in origins:
        try:
            shortest_path[o] = dict(nx.single_source_shortest_path_length(g, o))
        except nx.NodeNotFound:
            shortest_path[o] = {}

    return GraphSnapshot(
        nodes=nodes,
        edges=edges,
        centrality=centrality,
        shortest_path=shortest_path,
    )
