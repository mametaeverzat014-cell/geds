"""Schema + integrity tests for the standardized production-impact targets (Task #2).

Pins the contract of standardized_targets.csv: a single, consistently-defined
target per event (peak source-sector output loss, or chokepoint throughput loss),
with explicit null status where no clean primary source exists. See PROGRESS
Batch 12 for the methodological finding.
"""

from __future__ import annotations

from app.data.csv_loader import (
    clean_calibration_targets,
    load_standardized_targets_csv,
)

_MEASURED_CLASSES = {
    "source_sector_output",
    "chokepoint_throughput",
    "facility_capacity",
    "facility_throughput",
    "national_index_proxy",
    "logistics_throughput",
}


def test_standardized_targets_schema():
    rows = load_standardized_targets_csv()
    assert len(rows) == 24, "15 priority + 8 secondary + 1 (gfc-auto-collapse-2008-2009) events"
    for r in rows:
        assert r.target_class in _MEASURED_CLASSES, r.target_class
        assert r.status in {"measured", "null"}
        if r.status == "measured":
            assert r.value_pct is not None, f"{r.engine_slug} measured but no value"
            assert 0.0 <= r.value_pct <= 1.0, f"{r.engine_slug} value out of [0,1]"
            assert r.source, f"{r.engine_slug} measured but no source"
        else:
            assert r.value_pct is None, f"{r.engine_slug} null but has a value"
            assert r.note, f"{r.engine_slug} null but no reason given"


def test_measured_null_split():
    rows = load_standardized_targets_csv()
    measured = [r for r in rows if r.status == "measured"]
    null = [r for r in rows if r.status == "null"]
    assert len(measured) == 15
    assert len(null) == 9


def test_semiconductor_source_events_have_no_clean_target():
    """The core Batch 12 finding: chip-source events lack a measurable source-side
    output loss (no agency publishes monthly fab-output indices)."""
    rows = {r.engine_slug: r for r in load_standardized_targets_csv()}
    for slug in (
        "covid-semiconductor-2020-2021",
        "auto-chip-shortage-2021",
        "texas-winter-storm-2021",
        "taiwan-chichi-earthquake-1999",
    ):
        assert rows[slug].status == "null", slug
    # malaysia is a weak broad-manufacturing proxy, explicitly not the semi sub-sector
    assert rows["malaysia-semiconductor-2021"].usability == "national_proxy"


def test_clean_calibration_targets_are_all_automotive():
    """All directly-measured source-sector targets are vehicle-production figures."""
    clean = clean_calibration_targets()
    assert set(clean) == {
        "japan-triple-disaster-2011",
        "eu-energy-crisis-2021",
        "shanghai-lockdown-2022",
        "wuhan-lockdown-2020",
        "thailand-floods-2011",
        "gfc-auto-collapse-2008-2009",
    }
    # sanity: peak monthly losses are large (node-level, not global-annual)
    assert clean["wuhan-lockdown-2020"] > 0.7
    assert all(0.0 < v <= 1.0 for v in clean.values())
