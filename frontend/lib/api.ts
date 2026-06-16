import type { AdvisorResult, GraphSnapshot, Scenario, SimulationResult } from "./types";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const WS = (process.env.NEXT_PUBLIC_WS_URL || "ws://127.0.0.1:8000").replace(/\/$/, "");

/** Single source of truth for the backend base URL — import this, don't re-derive it. */
export const API_BASE = API;

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

// ─── model comparison + forecast band (Tasks #4/#5) ─────────────────────────

export interface BaselineModel {
  model: string;
  industry_loss: number;
  recovery_weeks: number;
  parameters: number;
}
export interface BaselineCompare {
  industry: string;
  models: BaselineModel[];
}
export interface ForecastBand {
  n_folds: number;
  metric: string;
  available: boolean;
  median?: number;
  p10?: number;
  p90?: number;
  min?: number;
  max?: number;
  rel_width?: number;
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
  /** "live" = fetched from NewsAPI/GNews; "stub" = labelled demo data (no API key). */
  mode: "live" | "stub";
  events: NewsEvent[];
}

export interface NewsOverlayState {
  active: boolean;
  applied_at?: string;
  active_until?: string;
  n_nodes_affected: number;
  deltas: Record<string, { vuln_delta: number; d_eff_multiplier: number; confidence: number; source: string; event_type: string }>;
}

// ─── Validation / track record ─────────────────────────────────────────────

export interface CVReport {
  method: string;
  n_events: number;
  runtime_seconds: number;
  pass_rate_25pct: number;
  pass_rate_25pct_ci95_lo: number;
  pass_rate_25pct_ci95_hi: number;
  pass_rate_50pct: number;
  pass_rate_50pct_ci95_lo: number;
  pass_rate_50pct_ci95_hi: number;
  mae_industry_loss: number;
  mae_inflation: number;
  mae_recovery_weeks: number;
  pearson_loss: number;
  spearman_loss: number;
  rmse_normalized: number;
  timestamp: string;
}

// ─── Crisis radar (Claude) ───────────────────────────────────────────────────

export interface CrisisScenario {
  title_en: string; title_ru: string;
  trigger_en: string; trigger_ru: string;
  mechanism_en: string; mechanism_ru: string;
  watch_en: string; watch_ru: string;
  basis: string;
  severity: "low" | "medium" | "high";
}

export interface CrisisRadarResult {
  overview_en: string; overview_ru: string;
  scenarios: CrisisScenario[];
  disclaimer_en: string; disclaimer_ru: string;
  model: string;
  cached: boolean;
  latency_ms: number;
  /** "live" = real Claude call; "stub" = no ANTHROPIC_API_KEY (labelled demo). */
  mode: "live" | "stub";
  configured: boolean;
  n_signals: number;
  active_news_count: number;
}

// ─── API client ────────────────────────────────────────────────────────────

export const api = {
  graph: (version: "v2" | "v3" = "v2"): Promise<GraphSnapshot> =>
    getJson(version === "v3" ? "/api/v1/graph?version=v3" : "/api/v1/graph"),
  scenarios: (): Promise<Scenario[]> => getJson("/api/v1/scenarios"),
  scenario: (id: string): Promise<Scenario> => getJson(`/api/v1/scenarios/${id}`),
  simulate: (req: { scenario_id?: string; custom?: unknown }): Promise<SimulationResult> =>
    postJson("/api/v1/simulate", req),
  baselineCompare: (req: { scenario_id?: string; custom?: unknown }): Promise<BaselineCompare> =>
    postJson("/api/v1/baseline-compare", req),
  forecastBand: (req: { scenario_id?: string; custom?: unknown }): Promise<ForecastBand> =>
    postJson("/api/v1/forecast-band", req),
  policy: (req: { scenario_id?: string; custom?: unknown }): Promise<AdvisorResult> =>
    postJson("/api/v1/policy", req),
  wsStreamUrl: () => `${WS}/ws/simulate`,

  // Liveness probe — root-level (/healthz), not under /api/v1.
  //
  // Returns true if the backend HOST is reachable — i.e. it answered with *any*
  // HTTP status. We deliberately do NOT require 2xx: a stale deploy that 404s on
  // /healthz, or a 500, still proves the server is up and the data endpoints may
  // work. Only a network-level failure (connection refused, DNS, CORS block, or
  // timeout) — where fetch() itself rejects — counts as offline, so the banner
  // can't false-fire against a reachable-but-imperfect backend.
  healthz: async (): Promise<boolean> => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    try {
      await fetch(`${API}/healthz`, { signal: ctrl.signal });
      return true; // any HTTP response means the host is reachable
    } catch {
      return false; // network error / timeout → genuinely unreachable
    } finally {
      clearTimeout(timer);
    }
  },

  // Grok narrative
  narrative: (req: {
    scenario_id?: string;
    custom?: unknown;
    lang?: "en" | "ru";
    force_refresh?: boolean;
  }): Promise<GrokNarrative> => postJson("/api/v1/narrative", req),

  // Crisis radar — Claude-analyzed danger scenarios (bilingual), grounded in GEDS signals
  crisisRadar: (req: { force_refresh?: boolean } = {}): Promise<CrisisRadarResult> =>
    postJson("/api/v1/crisis-radar", req),

  // News pipeline
  newsRecent: (lang: "en" | "ru" = "en", use_stub = false): Promise<NewsRecentResponse> =>
    getJson(`/api/v1/news/recent?lang=${lang}&use_stub=${use_stub}`),
  newsApply: (req: {
    use_stub?: boolean;
    decay_hours?: number;
    confidence_floor?: number;
    lang?: "en" | "ru";
  }): Promise<{ applied_at: string; active_until: string; n_nodes_affected: number; deltas: Record<string, unknown>; mode: "live" | "stub" }> =>
    postJson("/api/v1/news/apply", req),
  newsOverlay: (): Promise<NewsOverlayState> => getJson("/api/v1/news/overlay"),
  newsOverlayClear: (): Promise<{ cleared: boolean }> => deleteJson("/api/v1/news/overlay"),

  // Validation / track record (used by the truthful badge)
  cvReport: (): Promise<CVReport> => getJson("/api/v1/cv-report"),

  // Data freshness (populated by GitHub Actions daily refresh)
  lastRefresh: (): Promise<{
    last_refresh_utc: string | null;
    age_hours: number | null;
    source: string;
    workflow_run_url?: string | null;
  }> => getJson("/api/v1/data/last-refresh"),
};
