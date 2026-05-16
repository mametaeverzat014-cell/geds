# API Specification

FastAPI. REST for resources, WebSocket for live simulation streams, GraphQL as an optional escape hatch for flexible dashboard queries (not in MVP). All endpoints versioned under `/api/v1/`. JSON request/response. Snake_case fields (Pydantic auto-camel-cases for the JS client if needed).

---

## 1. Conventions

- **Auth**: `Authorization: Bearer <jwt>`. Short-lived access (15min) + refresh. OAuth provider issues; gateway verifies.
- **Pagination**: cursor-based on list endpoints. Response: `{ "items": [...], "next_cursor": "..." | null }`.
- **Errors**: RFC 7807 problem+json. Codes: `400` validation, `401` auth, `403` forbidden, `404` not found, `409` conflict, `422` schema, `429` rate limit, `500` server. Body always includes `code` (machine-friendly), `message`, optional `details`.
- **Idempotency**: mutating endpoints accept `Idempotency-Key` header.
- **Cache headers**: read endpoints set `Cache-Control` and `ETag`. Hot resources cached at the edge for ≤60s.
- **Rate limit**: 60 req/min per JWT for reads, 10 req/min for simulation starts. Returned headers: `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

---

## 2. Reference resources

```http
GET /api/v1/countries
GET /api/v1/countries/{iso3}
GET /api/v1/countries/{iso3}/dependencies?year=2024&top=20
GET /api/v1/countries/{iso3}/partners?hs=8542&direction=import|export
GET /api/v1/countries/{iso3}/vulnerability?sector=automotive

GET /api/v1/commodities
GET /api/v1/commodities/{hs}
GET /api/v1/commodities/{hs}/flows?year=2024&top_exporters=10&top_importers=10
GET /api/v1/commodities/{hs}/price-history?from=2020-01-01

GET /api/v1/sectors
GET /api/v1/sectors/{code}

GET /api/v1/chokepoints
GET /api/v1/chokepoints/{id}
GET /api/v1/chokepoints/{id}/criticality
GET /api/v1/chokepoints/{id}/routed-flows?year=2024
```

Example: `GET /api/v1/countries/DEU/dependencies?year=2024&top=5`

```json
{
  "iso3": "DEU",
  "year": 2024,
  "dependencies": [
    {
      "hs_code": "8542",
      "name": "Electronic integrated circuits",
      "import_share": 0.82,
      "hhi_partners": 0.61,
      "top_partner": { "iso3": "TWN", "share": 0.48 },
      "stockpile_ratio": 0.12,
      "alt_capacity_idx": 0.34,
      "vulnerability_score": 0.78
    }
    /* … */
  ]
}
```

---

## 3. Scenarios & simulation

### 3.1 Create scenario

```http
POST /api/v1/scenarios
Content-Type: application/json

{
  "name": "Suez 2-month closure + Hormuz partial",
  "based_on_event": null,
  "horizon_weeks": 52,
  "shocks": [
    {
      "target_kind": "chokepoint",
      "target": "<suez_uuid>",
      "kind": "capacity_cap",
      "magnitude": 0.05,
      "start_week": 0,
      "duration_weeks": 8,
      "decay_curve": "step"
    },
    {
      "target_kind": "chokepoint",
      "target": "<hormuz_uuid>",
      "kind": "capacity_cap",
      "magnitude": 0.5,
      "start_week": 2,
      "duration_weeks": 6
    }
  ],
  "config": {
    "ensemble_size": 200,
    "deterministic": false,
    "rerouting": "k_shortest"
  }
}
```

Response: `201 Created`, body is the persisted scenario including its `id`.

### 3.2 Templates

```http
GET  /api/v1/scenarios/templates
GET  /api/v1/scenarios/{id}
POST /api/v1/scenarios/{id}/duplicate   # clones for editing
PATCH /api/v1/scenarios/{id}            # only on user-owned, non-shared scenarios
```

### 3.3 Run simulation

```http
POST /api/v1/scenarios/{id}/simulate?mode=sync|async
```

`mode=sync`: returns the full result inline if the run fits the sync SLO (horizon ≤ 52 weeks, ensemble_size ≤ 1, single shock — heuristic). Otherwise 422.

`mode=async`: returns `{ "run_id": "...", "status": "queued" }` immediately.

```http
GET /api/v1/simulations/{run_id}
```

```json
{
  "id": "…",
  "scenario_id": "…",
  "status": "succeeded",
  "started_at": "…",
  "finished_at": "…",
  "horizon_weeks": 52,
  "ensemble_size": 200,
  "metrics_summary": {
    "peak_inflation_dev": { "iso3": "EGY", "value": 0.087, "week": 11 },
    "max_gdp_dev":        { "iso3": "GBR", "value": -0.021, "week": 14 },
    "global_fragility_index": 0.42
  },
  "graph_version": "2026-04-01-comtrade-v3",
  "model_versions": { "xgb_inflation_12w": "1.4.2+a7e9", "gnn_propagation": "0.6.0+b12f" }
}
```

### 3.4 Frames (the actual time-series)

```http
GET /api/v1/simulations/{run_id}/frames?
        country=DEU&hs=8542&from_week=0&to_week=26&downsample=1
