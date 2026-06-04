# GEDS — Current State of Reality

**Snapshot date**: 2026-05-25
**Method**: aggregated from master registries + Phase 1–5 artefacts.
**Purpose**: single source of truth for what the engine and data layer actually contain.

## Headline numbers

- **Historical events catalogued:** 42
  - With observed GDP impact value: 40 (95.2%)
  - With v2 institutional ground-truth attached: 8
  - With peer-reviewed paper corroboration: 1
  - Mapping to ≥1 node in the *default* engine graph (40 nodes): 11
  - Scenario / forward-looking: 1
- **Datasets catalogued:** 53 (HIGH/MEDIUM/LOW counts in `MASTER_STATE.md`)
- **Benchmark models catalogued:** 10 (in `master_model_registry.csv`)
- **Literature entries:** 61 (25 deeply-cataloged + 36 title-only)
- **Event evidence rows mined:** 319 across 41 events
  - Peer-reviewed paper-derived rows: 10 events

## Graph

**Default engine graph:**
- Nodes: 40 (36 country×industry + 4 chokepoints)
- Edges (default): 64 hardcoded MVP
- Edges (Comtrade-merged, opt-in via `GEDS_USE_COMTRADE_EDGES=1`): 201

**Expanded graph (Phase 1 — opt-in, not yet wired into `seed.py`):**
- Nodes: 110 (102 country×industry + 8 chokepoints)
- Edges: 234
- Country coverage: 34 ISO3 (G20 + key trade hubs)
- See `docs/GRAPH_EXPANSION.md` for the integration roadmap.

## Validation

- `validation_targets_v2.csv` — 178 institutional ground-truth rows across 8 events (✅/⚠️ flagged)
- `validation_targets_expanded.csv` — 94 rows across 42 events (literature + aggregates)
- `event_evidence.csv` — 319 rows (Phase 2) cross-linking papers + v2 + aggregates per event
- `benchmark_inputs.csv` — 42 event-level aggregates

## Benchmark (Phase 3 result)

- **Benchmark v2** (`benchmark_v2.json`):
  - N benchmarked: **11** / 42 (engine sector/graph limits)
  - Winner by MAE: `Linear Diffusion (network)`
  - Winner by R²: `Naive Persistence (mean)`

  Per-model scores:

  | Model | MAE | R² | Pearson | Skill |
  |---|---|---|---|---|
  | SEIRS-Bullwhip-Hysteresis (GEDS) | 0.1607 | -0.310 | 0.784 | -0.310 |
  | Leontief (input-output equilibrium) | 0.1609 | -0.312 | 0.779 | -0.312 |
  | Linear Diffusion (network) | 0.1593 | -0.294 | 0.769 | -0.294 |
  | Naive Persistence (mean) | 0.1942 | 0.000 | 0.000 | +0.000 |

**Comparison vs prior benchmark (`benchmark.json`):**

- Prior N = 8; new N = 11

## Calibration (Phase 4 result)

- **Calibration v2** (`calibration_v2.json`):
  - Best method: `DE`
  - Default-config RMSE: 0.27762
  - Best-params RMSE: 0.27680
  - Improvement vs default: 0.00184
  - Sobol identifiable parameters: 2 / 5

- **MCMC posterior** (`posterior_v2.json`):
  - Walkers × steps: 20 × 150 (burn-in 50)
  - Acceptance fraction: 0.305
  - Autocorr time max: 18.5
  - Converged heuristic: False

  Posterior summary (mean ± std, [P05, P95]):

  | Parameter | Mean | Std | P05 | P50 | P95 |
  |---|---|---|---|---|---|
  | propagation_decay | 0.7961 | 0.1489 | 0.5318 | 0.8283 | 0.9814 |
  | amplification_mu | 2.4828 | 1.2544 | 0.1611 | 2.7377 | 3.9519 |
  | amplification_eps | 0.1335 | 0.0524 | 0.0291 | 0.1435 | 0.1974 |
  | recovery_rate | 0.0634 | 0.0547 | 0.0125 | 0.0475 | 0.1681 |
  | bullwhip_factor | 1.2448 | 0.2066 | 1.0168 | 1.1849 | 1.5795 |

  _Compute-budget note: Production-grade budget per user spec is MCMC 600-1000 steps × ≥100 walkers. This run used 20×150 to fit the session window; results are informative but not publication-grade. Re-run with MCMC_STEPS=600 + MCMC_WALKERS=100 for tighter posteriors (~270 min)._

## Known weaknesses (do not exaggerate)

1. **Sector enum is the bottleneck.** Engine `Industry` enum has only 7
   members; 31 of 42 events touch sectors outside the enum and are
   excluded from the benchmark. The Phase 1 expanded-graph CSV is
   *data only* — wiring it into `seed.py` requires careful re-tuning
   of per-node parameters that this session did not perform.

2. **N benchmarked = ~11.** Even at N=42 corpus size, only the subset
   matching engine-known sectors AND engine graph nodes can be scored.
   Any 'GEDS beats baseline' claim is currently an N=11 claim.

3. **MCMC budget is below user spec.** User asked for 600–1000 steps;
   this session ran 150 steps × 20 walkers to fit the time window.
   Posterior widths are wider than they would be with production budget.
   See `posterior_v2.json::compute_budget_note`.

4. **Only 1–10 events have paper corroboration depending on definition.**
   Curated `PAPER_TO_EVENTS` map in `phase1_2_expand_and_mine.py` links
   25 papers to events, but only papers with extractable numbers contribute
   numeric evidence rows. Most papers are theoretical methodology, not
   per-event measurements.

5. **Recovery-time data is 97.6% blank.** Source docx never had an
   explicit Recovery Time field — values exist only when paper text
   explicitly says e.g. 'reconstruction: 10 years'.

6. **Disk-space note.** During this session the local `C:` drive was
   reported at 100% utilisation; pipeline runs should be kept on `D:`
   until that's resolved.

## Confidence summary

| Layer | Aggregate confidence | Source |
|---|---|---|
| Event registry | 4.14 / 5 | source-rated in docx |
| Dataset registry | 3.26 / 5 | derived from provider + API + Python-package signals |
| Literature registry | 3.26 / 5 | 5 for deeply-cataloged papers, 2-3 for title-only |

## What is reproducible

Every number in this doc traces to a file in the repo:

- Event counts → `master_event_registry.csv`
- Dataset counts → `master_dataset_registry.csv`
- Graph node counts → `expanded_graph_nodes.csv` and `seed_data.py`
- Benchmark numbers → `backend/data/calibration/benchmark_v2.json`
- Calibration numbers → `backend/data/calibration/calibration_v2.json`
- Posterior numbers → `backend/data/calibration/posterior_v2.json`

Re-run order: `phase1_2_expand_and_mine.py` → `phase3_benchmark_v2.py`
→ `phase4_calibrate_v2.py` → `phase5_regenerate_state.py`.
