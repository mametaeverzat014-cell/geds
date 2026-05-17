"""Conversion: raw Comtrade rows → GEDS edges with import-penetration ratios.

GEDS edges encode `dependency_weight = import_penetration_ratio`, defined as:

    dep_weight(importer X → exporter Y, sector S) = M_{X,Y,S} / M_{X,World,S}

i.e. share of X's total sector-S imports that come from Y.  This is the
standard formulation used in Feenstra & Taylor 2014 and in IMF Article IV
trade-vulnerability assessments.

This module produces edges in the same dict shape as `seed_data.EDGES_RAW`
so they can be appended to or substituted for the hardcoded MVP edges.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

try:
    import pandas as pd
except ImportError:
    pd = None

from .comtrade_fetcher import (
    HS_CODES_BY_INDUSTRY, FetchResult, fetch_batch, read_fetch,
)


log = logging.getLogger("geds.comtrade.processor")


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class TradeEdgeRow:
    """One bilateral edge after processing."""
    importer_iso3: str
    exporter_iso3: str
    industry: str
    hs_code: str
    period: str
    import_value_usd: float
    importer_total_in_sector_usd: float
    import_penetration_ratio: float    # = dep_weight
    n_partners_for_importer: int       # diversity context
    source_url: str                    # back-reference for ISEF judges


# ─────────────────────────── helpers ───────────────────────────────────────


def _world_row_value(df) -> float:
    """The 'World' aggregate row in a Comtrade fetch gives the total imports."""
    if pd is None or df is None or len(df) == 0:
        return 0.0
    # Comtrade marks the world aggregate as partnerCode=0 / partnerISO='W00'
    world_rows = df[df["partnerCode"] == 0]
    if len(world_rows) == 0:
        # Sometimes no explicit world row — sum non-zero partners as proxy.
        return float(df["primaryValue"].sum())
    return float(world_rows["primaryValue"].iloc[0])


def _partner_rows(df) -> list[tuple[str, float]]:
    """Return list of (partner_iso3, value_usd) for non-aggregate rows."""
    if pd is None or df is None or len(df) == 0:
        return []
    real = df[(df["partnerCode"] != 0) & df["partnerISO"].notna()]
    out: list[tuple[str, float]] = []
    for _, r in real.iterrows():
        iso = str(r["partnerISO"]).strip()
        val = float(r["primaryValue"])
        if iso and val > 0:
            out.append((iso, val))
    return out


# ─────────────────────────── industry mapping ──────────────────────────────


def hs_to_industry(hs_code: str) -> str | None:
    """Reverse-map an HS code to GEDS industry."""
    hs = hs_code.strip()
    for industry, codes in HS_CODES_BY_INDUSTRY.items():
        if hs in codes:
            return industry
    # Prefix match (e.g. '85421' → '8542')
    for industry, codes in HS_CODES_BY_INDUSTRY.items():
        for c in codes:
            if hs.startswith(c):
                return industry
    return None


# ─────────────────────────── main ETL ──────────────────────────────────────


def fetch_to_edges(
    importers: list[str],
    industries: list[str] | None = None,
    period: str = "2019",
    subscription_key: str | None = None,
    min_penetration: float = 0.02,
) -> list[TradeEdgeRow]:
    """End-to-end: fetch for every (importer × HS code in selected industries) and
    convert into TradeEdgeRow records.

    `min_penetration` drops noise edges below this threshold — typical GEDS
    edges have dep_weight > 0.05; below 2% the propagation contribution
    is negligible.
    """
    if pd is None:
        raise ImportError("pandas required")

    industries = industries or list(HS_CODES_BY_INDUSTRY.keys())
    hs_codes: list[tuple[str, str]] = []   # (hs_code, industry)
    for ind in industries:
        for hs in HS_CODES_BY_INDUSTRY.get(ind, []):
            hs_codes.append((hs, ind))

    if not hs_codes:
        return []

    # Fetch all needed cells (cached)
    hs_only = [h for h, _ in hs_codes]
    fetches = fetch_batch(
        reporters=importers,
        hs_codes=hs_only,
        period=period, flow="M",
        subscription_key=subscription_key,
    )

    # Index fetches by (importer, hs)
    idx: dict[tuple[str, str], FetchResult] = {}
    for f in fetches:
        idx[(f.reporter_iso3.upper(), f.hs_code)] = f

    out: list[TradeEdgeRow] = []
    for iso3 in importers:
        iso3u = iso3.upper()
        for hs, industry in hs_codes:
            f = idx.get((iso3u, hs))
            if f is None:
                continue
            df = read_fetch(f)
            if len(df) == 0:
                continue
            total = _world_row_value(df)
            if total <= 0:
                continue
            partner_vals = _partner_rows(df)
            for partner_iso, val in partner_vals:
                ratio = val / total
                if ratio < min_penetration:
                    continue
                out.append(TradeEdgeRow(
                    importer_iso3=iso3u,
                    exporter_iso3=partner_iso.upper(),
                    industry=industry,
                    hs_code=hs,
                    period=period,
                    import_value_usd=round(val, 2),
                    importer_total_in_sector_usd=round(total, 2),
                    import_penetration_ratio=round(ratio, 4),
                    n_partners_for_importer=len(partner_vals),
                    source_url=f"https://comtrade.un.org/data/?r={iso3u}&p=all&px=HS&cc={hs}&y={period}",
                ))
    return out


def aggregate_to_industry_edges(
    rows: list[TradeEdgeRow],
) -> list[dict]:
    """Collapse multiple HS-codes per industry into single edges.

    For an industry with multiple HS codes (e.g., automotive = 8703 + 8704 + 8708),
    take the value-weighted average penetration ratio per (importer, exporter, industry).
    """
    # Group by (importer, exporter, industry)
    groups: dict[tuple[str, str, str], list[TradeEdgeRow]] = {}
    for r in rows:
        key = (r.importer_iso3, r.exporter_iso3, r.industry)
        groups.setdefault(key, []).append(r)

    edges: list[dict] = []
    for (imp, exp, ind), group in groups.items():
        total_value = sum(r.import_value_usd for r in group)
        total_sector_imports = sum(r.importer_total_in_sector_usd for r in group)
        # Value-weighted penetration ratio
        if total_sector_imports > 0:
            weighted_ratio = total_value / total_sector_imports
        else:
            weighted_ratio = 0.0
        edges.append({
            "source_iso3": exp,
            "source_industry": ind,
            "target_iso3": imp,
            "target_industry": ind,           # same-industry trade; downstream maps to dependent industries
            "industry": ind,
            "dependency_weight": round(weighted_ratio, 4),
            "flow_value_usd": round(total_value, 2),
            "hs_codes": sorted({r.hs_code for r in group}),
            "n_hs_codes": len({r.hs_code for r in group}),
            "source_urls": sorted({r.source_url for r in group}),
            "period": group[0].period,
        })
    edges.sort(key=lambda e: e["dependency_weight"], reverse=True)
    return edges


# ─────────────────────────── persistence ───────────────────────────────────


def save_edges_csv(edges: list[dict], path: Path) -> Path:
    """Write aggregated edges to CSV (consumable by seed_data integration)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not edges:
        return path
    fieldnames = list(edges[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for e in edges:
            row = {k: (";".join(v) if isinstance(v, list) else v) for k, v in e.items()}
            w.writerow(row)
    return path


__all__ = [
    "TradeEdgeRow",
    "hs_to_industry", "fetch_to_edges", "aggregate_to_industry_edges",
    "save_edges_csv",
]
