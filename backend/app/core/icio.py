"""OECD ICIO 2025 (year 2019) cross-validation of the hand-authored graph.

The 12x6 GEDS graph was authored from UN Comtrade penetration ratios and
sector-exposure factors (see seed_data.py header). The OECD Inter-Country
Input-Output table measures the same thing independently and at full
economy coverage: how many dollars of intermediate inputs each
country-industry buys from each other country-industry. Before any graph
expansion is built on ICIO, this module checks the hands we already played:
every EDGES_RAW dependency weight is recomputed from the measured 2019
flows and reported side by side with the authored value.

Two ICIO-derived measures per edge (src country-industry -> tgt):

  input_share  = flow(src, tgt) / total intermediate inputs of tgt
      "What fraction of everything tgt buys (from anyone, any sector)
       comes from src?"  This is the direct technical-coefficient share.

  penetration  = flow(src, tgt) / flow(all countries' src-industry, tgt)
      "Of tgt's purchases of the src INDUSTRY type, what share comes from
       the src COUNTRY?"  This mirrors the Comtrade import-penetration
       convention most EDGES_RAW weights were authored with (the TWN-semi
       family is penetration x sector_exposure_factor).

Chokepoint links are excluded: straits are not producing sectors, and their
weights follow the capacity-factor convention validated against IMF
PortWatch (PROGRESS.md Batch 5), not input-output flows.

Sector mapping (GEDS Industry -> ICIO 2025 activity codes, ISIC Rev.4):
  semiconductors -> C26        computer/electronic/optical (no finer split
                               exists in ICIO; collides with electronics,
                               so semi->elec edges are C26->C26 shares
                               including the within-sector supply chain)
  electronics    -> C26
  automotive     -> C29        motor vehicles
  aerospace      -> C302T309   other transport equipment (2025 ed. excludes
                               shipbuilding C301 -- cleaner than 2023 ed.)
  consumer_goods -> C10T12 + C13T15 + C31T33   (food/bev/tobacco, textiles/
                               apparel/leather, furniture/other mfg)
  shipping       -> H50        water transport

Known mapping caveats, reported per edge:
  - NLD:semiconductors is ASML (lithography equipment); equipment partly
    classifies as C28 machinery, so C26 understates the true dependency.
  - semiconductors vs electronics share C26 (above).

Raw data:  backend/data/raw/external/icio2025/2019_SML.csv.gz
Reproduce: python -m scripts.icio_derive_edges
Artifact:  data/calibration/icio_edge_check.json
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ICIO_DIR = (
    Path(__file__).resolve().parents[2]
    / "data" / "raw" / "external" / "icio2025"
)

ICIO_N_ECONOMIES = 81          # 80 economies + ROW (2025 ed., small version)
ICIO_N_INDUSTRIES = 50
SPECIAL_ROWS = ("TLS", "VA", "OUT")
FINAL_DEMAND_CATEGORIES = ("HFCE", "NPISH", "GGFC", "GFCF", "INVNT", "DPABR")

SECTOR_MAP: dict[str, list[str]] = {
    "semiconductors": ["C26"],
    "electronics":    ["C26"],
    "automotive":     ["C29"],
    "aerospace":      ["C302T309"],
    "consumer_goods": ["C10T12", "C13T15", "C31T33"],
    "shipping":       ["H50"],
}

MAPPING_CAVEATS: dict[str, str] = {
    "semiconductors": "ICIO has no semi split; uses all of C26 (collides with electronics)",
    "electronics":    "ICIO has no semi split; uses all of C26 (collides with semiconductors)",
    "NLD:semiconductors": "ASML litho equipment partly classifies as C28 machinery; C26 understates it",
}

# For the expanded-graph prototype the C26 collision cannot be ducked by
# annotation: keeping both industries would emit duplicate nodes with double-
# counted flows. The prototype therefore merges semiconductors+electronics
# into one C26 node type ("electronics_c26") until a finer split (e.g. via
# Comtrade HS 8541/8542 shares) is layered on top.
EXPANSION_SECTOR_MAP: dict[str, list[str]] = {
    "electronics_c26": ["C26"],
    "automotive":      ["C29"],
    "aerospace":       ["C302T309"],
    "consumer_goods":  ["C10T12", "C13T15", "C31T33"],
    "shipping":        ["H50"],
}


# ----------------------------- loading --------------------------------------


@lru_cache(maxsize=1)
def load_icio(year: int = 2019) -> pd.DataFrame:
    """Full ICIO matrix for one year, rows/cols indexed by label.

    Accepts both `<year>_SML.csv` and `<year>_SML.csv.gz` (the repo commits
    the gz; pandas decompresses transparently).
    """
    for suffix in (".csv.gz", ".csv"):
        path = ICIO_DIR / f"{year}_SML{suffix}"
        if path.exists():
            df = pd.read_csv(path, index_col=0)
            df.index.name = "row"
            return df
    raise FileNotFoundError(f"no {year}_SML.csv[.gz] under {ICIO_DIR}")


def intermediate_block(df: pd.DataFrame) -> pd.DataFrame:
    """The z block: country_industry rows x country_industry columns."""
    inter_rows = [r for r in df.index if r not in SPECIAL_ROWS]
    inter_cols = [
        c for c in df.columns
        if c != "OUT" and c.rsplit("_", 1)[-1] not in FINAL_DEMAND_CATEGORIES
    ]
    return df.loc[inter_rows, inter_cols]


def economies(df: pd.DataFrame) -> list[str]:
    return sorted({r.split("_", 1)[0] for r in df.index if r not in SPECIAL_ROWS})


def industries(df: pd.DataFrame) -> list[str]:
    return sorted({r.split("_", 1)[1] for r in df.index if r not in SPECIAL_ROWS})


# ------------------------ edge-level measures --------------------------------


def _labels(country: str, industry_value: str, sector_map: dict[str, list[str]] | None = None) -> list[str]:
    codes = (sector_map or SECTOR_MAP)[industry_value]
    return [f"{country}_{code}" for code in codes]


def edge_measures(df: pd.DataFrame, z: pd.DataFrame, src_id: str, tgt_id: str) -> dict:
    """ICIO measures for one GEDS edge.

    Four shares, because the hand-authored weights mix conventions:

      input_share              flow / ALL intermediate inputs of tgt
      penetration              flow / src-industry inputs of tgt (incl. the
                               tgt country's own domestic supply)
      import_penetration       flow / src-industry inputs of tgt from
                               FOREIGN sources only -- the Comtrade
                               convention the weights were authored with
      import_penetration_incl_fd   same, but absorption = intermediate cols
                               of the tgt sector + final-demand cols of the
                               tgt country (finished goods -- e.g. cars --
                               land in HFCE/GFCF, not in z)
    """
    src_c, src_ind = src_id.split(":")
    tgt_c, tgt_ind = tgt_id.split(":")

    src_rows = _labels(src_c, src_ind)
    tgt_cols = _labels(tgt_c, tgt_ind)
    # all-country rows of the source industry type, for penetration denominators
    src_codes = set(SECTOR_MAP[src_ind])
    type_rows = [r for r in z.index if r.split("_", 1)[1] in src_codes]
    foreign_type_rows = [r for r in type_rows if not r.startswith(f"{tgt_c}_")]
    fd_cols = [f"{tgt_c}_{cat}" for cat in FINAL_DEMAND_CATEGORIES]

    flow = float(z.loc[src_rows, tgt_cols].to_numpy().sum())
    total_inputs = float(z[tgt_cols].to_numpy().sum())
    type_inputs = float(z.loc[type_rows, tgt_cols].to_numpy().sum())
    foreign_type_inputs = float(z.loc[foreign_type_rows, tgt_cols].to_numpy().sum())

    absorb = lambda rows: float(  # noqa: E731 — tgt-sector z cols + tgt-country FD cols
        z.loc[rows, tgt_cols].to_numpy().sum() + df.loc[rows, fd_cols].to_numpy().sum()
    )
    flow_incl_fd = absorb(src_rows) if src_c != tgt_c else None
    foreign_absorption = absorb(foreign_type_rows)

    caveats = [
        v for k, v in MAPPING_CAVEATS.items()
        if k in (src_ind, tgt_ind, src_id, tgt_id)
    ]
    rec = {
        "src": src_id,
        "tgt": tgt_id,
        "icio_flow_usd_m": round(flow, 1),
        "icio_input_share": round(flow / total_inputs, 5) if total_inputs else None,
        "icio_penetration": round(flow / type_inputs, 5) if type_inputs else None,
        "icio_import_penetration": (
            round(flow / foreign_type_inputs, 5)
            if foreign_type_inputs and src_c != tgt_c else None
        ),
        "icio_import_penetration_incl_fd": (
            round(flow_incl_fd / foreign_absorption, 5)
            if flow_incl_fd is not None and foreign_absorption else None
        ),
        "mapping_caveats": sorted(set(caveats)),
    }
    # ASML channel: lithography equipment is C28 machinery flowing into the
    # buyer country's GFCF (investment), structurally invisible in z.
    if src_id == "NLD:semiconductors":
        rec["nld_c28_to_tgt_gfcf_usd_m"] = round(float(df.loc["NLD_C28", f"{tgt_c}_GFCF"]), 1)
    return rec


def classify_edge_family(src_id: str, tgt_id: str) -> str:
    """Authoring family per the seed_data.py conventions (drives which ICIO
    measure is the fair comparator)."""
    src_ind = src_id.split(":")[1]
    tgt_ind = tgt_id.split(":")[1]
    if src_ind == "semiconductors":
        return "penetration_x_exposure"      # Comtrade penetration x sector exposure
    if src_ind == "automotive" and tgt_ind == "automotive":
        return "pure_penetration"            # Comtrade HS-8703 penetration ratio
    return "authored"                        # literature/calibrated weights


# ----------------------------- the check ------------------------------------


def run_edge_check(year: int = 2019) -> dict:
    """Compare every seed-graph edge weight against ICIO-derived measures.

    Production edges (EDGES_RAW) get the four flow shares; chokepoint links
    are included as records but not scored -- straits are not producing
    sectors and their weights follow the PortWatch-validated capacity-factor
    convention (PROGRESS.md Batch 5), which has no input-output analog.
    """
    from scipy import stats

    from ..data.seed_data import CHOKEPOINT_LINKS, EDGES_RAW

    df = load_icio(year)
    z = intermediate_block(df)

    records: list[dict] = []
    for src, tgt, dep, *_rest in EDGES_RAW:
        rec = edge_measures(df, z, src, tgt)
        rec["manual_weight"] = dep
        rec["family"] = classify_edge_family(src, tgt)
        for key in ("icio_penetration", "icio_import_penetration",
                    "icio_import_penetration_incl_fd"):
            short = key.replace("icio_", "")
            rec[f"manual_over_{short}"] = (
                round(dep / rec[key], 2) if rec[key] else None
            )
        records.append(rec)

    excluded = [
        {
            "src": src, "tgt": tgt, "manual_weight": dep,
            "family": "chokepoint_capacity_factor",
            "excluded_reason": "chokepoints are not producing sectors; weights follow the "
                               "capacity-factor convention validated against IMF PortWatch "
                               "(Batch 5), no I-O analog",
        }
        for src, tgt, dep in CHOKEPOINT_LINKS
    ]

    manual = np.array([r["manual_weight"] for r in records])
    measures = {
        key: np.array(
            [r[key] if r[key] is not None else np.nan for r in records], dtype=float
        )
        for key in ("icio_input_share", "icio_penetration",
                    "icio_import_penetration", "icio_import_penetration_incl_fd")
    }

    def corr_block(x: np.ndarray, y: np.ndarray) -> dict:
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 3:
            return {"n": int(ok.sum())}
        return {
            "n": int(ok.sum()),
            "pearson": round(float(stats.pearsonr(x[ok], y[ok])[0]), 3),
            "spearman": round(float(stats.spearmanr(x[ok], y[ok])[0]), 3),
        }

    summary: dict = {
        "n_production_edges": len(records),
        "n_chokepoint_links_excluded": len(excluded),
        "n_total_seed_edges": len(records) + len(excluded),
        "correlations": {k: corr_block(manual, v) for k, v in measures.items()},
        "by_family": {},
    }
    for fam in sorted({r["family"] for r in records}):
        idx = np.array([r["family"] == fam for r in records])
        summary["by_family"][fam] = {
            k: corr_block(manual[idx], v[idx]) for k, v in measures.items()
        }

    # largest disagreements vs the fairest like-for-like measure:
    # import penetration incl. final demand, falling back to plain penetration
    # for domestic edges (import measures are undefined there).
    comparator = np.where(
        np.isfinite(measures["icio_import_penetration_incl_fd"]),
        measures["icio_import_penetration_incl_fd"],
        measures["icio_penetration"],
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        log_ratio = np.log10(manual / comparator)
    order = np.argsort(np.abs(np.where(np.isfinite(log_ratio), log_ratio, 0.0)))[::-1]
    summary["worst_disagreements"] = [
        {
            "edge": f"{records[i]['src']} -> {records[i]['tgt']}",
            "manual": records[i]["manual_weight"],
            "comparator": round(float(comparator[i]), 5) if np.isfinite(comparator[i]) else None,
            "manual_over_comparator": (
                round(float(manual[i] / comparator[i]), 2)
                if np.isfinite(comparator[i]) and comparator[i] > 0 else None
            ),
            "family": records[i]["family"],
            "mapping_caveats": records[i]["mapping_caveats"],
        }
        for i in order[:10]
    ]

    return {
        "year": year,
        "source": "OECD ICIO 2025 edition, small (81 economies x 50 industries)",
        "raw_file": f"backend/data/raw/external/icio2025/{year}_SML.csv.gz",
        "method": {
            "input_share": "flow(src,tgt) / total intermediate inputs of tgt (z columns only; "
                           "VA/TLS/final demand excluded)",
            "penetration": "flow(src,tgt) / flow(all countries' src-industry rows, tgt), "
                           "domestic supply included in the denominator",
            "import_penetration": "as penetration but FOREIGN sources only -- the Comtrade "
                                  "convention most weights were authored with",
            "import_penetration_incl_fd": "import penetration over absorption = tgt-sector "
                                          "intermediate cols + tgt-country final-demand cols "
                                          "(finished goods land in HFCE/GFCF, not z)",
            "sector_map": {k: v for k, v in SECTOR_MAP.items()},
            "chokepoint_links": "included as excluded records (capacity-factor convention)",
        },
        "summary": summary,
        "edges": records,
        "excluded_chokepoint_links": excluded,
    }


# ------------------------ expanded-graph prototype ---------------------------


def run_graph_expansion(
    year: int = 2019,
    min_flow_usd_m: float = 50.0,
    min_input_share: float = 0.002,
    min_penetration: float = 0.05,
    sector_map: dict[str, list[str]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Prototype node/edge tables for the full ICIO graph (NOT wired into the
    engine -- exported as CSV for inspection).

    Nodes: every economy x industry under EXPANSION_SECTOR_MAP (81 x 5 = 405;
    semiconductors+electronics merged into electronics_c26, see note on the
    map), sized by 2019 gross output and world-sector share.

    Edges: every cross-node pair whose measured flow clears
    `min_flow_usd_m` AND clears either share threshold. Self-pairs
    (same node to itself) are excluded; cross-border AND domestic
    cross-industry pairs are kept (the 12x6 graph also has intra-country
    edges).
    """
    smap = sector_map or EXPANSION_SECTOR_MAP
    df = load_icio(year)
    z = intermediate_block(df)
    econs = economies(df)
    inds = list(smap)

    # aggregate z rows to (economy x industry)
    row_group: dict[tuple[str, str], list[str]] = {}
    for r in z.index:
        c, code = r.split("_", 1)
        for ind, codes in smap.items():
            if code in codes:
                row_group.setdefault((c, ind), []).append(r)

    agg_rows = {key: z.loc[rows].sum(axis=0) for key, rows in row_group.items()}
    agg = pd.DataFrame(agg_rows).T          # MultiIndex (econ, ind) -> all z columns
    cols_total = z.sum(axis=0)            # total intermediate inputs per column

    node_rows = []
    out_col = df["OUT"]
    for c in econs:
        for ind in inds:
            output = float(out_col.loc[_labels(c, ind, smap)].sum())
            node_rows.append({
                "node_id": f"{c}:{ind}",
                "country_iso3": c,
                "industry": ind,
                "icio_codes": "+".join(smap[ind]),
                "output_usd_m": round(output, 1),
            })
    nodes = pd.DataFrame(node_rows)
    world_output = nodes.groupby("industry")["output_usd_m"].transform("sum")
    nodes["world_sector_share"] = (nodes["output_usd_m"] / world_output).round(5)

    edge_rows = []
    for tc in econs:
        for tind in inds:
            tgt_cols = _labels(tc, tind, smap)
            tgt_flow = agg[tgt_cols].sum(axis=1)           # inflow from every (sc, sind)
            total_inputs = float(cols_total[tgt_cols].sum())
            if total_inputs <= 0:
                continue
            type_totals = tgt_flow.groupby(level=1).sum()
            for (sc, sind), flow in tgt_flow.items():
                if (sc == tc and sind == tind) or flow < min_flow_usd_m:
                    continue
                input_share = flow / total_inputs
                type_total = float(type_totals[sind])
                penetration = flow / type_total if type_total > 0 else 0.0
                if input_share < min_input_share and penetration < min_penetration:
                    continue
                edge_rows.append({
                    "source": f"{sc}:{sind}",
                    "target": f"{tc}:{tind}",
                    "flow_usd_m": round(float(flow), 1),
                    "input_share": round(float(input_share), 5),
                    "penetration": round(float(penetration), 5),
                })
    edges = pd.DataFrame(edge_rows).sort_values(
        "flow_usd_m", ascending=False
    ).reset_index(drop=True)

    meta = {
        "year": year,
        "source": "OECD ICIO 2025 edition, small",
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "sector_map": {k: "+".join(v) for k, v in smap.items()},
        "note": "semiconductors+electronics merged into electronics_c26 "
                "(ICIO C26 is not separable); NOT wired into the engine",
        "filters": {
            "min_flow_usd_m": min_flow_usd_m,
            "min_input_share": min_input_share,
            "min_penetration": min_penetration,
        },
    }
    return nodes, edges, meta


# ------------------- C26 semi/electronics split overlay ----------------------
#
# ICIO C26 bundles semiconductors with the rest of computer/electronic/optical
# manufacturing — the one mapping collision flagged by run_edge_check and the
# expansion prototype. The committed UN Comtrade 2019 imports (the same pull
# the original edge weights were authored from) let us measure, per importer
# and per trade partner, what share of C26-type goods is semiconductors:
#
#   semi_share = (HS 8541 + 8542) / (HS 8541 + 8542 + 8471 + 8517 + 8528)
#
# i.e. chips+components over chips+components+computers+phones+displays.
# This is goods trade only (CIF, importer-reported) — an approximation of the
# C26 product mix, not of domestic production, so it refines only the
# cross-border semi-family comparators.

COMTRADE_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "comtrade"

SEMI_HS = ("8541", "8542")
ELEC_HS = ("8471", "8517", "8528")

# UN M49 reporter codes of the committed pull -> graph country codes.
# 490 "Other Asia, nes" is how Comtrade reports Taiwan (also partnerISO S19).
COMTRADE_REPORTERS = {
    156: "CHN", 276: "DEU", 392: "JPN", 410: "KOR", 458: "MYS", 484: "MEX",
    490: "TWN", 528: "NLD", 699: "IND", 704: "VNM", 764: "THA", 842: "USA",
}
_PARTNER_ISO_FIX = {"S19": "TWN"}


def load_c26_trade(year: int = 2019) -> pd.DataFrame:
    """Tidy (importer, exporter, hs, value_usd) for the five C26-type HS codes."""
    frames = []
    for m49, iso3 in COMTRADE_REPORTERS.items():
        for hs in SEMI_HS + ELEC_HS:
            path = COMTRADE_DIR / f"comtrade_A_M_{m49}_{hs}_{year}.parquet"
            if not path.exists():
                continue
            df = pd.read_parquet(
                path, columns=["partnerISO", "cmdCode", "primaryValue"]
            )
            df = df.rename(columns={"partnerISO": "exporter", "cmdCode": "hs",
                                    "primaryValue": "value_usd"})
            df["exporter"] = df["exporter"].replace(_PARTNER_ISO_FIX)
            df["importer"] = iso3
            frames.append(df)
    if not frames:
        raise FileNotFoundError(f"no Comtrade parquet files under {COMTRADE_DIR}")
    return pd.concat(frames, ignore_index=True)


def run_c26_split(year: int = 2019, min_pair_usd: float = 5e7) -> dict:
    """Measure semi vs non-semi composition of C26-type imports, then rescore
    the cross-border semi-family edges with a semi-specific import penetration.

    Refinement: every exporter's ICIO C26 flow into the target sector is
    multiplied by that (exporter -> importer) semi_share (fallback: the
    importer's world share) before the penetration ratio is recomputed, so the
    denominator is the target's *semiconductor* import basket instead of all
    C26 goods.
    """
    from scipy import stats

    from ..data.seed_data import EDGES_RAW

    trade = load_c26_trade(year)

    # importer-level shares from the World rows (W00)
    world = trade[trade["exporter"] == "W00"]
    world_semi = world[world["hs"].isin(SEMI_HS)].groupby("importer")["value_usd"].sum()
    world_all = world.groupby("importer")["value_usd"].sum()
    world_share = (world_semi / world_all).to_dict()

    # pair-level shares
    pairs = trade[trade["exporter"] != "W00"]
    pair_tot = pairs.groupby(["importer", "exporter"])["value_usd"].sum()
    pair_semi = (
        pairs[pairs["hs"].isin(SEMI_HS)]
        .groupby(["importer", "exporter"])["value_usd"].sum()
    )
    pair_share = (pair_semi / pair_tot).dropna()
    pair_share = pair_share[pair_tot.loc[pair_share.index] >= min_pair_usd]

    def share(importer: str, exporter: str) -> float:
        v = pair_share.get((importer, exporter))
        return float(v) if v is not None else float(world_share.get(importer, np.nan))

    # rescore the cross-border semi-family edges
    df = load_icio(year)
    z = intermediate_block(df)
    c26_rows = [r for r in z.index if r.endswith("_C26")]

    records = []
    for src, tgt, dep, *_rest in EDGES_RAW:
        if classify_edge_family(src, tgt) != "penetration_x_exposure":
            continue
        src_c, src_ind = src.split(":")
        tgt_c, tgt_ind = tgt.split(":")
        if src_c == tgt_c or src_ind != "semiconductors":
            continue
        tgt_cols = _labels(tgt_c, tgt_ind)
        flows = z.loc[c26_rows, tgt_cols].sum(axis=1)          # per exporter row
        semi_flows = {
            r.split("_", 1)[0]: float(flows[r]) * share(tgt_c, r.split("_", 1)[0])
            for r in c26_rows
        }
        foreign_total = sum(
            v for c, v in semi_flows.items() if c != tgt_c and np.isfinite(v)
        )
        refined = (
            semi_flows[src_c] / foreign_total
            if foreign_total > 0 and np.isfinite(semi_flows[src_c]) else None
        )
        records.append({
            "src": src, "tgt": tgt,
            "manual_weight": dep,
            "semi_share_pair": round(share(tgt_c, src_c), 4),
            "icio_semi_import_penetration": round(refined, 5) if refined else None,
        })

    manual = np.array([r["manual_weight"] for r in records])
    refined_arr = np.array(
        [r["icio_semi_import_penetration"] or np.nan for r in records], dtype=float
    )

    def corr_block(mask: np.ndarray) -> dict:
        ok = mask & np.isfinite(refined_arr)
        if ok.sum() < 3:
            return {"n": int(ok.sum())}
        return {
            "n": int(ok.sum()),
            "pearson": round(float(stats.pearsonr(manual[ok], refined_arr[ok])[0]), 3),
            "spearman": round(float(stats.spearmanr(manual[ok], refined_arr[ok])[0]), 3),
        }

    all_mask = np.ones(len(records), dtype=bool)
    # the three NLD/ASML edges are a measured capital-account channel
    # (C28 -> GFCF, see run_edge_check) — no flow share can represent them
    non_capital = np.array(
        [not r["src"].startswith("NLD:") for r in records], dtype=bool
    )
    corr = corr_block(all_mask)
    corr_excl_capital = corr_block(non_capital)

    return {
        "year": year,
        "source": "UN Comtrade 2019 (committed parquet pull) x OECD ICIO 2025",
        "method": {
            "semi_share": "(HS 8541+8542) / (8541+8542+8471+8517+8528), CIF import values",
            "refined_penetration": "exporter C26 flows weighted by pair semi_share "
                                   "(fallback: importer world share) before the "
                                   "foreign-source penetration ratio",
            "min_pair_usd": min_pair_usd,
            "limitation": "goods trade approximates the C26 product mix; domestic "
                          "flows stay unsplit, so only cross-border semi-family "
                          "edges are rescored",
        },
        "importer_world_semi_share": {k: round(v, 4) for k, v in sorted(world_share.items())},
        "n_pair_shares": len(pair_share),
        "semi_family_correlation_manual_vs_refined": corr,
        "semi_family_correlation_excl_capital_channel": corr_excl_capital,
        "edges": records,
    }


__all__ = [
    "COMTRADE_REPORTERS",
    "EXPANSION_SECTOR_MAP",
    "ICIO_DIR",
    "SECTOR_MAP",
    "classify_edge_family",
    "economies",
    "edge_measures",
    "industries",
    "intermediate_block",
    "load_c26_trade",
    "load_icio",
    "run_c26_split",
    "run_edge_check",
    "run_graph_expansion",
]
