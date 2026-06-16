"""Smoke tests for the ICIO-grounded expanded (v3) graph.

These pin the structural contract of the 81-economy × 5-sector graph and prove
it runs end-to-end through the existing engine, so the opt-in expansion can't
silently rot. The v2 default path is exercised by the rest of the suite; here we
verify v3 specifically.
"""

from __future__ import annotations

from app.core.graph import compile_graph
from app.core.propagation import simulate
from app.core.types import EngineConfig, Industry, NodeKind, Scenario, ShockSpec
from app.data.expanded_graph import build_expanded_snapshot, to_v3_node
from app.data.seed import compiled_graph_for


def test_v3_snapshot_shape():
    snap = build_expanded_snapshot()
    assert len(snap.nodes) == 405, "expected 81 economies × 5 sectors"
    assert len(snap.edges) == 1964
    # every edge endpoint resolves to a node; no self-loops
    ids = {n.id for n in snap.nodes}
    assert all(e.source in ids and e.target in ids for e in snap.edges)
    assert all(e.source != e.target for e in snap.edges)
    # full centrality coverage; ECV-geo origins are the electronics_c26 (semi proxy) nodes
    assert len(snap.centrality) == 405
    assert len(snap.shortest_path) == 81


def test_v3_industry_mapping_and_resilience():
    snap = build_expanded_snapshot()
    by_id = {n.id: n for n in snap.nodes}
    twn = by_id["TWN:electronics_c26"]
    # merged C26 bucket carries ELECTRONICS coefficients
    assert twn.industry is Industry.ELECTRONICS
    assert twn.meta["icio_industry"] == "electronics_c26"
    assert twn.kind is NodeKind.COUNTRY_INDUSTRY
    # TWN has a real LPI 2018 resilience; an unlisted economy gets the neutral default
    assert twn.meta["resilience_source"] == "lpi_2018"
    assert 0.20 <= twn.resilience <= 0.80
    n_real = sum(1 for n in snap.nodes if n.meta.get("resilience_source") == "lpi_2018")
    assert n_real == 60, "12 LPI-covered countries × 5 sectors"


def test_v3_compiles_and_cascades():
    snap = build_expanded_snapshot()
    cg = compile_graph(snap)
    assert cg.n == 405
    assert cg.D_eff.nnz == 1964

    scen = Scenario(
        id="v3-smoke",
        name="v3 smoke",
        horizon_weeks=20,
        shocks=[
            ShockSpec(
                target_node_id="TWN:electronics_c26",
                magnitude=0.6,
                start_week=0,
                duration_weeks=4,
                decay_curve="step",
            )
        ],
        config=EngineConfig(),
    )
    res = simulate(scen, cg)
    assert len(res.frames) == 20
    peak_affected = max(f.affected_count for f in res.frames)
    assert peak_affected > 1, "shock must cascade beyond the directly-hit node"


def test_v3_nodes_have_map_coordinates():
    snap = build_expanded_snapshot()
    with_coords = [n for n in snap.nodes if n.lat is not None and n.lon is not None]
    # all but the 5 ROW (Rest-of-World) sector nodes have a country centroid
    assert len(with_coords) == 400
    twn = next(n for n in snap.nodes if n.id == "TWN:electronics_c26")
    assert 20 < twn.lat < 27 and 118 < twn.lon < 126  # near Taiwan


def test_v2_to_v3_node_mapping():
    assert to_v3_node("TWN:semiconductors") == "TWN:electronics_c26"
    assert to_v3_node("CHN:electronics") == "CHN:electronics_c26"
    assert to_v3_node("DEU:automotive") == "DEU:automotive"
    assert to_v3_node("CP:Suez") is None          # chokepoints have no v3 node
    assert to_v3_node("USA:energy") is None        # sector absent from the 5-sector v3


def test_compiled_graph_for_runs_remapped_scenario():
    """The exact run-flow the WebSocket uses when graph_version=v3."""
    g3 = compiled_graph_for("v3")
    assert g3.n == 405
    assert compiled_graph_for("v3") is g3, "compiled v3 graph must be cached"

    node = to_v3_node("TWN:semiconductors")
    scen = Scenario(
        id="v3-run", name="v3 run", horizon_weeks=20,
        shocks=[ShockSpec(target_node_id=node, magnitude=0.6, start_week=0, duration_weeks=4)],
        config=EngineConfig(),
    )
    res = simulate(scen, g3)
    assert max(f.affected_count for f in res.frames) > 1
