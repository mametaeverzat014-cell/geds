# GEDS — Global Economic Disruption Simulator

> A research-grade platform that models the global economy as a weighted, directed multigraph of countries × sectors × commodities, propagates shocks through it in discrete time, and forecasts the cascading effects with a stack of ML models (GNN, XGBoost, temporal forecasting, RL). The output: real-time, interactive, cinematic visualizations of systemic global fragility.

This document is the master blueprint. It covers the fifteen design areas from the spec at a strategic level, with deep-dive supplementary docs in [`docs/`](./docs/).

---

## 0. Vision

Three positioning claims that drive every design decision:

1. **Network-first.** The world economy is a graph, not a table. Every model, schema, and visualization derives from the graph representation. Tabular views are projections, not the source of truth.
2. **Simulation over reporting.** GEDS does not just *describe* the present; it generates counterfactual futures. Every screen has a "what if" affordance — the simulator is always one click away.
3. **Explainability as a first-class feature.** A black-box forecast that says "Germany's GDP drops 2.3%" is useless. Every prediction must surface: which nodes drove it, which edges carried the shock, what the second-order effects were, and what policy interventions move the needle.

If any feature, model, or screen does not advance one of those three, it does not ship.

---

## 1. System Architecture

### 1.1 Component overview

```
                              ┌────────────────────────────────────────┐
                              │                FRONTEND                │
                              │  Next.js · React · TS · Three.js · D3  │
                              │  Mapbox/deck.gl · Framer Motion        │
                              └───────────────┬────────────────────────┘
                                              │ HTTPS · WSS
                              ┌───────────────▼────────────────────────┐
                              │           API GATEWAY (FastAPI)        │
                              │  REST · WebSocket · GraphQL (optional) │
                              │  Auth · Rate limit · Caching headers   │
                              └─┬───────────┬───────────┬──────────────┘
                                │           │           │
              ┌─────────────────▼──┐  ┌─────▼──────┐  ┌─▼──────────────────┐
              │ SIMULATION SERVICE │  │ ML SERVICE │  │ ANALYTICS SERVICE  │
              │  Shock propagation │  │  GNN · XGB │  │  Aggregations,     │
              │  Rerouting · State │  │  TFT · RL  │  │  rankings, KPIs    │
              │  Engine (Python)   │  │  PyTorch   │  │  Query layer       │
              └────────┬───────────┘  └─────┬──────┘  └──────────┬─────────┘
                       │                    │                    │
                       │      ┌─────────────▼────────────┐       │
                       │      │   FEATURE / EMBEDDING    │       │
                       │      │   STORE (Redis + PG)     │       │
                       │      └──────────────────────────┘       │
                       │                                         │
              ┌────────▼─────────────────────────────────────────▼─────────┐
              │                        DATA LAYER                          │
              │   PostgreSQL (relational) · TimescaleDB (time-series)      │
              │   Neo4j (graph)          · Redis (cache + pubsub)          │
              │   Object store (raw datasets, replays, model artifacts)    │
              └────────┬──────────────────────────────────────────┬────────┘
                       │                                          │
              ┌────────▼─────────────┐                  ┌─────────▼────────┐
              │  INGEST PIPELINES    │                  │  ML TRAINING     │
              │  Airflow / Prefect   │                  │  Pipelines       │
              │  Connectors:         │                  │  (offline, GPU)  │
              │  WTO, Comtrade,      │                  │  Versioned       │
              │  OECD, IMF, World    │                  │  artifacts       │
              │  Bank, AIS, prices   │                  │                  │
              └──────────────────────┘                  └──────────────────┘
```

### 1.2 Service boundaries

| Service | Owns | Talks to | Language |
|---|---|---|---|
| **API Gateway** | HTTP/WS surface, auth, validation, response shaping | every backend service | Python / FastAPI |
| **Simulation Service** | Discrete-time shock engine, state, rerouting | Neo4j, Postgres, Redis (state), ML service (priors) | Python (NumPy / SciPy / NetworkX / Numba) |
| **ML Service** | Inference for GNN, XGBoost, temporal models, RL policy | Feature store, Postgres, model registry | Python / PyTorch / XGBoost / PyTorch Geometric |
| **Analytics Service** | Aggregations, rankings, KPIs, comparison queries | Postgres, TimescaleDB, Redis cache | Python / SQLAlchemy |
| **Ingest Pipelines** | Source connectors, validation, normalization, replay | external APIs, Postgres, Neo4j, object store | Python / Airflow or Prefect |
| **ML Training** | Offline model training, evaluation, registry | object store, Postgres, GPU pool | Python / PyTorch Lightning |

