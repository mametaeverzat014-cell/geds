# Data Ingestion

The platform is only as good as the data it stands on. Ingest is treated as a first-class system, not as a one-time setup script.

Design principles:

1. **Idempotent, versioned, atomic.** Every dataset version is immutable. A load writes to a new version then flips a pointer.
2. **One pipeline per source.** Each external source has its own `Connector` with `extract → validate → normalize → load` stages. Shared utilities, not shared pipelines.
3. **Schema-on-load.** Raw is preserved verbatim; normalization happens in a separate stage. We never lose source fidelity.
4. **Replay-ready.** All historical loads are kept; we can rewind the platform to any past dataset state for reproducible training and replay tests.

---

## 1. Sources

| Source | Format | Frequency | Critical | Tier |
|---|---|---|---|---|
| **UN Comtrade** — bilateral trade flows, HS6 | REST / bulk parquet | annual + monthly | yes | A |
| **WTO** — tariffs, trade in value-added, services trade | CSV via portal | annual | yes | A |
| **OECD** — input-output tables, indicators | API + CSV | annual | yes | A |
| **IMF (WEO, IFS, BoP, CPI)** — macro indicators | API / SDMX | monthly–quarterly | yes | A |
| **World Bank (WDI, Pink Sheet, Crisis DB)** — indicators, commodity prices, crisis events | API / parquet | various | yes | A |
| **AIS shipping data** — vessel positions, port calls, chokepoint transits | streaming feed | real-time | yes | B |
| **FRED / OECD MEI** — fast macro indicators | API | weekly–monthly | yes | B |
| **SIA / SEMI** — semiconductor production, shipments, capacity | CSV / pdf scrape | quarterly | yes | B |
| **Commodity-specific** — OPEC oil, IEA energy, FAO food | API / CSV | monthly | yes | B |
| **Curated historical events** — crisis database we maintain | YAML in repo | manual | yes | A |
| **News / event feeds** (future) — for LLM-driven scenario seeding | RSS / API | real-time | no | C |

Tier A is required for MVP. Tier B activates in months 4–6. Tier C is future work.

---

## 2. Connector contract

Every connector implements the same interface:

```python
# backend/app/workers/ingest/base.py
class Connector(Protocol):
    name: str
    schedule: Schedule

    def extract(self, ctx: IngestContext) -> RawBundle: ...
    def validate(self, raw: RawBundle, ctx: IngestContext) -> ValidationReport: ...
    def normalize(self, raw: RawBundle, ctx: IngestContext) -> NormalizedBundle: ...
    def load(self, normalized: NormalizedBundle, ctx: IngestContext) -> LoadReport: ...
```

Pipeline orchestration is Prefect (chosen over Airflow for dynamic flows and a lighter footprint at our scale). Each connector lives in `backend/app/workers/ingest/<source>/` with:

```
backend/app/workers/ingest/comtrade/
├── connector.py       # implements Connector
├── schema.py          # Pydantic models for raw + normalized
├── tests/
└── fixtures/          # small golden samples for tests
```

---

## 3. Dataset versioning

Every load produces a new `dataset_version` row:

```
'2026-05-01-comtrade-v3'
 │           │         │
 │           │         └── major version (changes when schema changes)
 │           └── source name
 └── snapshot date
```

Postgres `dataset_versions` table tracks all versions; `is_active=true` on at most one per source. Promotion is atomic:

```sql
BEGIN;
UPDATE dataset_versions SET is_active = false WHERE source = 'comtrade';
UPDATE dataset_versions SET is_active = true  WHERE version = '2026-05-01-comtrade-v3';
COMMIT;
```

All entity tables (`trade_flows`, `dependencies`, etc.) carry `dataset_version` as a column. Reads filter by the active version unless explicitly asked for a historical one. This makes replay trivial: pin a version, run the simulator, get the past's view of the future.

---

## 4. Validation

Every extracted bundle goes through two validation layers:

### 4.1 Schema validation (Pydantic)

Every raw row is parsed into a Pydantic model. Anything failing parse goes to a quarantine table with the parse error. We never silently drop.

### 4.2 Statistical validation (Great Expectations or custom)

Per-source rules:

- **Comtrade**: total world export ≈ total world import per HS code (allow ±5% mismatch — known data artifact).
- **WDI**: country-year inflation values within plausible bounds (-50% to +5000%; outliers flagged for review).
- **AIS**: vessel counts at each chokepoint within historical p1/p99 range; trigger review if outside.
- **OECD I-O**: row sums equal column sums (within rounding).
- **All sources**: monotonic time coverage (no gaps, no time travel).

Failures don't abort the pipeline; they produce a `ValidationReport` with severity (`info`, `warn`, `block`). Only `block` aborts. Everything else proceeds with the report stored alongside the load.

---

## 5. Normalization

Hard part. Different sources speak different dialects:

- **Country codes**: ISO3 is our canonical. Connectors map source codes (Comtrade's M49, WTO's 3-letter, World Bank's WB-3) via a lookup table. Unknown codes are quarantined.
- **Commodity codes**: HS6 canonical (HS-2017 revision). Comtrade is native; WTO sometimes uses HS4 — we expand by population-weighted rules from OECD's HS-bridge tables (and flag the expansion).
- **Sector codes**: ISIC rev. 4 canonical. Source-specific sector mappings live in `data/fixtures/sector-mapping.csv`.
- **Currency**: USD canonical at constant 2020 prices. CPI-deflate at load using IMF WEO deflators.
- **Time**: UTC, ISO-8601, end-of-period for monthly/quarterly/annual.
- **Geography**: when boundaries change (post-2022 Russia/Ukraine territorial), we follow ISO and UN gazetteer; historical data is preserved with its contemporary mapping.

Normalization is *not* in the connector. Connectors output a "normalized bundle" using these conventions; a shared `Normalizer` enforces them. This keeps source connectors thin.

---

## 6. Load

Load is into Postgres first (entities + relationships), then projected to Neo4j (graph), then warm caches in Redis are invalidated. Order matters: Postgres is the source of truth; Neo4j is a derived view.

### 6.1 Postgres load

- Bulk `COPY` into staging tables.
- `INSERT ... ON CONFLICT ... DO UPDATE` from staging into target, scoped by `dataset_version`.
- Affected rows: dataset_version flip is the actual cutover.

### 6.2 Neo4j projection

After the Postgres flip, run a deterministic Cypher projection (see `graph-model.cypher`) that rebuilds all `EXPORTS`, `DEPENDS_ON`, `ROUTES_THROUGH` edges from current Postgres state. The projection uses `MERGE` with the new dataset_version so it can run live; old edges with the previous dataset_version are deleted in a follow-up step once the active version flip is confirmed.

### 6.3 Cache invalidation

Tagged invalidation: every Redis cache key carries tags (e.g., `tag:country:DEU`, `tag:dataset:active`). Post-load, the loader emits an invalidation for the changed tags. Hot reads warm again on first request.

### 6.4 Downstream rebuilds

- **Materialized views** in Postgres (`mv_country_fragility`, etc.) — concurrent refresh.
- **GNN feature store** — recompute features that depend on changed dependency / trade data.
- **Replay-test trigger** — schedule a CI run to verify replay metrics still pass against the new dataset (catches regressions in the simulator's calibration relative to new historical data).

---

## 7. Real-time AIS

The only source that's not batch. Architecture:

```
AIS stream → Kafka → AIS normalizer (worker) → TimescaleDB ais_movements
                                            ↘ Redis pubsub (live chokepoint indicator)
                                            ↘ Anomaly detector (LSTM autoencoder)
```

The anomaly detector ingests rolling 4-week windows and emits scores that the API exposes on the Atlas page. Backpressure: if Kafka lag exceeds threshold, the AIS normalizer drops low-priority vessel classes (yachts, military) and prioritizes commercial cargo.

---

## 8. Replay

The killer feature for credibility.

A "replay" is: pin a dataset version to the state it was in at date X, run the simulator against the same graph that existed then, with the models that were live then, and see how the platform's predictions compare to what actually happened.

```python
# backend/app/services/replay.py
def replay(event_slug: str, freeze_date: date) -> ReplayResult:
    version = dataset_version_repo.active_at(freeze_date)
    graph_snapshot = neo4j_repo.snapshot_at(freeze_date)
    models = model_registry_repo.active_at(freeze_date)
    scenario = scenario_repo.from_historical_event(event_slug)
    return simulate(scenario, EngineContext(version, graph_snapshot, models))
```

Replay metrics (per replay, against ground truth):

- MAPE on inflation by country
- Mean absolute error on GDP delta
- Brier score on shortage occurrence
- Recovery time error

These metrics are tracked over time; if a new dataset or model release worsens them, CI blocks promotion until a human reviews.

---

## 9. Operations

- **Scheduling**: Prefect deployment per connector, schedule in source code, runtime overrides via UI.
- **Retries**: exponential backoff with jitter, max 5 attempts. After max, page on-call (or open a ticket in the off-hours queue).
- **Backfill**: every connector supports a `backfill(from_date, to_date)` mode that loads historical chunks idempotently.
- **Cost control**: rate-limit external API hits; cache responses at the connector layer with TTLs aligned to source update frequency.
- **Data dictionary**: every column in every normalized table has an entry in `docs/data-dictionary.md` (auto-generated from Pydantic models + comments). Future doc; placeholder lives in this repo.
- **Lineage**: each row carries `source`, `dataset_version`, and `ingested_at`. Lineage queries are first-class.

---

## 10. Quality SLOs

| SLO | Target |
|---|---|
| Comtrade monthly load freshness | within 7 days of source publication |
| AIS lag (event → DB) | < 60s, p95 |
| Replay metrics regression | none of the historical events worsen beyond tolerance after a load |
| Quarantine rate | < 1% of incoming rows |
| Schema mismatch (block-severity) | 0 in production; one is an incident |

These are on a Grafana dashboard; the data team's standup starts with it.

---

## 11. Privacy and licensing

- All Tier A sources are public or available under research-friendly licenses; we keep a `LICENSES.md` summary for each.
- AIS data is treated as commercial-public; we redact vessel-owner metadata not needed for aggregated chokepoint metrics.
- No PII, ever.
- Outbound rate limits respect source ToS; we expose attribution in the UI.

---

## 12. What we explicitly defer

- **Firm-level trade flows** (top-1000 multinationals) — needs commercial data; Year 2.
- **Carbon and climate datasets** — separate ingest project; Year 2.
- **News / event feeds for LLM scenario seeding** — Tier C; experimental, not in MVP critical path.
- **Real-time inflation nowcasting** — needs a dedicated forecaster; out of scope until Tier B is stable.
