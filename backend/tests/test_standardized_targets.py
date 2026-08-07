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
    # 24 from Batch 12 (15 priority + 8 secondary + gfc-auto-collapse-2008-2009),
    # +1 added 2026-08: ukraine-war-harness-2022, measured from the VDA series
    # already in the repo. texas-winter-storm-2021 was not added but UPDATED in
    # place from status=null to a measured national proxy (Fed G.17), so the
    # count rises by one, not two.
    assert len(rows) == 25
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


def test_one_row_per_event():
    """The file's contract is a single target row per event.

    Added 2026-08 after an append accidentally created a second row for
    texas-winter-storm-2021 alongside its existing null row — two rows for one
    event silently double-count it in any downstream aggregation, and nothing
    was checking for it.
    """
    rows = load_standardized_targets_csv()
    seen: dict[str, int] = {}
    for r in rows:
        seen[r.engine_slug] = seen.get(r.engine_slug, 0) + 1
    dups = {k: v for k, v in seen.items() if v > 1}
    assert not dups, f"duplicate engine_slug rows: {dups}"


def test_measured_null_split():
    rows = load_standardized_targets_csv()
    measured = [r for r in rows if r.status == "measured"]
    null = [r for r in rows if r.status == "null"]
    assert len(measured) == 17   # 15 from Batch 12 + ukraine-war-harness + texas-winter-storm
    assert len(null) == 8        # texas-winter-storm-2021 moved null -> measured proxy


def test_semiconductor_source_events_have_no_clean_target():
    """The core Batch 12 finding: chip-source events lack a measurable source-side
    output loss (no agency publishes monthly fab-output indices).

    The claim is about CLEAN source-side targets, so the invariant is that no
    chip-source event is ever `usability == "direct"` — not that every one of
    them is unmeasured. texas-winter-storm-2021 moved from null to a measured
    national proxy in 2026-08 (Fed G.17 NAICS 3344, -1.0% MoM SA in Feb 2021),
    which is the same category malaysia-semiconductor-2021 already occupied and
    does not weaken the finding: the national index cannot isolate the Austin
    fabs, and its own note says so.
    """
    rows = {r.engine_slug: r for r in load_standardized_targets_csv()}
    for slug in (
        "covid-semiconductor-2020-2021",
        "auto-chip-shortage-2021",
        "taiwan-chichi-earthquake-1999",
    ):
        assert rows[slug].status == "null", slug
    # measured only as proxies, never as clean source-sector targets
    for slug in ("texas-winter-storm-2021", "malaysia-semiconductor-2021"):
        assert rows[slug].usability == "national_proxy", slug
        assert rows[slug].usability != "direct", slug


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
        # added 2026-08 from the VDA series already in the repo; also a vehicle-
        # production figure, so the stated invariant is unchanged
        "ukraine-war-harness-2022",
    }
    # sanity: peak monthly losses are large (node-level, not global-annual)
    assert clean["wuhan-lockdown-2020"] > 0.7
    assert all(0.0 < v <= 1.0 for v in clean.values())
