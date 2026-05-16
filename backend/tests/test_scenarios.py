"""Tests for the scenario registry and Taiwan flagship scenario semantics."""

from __future__ import annotations

import pytest

from app.core import scenarios as scen
from app.core.types import Industry


def test_registry_has_taiwan_scenario():
    s = scen.by_id("taiwan-semi-75")
    assert s.name.startswith("Taiwan Semiconductor")
    assert s.horizon_weeks == 52
    assert any(sh.target_node_id == f"TWN:{Industry.SEMICONDUCTORS.value}" for sh in s.shocks)


def test_registry_lists_all_named_scenarios():
    expected = {
        "taiwan-semi-75",
        "taiwan-semi-80",
        "taiwan-strait",
        "historical-suez-2021",
        "historical-covid-semi",
        "hypothetical-hormuz",
    }
    actual = {s.id for s in scen.list_scenarios()}
    assert expected.issubset(actual)


def test_unknown_scenario_raises():
    with pytest.raises(KeyError):
        scen.by_id("not-a-real-scenario")


def test_taiwan_with_strait_adds_third_shock():
    s = scen.taiwan_semiconductor_shock(magnitude=0.75, include_taiwan_strait=True)
    targets = {sh.target_node_id for sh in s.shocks}
    assert "CP:TaiwanStrait" in targets
    assert len(s.shocks) == 3


def test_taiwan_scenario_magnitude_passes_through():
    s = scen.taiwan_semiconductor_shock(magnitude=0.6)
    primary = next(sh for sh in s.shocks if sh.target_node_id.startswith("TWN:semi"))
    assert primary.magnitude == 0.6
