"""Tests for the OECD ICIO 2025 cross-validation layer.

Assertions are pinned to *measured facts* in the committed raw table
(backend/data/raw/external/icio2025/2019_SML.csv.gz), so they double as a
data-integrity check: replacing the file with a different export/edition
that violates these known totals will be caught here.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.icio import (
    SPECIAL_ROWS,
    economies,
    industries,
    intermediate_block,
    load_icio,
    run_edge_check,
    run_graph_expansion,
)
from app.data.seed_data import CHOKEPOINT_LINKS, EDGES_RAW


@pytest.fixture(scope="module")
def df():
    return load_icio(2019)


@pytest.fixture(scope="module")
def edge_check():
    return run_edge_check(2019)


def test_matrix_shape_and_labels(df):
    assert df.shape == (4053, 4537)          # 81*50 + TLS/VA/OUT x 4050 + 81*6 FD + OUT
    assert len(economies(df)) == 81          # 80 economies + ROW (2025 ed., small)
    assert len(industries(df)) == 50
    for row in SPECIAL_ROWS:
        assert row in df.index
    # 2025-edition markers: new countries and the new sector splits
    for label in ("AGO_A01", "ARE_C26", "TWN_C24A", "JPN_C301"):
        assert label in df.index


def test_world_value_added_magnitude(df):
    # VA summed over all production columns ~ world GDP 2019 ~ 87 USD trillion
    z = intermediate_block(df)
    va = float(df.loc["VA", z.columns].sum())
    assert 7.0e7 < va < 1.0e8                # USD million


def test_taiwan_c26_is_a_top5_world_producer(df):
    out = df["OUT"]
    c26 = {r: out[r] for r in df.index if r.endswith("_C26")}
    top5 = sorted(c26, key=c26.get, reverse=True)[:5]
    assert "TWN_C26" in top5
    assert c26["TWN_C26"] > 100_000          # > 100 USD billion gross output


def test_known_flows(df):
    # Taiwan electronics/semis into China electronics: tens of billions
    assert df.loc["TWN_C26", "CHN_C26"] > 20_000
    # The ASML capital channel: NLD machinery into Taiwan's investment column.
    # This is the measured basis for keeping NLD:semi edges literature-authored
    # (equipment flows are GFCF, structurally invisible in Z).
    assert df.loc["NLD_C28", "TWN_GFCF"] > 1_000


def test_edge_check_covers_every_seed_edge(edge_check):
    assert edge_check["summary"]["n_production_edges"] == len(EDGES_RAW)
    assert edge_check["summary"]["n_chokepoint_links_excluded"] == len(CHOKEPOINT_LINKS)
    assert (
        edge_check["summary"]["n_total_seed_edges"]
        == len(EDGES_RAW) + len(CHOKEPOINT_LINKS)
    )


def test_edge_check_measures_are_shares(edge_check):
    for rec in edge_check["edges"]:
        assert rec["icio_flow_usd_m"] >= 0.0
        for key in ("icio_input_share", "icio_penetration",
                    "icio_import_penetration", "icio_import_penetration_incl_fd"):
            v = rec[key]
            if v is not None:
                assert 0.0 <= v <= 1.0, f"{rec['src']}->{rec['tgt']} {key}={v}"
        # import measures are undefined exactly for domestic edges
        src_c = rec["src"].split(":")[0]
        tgt_c = rec["tgt"].split(":")[0]
        if src_c == tgt_c:
            assert rec["icio_import_penetration"] is None


def test_edge_check_pins_the_key_findings(edge_check):
    by_edge = {(r["src"], r["tgt"]): r for r in edge_check["edges"]}
    # DEU->JPN auto: import penetration ~0.23 (manual 0.451 was finished-car
    # import share; plain penetration ~0.015 because domestic supply dominates)
    deu_jpn = by_edge[("DEU:automotive", "JPN:automotive")]
    assert 0.15 < deu_jpn["icio_import_penetration"] < 0.35
    assert deu_jpn["icio_penetration"] < 0.05
    # ASML edges: flow shares cannot represent the dependency (capital channel)
    asml = by_edge[("NLD:semiconductors", "TWN:semiconductors")]
    assert asml["icio_penetration"] < 0.01
    assert asml["nld_c28_to_tgt_gfcf_usd_m"] > 1_000


def test_expansion_prototype_consistency():
    nodes, edges, meta = run_graph_expansion(2019)
    assert len(nodes) == 81 * 5              # EXPANSION_SECTOR_MAP merges semi+elec
    assert meta["n_edges"] == len(edges) > 1_000
    node_ids = set(nodes["node_id"])
    assert set(edges["source"]).issubset(node_ids)
    assert set(edges["target"]).issubset(node_ids)
    assert (edges["flow_usd_m"] >= meta["filters"]["min_flow_usd_m"]).all()
    assert (edges["penetration"] <= 1.0 + 1e-9).all()
    assert not (edges["source"] == edges["target"]).any()
    # world sector shares sum to 1 per industry
    sums = nodes.groupby("industry")["world_sector_share"].sum()
    assert np.allclose(sums, 1.0, atol=0.01)


def test_c26_split_overlay():
    from app.core.icio import run_c26_split

    payload = run_c26_split()
    shares = payload["importer_world_semi_share"]
    # measured trade structure: chip-importing assemblers vs finished-goods importers
    assert shares["TWN"] > 0.80
    assert shares["MYS"] > 0.75
    assert shares["USA"] < 0.25
    # every cross-border semi-family edge is rescored
    assert len(payload["edges"]) == 28
    for r in payload["edges"]:
        pen = r["icio_semi_import_penetration"]
        if pen is not None:
            assert 0.0 <= pen <= 1.0
    # the headline: with the three capital-channel (ASML) edges excluded, the
    # hand-authored semi weights track the measured semi-specific penetration
    corr = payload["semi_family_correlation_excl_capital_channel"]
    assert corr["n"] == 25
    assert corr["pearson"] > 0.7
    assert corr["spearman"] > 0.7
