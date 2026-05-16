import type { AdvisorResult, GraphSnapshot, Scenario, SimulationResult } from "./types";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const WS = (process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000").replace(/\/$/, "");

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json();
}

async function deleteJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`);
  return res.json();
}

// ─── Grok narrative ────────────────────────────────────────────────────────

export interface PolicyRec {
  action: string;
  target: string;
  time_horizon_weeks: number;
}

export interface GrokNarrative {
  scenario_id: string;
  lang: "en" | "ru";
  model: string;
  cached: boolean;
  latency_ms: number;
  confidence: "low" | "medium" | "high";
  executive_summary: string;
  cascade_mechanism: string;
  immediate_risks: string[];
  structural_vulnerabilities: string[];
  policy_recommendations: PolicyRec[];
  overlay_active: boolean;
  overlay_node_count: number;
}

// ─── News pipeline ─────────────────────────────────────────────────────────

export interface NewsDelta {
  node_id: string;
  vulnerability_delta: number;
  d_eff_multiplier: number;
  decay_weeks: number;
  confidence: number;
}

export interface NewsEvent {
  headline: {
    title: string;
    description: string;
    source: string;
    url: string;
    published_at: string;
  };
  event_type: "strike" | "conflict" | "disaster" | "policy" | "logistics" | "unknown";
  matched_nodes: string[];
  entities: string[];
  deltas: NewsDelta[];
}

export interface NewsRecentResponse {
  n_events: number;
  lang: "en" | "ru";
  events: NewsEvent[];
}

export interface NewsOverlayState {
  active: boolean;
  applied_at?: string;
  active_until?: string;
  n_nodes_affected: number;
  deltas: Record<string, { vuln_delta: number; d_eff_multiplier: number; confidence: number; source: string; event_type: string }>;
}

// ─── API client ────────────────────────────────────────────────────────────

export const api = {
  graph: (): Promise<GraphSnapshot> => getJson("/api/v1/graph"),
  scenarios: (): Promise<Scenario[]> => getJson("/api/v1/scenarios"),
  scenario: (id: string): Promise<Scenario> => getJson(`/api/v1/scenarios/${id}`),
  simulate: (req: { scenario_id?: string; custom?: unknown }): Promise<SimulationResult> =>
    postJson("/api/v1/simulate", req),
  policy: (req: { scenario_id?: string; custom?: unknown }): Promise<AdvisorResult> =>
    postJson("/api/v1/policy", req),
  wsStreamUrl: () => `${WS}/ws/simulate`,

  // Grok narrative
  narrative: (req: {
    scenario_id?: string;
    custom?: unknown;
    lang?: "en" | "ru";
    force_refresh?: boolean;
  }): Promise<GrokNarrative> => postJson("/api/v1/narrative", req),

  // News pipeline
  newsRecent: (lang: "en" | "ru" = "en", use_stub = false): Promise<NewsRecentResponse> =>
    getJson(`/api/v1/news/recent?lang=${lang}&use_stub=${use_stub}`),
  newsApply: (req: {
    use_stub?: boolean;
    decay_hours?: number;
    confidence_floor?: number;
    lang?: "en" | "ru";
  }): Promise<{ applied_at: string; active_until: string; n_nodes_affected: number; deltas: Record<string, unknown> }> =>
    postJson("/api/v1/news/apply", req),
  newsOverlay: (): Promise<NewsOverlayState> => getJson("/api/v1/news/overlay"),
  newsOverlayClear: (): Promise<{ cleared: boolean }> => deleteJson("/api/v1/news/overlay"),
};
