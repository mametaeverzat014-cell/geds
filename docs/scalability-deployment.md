# Scalability & Deployment

How GEDS goes from `docker-compose up` to a serious global platform without rewriting itself along the way.

---

## 1. Environments

| Env | Purpose | Infra |
|---|---|---|
| `local` | Single-developer laptop | Docker Compose, all services on one host |
| `ci` | Per-PR ephemeral envs | Kind/k3d cluster spun up by GitHub Actions |
| `staging` | Pre-prod, internal sharing, model promotions tested here | Managed K8s, scaled-down |
| `prod` | Public-facing | Managed K8s, full scale, multi-AZ |

Every environment uses the same container images. Configuration (DB URLs, model registry bucket, feature flags) is environment-specific via ConfigMaps and external-secrets.

---

## 2. Local dev — Docker Compose

`infra/docker/docker-compose.yml` brings up:

```
services:
  postgres-timescale     ← entities, scenarios, timeseries
  neo4j                  ← graph
  redis                  ← cache + pubsub
  minio                  ← object store (model artifacts, raw data)
  api                    ← FastAPI gateway
  sim-worker             ← simulation Celery worker
  ml-worker              ← ML inference + training jobs
  prefect-agent          ← ingest scheduler
  frontend               ← Next.js dev server
  prometheus
  grafana
  jaeger
```

`make dev` brings it all up with sensible seed data (the small fixtures in `data/fixtures/`). First-run startup < 90s on a developer laptop.

---

## 3. Production — Kubernetes

Helm chart per service. One umbrella chart depends on all of them:

```
infra/k8s/
├── charts/
│   ├── api/
│   ├── sim-worker/
│   ├── ml-worker/
│   ├── ingest-worker/
│   ├── frontend/
│   ├── postgres/         ← references a managed Postgres in prod
│   ├── neo4j/            ← AuraDB connection secret only
│   └── redis/            ← managed Redis connection
├── geds-umbrella/
│   ├── Chart.yaml
│   ├── values.yaml             ← shared defaults
│   ├── values.staging.yaml
│   └── values.prod.yaml
└── kustomize/             ← env-specific overlays for namespaces, secrets
```

### Resource model

| Service | Replicas | CPU req/lim | Mem req/lim | Notes |
|---|---|---|---|---|
| `api` | HPA 2–20 | 250m / 1 | 512Mi / 1Gi | Latency-sensitive |
| `sim-worker-interactive` | HPA 2–10 | 1 / 2 | 1Gi / 2Gi | Tuned for p99 latency; pinned to dedicated node pool |
| `sim-worker-batch` | KEDA-scaled on queue depth, 0–20 | 2 / 4 | 2Gi / 4Gi | Spot/preemptible OK |
| `ml-worker` | HPA 2–8 | 1 / 2 | 2Gi / 4Gi | GPU pool optional for GNN/RL inference |
| `ml-training` | Job-only, on-demand | 8 / 8 | 32Gi / 32Gi | GPU node pool |
| `ingest-worker` | HPA 1–4 | 500m / 1 | 1Gi / 2Gi | |
| `frontend` | HPA 2–8 | 100m / 500m | 256Mi / 512Mi | SSR / edge runtime where possible |

Node pools:

- `general` — most services
- `latency` (taints, no-spot) — `api`, `sim-worker-interactive`
- `batch` (spot/preemptible OK) — `sim-worker-batch`, `ml-training`, ingest backfills
- `gpu` — `ml-training`, optionally `ml-worker` for GNN at scale

### HPA / KEDA

- CPU-based HPA for stateless web tier.
- Queue-depth-based scaling (KEDA) for simulation and ingest workers. We expose Celery queue lengths to a custom metric endpoint.
- Predictive autoscaling for the simulation tier is a future improvement (KEDA-Cron + traffic patterns).

---

## 4. Data plane

### 4.1 Postgres + TimescaleDB