The simulation service and ML service are **stateless workers** that scale horizontally. State lives in the data layer. The simulation service can run synchronously (interactive scenario, <1s) or asynchronously via a Celery job queue (multi-year, multi-shock runs).

### 1.3 Data flow

- **Read path:** Frontend → API Gateway → Analytics Service → Postgres / TimescaleDB → response (cached in Redis when hot).
- **Simulation path:** Frontend → API Gateway → Simulation Service → loads graph from Neo4j → runs propagation loop → writes intermediate frames to Redis (pubsub) → API Gateway streams frames over WebSocket → Frontend renders animated propagation.
- **Forecast path:** Simulation Service computes prior trajectory → ML Service consumes prior + graph features → returns probabilistic forecast (mean + intervals + attributions) → returned alongside simulation result.
- **Ingest path:** Scheduled DAG → connector → raw store → validation → normalization → upsert into Postgres (entities) + Neo4j (graph) → cache invalidation in Redis → ML feature recomputation triggered.

### 1.4 Communication patterns

- **REST** for resources (countries, sectors, scenarios, results).
- **WebSocket** for live simulation streaming and collaborative scenario sessions.
- **Redis pubsub** internally between simulation workers and the gateway.
- **gRPC (optional, future)** for high-throughput simulation → ML calls if Python-to-Python REST becomes a bottleneck.

See [`docs/api-specification.md`](./docs/api-specification.md) for the full surface.

---

## 2. Folder / Project Structure

```
GEDS/
├── ARCHITECTURE.md                  ← this file
├── docs/                            ← deep-dive design docs
│   ├── mathematical-framework.md
│   ├── database-schema.sql
│   ├── graph-model.cypher
│   ├── simulation-engine.md
│   ├── ai-ml-models.md
│   ├── api-specification.md
│   ├── frontend-architecture.md
│   ├── ui-ux-design.md
│   ├── data-ingestion.md
│   ├── scalability-deployment.md
│   └── roadmap.md
│
├── backend/                         ← FastAPI services
│   └── app/
│       ├── api/                     ← HTTP/WS routers
│       ├── core/                    ← config, logging, security
│       ├── simulation/              ← shock engine (propagation, rerouting)
│       ├── models/                  ← Pydantic + SQLAlchemy models
│       ├── services/                ← analytics, scenario, policy advisor
│       ├── db/                      ← session, migrations, repos
│       └── workers/                 ← Celery tasks, schedulers
│
├── frontend/                        ← Next.js app
│   ├── app/                         ← App Router routes
│   ├── components/                  ← Globe, Heatmap, Timeline, ScenarioBuilder, …
│   ├── lib/                         ← API client, simulation state, hooks
│   ├── public/
│   └── styles/
│
├── ml/                              ← models, training, inference
│   ├── models/                      ← GNN, XGBoost, TFT, RL policy
│   ├── training/                    ← pipelines, callbacks, configs
│   ├── features/                    ← feature engineering
│   ├── inference/                   ← model serving wrappers
│   └── notebooks/                   ← exploratory analysis, validation
│
├── data/                            ← datasets and replays
│   ├── raw/                         ← source dumps (gitignored)
│   ├── processed/                   ← normalized parquet (gitignored)
│   ├── fixtures/                    ← small seed data for tests
│   └── replay/                      ← historical crisis replays (COVID, Suez…)
│
├── simulations/                     ← named scenarios and persisted results
│   ├── scenarios/                   ← JSON scenario definitions
│   └── results/                     ← serialized simulation outputs
│
└── infra/
    ├── docker/                      ← Dockerfiles, compose
    ├── k8s/                         ← manifests / Helm
    └── terraform/                   ← cloud infra (optional)
```

---

## 3. Database Schema

Two engines, two responsibilities:

- **PostgreSQL** is the system of record for entities, scenarios, simulation runs, and model registry. TimescaleDB extension handles time-series (prices, indices, simulation frames).
- **Neo4j** is the graph engine for the trade network. It is the query target for path-finding, centrality, chokepoint analysis, and adaptive rerouting.

