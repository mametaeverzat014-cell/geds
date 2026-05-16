# Roadmap

Honest dates require honest scope. This roadmap is calibrated for a small team (2–4 engineers + a researcher) building hard. Larger teams can compress.

Today's date for sequencing: **2026-05-12**.

---

## Phase 0 — Foundations (Weeks 1–2 · 2026-05-12 → 2026-05-26)

Goal: the platform can be checked out, started, and built upon.

| | Deliverable | Owner |
|---|---|---|
| ☐ | Docker Compose stack boots end-to-end (Postgres, Neo4j, Redis, MinIO, API stub, frontend stub) | Backend |
| ☐ | CI: lint + unit + integration green on main | Platform |
| ☐ | Postgres + Neo4j schemas applied from migrations | Backend |
| ☐ | Seed data fixtures (30 countries × 50 commodities, 1 historical event: Suez 2021) | Data |
| ☐ | Observability skeleton: Prometheus + Grafana + log aggregation, one dashboard | Platform |

**Exit criteria**: a fresh clone → `make dev` → working stack with a hello-world request flowing through API → Postgres → Neo4j round trip.

---

## Phase 1 — Vertical Slice MVP (Weeks 3–12 · 2026-05-26 → 2026-08-04)

Goal: one real shock, one real graph, one real model, one real animation. End-to-end.

### Sprint 1 (Weeks 3–4) — Ingest pipeline + graph projection

| | Deliverable |
|---|---|
| ☐ | Comtrade connector: extract → validate → normalize → load (last 5 years, top 30 countries × top 50 HS6) |
| ☐ | Postgres → Neo4j projection job (`EXPORTS`, `DEPENDS_ON`, `ROUTES_THROUGH`) |
| ☐ | Dataset version flip mechanism with replay verification |
| ☐ | Materialized view `mv_country_fragility` refreshing on schedule |

### Sprint 2 (Weeks 5–7) — Simulation engine v1

| | Deliverable |
|---|---|
| ☐ | `propagate()` primitive: NumPy sparse matmul implementation of math doc §2 |
| ☐ | `apply_shocks()` + scenario JSON schema |
| ☐ | `amplification()` primitive |
| ☐ | Proportional rerouting (baseline) |
| ☐ | Synchronous `simulate()` API endpoint (single shock, 52 weeks, ensemble_size=1) |
| ☐ | Replay test for Suez 2021: peak inflation deviation matches reality within ±20% |

### Sprint 3 (Weeks 8–9) — Forecasting baseline + policy advisor v0

| | Deliverable |
|---|---|
| ☐ | XGBoost inflation forecasters (4w, 12w) trained on historical + simulator-generated data |
| ☐ | XGBoost GDP delta forecaster (12w) |
| ☐ | SHAP attributions exposed via API |
| ☐ | Rule-based policy advisor v0: diversification, stockpile, reroute suggestions |
| ☐ | Forecast endpoints (`POST /api/v1/forecasts`) |

### Sprint 4 (Weeks 10–11) — Frontend Atlas + Simulation Theater

| | Deliverable |
|---|---|
| ☐ | Next.js app shell, design tokens, theme provider |
| ☐ | Atlas page with globe, trade flow arcs, chokepoint markers, fragility index ribbon |
| ☐ | Scenario builder (templates + custom shocks) |
| ☐ | Simulation Theater with WebSocket frame streaming, timeline scrub, top-k panels |
| ☐ | Forecast dashboard quadrants (inflation, GDP, shortage, unemployment) |

### Sprint 5 (Week 12) — Polish + internal demo

| | Deliverable |
|---|---|
| ☐ | Performance pass: globe at 60fps on a mid-tier laptop, scenario TTI < 1.5s |
| ☐ | Accessibility pass: WCAG AA, keyboard shortcuts, screen-reader live regions |
| ☐ | Replay test suite passing for: Suez 2021, COVID 2020 commodity shock, 2014 oil shock |
| ☐ | Internal demo + feedback collection |

**Exit criteria for MVP**:

1. A user can create a scenario, run it, watch the propagation animation, see forecasts with intervals, get policy recommendations, and run a counterfactual — all in under 5 minutes from cold start.
2. Three historical events replay within tolerance.
3. End-to-end latency from "click Run" to "first WS frame" < 1 second.