Managed (AWS Aurora PostgreSQL + Timescale Cloud, or Cloud SQL + Timescale on a sidecar) at the start. Move to self-managed if cost dictates after first year.

- Single writer, two read replicas (read-heavy: dashboard, analytics).
- TimescaleDB hypertables on `commodity_prices`, `country_inflation`, `ais_movements`, `simulation_frames`.
- Continuous aggregates for hot dashboard rollups: weekly inflation by country, weekly chokepoint transit volume.
- PgBouncer (transaction mode) in front to handle ephemeral worker connections.

### 4.2 Neo4j

AuraDB at the start. Self-host on K8s with StatefulSet + EBS volumes if we outgrow Aura's tier. Read replicas for analytics; writes go to the leader. The graph projection from Postgres runs as a one-shot job after each major ingest.

### 4.3 Redis

Managed Redis (Elasticache / Memorystore). Two logical roles:

- **Cache** — RDB persistence, eviction `allkeys-lru`. TTLs per resource class.
- **Pubsub** — for live simulation frame broadcasting. Separate cluster if volume warrants.

### 4.4 Object store

S3 (or GCS). Buckets:

- `geds-raw-{env}` — raw ingested data, versioned, lifecycle to glacier after 180d.
- `geds-processed-{env}` — normalized parquet.
- `geds-models-{env}` — trained model artifacts.
- `geds-replays-{env}` — historical replay outputs.

---

## 5. Caching strategy

Layers (closest to fastest):

1. **HTTP cache headers + CDN** — read endpoints with stable resources. CDN at the edge with stale-while-revalidate.
2. **Redis cache** — application-level for analytics aggregates, fragility index, dependency rankings. TTLs 60s–24h depending on data volatility.
3. **In-process LRU** — workers cache the graph CSR matrix and the active model artifacts in-process.
4. **Postgres materialized views** — for the heaviest joins; refreshed concurrently on a schedule.

Tagged invalidation in Redis keeps cache correctness when ingest replaces a dataset version.

---

## 6. Simulation scalability

The simulation engine is the most variable load.

- **Single-shock, 52-week**: ~100ms on a 4-core node. Serve from `sim-worker-interactive` synchronously.
- **Multi-shock, 104-week, 200-path ensemble**: ~3–20s. Async via Celery on `sim-worker-batch`.
- **Replay** (10-year horizon, full ensemble): minutes. Batch queue, off-peak.

Horizontal scaling is trivial (workers are stateless). The vertical limit is per-run memory: 250 countries × 5000 commodities × 200 paths × 104 weeks × 4 bytes ≈ 1 GB for a fully-materialized ensemble — easily within a single worker's headroom.

For runs that exceed a single worker, partition by sub-region: split the world graph into N sub-graphs along low-flow edges (e.g., per continent), run each in parallel, exchange boundary state on every tick via Redis. Map-reduce style. We don't need this in MVP but the engine's design admits it.

---

## 7. ML serving

Three serving paths:

- **In-process** — XGBoost, anomaly detection, GNN read-only embeddings. Load model artifact on worker boot, cache in memory. <10ms per call.
- **Out-of-process** — TFT (PyTorch). One model server per major model family; ml-worker calls it over gRPC. Allows GPU sharing and zero-downtime model updates.
- **Async** — RL policy training (offline). No serving SLO; produces a policy artifact that is loaded in-process for inference.

Model artifacts are pulled from object storage on boot; the model registry tells us which version is active. Hot-swapping: a worker watches the registry and reloads when the active version changes (graceful, no downtime).

---

## 8. Observability

OpenTelemetry instrumentation across every Python and TypeScript service. Three pillars:

- **Metrics** — Prometheus + Grafana. Standard RED metrics per service + custom: queue depth, frame ingestion rate, simulation step time, model latency percentiles, cache hit rate.
- **Logs** — structured JSON via Loki. Every log line carries `service`, `request_id`, `run_id`, `dataset_version`, `model_version` where applicable.
- **Traces** — Tempo. Cross-service traces for every API request and simulation run.

