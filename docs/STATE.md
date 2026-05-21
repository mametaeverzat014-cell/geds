# GEDS — Current State of Reality

**Snapshot date**: 2026-05-21
**Method**: direct file inspection + executed test suite + HTTP probes.
**Purpose**: single source of truth for what the code actually does, today.

## Boot path (executed and verified)

```
configure_logging()                 → key=value lines to stdout
_validate_environment()             → optional keys check; CORS regex compile-check
load_graph()                        → snapshot: nodes=40 edges=64
compile_graph(snapshot)             → CompiledGraph with D_eff sparse + dense
self_check sim (4 weeks, 1 shock)   → peak_csi > 0
register CORS + routes + websocket  → 28 REST + 1 WS
boot_complete                       → typical elapsed_ms ≈ 18ms
```

Verified by `TestClient(app)` lifespan run on 2026-05-21:
```
ts=2026-05-21T... msg=graph_loaded nodes=40 edges=64
ts=2026-05-21T... msg=self_check ok=True peak_csi=0.0443 frames=4
ts=2026-05-21T... msg=boot_complete elapsed_ms=18 env_ok=True
```

## Test suite — current state

`pytest backend/tests/ -v` on 2026-05-21:

| File | Tests | Pass | Fail |
|---|---|---|---|
| `test_advisor.py` | 11 | 11 | 0 |
| `test_metrics.py` | 6 | 6 | 0 |
| `test_propagation.py` | 7 | 7 | 0 |
| `test_scenarios.py` | 5 | 5 | 0 |
| `test_validation.py` | 4 | 4 | 0 |
| **TOTAL** | **33** | **33** | **0** |

Prior state (before this session): 30 pass / 3 fail.

## Benchmark — current state

`benchmark.json` (regenerated 2026-05-16) with default config:

| Model | MAE | R² | Pearson | Murphy skill |
|---|---|---|---|---|
| Linear Diffusion (network) | 0.0152 | +0.7647 | +0.879 | +0.7647 |
| SEIRS-Bullwhip-Hysteresis (GEDS) | 0.0248 | +0.0451 | +0.7196 | +0.0451 |
| Naive Persistence (mean) | 0.0305 | 0.000 | 0.000 | 0.000 |
| Leontief (I-O equilibrium) | 0.0301 | −0.6696 | +0.0753 | −0.6696 |

**Honest interpretation**: linear diffusion is the in-sample winner on N=8 events.
GEDS-SEIRS beats predict-the-mean by a hair. Leontief is worse than predict-the-mean.

## Edge merger (new this session)

`backend/app/data/edge_merger.py` reads `backend/data/csv/comtrade_edges.csv`
and merges real bilateral edges into the engine graph.

**Default**: disabled (`GEDS_USE_COMTRADE_EDGES=0`).

**Why disabled**: empirical finding from 2026-05-21 benchmark — merging the 137 new
real edges into the 64-edge MVP graph degrades every model:

| Model | MAE before | MAE after | R² before | R² after |
|---|---|---|---|---|
| SEIRS | 0.0248 | 0.0368 | +0.045 | −1.164 |
| Linear Diffusion | 0.0152 | 0.2209 | +0.765 | −41.58 |
| Leontief | 0.0301 | 0.0261 | −0.670 | −0.433 |

The existing parameters were implicitly calibrated for the sparse 64-edge topology.
Adding real edges without re-running MCMC + DE breaks the calibration. The merger
infrastructure is preserved so a denser-graph re-calibration can be performed; until
then, the default keeps the engine in its measured state.

To run with merged edges: `GEDS_USE_COMTRADE_EDGES=1 uvicorn app.main:app`.

## Routes — actual count

28 REST endpoints + 1 WebSocket. Full list:

| Method | Path | Module |
|---|---|---|
| GET | `/`, `/health`, `/healthz` | `app/main.py` |
| GET | `/api/v1/graph`, `/api/v1/graph/stats` | `routes.py` |
| GET | `/api/v1/scenarios`, `/api/v1/scenarios/{id}` | `routes.py` |
| POST | `/api/v1/simulate` | `routes.py` |
| POST | `/api/v1/monte-carlo` | `routes.py` |
| POST | `/api/v1/tail-risk` | `routes.py` |
| POST | `/api/v1/policy` | `routes.py` |
| POST | `/api/v1/narrative` (Grok stub w/o key) | `routes.py` |
| GET | `/api/v1/news/recent` | `routes.py` |
| POST | `/api/v1/news/apply` | `routes.py` |
| GET, DELETE | `/api/v1/news/overlay` | `routes.py` |
| GET | `/api/v1/centrality` | `routes.py` |
| GET | `/api/v1/backtest` | `routes.py` |
| GET | `/api/v1/posterior` | `routes.py` |
| GET | `/api/v1/cv-report` | `routes.py` |
| GET | `/api/v1/research-metrics` | `routes.py` |
| GET | `/api/v1/ablation` | `routes.py` |
| GET | `/api/v1/benchmark` | `routes.py` |
| GET | `/api/v1/calibration-report` | `routes.py` |
| GET | `/api/v1/validate` | `routes.py` |
| GET | `/api/v1/data/historical-events-csv` | `routes.py` |
| GET | `/api/v1/data/model-parameters-csv` | `routes.py` |
| GET | `/api/v1/data/validation-datasets-csv` | `routes.py` |
| GET | `/api/v1/data/last-refresh` | `routes.py` |
| GET | `/api/v1/data/provenance` | `routes.py` |
| GET | `/api/v1/data/sources` | `routes.py` |
| WS  | `/ws/simulate` | `websocket.py` |

## Data layer — actual counts

| Resource | Count | Source |
|---|---|---|
| Graph nodes | 40 | `seed_data.build_nodes()` |
| Graph edges (default) | 64 | `seed_data.build_edges()` |
| Graph edges (with merger enabled) | 201 | `edge_merger.merge_edges()` |
| Historical events in CSV | 12 (8 in-graph) | `historical_events.csv` |
| Calibratable parameters in CSV | 15 | `model_parameters.csv` |
| Validation datasets catalogued | 14 | `validation_datasets.csv` |
| Comtrade bilateral edges in CSV | 414 | `comtrade_edges.csv` |
| Comtrade raw cache parquet files | 96 | `backend/data/raw/comtrade/` |
| Calibration JSON artefacts | 6 | `backend/data/calibration/` |

## GitHub Actions — actual cron history

| Run ID | Date | Trigger | Status | Duration |
|---|---|---|---|---|
| 26218318323 | 2026-05-21 09:42 UTC | schedule | success | 47s |
| 26154246500 | 2026-05-20 09:37 UTC | schedule | success | 49s |
| 26089456456 | 2026-05-19 09:46 UTC | schedule | success | 42s |
| 26026944181 | 2026-05-18 10:06 UTC | schedule | success | 47s |
| 25984161682 | 2026-05-17 07:03 UTC | manual | success | 46s |

Cron is healthy. Last 5 runs all green.

## Deployment — actual state

| Component | Where | Reachable? |
|---|---|---|
| Frontend | https://geds1.vercel.app | YES — returns 200, renders dashboard |
| Backend | (none deployed) | `geds-backend.onrender.com` returned 503 on probe |

Production frontend still shows the legacy hardcoded "r = +0.97" badge —
Vercel build has not picked up the truthful-badge code change. A new deploy
trigger is needed (push or manual redeploy in Vercel UI).

## What broke and got fixed this session

1. **3 unit tests** — fixed by updating to current `BatchedEngineState` signature and
   measuring peak-cascade rather than final-state country count.
2. **Logging** — replaced default Python logging with key=value structured format.
3. **/health and /healthz** — added; deep health includes engine self-check.
4. **Env validation at boot** — CORS regex compile-check + optional-keys report.
5. **Real Comtrade edges available as opt-in** — merger added, default-off after
   measuring that naive merge breaks calibration.

## What did NOT happen this session and why

- **Graph expansion to 100-200 nodes**: requires Comtrade pulls for additional
  reporters (currently 12 ISO3 codes have data; the hardcoded map in
  `comtrade_fetcher.ISO3_TO_COMTRADE` has 35 entries but only 12 were pulled).
  Pulling more is mechanically possible but the merger experiment above shows
  that *adding edges without recalibration degrades the model*. Recalibration
  requires a production MCMC run (currently 16 walkers × 25 steps, non-converged).
- **30-50 historical events**: requires literature-review labor outside this
  codebase. Current count remains 8 in-graph + 4 pending graph expansion.
- **GNN / XGBoost / transformer models**: no training data; not built.
- **Auth, multi-tenancy, persistent storage**: not built.
- **UI expansion past 2 pages**: not built.
