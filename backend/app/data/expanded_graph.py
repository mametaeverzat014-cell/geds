"""Build a GraphSnapshot from the ICIO-grounded expanded graph (v3).

The v3 prototype (backend/data/csv/expanded_graph_{nodes,edges}_v3.csv, produced
by core.icio.run_graph_expansion) is the 81-economy × 5-sector projection of the
OECD ICIO 2019 table: 405 nodes, ~1964 intermediate-input edges. Unlike the
hand-authored 12-country seed graph, the v3 CSVs carry only ICIO *structural*
quantities (output, bilateral flow, input share, import penetration) — they do
NOT carry the engine's behavioral parameters. This module supplies those by
documented derivation, so the expanded graph can run through the existing
PropagationEngine unchanged.

Opt-in: load_graph() (seed.py) dispatches here only when GEDS_GRAPH_VERSION=v3.
Default stays v2, so the calibrated baseline, golden reproducibility snapshot and
all validated events are untouched.

Parameter derivation (all uncalibrated structural priors — see PROGRESS Batch 11):
  Node
    industry      ICIO label → Industry enum. electronics_c26 (merged C26
                  semiconductors+electronics, which ICIO cannot split) → ELECTRONICS.
    resilience    LPI 2018 where available (same formula as seed_data:
                  0.20 + 0.60·(LPI−3.05)/1.15, clipped [0.20,0.80]); neutral 0.50
                  for the 69 economies LPI 2018 does not yet cover in this repo.
    vulnerability 1 − resilience.
    amplification / threshold   sector defaults (mirroring the seed graph's ranges).
    gdp_usd       node output_usd_m × 1e6 (economic mass for ECV weighting).
    recovery_delay_weeks   8.0 (engine reference).
  Edge
    dependency_weight        import penetration, clipped [0,1] (same quantity the
                             seed TWN-semi edges use as their penetration_ratio base).
    substitution_difficulty  sector default keyed on the source industry.
    rerouting_capability 0.25, resilience_coefficient 0.22, recovery_delay 8.0.
    flow_value_usd           flow_usd_m × 1e6. kind = PRODUCTION_INPUT.

These priors are NOT calibrated to the v3 topology — the seed parameters were fit
to the sparse 12-country graph. v3 is wired in for structural/expansion work
(turning the "partial" historical events into in-graph calibration targets); a
dedicated DE/MCMC recalibration on the dense graph is the separate next step.
"""

from __future__ import annotations

import csv
import json
import logging
from functools import lru_cache
from pathlib import Path

import networkx as nx

from ..core.types import Edge, EdgeKind, GraphSnapshot, Industry, Node, NodeKind

log = logging.getLogger("geds.expanded_graph")

_CSV_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "csv"
_RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"

# ICIO 5-sector label → engine Industry enum. electronics_c26 is the merged C26
# bucket (semiconductors+electronics) that ICIO cannot disaggregate; it carries
# ELECTRONICS coefficients, which is the closest calibrated analog.
_INDUSTRY_MAP: dict[str, Industry] = {
    "electronics_c26": Industry.ELECTRONICS,
    "automotive": Industry.AUTOMOTIVE,
    "consumer_goods": Industry.CONSUMER_GOODS,
    "aerospace": Industry.AEROSPACE,
    "shipping": Industry.SHIPPING,
}

# Sector behavioral defaults, mirroring the seed graph's per-sector ranges
# (seed_data.NODE_SPECS). (amplification, threshold, substitution_difficulty).
_SECTOR_DEFAULTS: dict[str, tuple[float, float, float]] = {
    "electronics_c26": (1.22, 0.45, 0.82),
    "automotive":      (1.25, 0.45, 0.78),
    "consumer_goods":  (1.05, 0.55, 0.50),
    "aerospace":       (1.10, 0.55, 0.65),
    "shipping":        (1.10, 0.55, 0.60),
}

_DEFAULT_RESILIENCE = 0.50   # neutral prior for economies LPI 2018 doesn't cover here


@lru_cache(maxsize=1)
def _lpi_resilience() -> dict[str, float]:
    """ISO3 → resilience, using the same LPI→resilience map as seed_data.

    resilience_i = 0.20 + 0.60·(LPI_i − 3.05)/1.15, clipped to [0.20, 0.80].
    """
    path = _RAW_DIR / "wb_lpi_2018.json"
    out: dict[str, float] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.warning("LPI 2018 file missing/unreadable; using neutral resilience for all")
        return out
    for rec in data.get("records", []):
        iso3 = rec.get("iso3")
        lpi = rec.get("value")
        if not iso3 or lpi is None:
            continue
        res = 0.20 + 0.60 * (float(lpi) - 3.05) / 1.15
        out[iso3] = max(0.20, min(0.80, round(res, 3)))
    return out


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _build_nodes(rows: list[dict[str, str]]) -> list[Node]:
    lpi = _lpi_resilience()
    nodes: list[Node] = []
    for r in rows:
        icio_industry = r["industry"]
        ind = _INDUSTRY_MAP.get(icio_industry)
        if ind is None:
            log.warning("Unknown v3 industry %r on node %s — skipped", icio_industry, r["node_id"])
            continue
        iso3 = r["country_iso3"]
        resilience = lpi.get(iso3, _DEFAULT_RESILIENCE)
        amp, thresh, _sub = _SECTOR_DEFAULTS[icio_industry]
        output_usd = float(r.get("output_usd_m", 0.0) or 0.0) * 1e6
        nodes.append(
            Node(
                id=r["node_id"],
                name=f"{iso3} · {icio_industry.replace('_', ' ').title()}",
                kind=NodeKind.COUNTRY_INDUSTRY,
                country=iso3,
                industry=ind,
                gdp_usd=output_usd,
                vulnerability=round(1.0 - resilience, 3),
                resilience=resilience,
                amplification=amp,
                threshold=thresh,
                recovery_delay_weeks=8.0,
                meta={
                    "icio_industry": icio_industry,
                    "icio_codes": r.get("icio_codes", ""),
                    "world_sector_share": float(r.get("world_sector_share", 0.0) or 0.0),
                    "resilience_source": "lpi_2018" if iso3 in lpi else "neutral_default",
                },
            )
        )
    return nodes


