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

# v2 sector → v3 ICIO sector. semiconductors+electronics collapse into the merged
# C26 bucket (ICIO cannot split them); chemicals/energy/agriculture have no v3 node.
_V2_TO_V3_SECTOR = {
    "semiconductors": "electronics_c26",
    "electronics": "electronics_c26",
    "automotive": "automotive",
    "consumer_goods": "consumer_goods",
    "shipping": "shipping",
    "aerospace": "aerospace",
}


def to_v3_node(node_id: str) -> str | None:
    """Map a v2 'COUNTRY:sector' id to its v3 equivalent, or None if unrepresentable
    (chokepoints 'CP:*', or chemicals/energy/agriculture absent from the 5-sector v3)."""
    if ":" not in node_id:
        return None
    country, sector = node_id.split(":", 1)
    v3_sector = _V2_TO_V3_SECTOR.get(sector)
    return f"{country}:{v3_sector}" if v3_sector else None


# Approximate country centroids (lat, lon) for the 81 ICIO economies, so v3 nodes
# render on the world map. ROW (Rest of World) is an aggregate with no location.
_COUNTRY_CENTROID: dict[str, tuple[float, float]] = {
    "AGO": (-12.3, 17.5), "ARE": (23.4, 53.8), "ARG": (-38.4, -63.6), "AUS": (-25.3, 133.8),
    "AUT": (47.5, 14.6), "BEL": (50.5, 4.5), "BGD": (23.7, 90.4), "BGR": (42.7, 25.5),
    "BLR": (53.7, 27.9), "BRA": (-14.2, -51.9), "BRN": (4.5, 114.7), "CAN": (56.1, -106.3),
    "CHE": (46.8, 8.2), "CHL": (-35.7, -71.5), "CHN": (35.9, 104.2), "CIV": (7.5, -5.5),
    "CMR": (7.4, 12.4), "COD": (-4.0, 21.8), "COL": (4.6, -74.3), "CRI": (9.7, -83.8),
    "CYP": (35.1, 33.4), "CZE": (49.8, 15.5), "DEU": (51.2, 10.4), "DNK": (56.3, 9.5),
    "EGY": (26.8, 30.8), "ESP": (40.5, -3.7), "EST": (58.6, 25.0), "FIN": (61.9, 25.7),
    "FRA": (46.2, 2.2), "GBR": (55.4, -3.4), "GRC": (39.1, 21.8), "HKG": (22.3, 114.2),
    "HRV": (45.1, 15.2), "HUN": (47.2, 19.5), "IDN": (-0.8, 113.9), "IND": (20.6, 78.9),
    "IRL": (53.4, -8.2), "ISL": (64.9, -19.0), "ISR": (31.0, 34.9), "ITA": (41.9, 12.6),
    "JOR": (30.6, 36.2), "JPN": (36.2, 138.3), "KAZ": (48.0, 66.9), "KHM": (12.6, 104.9),
    "KOR": (35.9, 127.8), "LAO": (19.9, 102.5), "LTU": (55.2, 23.9), "LUX": (49.8, 6.1),
    "LVA": (56.9, 24.6), "MAR": (31.8, -7.1), "MEX": (23.6, -102.5), "MLT": (35.9, 14.4),
    "MMR": (21.9, 96.0), "MYS": (4.2, 101.9), "NGA": (9.1, 8.7), "NLD": (52.1, 5.3),
    "NOR": (60.5, 8.5), "NZL": (-40.9, 174.9), "PAK": (30.4, 69.3), "PER": (-9.2, -75.0),
    "PHL": (12.9, 121.8), "POL": (51.9, 19.1), "PRT": (39.4, -8.2), "ROU": (45.9, 25.0),
    "RUS": (61.5, 105.3), "SAU": (23.9, 45.1), "SEN": (14.5, -14.5), "SGP": (1.35, 103.8),
    "STP": (0.2, 6.6), "SVK": (48.7, 19.7), "SVN": (46.2, 14.8), "SWE": (60.1, 18.6),
    "THA": (15.9, 100.9), "TUN": (33.9, 9.6), "TUR": (39.0, 35.2), "TWN": (23.7, 121.0),
    "UKR": (48.4, 31.2), "USA": (37.1, -95.7), "VNM": (14.1, 108.3), "ZAF": (-30.6, 22.9),
}

# Stable per-sector angular offset so a country's 5 sector-nodes form a small
# legible cluster instead of stacking on one pixel.
_SECTOR_ORDER = ["electronics_c26", "automotive", "consumer_goods", "aerospace", "shipping"]


def _node_coords(iso3: str, icio_industry: str) -> tuple[float | None, float | None]:
    base = _COUNTRY_CENTROID.get(iso3)
    if base is None:
        return None, None
    import math
    i = _SECTOR_ORDER.index(icio_industry) if icio_industry in _SECTOR_ORDER else 0
    r = 1.4  # degrees
    angle = (2 * math.pi / len(_SECTOR_ORDER)) * i
    return round(base[0] + r * math.sin(angle), 3), round(base[1] + r * math.cos(angle), 3)


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
        lat, lon = _node_coords(iso3, icio_industry)
        nodes.append(
            Node(
                id=r["node_id"],
                name=f"{iso3} · {icio_industry.replace('_', ' ').title()}",
                kind=NodeKind.COUNTRY_INDUSTRY,
                country=iso3,
                industry=ind,
                lat=lat,
                lon=lon,
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