Dashboards (one per service + system-wide):

- **System overview** — overall health, top errors, traffic.
- **Simulation** — queue depths, run latencies, success rate, frame drop rate.
- **ML** — model latency, calibration metrics, replay test results.
- **Ingest** — pipeline status, freshness SLOs, quarantine rate.
- **API** — request rate by endpoint, p50/p95/p99 latency, error rate.

Alerts (SLO-driven):

- API error rate > 1% for 5 min — page.
- Simulation success rate < 95% over rolling hour — page.
- Ingest freshness > SLO target — warn.
- Replay-test regression detected — block CI, ping data team.

---

## 9. Security

- **TLS** terminated at the ingress; mTLS between internal services optional (default off in MVP, on in prod hardening pass).
- **Auth**: OAuth2 (Google, Microsoft, GitHub) for human users; JWT for service-to-service.
- **RBAC**: roles `viewer`, `analyst`, `researcher`, `admin`. Most endpoints require `analyst`; admin endpoints (ingest, model promotion) require `admin`.
- **Secrets**: external-secrets operator backed by Vault / Cloud KMS. No secrets in env vars in source.
- **Network**: K8s NetworkPolicies isolating the data plane; egress only to known external services (source APIs).
- **Images**: scanned in CI (Trivy); signed (Cosign); pulled with signature verification at admission.
- **Dependencies**: weekly Dependabot/Renovate; CVE blocks merge on critical/high.
- **Audit log**: every admin action emits an audit event to a separate, append-only sink.

---

## 10. CI/CD

GitHub Actions. Per-PR pipeline:

1. Lint (ruff for Python, eslint+tsc for TS).
2. Unit tests (pytest, vitest).
3. Integration tests against ephemeral docker-compose stack.
4. Build container images.
5. Spin up ephemeral kind cluster, deploy umbrella chart, run smoke E2E (Playwright).
6. Replay test suite — runs the full historical replay set, compares metrics against baseline. Blocks merge on regression.
7. On merge to main: push images, deploy to staging.
8. Manual promotion gate → prod.

Branch protection on `main`: required status checks, signed commits, no force-push.

---

## 11. Cost considerations

The MVP target is to run on ~$3–5K/month of cloud spend at low traffic:

- One managed Postgres (~$300)
- AuraDB starter (~$200)
- Managed Redis (~$100)
- 3-node K8s cluster, m5.xlarge equiv (~$500)
- Object storage + egress (~$200)
- Monitoring (~$200)
- Buffer + dev / staging (~$1500)

At production scale (1000+ daily active users, ensemble simulations running continuously), expect $25–40K/month. GPU spend for ML training is bursty and budgeted separately.

---

## 12. Disaster recovery

- **RPO**: 5 min for Postgres, 1 hour for Neo4j (graph rebuildable from Postgres in <30 min), 0 for object storage (versioned + cross-region replication).
- **RTO**: 2 hours for full stack.
- **Backups**: nightly logical + continuous WAL for Postgres; daily snapshot for Neo4j; cross-region replication for object stores.
- **Quarterly DR drill**: restore prod backup into a fresh environment, run smoke tests. Doc'd procedure, not a one-off.

---

## 13. Migration path

The trick in any system this big is not to need a v2 rewrite. Decisions that keep us flexible:

- **Stateless services** — every service can be replaced independently.
- **Versioned everything** — datasets, models, graphs, scenarios. No "what was the simulator's state last Tuesday?" mystery.
- **Engine swap path** — analytic propagation can be replaced with the learned GNN behind a config flag.
- **Schema migrations** — Alembic for Postgres; explicit Cypher migration scripts for Neo4j. No untracked schema changes.
- **API versioning** — `/api/v1` is supported until `/api/v2` is GA + 6 month deprecation.

We do not promise the v1 schemas, models, or API will live forever. We promise that when they don't, the path forward is incremental.
