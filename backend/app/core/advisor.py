"""Policy Advisor.

Given a completed SimulationResult, this module generates prioritized,
actionable policy recommendations drawn from the simulation's evidence:
peak shocks, centrality rankings, chokepoint alerts, sector fragility, and
the estimated intervention window.

Design principle: rule-based for MVP (no ML inference overhead). Each
recommendation is derived from a specific evidence threshold so the output
is fully traceable and auditable — a key property for a policy tool.

Recommendation IDs are stable strings so callers can deduplicate across
multiple runs of the same scenario.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .types import (
    AdvisorResult,
    Industry,
    NodeKind,
    PolicyCategory,
    PolicyPriority,
    PolicyRecommendation,
    SimulationResult,
)

if TYPE_CHECKING:
    from .graph import CompiledGraph


# ──────────────────────── thresholds ────────────────────────

_CRITICAL_SHOCK       = 0.55   # peak shock → node is "critically disrupted"
_HIGH_SHOCK           = 0.35   # peak shock → node is "highly disrupted"
_CHOKEPOINT_ALERT     = 0.25   # chokepoint shock → alert
_CENTRALITY_CRITICAL  = 0.65   # centrality → structurally critical
_PEAK_CSI_EMERGENCY   = 0.70   # peak CSI → recommend emergency monetary policy
_SHORTFALL_THRESHOLD  = 0.50   # shortage_prob → recommend stockpiling

# Industries for which stockpiling / diversification is actionable.
_STOCKPILE_INDUSTRIES = {Industry.SEMICONDUCTORS, Industry.ENERGY}
_DIVERSIFY_INDUSTRIES = {Industry.SEMICONDUCTORS, Industry.ELECTRONICS, Industry.AUTOMOTIVE}


def analyze(result: SimulationResult, g: "CompiledGraph") -> AdvisorResult:
    """Entry point: produce an AdvisorResult from a finished simulation."""

    frames = result.frames
    snapshot = g.snapshot

    # ── per-node peak shock ──────────────────────────────────
    peak_shock: dict[str, float] = {nid: 0.0 for nid in g.node_ids}
    peak_shortage: dict[str, float] = {nid: 0.0 for nid in g.node_ids}
    for f in frames:
        for nf in f.nodes:
            peak_shock[nf.id] = max(peak_shock.get(nf.id, 0.0), nf.shock)
            peak_shortage[nf.id] = max(peak_shortage.get(nf.id, 0.0), nf.shortage_prob)

    # ── intervention window ──────────────────────────────────
    # How many weeks until peak CSI? If CSI is already near its peak at week 0,
    # there is no lead time — we report 0.
    csi_series = [f.csi for f in frames]
    peak_csi_week = int(max(range(len(csi_series)), key=lambda i: csi_series[i], default=0))
    intervention_window = peak_csi_week

    # ── critical nodes ───────────────────────────────────────
    def _priority_score(nid: str) -> float:
        cent = float(g.centrality[g.index[nid]])
        ps = peak_shock.get(nid, 0.0)
        return ps * cent

    critical_nodes = sorted(
        [n.id for n in snapshot.nodes if peak_shock.get(n.id, 0.0) >= _HIGH_SHOCK],
        key=_priority_score,
        reverse=True,
    )[:12]

    # ── chokepoint alerts ────────────────────────────────────
    chokepoint_alerts = [
        n.id
        for n in snapshot.nodes
        if n.kind == NodeKind.CHOKEPOINT and peak_shock.get(n.id, 0.0) >= _CHOKEPOINT_ALERT
    ]

    # ── build recommendations ────────────────────────────────
    recs: list[PolicyRecommendation] = []
    _id = _make_id_gen()

    # 1. Emergency response for critically shocked semiconductor hub(s)
    semi_origin_countries = sorted(
        {
            n.country
            for n in snapshot.nodes
            if n.industry == Industry.SEMICONDUCTORS
            and peak_shock.get(n.id, 0.0) >= _CRITICAL_SHOCK
            and n.country
        }
    )
    if semi_origin_countries:
        recs.append(PolicyRecommendation(
            id=_id("emergency-semi-stockpile"),
            title="Emergency semiconductor strategic reserve activation",
            description=(
                "Peak shock on {countries} semiconductor nodes exceeds {pct}%. "
                "Activate national strategic semiconductor reserves and coordinate "
                "with allied producers (USA, KOR, JPN, NLD) for emergency allocation "
                "protocols. Target: sustain 8–12 weeks of critical consumer supply."
            ).format(
                countries=", ".join(semi_origin_countries),
                pct=int(_CRITICAL_SHOCK * 100),
            ),
            priority=PolicyPriority.CRITICAL,
            category=PolicyCategory.EMERGENCY,
            target_countries=semi_origin_countries,
            target_industries=["semiconductors"],
            estimated_impact=0.30,
            implementation_difficulty=0.45,
            horizon_weeks=4,
        ))

    # 2. Supply-chain diversification for high-dependency countries
    high_dep_countries: dict[str, list[str]] = {}
    for n in snapshot.nodes:
        if (
            n.industry in _DIVERSIFY_INDUSTRIES
            and peak_shock.get(n.id, 0.0) >= _HIGH_SHOCK
            and n.country
        ):
            high_dep_countries.setdefault(n.country, []).append(
                n.industry.value if n.industry else ""
            )

    if high_dep_countries:
        top_countries = sorted(
            high_dep_countries.keys(),
            key=lambda c: max(
                peak_shock.get(n.id, 0.0)
                for n in snapshot.nodes
                if n.country == c
            ),
            reverse=True,
        )[:5]
        recs.append(PolicyRecommendation(
            id=_id("diversify-supply-chain"),
            title="Accelerate supply-chain geographic diversification",
            description=(
                "Countries {countries} show ≥{pct}% disruption in {industries}. "
                "Fast-track trade agreements with Vietnam, India, and Mexico to "
                "absorb displaced semiconductor and electronics assembly capacity. "
                "Provide investment incentives for dual-sourcing critical components "
                "within 12–24 months."
            ).format(
                countries=", ".join(top_countries),
                pct=int(_HIGH_SHOCK * 100),
                industries=", ".join(sorted({
                    i for inds in high_dep_countries.values() for i in inds
                })),
            ),
            priority=PolicyPriority.HIGH,
            category=PolicyCategory.DIVERSIFICATION,
            target_countries=top_countries,
            target_industries=sorted({i for v in high_dep_countries.values() for i in v}),
            estimated_impact=0.40,
            implementation_difficulty=0.70,
            horizon_weeks=52,
        ))

    # 3. Chokepoint diplomatic de-escalation
    for cp_id in chokepoint_alerts:
        cp_node = next((n for n in snapshot.nodes if n.id == cp_id), None)
        if cp_node is None:
            continue
        shock_pct = int(peak_shock.get(cp_id, 0.0) * 100)
        priority = (
            PolicyPriority.CRITICAL
            if peak_shock.get(cp_id, 0.0) >= 0.70
            else PolicyPriority.HIGH
        )
        recs.append(PolicyRecommendation(
            id=_id(f"chokepoint-{cp_id.lower().replace(':', '-').replace(' ', '-')}"),
            title=f"Chokepoint alert — {cp_node.name}: engage diplomatic de-escalation",
            description=(
                f"The {cp_node.name} is at {shock_pct}% simulated disruption. "
                "Coordinate with regional partners to establish alternative routing corridors. "
                "Engage naval escort frameworks. Notify carriers and shippers of contingency "
                "routes within 48 hours."
            ),
            priority=priority,
            category=PolicyCategory.DIPLOMATIC,
            target_countries=[],
            target_industries=["shipping"],
            estimated_impact=0.55,
            implementation_difficulty=0.80,
            horizon_weeks=2,
        ))

    # 4. Automotive sector stockpiling
    auto_crisis_countries = [
        n.country
        for n in snapshot.nodes
        if n.industry == Industry.AUTOMOTIVE
        and peak_shortage.get(n.id, 0.0) >= _SHORTFALL_THRESHOLD
        and n.country
    ]
    if auto_crisis_countries:
        recs.append(PolicyRecommendation(
            id=_id("auto-component-stockpile"),
            title="Automotive sector: emergency component pre-procurement programme",
            description=(
                "Shortage probability ≥{pct}% in automotive nodes for {countries}. "
                "Direct OEMs to increase safety stock of MCUs and power semiconductors to "
                "a minimum 12-week buffer. Authorise expedited customs clearance for "
                "component shipments and waive import duties for 6 months."
            ).format(
                pct=int(_SHORTFALL_THRESHOLD * 100),
                countries=", ".join(sorted(set(auto_crisis_countries))[:4]),
            ),
            priority=PolicyPriority.HIGH,
            category=PolicyCategory.STOCKPILING,
            target_countries=sorted(set(auto_crisis_countries)),
            target_industries=["automotive", "semiconductors"],
            estimated_impact=0.25,
            implementation_difficulty=0.35,
            horizon_weeks=8,
        ))

    # 5. Emergency monetary / fiscal policy if systemic
    peak_csi = result.summary.peak_csi
    if peak_csi >= _PEAK_CSI_EMERGENCY:
        affected_iso3 = sorted({
            n.country
            for n in snapshot.nodes
            if n.country and peak_shock.get(n.id, 0.0) >= _HIGH_SHOCK
        })
        recs.append(PolicyRecommendation(
            id=_id("monetary-emergency"),
            title="Systemic crisis: coordinate G7 emergency monetary response",
            description=(
                "Peak CSI of {csi:.2f} indicates systemic cascade severity. "
                "Coordinate G7 central banks for: (1) emergency swap lines to prevent "
                "USD liquidity squeeze; (2) fiscal emergency funds for affected sectors; "
                "(3) waiver of Basel III countercyclical buffers to sustain credit supply "
                "to impacted industries in {countries}."
            ).format(
                csi=peak_csi,
                countries=", ".join(affected_iso3[:5]),
            ),
            priority=PolicyPriority.CRITICAL,
            category=PolicyCategory.MONETARY,
            target_countries=affected_iso3,
            target_industries=[],
            estimated_impact=0.35,
            implementation_difficulty=0.85,
            horizon_weeks=3,
        ))

    # 6. Long-term domestic semiconductor capacity investment
    if any(
        n.industry == Industry.SEMICONDUCTORS
        and peak_shock.get(n.id, 0.0) >= _HIGH_SHOCK
        for n in snapshot.nodes
    ):
        recs.append(PolicyRecommendation(
            id=_id("domestic-fab-investment"),
            title="Strategic investment in domestic and allied semiconductor fabrication",
            description=(
                "This event demonstrates structural dependency on a single-region semiconductor "
                "cluster. Allocate strategic investment (cf. CHIPS Act scale) to: "
                "(1) domestic advanced node fab construction (18–36 month timeline); "
                "(2) allied-country (JPN, DEU, NLD) capacity subsidies; "
                "(3) mature-node (28nm+) domestic capacity for automotive and industrial MCUs."
            ),
            priority=PolicyPriority.MEDIUM,
            category=PolicyCategory.INFRASTRUCTURE,
            target_countries=["USA", "JPN", "DEU", "NLD", "KOR"],
            target_industries=["semiconductors", "electronics", "automotive"],
            estimated_impact=0.60,
            implementation_difficulty=0.90,
            horizon_weeks=104,
        ))

    # 7. Energy-sector hedging if Hormuz/energy nodes shocked
    energy_shocked = any(
        n.industry == Industry.ENERGY
        and peak_shock.get(n.id, 0.0) >= _HIGH_SHOCK
        for n in snapshot.nodes
    )
    if energy_shocked:
        recs.append(PolicyRecommendation(
            id=_id("energy-hedge"),
            title="Energy sector: strategic petroleum reserve draw-down + LNG rerouting",
            description=(
                "Energy nodes show material shock. Coordinate IEA member SPR release "
                "(up to 60 days supply) to suppress energy pass-through inflation. "
                "Activate LNG spot cargo rerouting from US Gulf Coast and Qatar to "
                "supplement disrupted flows."
            ),
            priority=PolicyPriority.HIGH,
            category=PolicyCategory.STOCKPILING,
            target_countries=["USA", "DEU", "JPN", "KOR", "IND"],
            target_industries=["energy", "shipping"],
            estimated_impact=0.30,
            implementation_difficulty=0.40,
            horizon_weeks=6,
        ))

    # Deduplicate and sort: CRITICAL first, then by estimated_impact desc.
    _priority_order = {
        PolicyPriority.CRITICAL: 0,
        PolicyPriority.HIGH: 1,
        PolicyPriority.MEDIUM: 2,
        PolicyPriority.LOW: 3,
    }
    recs = _dedup(recs)
    recs.sort(key=lambda r: (_priority_order[r.priority], -r.estimated_impact))

    return AdvisorResult(
        scenario_id=result.scenario_id,
        intervention_window_weeks=intervention_window,
        critical_nodes=critical_nodes,
        chokepoint_alerts=chokepoint_alerts,
        recommendations=recs,
    )


# ──────────────────────── helpers ────────────────────────


def _make_id_gen():
    seen: dict[str, int] = {}
    def gen(base: str) -> str:
        n = seen.get(base, 0)
        seen[base] = n + 1
        return base if n == 0 else f"{base}-{n}"
    return gen


def _dedup(recs: list[PolicyRecommendation]) -> list[PolicyRecommendation]:
    seen_ids: set[str] = set()
    out = []
    for r in recs:
        if r.id not in seen_ids:
            seen_ids.add(r.id)
            out.append(r)
    return out


__all__ = ["analyze"]
