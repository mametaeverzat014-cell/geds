"""Predefined scenarios.

The flagship is the Taiwan semiconductor shock. Other scenarios are provided
both for comparison and to serve as historical-replay validators.
"""

from __future__ import annotations

from typing import Callable

from .types import EngineConfig, Industry, Scenario, ShockSpec


def _n(country: str, industry: Industry) -> str:
    return f"{country}:{industry.value}"


# ────────────────────────── flagship: Taiwan semi shock ──────────────────────────


def taiwan_semiconductor_shock(
    magnitude: float = 0.75,
    duration_weeks: int = 20,
    horizon_weeks: int = 52,
    *,
    include_taiwan_strait: bool = False,
    name_suffix: str | None = None,
) -> Scenario:
    """The flagship MVP scenario: Taiwan semiconductor exports drop 70–80%.

    Parameters
    ----------
    magnitude :
        Magnitude of the direct shock on TWN:semiconductors, in [0, 1].
        0.75 ≈ a 75% reduction in effective semiconductor supply.
    duration_weeks :
        How long the disruption persists at full magnitude before decaying.
    horizon_weeks :
        Total simulation horizon.
    include_taiwan_strait :
        If True, add a compound chokepoint shock on the Taiwan Strait.
    """

    shocks = [
        ShockSpec(
            target_node_id=_n("TWN", Industry.SEMICONDUCTORS),
            magnitude=magnitude,
            start_week=0,
            duration_weeks=duration_weeks,
            decay_curve="exp",
            note="Direct disruption of Taiwan semiconductor output",
        ),
        # A secondary minor shock to TWN:electronics (Foxconn etc.) — same regional event.
        ShockSpec(
            target_node_id=_n("TWN", Industry.ELECTRONICS),
            magnitude=min(0.5, magnitude * 0.6),
            start_week=0,
            duration_weeks=max(8, duration_weeks // 2),
            decay_curve="linear",
            note="Knock-on disruption of Taiwan electronics assembly",
        ),
    ]

    if include_taiwan_strait:
        shocks.append(
            ShockSpec(
                target_node_id="CP:TaiwanStrait",
                magnitude=0.85,
                start_week=0,
                duration_weeks=min(8, duration_weeks),
                decay_curve="linear",
                note="Compound chokepoint disruption (Taiwan Strait)",
            )
        )

    name = "Taiwan Semiconductor Shock"
    if include_taiwan_strait:
        name += " + Strait Closure"
    if name_suffix:
        name += f" — {name_suffix}"

    suffix = "-strait" if include_taiwan_strait else ""
    return Scenario(
        id=f"taiwan-semi-{int(magnitude * 100)}{suffix}",
        name=name,
        description=(
            "Flagship MVP scenario: a 70–80% reduction in Taiwan's semiconductor exports "
            "cascading through global electronics, automotive, and consumer goods supply chains."
        ),
        horizon_weeks=horizon_weeks,
        shocks=shocks,
        config=EngineConfig(
            propagation_decay=0.85,
            rerouting_efficiency=0.50,
            amplification_mu=2.4,
            amplification_eps=0.06,
            recovery_rate=0.07,
        ),
    )


# ────────────────────────── alternatives ─────────────────────────────


def suez_2021_replay() -> Scenario:
    """Historical replay: 2021 Suez Canal blockage. Short, sharp shock."""

    return Scenario(
        id="historical-suez-2021",
        name="Suez Canal Blockage (March 2021)",
        description="Six-day blockage of the Suez Canal; estimated 12% of global trade disrupted.",
        horizon_weeks=16,
        shocks=[
            ShockSpec(
                target_node_id="CP:Suez",
                magnitude=0.90,
                start_week=0,
                duration_weeks=2,
                decay_curve="step",
            ),
        ],
        config=EngineConfig(propagation_decay=0.80, recovery_rate=0.12),
    )


def covid_semi_replay() -> Scenario:
    """Historical replay: 2020–21 COVID semiconductor + electronics shock."""

    return Scenario(
        id="historical-covid-semi",
        name="COVID Semiconductor Shortage (2020–21)",
        description="Pandemic disruptions to Asian semiconductor and electronics production.",
        horizon_weeks=52,
        shocks=[
            ShockSpec(
                target_node_id=_n("TWN", Industry.SEMICONDUCTORS),
                magnitude=0.30,
                start_week=0,
                duration_weeks=26,
                decay_curve="exp",
            ),
            ShockSpec(
                target_node_id=_n("CHN", Industry.ELECTRONICS),
                magnitude=0.45,
                start_week=0,
                duration_weeks=14,
                decay_curve="linear",
            ),
        ],
        config=EngineConfig(propagation_decay=0.82, recovery_rate=0.06),
    )


def hormuz_oil_disruption() -> Scenario:
    """What-if: severe Hormuz disruption coupling with electronics supply chain stress."""

    return Scenario(
        id="hypothetical-hormuz",
        name="Strait of Hormuz Disruption",
        description="Hypothetical: severe Hormuz closure compounding global energy and shipping costs.",
        horizon_weeks=40,
        shocks=[
            ShockSpec(
                target_node_id="CP:Hormuz",
                magnitude=0.85,
                start_week=0,
                duration_weeks=12,
                decay_curve="linear",
            ),
        ],
        config=EngineConfig(propagation_decay=0.85, recovery_rate=0.08),
    )


def _taiwan_strait_variant() -> Scenario:
    s = taiwan_semiconductor_shock(0.75, 20, 52, include_taiwan_strait=True)
    s.id = "taiwan-strait"
    return s


REGISTRY: dict[str, Callable[[], Scenario]] = {
    "taiwan-semi-75":  lambda: taiwan_semiconductor_shock(0.75, 20, 52),
    "taiwan-semi-80":  lambda: taiwan_semiconductor_shock(0.80, 24, 52),
    "taiwan-strait":   _taiwan_strait_variant,
    "historical-suez-2021": suez_2021_replay,
    "historical-covid-semi": covid_semi_replay,
    "hypothetical-hormuz": hormuz_oil_disruption,
}


def by_id(scenario_id: str) -> Scenario:
    if scenario_id not in REGISTRY:
        raise KeyError(f"Unknown scenario id: {scenario_id}")
    return REGISTRY[scenario_id]()


def list_scenarios() -> list[Scenario]:
    return [factory() for factory in REGISTRY.values()]
