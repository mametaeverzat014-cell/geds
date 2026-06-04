# OECD-Graph Calibration Audit (Phase 1)

**Generated:** 2026-05-28
**Purpose:** verify inputs + set realistic compute budget BEFORE running calibration.

## Input file verification

| Required | Exists | Notes |
|---|---|---|
| `backend/data/calibration/benchmark_oecd.json` | ✓ | 21 events, 4 models. Pre-recalibration baseline. |
| `backend/data/csv/oecd_icio_edges.csv` | ✓ | 5,516,587 rows × 7 years. Filtered to year=2022 at runtime. |
| `backend/data/csv/oecd_country_sector_weights.csv` | ✓ | 28,350 rows. Source of node-level GDP and trade aggregates. |
| `backend/data/csv/country_sector_presence_real.csv` | ✓ | 1,134 DATA_PRESENT / 405 NULL (5 sectors absent in OECD). |
| `backend/data/csv/master_event_registry.csv` | ✓ | 42 events. |
| `backend/data/csv/benchmark_targets_expanded.csv` | ✓ | Peer-reviewed targets for 7 events. |
| `backend/data/calibration/calibration_v2.json` | ✓ | Prior calibrated params (heuristic graph). Will NOT be used as priors. |

## Event matrix coverage on OECD graph

Measured by re-running `remap_events_for_oecd_graph()`:

- **42 total events** in master registry
- **21 OK / eligible** (engine sector + OECD graph node exist + GDP target)
- **20 UNMAPPED / NO_TARGET / SCENARIO** (excluded)

Sectors required by eligible events (engine `Industry` enum):
- automotive, electronics, shipping, agriculture, consumer_goods, tourism,
  oil, banking, government, telecommunications, utilities

Sectors required by some events but NOT in engine-runnable set (OECD-absent
or enum-absent):
- semiconductors (no OECD source), gas (bundled in OECD B06), insurance
  (bundled in OECD K), capital_markets (bundled in OECD K), energy (composite),
  healthcare (no engine enum entry)

## Compute budget measurement

Direct measurement on this hardware (CPython 3.11, single-threaded NumPy):

| Operation | Time | Notes |
|---|---|---|
| OECD graph build (snapshot + compile) | **7.4 s** | one-time cost per session |
| Single backtest_event call | **518 ms** | on 1128-node OECD graph |
| One likelihood evaluation (21 events) | **10.87 s** | sequential, no event parallelism |
| MCMC 16 walkers × 100 steps (1,600 evals) | **~290 min** | 4.8 hours sequential |
| MCMC 32 walkers × 200 steps (6,400 evals) | **~19 hours** | publication-grade target |
| MCMC 64 walkers × 400 steps (25,600 evals) | **~77 hours** | aspirational target |

**Implication:** publication-grade MCMC requires overnight execution. This session
will run a **diagnostic-grade** calibration:

| Method | Budget this session | Wall time | Purpose |
|---|---|---|---|
| Optuna (TPE) | 30 trials | ~6 min | initial point identification |
| Differential evolution | 15 gen × 6 pop = 90 evals | ~17 min | escape Optuna local optima |
| MCMC (emcee EnsembleSampler) | 6 walkers × 30 steps = 180 evals | ~33 min | uncertainty characterisation |
| Fair re-benchmark | 1 LD-grid + 4 single evals = ~30 evals | ~6 min | head-to-head with re-tuned baselines |
| **Total** | **~330 likelihood evals** | **~62 min** | diagnostic, not publication |

**Resumability**: MCMC chain state will be saved to
`backend/data/calibration/oecd_mcmc/sampler_state.json` every 5 steps.
The user can run `run_oecd_mcmc.py --extend 200` to add 200 more steps
without losing the existing chain.

## Train / validation split

Events: 21 eligible total. Stratified by `is_scenario=false` (all 21).
- **Train: 16 events** (events 1, 3, 4, 6, 9, 11, 14, 16, 17, 18, 19, 21, 22, 24, 28, 30 — chosen by event_id order)
- **Validation: 5 events** (events 23, 25, 26, 27, 33 — held out)

Calibration objective is computed on the TRAIN set only. Reported metrics
include separate train and validation scores so over-fitting can be detected.

## Parameter space (Phase 2 preview)

9 parameters to calibrate. Bounds documented in
`backend/data/calibration/parameter_space_oecd.json` with literature anchors
where available.

| Parameter | Engine field | Literature anchor |
|---|---|---|
| `amplification_mu` | EngineConfig | Carvalho 2021 QJE: 3-4× multiplier → μ ≈ 2-3 |
| `amplification_eps` | EngineConfig | None — theoretical only |
| `propagation_decay` | EngineConfig | None — engine convention |
| `recovery_rate` | EngineConfig | Cerra 2020 IMF WP: slow recovery → ξ ≈ 0.02-0.10 |
| `distress_base` | EngineConfig | None — derived threshold |
| `bullwhip_factor` | EngineConfig | Lee 1997: Var ratio bounded 1.0-2.0 |
| `inventory_scale` | EngineConfig (proxy for recovery_delay) | IHS Markit / SEMI / Boeing per-sector |
| `r_output_floor` | EngineConfig (hysteresis floor) | Cerra 2020: 1-2% permanent → 0.01-0.30 range |
| `sanity_max_loss_fraction` | EngineConfig (vulnerability scaling proxy) | None — engine safeguard |

## Known limitations to flag upfront

1. **9 free parameters on N=16 training events** = 1.78 events per parameter.
   Severe over-parameterisation. Prior Sobol runs flagged 3 of 5 SEIRS
   parameters as non-identifiable; on N=16 with 9 params, expect more.
2. **No event parallelism in current backtest path.** Each likelihood eval
   is sequential 21-event loop.
3. **Chokepoint nodes are heuristic** (5 of 8) — calibration cannot fix this.
4. **5 of 19 GEDS sectors are NULL in OECD** (semiconductors, gas, insurance,
   capital_markets, energy). Events touching these still fall back to heuristic.
5. **`backend/data/raw/oecd_icio/parsed/provenance.json`** confirms OECD year=2022 was the latest used.

## Outputs to be generated

| File | Path | Phase |
|---|---|---|
| Parameter space | `backend/data/calibration/parameter_space_oecd.json` | 2 |
| MCMC engine | `backend/scripts/calibration/run_oecd_mcmc.py` | 3 |
| Optuna result | `backend/data/calibration/oecd_mcmc/optuna_best.json` | 3 |
| DE result | `backend/data/calibration/oecd_mcmc/de_best.json` | 3 |
| MCMC chain + state | `backend/data/calibration/oecd_mcmc/sampler_state.json` | 3 |
| Composite metric trace | `backend/data/calibration/oecd_mcmc/metric_trace.json` | 4 |
| Diagnostics | `backend/data/calibration/oecd_mcmc/diagnostics.json` | 5 |
| Fair benchmark | `backend/data/calibration/benchmark_oecd_recalibrated.json` | 6 |
| Recalibration report | `docs/OECD_RECALIBRATION_REPORT.md` | 7 |
| Limitations | `docs/CALIBRATION_LIMITATIONS.md` | 7 |
| Identifiability | `docs/PARAMETER_IDENTIFIABILITY.md` | 7 |

**Existing files preserved (NEVER overwritten):**
- `benchmark_oecd.json` (pre-recalibration baseline)
- `mechanism_trace_oecd.json`
- `ablation_oecd.json`
- `calibration_v2.json` (heuristic-graph calibration)
- `benchmark_v3.json`

End of audit.
