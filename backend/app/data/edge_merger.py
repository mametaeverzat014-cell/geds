"""Merge real Comtrade-derived edges with hardcoded MVP edges.

Source of real data: backend/data/csv/comtrade_edges.csv (produced by
scripts/fetch_comtrade.py; refreshed daily by GitHub Actions cron).

Strategy
--------
1. Read all `EDGES_RAW` and `CHOKEPOINT_LINKS` from seed_data.py (the legacy
   hardcoded MVP edges). Keep them as the baseline.
2. Read comtrade_edges.csv. For each row:
   a. If the (source_node_id, target_node_id) already exists in EDGES_RAW,
      OVERRIDE the hardcoded `dependency_weight` and `flow_value_usd`
      with the real Comtrade value (keep other attributes from the
      hardcoded entry: substitution_difficulty, rerouting_capability, etc.)
   b. If it does NOT exist, ADD it as a new edge with reasonable defaults
      for the non-dependency parameters.
3. Skip Comtrade edges whose source or target node is not in the GEDS
   node set (e.g. South Africa, since we only have 12 countries).
4. Skip self-loops (source == target).

This is the highest-leverage scientific improvement available right now:
it injects ~hundreds of real bilateral flows into the engine without
fabricating any numbers.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..core.types import Edge, EdgeKind, Industry


log = logging.getLogger("geds.edge_merger")


COMTRADE_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "csv" / "comtrade_edges.csv"


# Defaults applied to Comtrade-derived edges that don't exist in the
# hardcoded set. Conservative middle-of-the-road values per OECD STAN +
# substitution-elasticity literature (cf. model_parameters.csv).
DEFAULT_SUBSTITUTION_DIFFICULTY = 0.60   # mid-range for industrial goods
DEFAULT_REROUTING_CAPABILITY = 0.30      # mid-range
DEFAULT_RESILIENCE_COEFFICIENT = 0.20    # mid-range
DEFAULT_RECOVERY_DELAY_WEEKS = 8.0       # auto-industry typical


@dataclass
class MergeReport:
    n_hardcoded: int
    n_comtrade_csv: int
    n_overridden: int                # hardcoded edge had its weight replaced by Comtrade
    n_added: int                     # new edge appended from Comtrade
    n_skipped_unknown_node: int      # source or target not in graph
    n_skipped_self_loop: int
    n_final: int


def _build_node_id(iso3: str, industry: str) -> str:
    return f"{iso3}:{industry}"


def _is_valid_industry(industry_str: str) -> bool:
    try:
        Industry(industry_str)
        return True
    except ValueError:
        return False


def merge_edges(
    hardcoded_edges: list[Edge],
    valid_node_ids: set[str],
    csv_path: Path | None = None,
) -> tuple[list[Edge], MergeReport]:
    """Merge hardcoded MVP edges with real Comtrade edges from CSV.

    Returns (merged_edge_list, report).
    """
    csv_path = csv_path or COMTRADE_CSV

    # Index hardcoded edges by (source_id, target_id) for O(1) override lookup.
    by_key: dict[tuple[str, str], Edge] = {
        (e.source, e.target): e for e in hardcoded_edges
    }
    n_hardcoded = len(by_key)

    n_comtrade_csv = 0
    n_overridden = 0
    n_added = 0
    n_skipped_unknown_node = 0
    n_skipped_self_loop = 0

    if not csv_path.exists():
        log.warning("Comtrade CSV not found at %s — using hardcoded edges only", csv_path)
        return list(by_key.values()), MergeReport(
            n_hardcoded=n_hardcoded, n_comtrade_csv=0,
            n_overridden=0, n_added=0,
            n_skipped_unknown_node=0, n_skipped_self_loop=0,
            n_final=n_hardcoded,
        )

    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n_comtrade_csv += 1
            src_iso = row["source_iso3"].strip()
            src_ind = row["source_industry"].strip()
            tgt_iso = row["target_iso3"].strip()
            tgt_ind = row["target_industry"].strip()

            # Skip rows whose industry is unknown to the engine (e.g. 'aviation').
            if not (_is_valid_industry(src_ind) and _is_valid_industry(tgt_ind)):
                n_skipped_unknown_node += 1
                continue

            # Skip rows whose ISO3 isn't in our 12-country node set.
            src_id = _build_node_id(src_iso, src_ind)
            tgt_id = _build_node_id(tgt_iso, tgt_ind)
            if src_id not in valid_node_ids or tgt_id not in valid_node_ids:
                n_skipped_unknown_node += 1
                continue

            # Skip self-loops (Pydantic Edge.target validator would reject them).
            if src_id == tgt_id:
                n_skipped_self_loop += 1
                continue

            try:
                dep = float(row["dependency_weight"])
                flow = float(row["flow_value_usd"])
            except (ValueError, KeyError):
                continue
            dep = max(0.0, min(1.0, dep))

            key = (src_id, tgt_id)
            if key in by_key:
                # Override the dependency_weight + flow_value of the hardcoded edge.
                hc = by_key[key]
                by_key[key] = Edge(
                    source=hc.source, target=hc.target, kind=hc.kind,
                    dependency_weight=dep,
                    substitution_difficulty=hc.substitution_difficulty,
                    rerouting_capability=hc.rerouting_capability,
                    resilience_coefficient=hc.resilience_coefficient,
                    recovery_delay_weeks=hc.recovery_delay_weeks,
                    flow_value_usd=flow,
                    meta={**hc.meta, "comtrade_overridden": True,
                          "comtrade_period": row.get("period", "")},
                )
                n_overridden += 1
            else:
                by_key[key] = Edge(
                    source=src_id, target=tgt_id,
                    kind=EdgeKind.PRODUCTION_INPUT,
                    dependency_weight=dep,
                    substitution_difficulty=DEFAULT_SUBSTITUTION_DIFFICULTY,
                    rerouting_capability=DEFAULT_REROUTING_CAPABILITY,
                    resilience_coefficient=DEFAULT_RESILIENCE_COEFFICIENT,
                    recovery_delay_weeks=DEFAULT_RECOVERY_DELAY_WEEKS,
                    flow_value_usd=flow,
                    meta={"source": "comtrade",
                          "period": row.get("period", ""),
                          "hs_codes": row.get("hs_codes", "")},
                )
                n_added += 1

    merged = list(by_key.values())
    return merged, MergeReport(
        n_hardcoded=n_hardcoded, n_comtrade_csv=n_comtrade_csv,
        n_overridden=n_overridden, n_added=n_added,
        n_skipped_unknown_node=n_skipped_unknown_node,
        n_skipped_self_loop=n_skipped_self_loop,
        n_final=len(merged),
    )


__all__ = ["MergeReport", "merge_edges"]