Both are kept consistent by the ingest pipeline (Postgres-first, Neo4j projected from it). Redis caches hot reads and broadcasts simulation frames.

Full DDL in [`docs/database-schema.sql`](./docs/database-schema.sql).

### Headline tables

- `countries`, `sectors`, `commodities`, `companies` (optional layer)
- `trade_flows` (country_a × country_b × commodity × year × value × quantity)
- `production` (country × sector × year × output × employment)
- `dependencies` (country × commodity × import_share × concentration_index)
- `chokepoints` (ports, straits, canals — with capacity and routing role)
- `historical_events` (COVID, Suez, oil shocks — for replay and ML training)
- `scenarios` (user-defined or AI-generated shock configurations)
- `simulation_runs`, `simulation_frames` (week-by-week state)
- `forecasts` (model_id × scenario_id × target × distribution)
- `policy_recommendations` (scenario_id × action × expected_impact × explanation)

---

## 4. Graph Data Model

Nodes:

- `(:Country {iso3, gdp, population, gini, …})`
- `(:Sector {code, name, gva_share})`
- `(:Commodity {hs_code, name, criticality_score})`
- `(:Port {id, lat, lon, throughput})`
- `(:Chokepoint {id, name, type, daily_capacity})` — Suez, Hormuz, Malacca, Panama, Bosporus, Bab-el-Mandeb, Taiwan Strait
- `(:Company {id, name, sector, hq_country})` *(optional firm-level layer)*

Relationships (all weighted, with temporal attributes):

- `(:Country)-[:EXPORTS {commodity, value, quantity, year}]->(:Country)`
- `(:Country)-[:PRODUCES {sector, output, employment, year}]->(:Sector)`
- `(:Country)-[:DEPENDS_ON {commodity, import_share, alt_sources}]->(:Commodity)`
- `(:Country)-[:ROUTES_THROUGH {fraction, alt_route_cost}]->(:Chokepoint)`
- `(:Port)-[:LOCATED_IN]->(:Country)`
- `(:Sector)-[:USES {intensity}]->(:Commodity)` *(input-output coefficient)*
- `(:Sector)-[:FEEDS {intensity}]->(:Sector)` *(intersectoral coupling)*

Why graph for trade and tabular for the rest: rerouting and chokepoint analysis are *fundamentally* path problems. Doing them in SQL is masochism; doing aggregations in Cypher is wasteful. Each engine plays its strength.

Full Cypher in [`docs/graph-model.cypher`](./docs/graph-model.cypher).

---

## 5. Simulation Engine Architecture

A discrete-time, event-driven propagation engine over the weighted graph. Each tick = 1 week (configurable). At each tick:

