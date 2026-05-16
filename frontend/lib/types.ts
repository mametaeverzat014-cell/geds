export type NodeKind = "country_industry" | "chokepoint" | "resource";

export type Industry =
  | "semiconductors"
  | "automotive"
  | "electronics"
  | "aerospace"
  | "shipping"
  | "energy"
  | "consumer_goods";

export interface GraphNode {
  id: string;
  name: string;
  kind: NodeKind;
  country?: string | null;
  industry?: Industry | null;
  lat?: number | null;
  lon?: number | null;
  gdp_usd: number;
  vulnerability: number;
  resilience: number;
  amplification: number;
  threshold: number;
  recovery_delay_weeks: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: string;
  dependency_weight: number;
  substitution_difficulty: number;
  rerouting_capability: number;
  resilience_coefficient: number;
  recovery_delay_weeks: number;
  flow_value_usd: number;
}

export interface GraphSnapshot {
  version: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  centrality: Record<string, number>;
}

export interface NodeFrame {
  id: string;
  shock: number;
  inflation_pressure: number;
  output_loss: number;
  shortage_prob: number;
  unemployment_risk: number;
}

export interface Frame {
  week: number;
  nodes: NodeFrame[];
  csi: number;
  ecv: number;
  ecv_geo: number;
  affected_count: number;
  total_output_loss: number;
}

export interface CountryRisk {
  iso3: string;
  risk_score: number;
  peak_shock: number;
  peak_inflation: number;
  peak_unemployment: number;
  expected_recovery_weeks: number;
}

export interface SectorFragility {
  industry: Industry;
  fragility_score: number;
  most_exposed_country: string;
  expected_disruption: number;
}

export interface SimulationSummary {
  peak_csi: number;
  peak_ecv: number;
  final_csi: number;
  total_output_loss_usd: number;
  max_inflation_country: [string, number];
  max_gdp_impact_country: [string, number];
  affected_country_count: number;
  global_recovery_weeks: number;
  country_risk: CountryRisk[];
  sector_fragility: SectorFragility[];
}

export interface ShockSpec {
  target_node_id: string;
  magnitude: number;
  start_week: number;
  duration_weeks: number;
  decay_curve: "step" | "linear" | "exp";
  note?: string | null;
}

export interface Scenario {
  id: string;
  name: string;
  description?: string | null;
  horizon_weeks: number;
  shocks: ShockSpec[];
}

export interface SimulationResult {
  scenario_id: string;
  horizon_weeks: number;
  graph_version: string;
  frames: Frame[];
  summary: SimulationSummary;
}

export type StreamMessage =
  | { event: "start"; scenario: Scenario; graph_version: string; node_count: number }
  | { event: "frame"; frame: Frame }
  | { event: "complete"; summary: SimulationSummary }
  | { event: "error"; message: string };

// ─────────────── policy advisor ───────────────

export type PolicyPriority = "critical" | "high" | "medium" | "low";
export type PolicyCategory =
  | "emergency"
  | "diversification"
  | "stockpiling"
  | "diplomatic"
  | "infrastructure"
  | "monetary";

export interface PolicyRecommendation {
  id: string;
  title: string;
  description: string;
  priority: PolicyPriority;
  category: PolicyCategory;
  target_countries: string[];
  target_industries: string[];
  estimated_impact: number;
  implementation_difficulty: number;
  horizon_weeks: number;
}

export interface AdvisorResult {
  scenario_id: string;
  intervention_window_weeks: number;
  critical_nodes: string[];
  chokepoint_alerts: string[];
  recommendations: PolicyRecommendation[];
}