def _build_edges(rows: list[dict[str, str]], valid_ids: set[str], node_industry: dict[str, str]) -> list[Edge]:
    edges: list[Edge] = []
    skipped_self = skipped_unknown = 0
    for r in rows:
        src, tgt = r["source"], r["target"]
        if src == tgt:
            skipped_self += 1
            continue
        if src not in valid_ids or tgt not in valid_ids:
            skipped_unknown += 1
            continue
        penetration = float(r.get("penetration", 0.0) or 0.0)
        dep = max(0.0, min(1.0, penetration))
        _amp, _thr, sub = _SECTOR_DEFAULTS.get(node_industry.get(src, ""), (1.0, 0.5, 0.6))
        edges.append(
            Edge(
                source=src,
                target=tgt,
                kind=EdgeKind.PRODUCTION_INPUT,
                dependency_weight=dep,
                substitution_difficulty=sub,
                rerouting_capability=0.25,
                resilience_coefficient=0.22,
                recovery_delay_weeks=8.0,
                flow_value_usd=float(r.get("flow_usd_m", 0.0) or 0.0) * 1e6,
                meta={"input_share": float(r.get("input_share", 0.0) or 0.0)},
            )
        )
    if skipped_self or skipped_unknown:
        log.info("v3 edges: skipped %d self-loops, %d unknown-endpoint", skipped_self, skipped_unknown)
    return edges


def _centrality_and_paths(
    nodes: list[Node], edges: list[Edge]
) -> tuple[dict[str, float], dict[str, dict[str, int]]]:
    """PageRank-on-reverse blended with weighted out-degree (same recipe as seed.py)."""
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(n.id)
    for e in edges:
        w = e.dependency_weight * (0.5 + 0.5 * e.substitution_difficulty)
        g.add_edge(e.source, e.target, weight=w)

    rev = g.reverse(copy=False)
    try:
        pr = nx.pagerank(rev, alpha=0.85, weight="weight", max_iter=500, tol=1e-8)
    except (nx.PowerIterationFailedConvergence, nx.NetworkXException):
        pr = {n: 1.0 / max(1, g.number_of_nodes()) for n in g.nodes()}

    out_deg = {n: 0.0 for n in g.nodes()}
    for u, _, data in g.edges(data=True):
        out_deg[u] += float(data.get("weight", 0.0))
    max_out = max(out_deg.values()) if out_deg else 1.0
    max_out = max_out or 1.0

    blended = {n: 0.6 * pr.get(n, 0.0) + 0.4 * (out_deg.get(n, 0.0) / max_out) for n in g.nodes()}
    max_c = max(blended.values()) if blended else 1.0
    max_c = max_c or 1.0
    centrality = {k: v / max_c for k, v in blended.items()}

    # ECV-geo origins: the electronics_c26 (semi proxy) nodes — the likely shock origins.
    origins = [n.id for n in nodes if n.meta.get("icio_industry") == "electronics_c26"]
    shortest_path: dict[str, dict[str, int]] = {}
    for o in origins:
        try:
            shortest_path[o] = dict(nx.single_source_shortest_path_length(g, o))
        except nx.NodeNotFound:
            shortest_path[o] = {}
    return centrality, shortest_path


@lru_cache(maxsize=1)
def build_expanded_snapshot() -> GraphSnapshot:
    """Materialize the ICIO 81×5 expanded graph as an engine-ready GraphSnapshot."""
    node_rows = _read_csv(_CSV_DIR / "expanded_graph_nodes_v3.csv")
    edge_rows = _read_csv(_CSV_DIR / "expanded_graph_edges_v3.csv")

    nodes = _build_nodes(node_rows)
    valid_ids = {n.id for n in nodes}
    node_industry = {n.id: n.meta.get("icio_industry", "") for n in nodes}
    edges = _build_edges(edge_rows, valid_ids, node_industry)

    centrality, shortest_path = _centrality_and_paths(nodes, edges)

    log.info("Built expanded (v3) snapshot: %d nodes, %d edges", len(nodes), len(edges))
    return GraphSnapshot(
        version="0.3.0-icio81x5",
        nodes=nodes,
        edges=edges,
        centrality=centrality,
        shortest_path=shortest_path,
    )