---

## Phase 2 — Model maturity (Months 4–6 · 2026-08-04 → 2026-11-04)

Goal: the platform's predictions become trustworthy enough to share externally.

### Highlights

- **GNN family**: GraphSAGE+GAT vulnerability head, FastRP pre-training, GNNExplainer attributions.
- **TFT**: multi-horizon commodity price forecasts; integrated into the inflation pipeline.
- **K-shortest path rerouting** (Yen's) replaces proportional baseline.
- **Full historical ingest**: 200+ countries × 5000+ HS6 commodities × 10+ years.
- **AIS integration**: live chokepoint indicators on the Atlas page.
- **Multi-shock scenarios**: simultaneous compound disruptions (Suez + Hormuz, climate + geopolitics).
- **Comparative Lab**: side-by-side scenarios, up to 4 overlays.
- **Replay test suite expanded** to 10+ historical events; CI gates promotions on it.
- **Public-facing demo** (rate-limited): an unauthenticated landing where visitors can run pre-baked scenarios.

### Critical milestones

| Date | Milestone |
|---|---|
| 2026-08-25 | GNN vulnerability head live, replacing the hand-tuned `R_i` formula |
| 2026-09-15 | TFT commodity price forecasts integrated into inflation pipeline |
| 2026-10-06 | Full historical ingest complete; replay test suite passing on 10 events |
| 2026-10-27 | Public demo deployed; comparative lab feature-complete |

---

## Phase 3 — Adaptive intelligence (Months 7–12 · 2026-11-04 → 2027-05-04)

Goal: the platform learns and recommends, not just simulates and reports.

- **RL rerouting policy** (PPO) trained against the simulator; A/B vs. k-shortest baseline.
- **AI policy advisor v2**: LLM-generated natural-language explanations grounded in SHAP/GNN attributions. Strictly grounded — no hallucination paths.
- **Firm-level layer** (top-1000 multinationals as nodes) for select sectors (semiconductors, automotive, pharma).
- **Counterfactual "alternative world" simulations**: what if Suez had a permanent bypass? What if Taiwan had 3x semiconductor capacity? — first-class feature.
- **Climate-shock integration**: heat, drought, sea-level rise as shock inputs (initial connector to a climate dataset).
- **Federated data partnerships**: pilot conversation with one central bank or port authority for non-public flow data.
- **GNN propagation kernel** replaces the analytic `propagate()` in shadow mode; A/B over 4 weeks before flipping default.

---

## Year 2 — Platform (2027-05 onward)

- **Real-time global fragility index** published as a public API.
- **Geopolitical-event-driven scenario generation**: LLM extracts shock parameters from a news article and proposes a scenario.
- **Multi-tenant**: research institutions, central banks, supply-chain operators each get isolated workspaces.
- **SLA-backed enterprise tier**.
- **Open-source the simulation core** (with the proprietary data layer and trained models kept private).
- **Annual "State of Global Fragility" research report**, generated from a year of platform data.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Data sources change schemas or licensing | Versioned connectors, abstraction layer, alternative sources identified for each Tier-A source |
| Replay tests catch a real bug after a model promotion | Replay tests are CI-blocking; rollback is one row update |
| Simulation engine performance regresses with bigger graphs | Profiling baseline established in Phase 1; weekly perf budget reviews |
| AI policy recommendations are wrong in a way that misleads policymakers | Every recommendation surfaces uncertainty + caveats; advisor never speaks in absolutes; legal review before any external rec is exposed |
| Calibration coefficients drift as the world structurally changes | Continuous recalibration on every dataset version; alert if coefficients move > 2σ |
| The team gets distracted building "AI features" instead of the boring data pipeline | This roadmap. The data pipeline is critical-path through Phase 1. Features that don't pass replay tests don't ship. |

---

## Definition of Done — per shipped feature

A feature is done when:

1. Code is merged with tests.
2. Telemetry is in place (metric or trace).
3. Docs are updated (architecture doc + any user-facing changelog).
4. Replay tests still pass.
5. Accessibility check passes for any UI changes.
6. Performance budget held for any changes to the hot path.
7. A real user has tried it (internal user counts for early phases).

Anything short of all seven is "shipped but on probation" and tracked in a follow-up.
