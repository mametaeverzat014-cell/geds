"""Pydantic types for the cascade propagation engine.

Style notes:
* Snake_case fields, serialized as-is over JSON.
* Floats for everything continuous; ints for counts and time steps.
* `model_dump(mode="json")` is the canonical serializer — used by API and WS frame encoding.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NodeKind(str, Enum):
    COUNTRY_INDUSTRY = "country_industry"
    CHOKEPOINT = "chokepoint"
    RESOURCE = "resource"


class EdgeKind(str, Enum):
    TRADE = "trade"                       # bilateral export → import
    PRODUCTION_INPUT = "production_input" # commodity → industry that uses it
    ROUTES_THROUGH = "routes_through"     # flow uses a chokepoint
    INTRA_INDUSTRY = "intra_industry"     # cross-sector coupling within a country


class Industry(str, Enum):
    SEMICONDUCTORS = "semiconductors"
    AUTOMOTIVE = "automotive"
    ELECTRONICS = "electronics"
    AEROSPACE = "aerospace"
    SHIPPING = "shipping"
    ENERGY = "energy"
    CONSUMER_GOODS = "consumer_goods"
    # Schema extension v2 — added 2026-05-26 to cover all 42 historical events.
    # Each new value requires entries in:
    #   - graph.INDUSTRY_COEFFICIENTS (pass_through, elasticity, labor)
    #   - seis.INDUSTRY_INVENTORY_WEEKS (SEIRS buffer depth in weeks)
    BANKING = "banking"
    INSURANCE = "insurance"
    CAPITAL_MARKETS = "capital_markets"
    OIL = "oil"
    GAS = "gas"
    UTILITIES = "utilities"
    AVIATION = "aviation"
    PORTS = "ports"
    TELECOMMUNICATIONS = "telecommunications"
    AGRICULTURE = "agriculture"
    TOURISM = "tourism"
    GOVERNMENT = "government"


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: NodeKind
    country: str | None = None                 # ISO3 for country_industry nodes
    industry: Industry | None = None
    lat: float | None = None
    lon: float | None = None

    gdp_usd: float = Field(0.0, ge=0)          # GDP share attributable to this node
    population_weight: float = Field(0.0, ge=0)
    employment: float = Field(0.0, ge=0)

    vulnerability: float = Field(0.5, ge=0, le=1)        # intrinsic shock sensitivity
    resilience: float = Field(0.5, ge=0, le=1)           # ability to absorb shock
    amplification: float = Field(1.0, ge=0)              # baseline amplification factor
    threshold: float = Field(0.5, ge=0, le=1)            # nonlinear-amplification threshold
    recovery_delay_weeks: float = Field(6.0, ge=0)
    inventory_weeks: int | None = Field(None, ge=0)      # SEIS buffer depth (None = industry default)

    meta: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    kind: EdgeKind
    dependency_weight: float = Field(..., ge=0, le=1)    # how much target depends on source
    substitution_difficulty: float = Field(0.5, ge=0, le=1)
    rerouting_capability: float = Field(0.3, ge=0, le=1)
    resilience_coefficient: float = Field(0.2, ge=0, le=1)
    recovery_delay_weeks: float = Field(4.0, ge=0)
    flow_value_usd: float = Field(0.0, ge=0)
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("target")
    @classmethod
    def _not_self_loop(cls, v: str, info: Any) -> str:
        if info.data.get("source") == v:
            raise ValueError("Edge source and target must differ")
        return v


class GraphSnapshot(BaseModel):
    """Immutable graph used by the engine. Built from seed data."""

    model_config = ConfigDict(extra="forbid")

    version: str = "0.1.0-mvp"
    nodes: list[Node]
    edges: list[Edge]
    centrality: dict[str, float] = Field(default_factory=dict)  # node_id → score
    shortest_path: dict[str, dict[str, int]] = Field(default_factory=dict)  # origin → {node: hops}


# ───────────────────────────── scenarios ─────────────────────────────


class ShockSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_node_id: str
    magnitude: float = Field(..., ge=0, le=1)
    start_week: int = Field(0, ge=0)
    duration_weeks: int = Field(8, ge=1)
    decay_curve: Literal["step", "linear", "exp"] = "step"
    note: str | None = None

    def factor(self, t: int) -> float:
        """Multiplicative factor in [0, 1] for the time-position within the shock window."""
        if t < self.start_week or t >= self.start_week + self.duration_weeks:
            return 0.0
        rel = (t - self.start_week) / max(1, self.duration_weeks - 1)
        if self.decay_curve == "step":
            return 1.0
        if self.decay_curve == "linear":
            return max(0.0, 1.0 - rel)
        # exp
        return float(2.71828 ** (-2.5 * rel))


class EngineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    propagation_decay: float = Field(0.85, gt=0, le=1)
    rerouting_efficiency: float = Field(0.55, ge=0, le=1)
    amplification_mu: float = Field(2.2, ge=0)
    amplification_eps: float = Field(0.06, gt=0)
    recovery_rate: float = Field(0.07, ge=0, le=1)
    stochastic_sigma: float = Field(0.0, ge=0)
    seed: int | None = None
    seis_enabled: bool = Field(True)
    adaptive_rerouting: bool = Field(True)

    # ── Calibratable behavioral parameters (lifted from hardcoded constants) ──
    bullwhip_factor: float = Field(1.25, ge=1.0, le=2.0)        # E-state inbound multiplier
    r_output_floor: float = Field(0.30, ge=0.0, le=1.0)         # R-state production cap (1 − floor = % capacity)
    inventory_scale: float = Field(1.0, ge=0.1, le=3.0)         # global multiplier on per-node inventory_weeks
    distress_base: float = Field(0.40, ge=0.10, le=0.80)        # base output-loss level for default risk
    distress_week_threshold: int = Field(6, ge=1, le=26)        # consecutive distress weeks → ~50% default prob
    sanity_max_loss_fraction: float = Field(0.15, ge=0.01, le=0.5)  # max event loss as fraction of horizon-global GDP


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None = None
    horizon_weeks: int = Field(52, ge=1, le=520)
    shocks: list[ShockSpec]
    config: EngineConfig = Field(default_factory=EngineConfig)


# ───────────────────────────── frames & results ─────────────────────────────


class NodeFrame(BaseModel):
    """Per-node state at a single timestep."""

    model_config = ConfigDict(extra="forbid")

    id: str
    shock: float                              # in [0, 1]
    inflation_pressure: float                 # in [0, 1+]
    output_loss: float                        # GDP loss as a fraction
    shortage_prob: float                      # in [0, 1]
    unemployment_risk: float                  # in [0, 1]
    seis_state: int = Field(0, ge=0, le=3)    # 0=Susceptible 1=Exposed 2=Infected 3=Recovering
    default_probability: float = Field(0.0, ge=0, le=1)   # technical-default risk


class Frame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week: int
    nodes: list[NodeFrame]
    csi: float                                # Cascade Severity Index
    ecv: float                                # Economic Contagion Velocity
    ecv_geo: float                            # geodesic ECV
    affected_count: int                       # nodes with shock > threshold
    total_output_loss: float                  # aggregated GDP loss


class CountryRisk(BaseModel):
    iso3: str
    risk_score: float
    peak_shock: float
    peak_inflation: float
    peak_unemployment: float
    expected_recovery_weeks: float


class SectorFragility(BaseModel):
    industry: Industry
    fragility_score: float
    most_exposed_country: str
    expected_disruption: float


class MarketCapImpact(BaseModel):
    """Projected market-cap loss for a single node."""
    model_config = ConfigDict(extra="forbid")
    node_id: str
    market_cap_loss_usd: float
    default_probability: float = Field(0.0, ge=0, le=1)


class SimulationSummary(BaseModel):
    peak_csi: float
    peak_ecv: float
    final_csi: float
    total_output_loss_usd: float
    max_inflation_country: tuple[str, float]
    max_gdp_impact_country: tuple[str, float]
    affected_country_count: int
    global_recovery_weeks: float
    country_risk: list[CountryRisk]
    sector_fragility: list[SectorFragility]
    # Financial intelligence layer (added in v0.2)
    total_market_cap_loss_usd: float = 0.0
    high_default_risk_count: int = 0           # nodes with default_probability > 0.5
    top_market_cap_impacts: list[MarketCapImpact] = Field(default_factory=list)


class SimulationResult(BaseModel):
    scenario_id: str
    horizon_weeks: int
    graph_version: str
    frames: list[Frame]
    summary: SimulationSummary


# ───────────────────────────── policy advisor ─────────────────────────────


class PolicyPriority(str, Enum):
    CRITICAL = "critical"   # act within 1–2 weeks
    HIGH = "high"           # act within 1–3 months
    MEDIUM = "medium"       # act within 6–12 months
    LOW = "low"             # long-term strategic


class PolicyCategory(str, Enum):
    EMERGENCY = "emergency"
    DIVERSIFICATION = "diversification"
    STOCKPILING = "stockpiling"
    DIPLOMATIC = "diplomatic"
    INFRASTRUCTURE = "infrastructure"
    MONETARY = "monetary"


class PolicyRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str
    priority: PolicyPriority
    category: PolicyCategory
    target_countries: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    estimated_impact: float = Field(..., ge=0, le=1)          # fractional risk reduction
    implementation_difficulty: float = Field(..., ge=0, le=1) # 0 = easy, 1 = very hard
    horizon_weeks: int = Field(..., ge=1)                      # weeks until policy takes effect


class AdvisorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    intervention_window_weeks: int    # estimated weeks before peak CSI; act within this window
    critical_nodes: list[str]         # node IDs ranked by (peak_shock × centrality) desc
    chokepoint_alerts: list[str]      # chokepoint node IDs with shock > 0.25
    recommendations: list[PolicyRecommendation]


# ───────────────────────────── Monte Carlo ────────────────────────────────────


class MonteCarloResult(BaseModel):
    """Output of N-iteration Monte Carlo over perturbed graph parameters."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    n_iterations: int
    param_noise_pct: float              # ±% applied to dependency weights
    # Weekly GDP loss confidence bands (length = horizon_weeks)
    weekly_loss_p5: list[float]
    weekly_loss_p50: list[float]
    weekly_loss_p95: list[float]
    # Summary scalars
    peak_csi_p5: float
    peak_csi_p50: float
    peak_csi_p95: float
    total_loss_p5: float
    total_loss_p50: float
    total_loss_p95: float
    total_loss_mean: float
    total_loss_std: float
    # Financial intelligence bands
    market_cap_loss_p5: float = 0.0
    market_cap_loss_p50: float = 0.0
    market_cap_loss_p95: float = 0.0
    high_default_risk_count_p50: int = 0
    runtime_seconds: float


# ───────────────────────────── Centrality ────────────────────────────────────


class NodeCentrality(BaseModel):
    """Per-node Cascading Impact Score and related trade-weighted metrics."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    name: str
    cis: float                   # Cascading Impact Score (weighted PageRank, 0–1)
    upstream_criticality: float  # importance as a supplier (weighted out-degree, 0–1)
    downstream_exposure: float   # economic value at risk downstream (0–1)
    chokepoint_exposure: float   # fraction of supply routed through chokepoints (0–1)
    rank: int                    # 1-indexed rank by CIS descending


class CentralityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[NodeCentrality]
    method: str = "weighted_pagerank_v2"
    data_sources: list[str]