1. **Apply scheduled shocks.** A shock is a multiplicative or additive perturbation on a node, edge, or chokepoint over a time window (e.g., "Suez throughput → 30% for 6 weeks").
2. **Propagate.** For every shocked node, compute first-order impact on neighbors using the weighted-graph propagation equation (see [math](./docs/mathematical-framework.md)). Apply resilience modifiers, propagation decay, and nonlinear amplification near thresholds.
3. **Reroute.** For commodities whose primary path is disrupted, find the shortest-cost alternative path (Yen's k-shortest paths or learned RL policy). Apply rerouting cost as inflation pressure.
4. **Update derived metrics.** Inflation, GDP impact, sector shortages, unemployment risk — per country, per sector — using the macro equations in the math doc.
5. **Persist frame.** Snapshot state to Redis (live stream) and TimescaleDB (durable).
6. **Check convergence / stop conditions.** End at horizon T or when the L2-norm of state delta < ε for K consecutive steps.

The engine is built around five primitives the spec names explicitly: **weighted graph traversal, propagation decay, resilience modifiers, adaptive rerouting, nonlinear amplification.** Each has a pluggable implementation so we can swap the analytical version for a learned one (RL rerouting, GNN propagation) without changing the orchestrator.

Full algorithmic detail in [`docs/simulation-engine.md`](./docs/simulation-engine.md).

---

## 6. AI / ML Architecture

Five model families, each owning a specific prediction:

| Model | Job | Why this family |
|---|---|---|
| **Graph Neural Network** (GraphSAGE + GAT hybrid) | Per-country, per-sector vulnerability and shock-response embeddings | Learns over the actual trade graph; respects neighborhood structure |
| **XGBoost** | Tabular forecasts (inflation, unemployment, GDP delta) conditioned on simulation features | Strong on tabular, fast, interpretable via SHAP |
| **Temporal Fusion Transformer** | Multi-horizon time-series forecasting per commodity, per index | Handles multivariate, static + dynamic covariates, gives prediction intervals |
| **Reinforcement Learning** (PPO over graph environment) | Adaptive rerouting policy under uncertainty | Pure search blows up; RL learns the cost surface |
| **Anomaly detection** (Isolation Forest + autoencoder) | Real-time deviation alerts on prices / flows | Unsupervised; catches regimes the supervised models weren't trained on |

Training data: historical crises labeled and aligned — COVID supply shock, Suez 2021 blockage, Russia-Ukraine 2022 commodity disruption, 1973/1979/2014 oil shocks, 2020–2023 semiconductor shortage, plus a long tail of trade disruptions from the World Bank's crisis database.

Inference is wrapped in a single `ModelEnsemble` interface so the simulation can request `ensemble.predict_inflation(country, horizon, scenario_features)` and receive a calibrated distribution rather than coupling to a specific model.

Full detail (architectures, hyperparameters, training pipelines, calibration) in [`docs/ai-ml-models.md`](./docs/ai-ml-models.md).

---

## 7. API Design

REST resources for CRUD, WebSocket for live simulation, GraphQL as an optional escape hatch for the dashboard.

Headline endpoints:

```
GET    /api/v1/countries
GET    /api/v1/countries/{iso3}
GET    /api/v1/countries/{iso3}/dependencies
GET    /api/v1/commodities/{hs}/flows
GET    /api/v1/chokepoints
GET    /api/v1/chokepoints/{id}/criticality

POST   /api/v1/scenarios                   ← create
GET    /api/v1/scenarios/{id}
POST   /api/v1/scenarios/{id}/simulate     ← run sync (small) or async (large)
GET    /api/v1/simulations/{run_id}
GET    /api/v1/simulations/{run_id}/frames

WS     /api/v1/simulations/{run_id}/stream ← live propagation frames

POST   /api/v1/forecasts                   ← ad-hoc forecast call
GET    /api/v1/policy/recommendations?scenario_id=…
GET    /api/v1/analytics/fragility-index
GET    /api/v1/analytics/dependency-ranking
GET    /api/v1/analytics/contagion-heatmap?scenario_id=…
```

Auth: JWT with short-lived access + refresh. Rate limit per key. Versioned URL prefix.

Full spec in [`docs/api-specification.md`](./docs/api-specification.md).

---

## 8. Frontend Architecture

Next.js 14+ App Router. TypeScript everywhere. State split:

- **Server state** (`@tanstack/react-query`): all API data, with cache invalidation on scenario changes.
- **Simulation state** (`zustand`): the active scenario, the playback head, selected entities — small, synchronous, persists across routes.
- **Visualization state** (per-component): camera, viewport, hovered ref, animation phase. Not lifted.

Rendering pipeline:

- **Globe view** — `react-globe.gl` or custom Three.js scene; great-circle arcs for flows, instanced meshes for nodes, additive shaders for shock pulses.
- **Map view** — Mapbox GL or deck.gl, layered: country choropleth, arc layer for flows, scatter for ports, heatmap for contagion.
- **Charts** — D3 for bespoke (sectoral graphs, propagation cascades), Recharts/Visx for stock charts and intervals.
- **Animations** — Framer Motion for UI; GSAP timeline for cinematic scenario intros; shaders for shock-front propagation.

A central `SimulationPlayer` orchestrates time. Every visualization subscribes to `(scenarioId, frameIndex)` from Zustand and renders the frame from a chunked stream pulled over WebSocket.

Full detail in [`docs/frontend-architecture.md`](./docs/frontend-architecture.md).

---

## 9. UI / UX Structure

Six core screens:

1. **Atlas** — the default landing: rotating 3D globe with live trade flow arcs, current fragility index in the corner, a "what's vulnerable today" ticker.
2. **Scenario Builder** — pick shock(s): nodes, commodities, chokepoints, magnitude, duration. Pre-built historical templates (COVID, Suez, Ukraine).
3. **Simulation Theater** — full-screen cinematic playback. Timeline scrub bar, propagation visualized as expanding shock fronts across the graph, derived metrics in floating panels.
4. **Forecast Dashboard** — per-country, per-sector breakdown: inflation, GDP, unemployment, shortage probability with intervals.
5. **Policy Advisor** — AI-generated recommendations ranked by expected impact, with side-by-side counterfactual ("with vs. without diversification").
6. **Comparative Lab** — run N scenarios in parallel, compare trajectories side-by-side.

Design language: dark-first, deep navy + carbon, accent colors mapped to severity (cyan → amber → magenta → blood-red), glassmorphism on panels, monospace numerics, generous negative space. Motion is meaningful — never decorative — and always conveys causation (a shock pulse moves *along an edge*, not in a vacuum).

Full design language, screen breakdowns, motion specs, and accessibility considerations in [`docs/ui-ux-design.md`](./docs/ui-ux-design.md).

---

## 10. Data Ingestion Pipelines

Sources:

- **WTO** — stats portal (tariffs, trade in value-added)
- **UN Comtrade** — bilateral trade flows (HS-coded)
- **OECD** — input-output tables, indicators
- **IMF** — WEO, IFS, BoP
- **World Bank** — WDI, crisis database
- **AIS shipping** — Marine Traffic / public AIS feeds
- **Commodity prices** — World Bank Pink Sheet, FRED
- **Inflation** — IMF CPI series, FRED
- **Semiconductors** — SIA, SEMI association datasets
- **Historical crises** — curated event database (manual + WB)

Architecture: each source has a `Connector` class with `extract → validate → normalize → load` stages. Scheduled via Prefect (preferred over Airflow for the lighter footprint and dynamic flows). All loads are **idempotent and versioned** — a load writes to a versioned dataset id, then atomically swaps the active pointer. This enables historical replay simulations and reproducible model training.

Full detail in [`docs/data-ingestion.md`](./docs/data-ingestion.md).

---

## 11. Mathematical Framework

The full formalism — propagation equations, resilience model, inflation transmission, GDP impact, cascade dynamics, network centrality, stochastic component, calibration approach — lives in [`docs/mathematical-framework.md`](./docs/mathematical-framework.md).

Five primitives anchor the model:

1. **Weighted directed multigraph** G = (V, E, W) with V = countries × sectors and E carrying commodity-tagged trade flows.
2. **Propagation with decay**: shock magnitude on node `i` at time `t+1` is the sum of decayed in-flows from shocked neighbors minus the node's resilience modifier.
3. **Resilience modifier**: a function of stockpiles, GDP per capita, sectoral diversification, and the alternate-sourcing concentration (HHI of import partners).
4. **Adaptive rerouting**: when an edge is disrupted, flow is redistributed along the lowest-cost alternative path; cost = distance + tariff + congestion penalty, optionally learned by RL.
5. **Nonlinear amplification**: when shock magnitude crosses a threshold (e.g., stockpile depletion), local response becomes superlinear via a logistic kicker. This produces the cliff-edge behavior real crises exhibit.

---

## 12. Scalability Plan

- **Horizontal stateless services.** Simulation and ML services scale on Kubernetes HPA driven by queue depth.
- **Sharded simulation.** Large multi-shock scenarios are partitioned by sub-region (e.g., per continent) for the propagation step, with a global reduce step. This keeps per-worker memory bounded while preserving global feedback.
- **Graph caching.** The full Neo4j graph is mirrored in-memory in the simulation worker as a NetworkX (or igraph) handle at startup; updates are deltas, not reloads.
- **TimescaleDB for frames.** Hypertable chunked by simulation_run_id × week, with continuous aggregates for the dashboard rollups.
- **Redis caching.** Read-through cache on hot analytics (fragility index, dependency rankings). TTL tuned per resource. Pubsub channel per simulation_run for live frames.
- **Async pipeline.** Long simulations and ML training go through Celery with priority queues; the API returns a `run_id` immediately and streams progress.
- **CDN at the edge.** Static assets and country-level static data behind a CDN.

Per-stage SLO targets:

| Operation | Target latency |
|---|---|
| Country / commodity read | p50 < 50ms, p99 < 200ms |
| Single-shock 52-week sim | p50 < 800ms, p99 < 2s |
| Multi-shock 104-week sim | async, return run_id < 100ms; result < 30s |
| Forecast ensemble call | p50 < 300ms |
| Live frame WS broadcast | < 100ms from frame computation |

---

## 13. Deployment Architecture

- **Dev** — Docker Compose. Single `docker-compose.yml` brings up Postgres+Timescale, Neo4j, Redis, API, simulation worker, ML worker, frontend, and a Prefect agent.
- **Staging / Prod** — Kubernetes (GKE / EKS / a managed flavor). Helm chart per service. HPA on CPU + custom queue-depth metric. ConfigMaps for non-secret config, sealed-secrets or external secrets operator for credentials.
- **Storage** — managed Postgres (Aurora / Cloud SQL) with Timescale where supported, managed Neo4j (AuraDB) or self-hosted on K8s, managed Redis, object storage for raw data and model artifacts.
- **CI/CD** — GitHub Actions: lint → test → build container → push to registry → deploy. Trunk-based with preview environments per PR.
- **Observability** — OpenTelemetry instrumentation across all services, Prometheus for metrics, Grafana dashboards, Loki for logs, traces in Tempo. One SLO dashboard per service.
- **Security** — TLS everywhere, JWT with short access tokens, OAuth provider for human auth, network policies isolating data plane, image scanning in CI, dependency scanning weekly.

Full detail in [`docs/scalability-deployment.md`](./docs/scalability-deployment.md).

---

## 14. MVP Roadmap (90 days)

Goal of MVP: end-to-end vertical slice — ingest one real dataset, run a real shock on a real graph, forecast with one real model, render a real propagation animation.

- **Weeks 1–2** — schema, graph projection, ingest UN Comtrade subset (top 30 countries × top 50 commodities). Set up CI, Docker Compose, observability skeleton.
- **Weeks 3–5** — simulation engine v1: weighted propagation + decay + simple resilience. Cypher-backed rerouting via Yen's k-shortest paths. Replay COVID-2020 commodity shock as a validation harness.
- **Weeks 6–7** — XGBoost forecasts for inflation and GDP delta, calibrated on historical events. SHAP attributions exposed via the API.
- **Weeks 8–10** — frontend Atlas + Simulation Theater. Globe with arc flows, scenario builder, animated propagation playback, forecast panel.
- **Weeks 11–12** — Policy Advisor v0 (rule-based, ML-augmented), fragility index, comparative scenarios. Polish. Internal demo.

Detail and exit criteria per milestone in [`docs/roadmap.md`](./docs/roadmap.md).

---

## 15. Advanced Future Roadmap

**Months 4–6**

- GNN-based propagation (replace analytic propagation with learned).
- TFT for multi-horizon commodity price forecasting.
- Full historical dataset (10+ years, 200+ countries, 5000+ HS commodities).
- Real-time AIS integration for live shipping flow.
- Multi-shock simultaneous scenarios.

**Months 7–12**

- RL-based adaptive rerouting policy, trained against the simulator.
- Counterfactual / "alternative world" simulations (what if Suez had a permanent bypass).
- AI policy advisor v2: generative natural-language explanations grounded in attributions.
- Firm-level layer (top 1000 multinationals as nodes).
- Public-facing demo with rate-limited API.

**Year 2+**

- Federated data partnerships (central banks, port authorities) for non-public flows.
- Climate-shock integration (heat, drought, sea-level) feeding the same simulator.
- Geopolitical-event-driven scenario generation from news (LLM extracts shock parameters from a news article).
- Real-time global fragility index published as a public dataset / API.

---

## Appendix: glossary

- **Chokepoint** — a constrained physical route (canal, strait) whose disruption affects a disproportionate share of global trade.
- **Cascade** — a sequence of failures or shortages where one node's disruption triggers another's.
- **Contagion** — the spread of a shock from origin to non-adjacent nodes via multi-hop transmission.
- **Fragility index** — a scalar summary of how exposed a node (or the system) is to plausible disruptions.
- **HHI** — Herfindahl-Hirschman Index, the standard measure of concentration (here: of import partners per commodity).
- **Resilience modifier** — a per-node factor that dampens incoming shock based on stockpiles, diversification, and economic capacity.
- **Replay** — re-running history with the current model and graph to validate predictions against known outcomes.