```

Returns a time-series suitable for charting. Without filters, returns global aggregates only (full per-country-commodity bulk is too large for a single GET — fetch via the streaming endpoint or download endpoint).

```http
GET /api/v1/simulations/{run_id}/download?format=parquet|csv|jsonl
```

Streams the full frame set.

### 3.5 Live stream

```http
WS /api/v1/simulations/{run_id}/stream
```

Server pushes msgpack frames as the simulation progresses. Frame shape:

```json
{
  "week": 7,
  "top_shocks":     [{ "iso3": "DEU", "hs": "8542", "s": 0.41 }, ...],
  "top_inflation":  [{ "iso3": "TUR", "dev": 0.063 }, ...],
  "top_gdp":        [{ "iso3": "VNM", "dev": -0.018 }, ...],
  "global":         { "fragility": 0.44, "reroute_share": 0.18 },
  "frame_hash":     "sha256:..."
}
```

Top-k per axis (default k=25). Client can request full state for a specific week via the frames endpoint.

The WebSocket also accepts client → server messages: `{ "action": "pause" | "resume" | "cancel" }`. Cancel triggers a graceful stop in the engine.

### 3.6 Cancel / re-run

```http
POST /api/v1/simulations/{run_id}/cancel
POST /api/v1/simulations/{run_id}/rerun    # re-execute with the recorded snapshot
```

---

## 4. Forecasts (ad-hoc, without a scenario)

```http
POST /api/v1/forecasts
{
  "targets":       ["inflation", "gdp"],
  "iso3":          "DEU",
  "horizon_weeks": 26,
  "conditioning": {
    "shock_state": { "8542": 0.4, "2710": 0.2 }
  }
}
```

Response includes point estimates and quantiles per target × horizon, plus attributions.

```http
GET /api/v1/forecasts/{forecast_id}
GET /api/v1/forecasts/{forecast_id}/explain
```

---

## 5. Policy advisor

```http
GET /api/v1/policy/recommendations?scenario_id=…&iso3=DEU&top=5
```

```json
{
  "iso3": "DEU",
  "recommendations": [
    {
      "action_kind": "diversify_imports",
      "action_detail": {
        "commodity_hs": "8542",
        "current_top_partner": { "iso3": "TWN", "share": 0.48 },
        "suggested_partners": [
          { "iso3": "KOR", "target_share": 0.20 },
          { "iso3": "JPN", "target_share": 0.15 }
        ]
      },
      "expected_impact_usd": 18000000000,
      "confidence": 0.71,
      "priority": 1,
      "explanation": "Concentration HHI = 0.61. Diversifying 28 pts to KOR/JPN reduces simulated peak GDP loss from -2.1% to -0.9% under the modeled scenario class. Substitution constrained by 4–6q lead time."
    }
  ]
}
```

```http
POST /api/v1/policy/simulate-intervention
{
  "scenario_id": "…",
  "interventions": [ { "kind": "stockpile", "iso3": "DEU", "hs": "8542", "delta_weeks_of_consumption": 8 } ]
}
```

Runs a counterfactual ("scenario with intervention") and returns the difference vs. the baseline.

---

## 6. Analytics

```http
GET /api/v1/analytics/fragility-index?as_of=2026-05-01
GET /api/v1/analytics/dependency-ranking?hs=8542&top=25
GET /api/v1/analytics/contagion-heatmap?scenario_id=…&week=12
GET /api/v1/analytics/chokepoint-criticality
GET /api/v1/analytics/sector-vulnerability?iso3=DEU
```

All read-heavy; all aggressively cached with sensible TTLs and ETags.

---

## 7. Admin / ingest (internal)

Behind a privileged scope (`role=admin`). Not exposed publicly.

```http
POST /api/v1/admin/ingest/{source}/trigger
GET  /api/v1/admin/ingest/runs
POST /api/v1/admin/models/{name}/promote?version=…
POST /api/v1/admin/models/{name}/rollback
POST /api/v1/admin/graph/refresh
GET  /api/v1/admin/health
```

---

## 8. OpenAPI

FastAPI generates `/api/v1/openapi.json` and a Swagger UI at `/docs`. Schema lives at `backend/app/api/openapi.py` and is checked into version control after every breaking change for diffability.

Versioning: minor / patch are backward-compatible. Breaking changes bump `v1 → v2` and run both for a deprecation window of ≥6 months.

---

## 9. Example end-to-end flow

The Suez scenario, from the frontend perspective:

```
1. POST /api/v1/scenarios                     ← create the shock
2. POST /api/v1/scenarios/{id}/simulate?mode=async   ← start
3. WS   /api/v1/simulations/{run_id}/stream   ← stream frames into the UI
4. GET  /api/v1/simulations/{run_id}          ← summary after finished
5. GET  /api/v1/policy/recommendations?scenario_id=…
6. POST /api/v1/policy/simulate-intervention  ← user clicks "what if Germany stockpiles +8w?"
7. WS   /api/v1/simulations/{intervention_run_id}/stream
```

Steps 3 and 7 are streamed; the rest are short-lived REST.
