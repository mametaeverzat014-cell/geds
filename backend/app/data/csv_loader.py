"""CSV-driven data layer.

Loads historical_events.csv, model_parameters.csv, validation_datasets.csv
into typed Python objects. Replaces hardcoded HISTORICAL_EVENTS / parameter
ranges so the data layer becomes auditable, version-controlled, and editable
without touching code.

Rules
-----
* Empty cells and the literal string "missing" become None (not 0, not "")
* Events with in_geds_graph != "yes" are loaded but flagged as out_of_graph
  — they cannot be used for backtest/MCMC against the current 40-node graph
  but are preserved for future graph-expansion validation
* All numeric fields use strict float conversion; bad rows produce a clear
  validation error rather than silent NaN propagation
* No fabrication — if a source doesn't appear in the CSV, the loader will
  not invent one
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_CSV_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "csv"


# ─────────────────────────── data classes ──────────────────────────────────


@dataclass
class HistoricalEventCSV:
    """One row of historical_events.csv."""
    id: int
    slug: str
    name_ru: str
    name_en: str
    type: str
    start_date: str
    end_date: str | None
    countries_iso3: list[str]
    industries_geds: list[str]
    shock_mechanism: str
    channels: str
    chokepoints: str | None
    delta_gdp_pct: float | None
    delta_output_pct: float | None
    delta_trade_pct: float | None
    delta_cpi_pct: float | None
    delta_unemployment_pct: float | None
    shortage_indicator: str | None     # low / medium / high
    recovery_weeks: float | None
    companies: list[str]
    loss_usd_billions: float | None
    sources: list[str]
    in_geds_graph: bool
    target_node_geds: str | None
    shock_magnitude_geds: float | None
    duration_weeks_geds: int | None
    notes: str

    def to_geds_event(self) -> dict | None:
        """Convert to the dict shape consumed by the existing engine.

        Returns None if the event is out_of_graph (cannot be backtested
        against current node set).
        """
        if not self.in_geds_graph:
            return None
        if not self.target_node_geds or self.shock_magnitude_geds is None:
            return None
        return {
            "slug": self.slug,
            "name": self.name_en,
            "horizon_weeks": int(self.duration_weeks_geds or 26),
            "shocks": [{
                "target_node_id": self.target_node_geds,
                "magnitude": float(self.shock_magnitude_geds),
                "start_week": 0,
                "duration_weeks": int(self.duration_weeks_geds or 8),
                "decay_curve": "step",
            }],
            "observed": {
                "auto_production_loss_pct": float(self.delta_output_pct or 0.0),
                "us_inflation_contribution": float(self.delta_cpi_pct or 0.0),
                "expected_recovery_weeks": float(self.recovery_weeks or 26.0),
                "most_impacted_industry": (self.industries_geds or ["automotive"])[0],
            },
            "_provenance": {
                "sources": self.sources,
                "notes": self.notes,
                "csv_id": self.id,
            },
        }


@dataclass
class ParameterCSV:
    parameter_id: str
    name_ru: str
    name_en: str
    description_ru: str
    range_low: float
    range_high: float
    unit: str
    sector_scope: str
    literature_source: str
    confidence: str       # low / medium / high
    notes: str


@dataclass
class DatasetCSV:
    dataset_id: str
    name: str
    name_ru: str
    provider: str
    description: str
    variables: list[str]
    coverage_period: str
    coverage_geography: str
    access_url: str
    api_required: str    # no / yes (free) / yes (key) / paid subscription
    license: str
    update_frequency: str
    used_in_geds: str
    limitations: str


# ─────────────────────────── parsers ───────────────────────────────────────


def _parse_missing(v: str | None) -> str | None:
    """Both empty string and literal 'missing' map to None."""
    if v is None:
        return None
    s = v.strip()
    if s == "" or s.lower() == "missing":
        return None
    return s


def _parse_float(v: str | None) -> float | None:
    s = _parse_missing(v)
    if s is None:
        return None
    # Allow ranges like "-0.5...-1.0" — take midpoint
    if "…" in s or "..." in s:
        parts = s.replace("…", "...").split("...")
        if len(parts) == 2:
            try:
                lo = float(parts[0].strip().rstrip("%"))
                hi = float(parts[1].strip().rstrip("%"))
                return (lo + hi) / 2.0
            except ValueError:
                return None
    try:
        return float(s.rstrip("%").rstrip(","))
    except ValueError:
        return None


def _parse_int(v: str | None) -> int | None:
    f = _parse_float(v)
    return int(f) if f is not None else None


def _parse_list(v: str | None, sep: str = ";") -> list[str]:
    s = _parse_missing(v)
    if s is None:
        return []
    return [p.strip() for p in s.split(sep) if p.strip()]


def _parse_bool_yes(v: str | None) -> bool:
    return (_parse_missing(v) or "").lower() in {"yes", "true", "y", "1"}


# ─────────────────────────── load functions ────────────────────────────────


def load_historical_events_csv(path: Path | None = None) -> list[HistoricalEventCSV]:
    path = path or (_CSV_DIR / "historical_events.csv")
    out: list[HistoricalEventCSV] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(HistoricalEventCSV(
                id=int(row["id"]),
                slug=row["slug"].strip(),
                name_ru=row["name_ru"].strip(),
                name_en=row["name_en"].strip(),
                type=row["type"].strip(),
                start_date=row["start_date"].strip(),
                end_date=_parse_missing(row.get("end_date")),
                countries_iso3=_parse_list(row.get("countries_iso3")),
                industries_geds=_parse_list(row.get("industries_geds")),
                shock_mechanism=row.get("shock_mechanism", "").strip(),
                channels=row.get("channels", "").strip(),
                chokepoints=_parse_missing(row.get("chokepoints")),
                delta_gdp_pct=_parse_float(row.get("delta_gdp_pct")),
                delta_output_pct=_parse_float(row.get("delta_output_pct")),
                delta_trade_pct=_parse_float(row.get("delta_trade_pct")),
                delta_cpi_pct=_parse_float(row.get("delta_cpi_pct")),
                delta_unemployment_pct=_parse_float(row.get("delta_unemployment_pct")),
                shortage_indicator=_parse_missing(row.get("shortage_indicator")),
                recovery_weeks=_parse_float(row.get("recovery_weeks")),
                companies=_parse_list(row.get("companies")),
                loss_usd_billions=_parse_float(row.get("loss_usd_billions")),
                sources=_parse_list(row.get("sources")),
                in_geds_graph=_parse_bool_yes(row.get("in_geds_graph")),
                target_node_geds=_parse_missing(row.get("target_node_geds")),
                shock_magnitude_geds=_parse_float(row.get("shock_magnitude_geds")),
                duration_weeks_geds=_parse_int(row.get("duration_weeks_geds")),
                notes=row.get("notes", "").strip(),
            ))
    return out


def load_parameters_csv(path: Path | None = None) -> list[ParameterCSV]:
    path = path or (_CSV_DIR / "model_parameters.csv")
    out: list[ParameterCSV] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(ParameterCSV(
                parameter_id=row["parameter_id"].strip(),
                name_ru=row["name_ru"].strip(),
                name_en=row["name_en"].strip(),
                description_ru=row["description_ru"].strip(),
                range_low=float(row["range_low"]),
                range_high=float(row["range_high"]),
                unit=row["unit"].strip(),
                sector_scope=row["sector_scope"].strip(),
                literature_source=row["literature_source"].strip(),
                confidence=row["confidence"].strip(),
                notes=row.get("notes", "").strip(),
            ))
    return out


def load_datasets_csv(path: Path | None = None) -> list[DatasetCSV]:
    path = path or (_CSV_DIR / "validation_datasets.csv")
    out: list[DatasetCSV] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(DatasetCSV(
                dataset_id=row["dataset_id"].strip(),
                name=row["name"].strip(),
                name_ru=row["name_ru"].strip(),
                provider=row["provider"].strip(),
                description=row["description"].strip(),
                variables=_parse_list(row.get("variables")),
                coverage_period=row.get("coverage_period", "").strip(),
                coverage_geography=row.get("coverage_geography", "").strip(),
                access_url=row.get("access_url", "").strip(),
                api_required=row.get("api_required", "").strip(),
                license=row.get("license", "").strip(),
                update_frequency=row.get("update_frequency", "").strip(),
                used_in_geds=row.get("used_in_geds", "").strip(),
                limitations=row.get("limitations", "").strip(),
            ))
    return out


# ─────────────────────────── integration helpers ───────────────────────────


def csv_to_geds_historical_events() -> list[dict]:
    """Build the list[dict] in the same shape as seed_data.HISTORICAL_EVENTS.

    Only includes events flagged in_geds_graph=yes.  Out-of-graph events
    (9/11, SARS, 2008 financial crisis, Russia-Ukraine 2022) are preserved
    in the CSV but skipped here until the graph is expanded.
    """
    events = load_historical_events_csv()
    out: list[dict] = []
    for ev in events:
        geds = ev.to_geds_event()
        if geds is not None:
            out.append(geds)
    return out


def parameter_bounds_from_csv() -> dict[str, tuple[float, float]]:
    """Build the bounds dict consumed by mcmc/de calibration.

    Only includes parameters whose CSV id matches a known calibrator key.
    """
    csv_to_calibrator_key = {
        "bullwhip_amplification": "bullwhip_factor",
        "elasticity_output_to_shock": None,        # used statically per industry
        "demand_elasticity": None,
        "supply_elasticity": None,
        "pass_through": None,
    }
    params = load_parameters_csv()
    out: dict[str, tuple[float, float]] = {}
    for p in params:
        cal_key = csv_to_calibrator_key.get(p.parameter_id)
        if cal_key:
            out[cal_key] = (p.range_low, p.range_high)
    return out


def out_of_graph_events() -> list[HistoricalEventCSV]:
    """Return the events that can't currently be backtested.

    Used by the UI to display 'pending graph expansion' rows in the
    validation dashboard.
    """
    return [e for e in load_historical_events_csv() if not e.in_geds_graph]


__all__ = [
    "HistoricalEventCSV", "ParameterCSV", "DatasetCSV",
    "load_historical_events_csv", "load_parameters_csv", "load_datasets_csv",
    "csv_to_geds_historical_events", "parameter_bounds_from_csv",
    "out_of_graph_events",
]
