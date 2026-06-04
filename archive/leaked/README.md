# Quarantined: leaked benchmark & calibration lineage

Everything in this directory is **scientifically invalid** and has been removed
from the active codebase. It is preserved for provenance and audit only. **Do
not run, cite, import, or revive any of it** without first fixing the defect
described below.

These artifacts do not appear in any reports/* output, are not read by the
FastAPI app (`backend/app/`), and are not referenced by the test suite. Removing
them does not affect the running application. The clean, valid benchmark is
`backend/app/core/benchmark.py` (see `docs/REPRODUCIBILITY.md`).

---

## The defect: target leakage

A benchmark must predict the observed outcome from inputs that are knowable
*before* the outcome. These scripts violate that: they derive the model **input**
(the shock magnitude) from the **observed target** they are supposed to predict.

Two leak roots, both deriving `magnitude` from the answer:

1. **`run_oecd_benchmark.remap_events_for_oecd_graph()`** — `run_oecd_benchmark.py:370`

   ```python
   magnitude = max(0.1, min(0.9, abs(gdp_t * 100) / 50.0))   # gdp_t = the target
   ```

2. **`phase3_benchmark_v2.translate_event()`** — `phase3_benchmark_v2.py:119`

   ```python
   magnitude = max(0.1, min(0.9, abs(gdp_v) / 50.0))          # gdp_v = the target
   ```

   and `phase_validation_expansion.py:303` sets the observation directly from the
   same target column:

   ```python
   translated["observed"]["auto_production_loss_pct"] = abs(float(row["gdp_target"]))
   ```

Because the shock is a deterministic function of the target, the "prediction"
task is partly solved by construction. Any reported skill on these event sets is
an artifact of the leak, **not** evidence that the model works. This is a
validity failure; it cannot be repaired by re-running or re-seeding.

A second, independent problem affects the `*_v3` lineage: `benchmark_v3.json`
claims to re-emit `benchmark_v2` with an identical config but the numbers differ
by ~40× because the config was silently changed — a provenance/reproducibility
failure on top of the leak.

---

## Quarantined scripts (`scripts/`)

| Script | Why quarantined |
|---|---|
| `run_oecd_benchmark.py` | **Leak root** — `remap_events_for_oecd_graph` derives magnitude from target |
| `phase3_benchmark_v2.py` | **Leak root** — `translate_event` derives magnitude from target |
| `phase_expanded_validation.py` | Own leak line (`:572`) + builds on the v2 lineage |
| `phase_validation_expansion.py` | Imports `translate_event`; sets observed = `abs(gdp_target)` |
| `run_wiod_benchmark.py` | Imports `remap_events_for_oecd_graph` (runs on leaked event set) |
| `calibration_stability.py` | Imports `remap_events_for_oecd_graph` |
| `event_uncertainty_breakdown.py` | Imports `remap_events_for_oecd_graph` |
| `monte_carlo_ensemble.py` | Imports `remap_events_for_oecd_graph` |
| `post_norm_ablation.py` | Imports `remap_events_for_oecd_graph` |
| `mechanism_forensics.py` | Imports `translate_event` |
| `phase4_calibrate_v2.py` | Imports `translate_event` (calibrates on leaked events) |
| `calibration/run_benchmark_v4.py` | Own leak line (`:83`) + imports `remap_events_for_oecd_graph` |
| `calibration/run_oecd_mcmc.py` | Imports `remap_events_for_oecd_graph` (MCMC on leaked events) |
| `calibration/run_cmaes_oecd.py` | Imports `remap_events_for_oecd_graph` (CMA-ES on leaked events) |
| `calibration/run_spectral_recalibration.py` | Imports `remap_events_for_oecd_graph` |

The cluster is closed: every importer of the two leak functions is included, so
no quarantined script depends on a script left in `backend/scripts/`. They are
**not runnable** from this location (their `from app.core …` imports assume the
`backend/` working tree) — this is intentional. They are archived, not ported.

## Quarantined data artifacts (`data/`)

Each file is the output of a quarantined producer above. Provably-leaked by
pipeline suffix (`_v2`, `_v3`, `_v4`, `_oecd`, `_wiod`) or as the sole output of
a confirmed-leaked script.

| Producer / lineage | Artifacts |
|---|---|
| v2 phase pipeline | `benchmark_v2.json`, `benchmark_v2_expanded.json`, `ablation_v2.json`, `mechanism_trace_v2.json`, `posterior_v2.json`, `calibration_v2.json` |
| v3 re-emit (leak + provenance failure) | `benchmark_v3.json` |
| v4 pipeline | `benchmark_v4.json`, `loeo_v4.json`, `bootstrap_v4.json`, `uncertainty_v4.json`, `v4_preaudit.json` |
| OECD pipeline | `benchmark_oecd.json`, `ablation_oecd.json`, `mechanism_trace_oecd.json`, `parameter_space_oecd.json`, `cmaes_best_params.json` |
| WIOD pipeline | `benchmark_wiod.json`, `ablation_wiod.json`, `mechanism_trace_wiod.json` |
| Spectral recalibration | `benchmark_spectral_normalized.json`, `spectral_metrics.json`, `stable_regime_analysis.json`, `ablation_post_normalization.json` |
| Monte-Carlo ensemble | `ensemble_predictions.json`, `ensemble_statistics.json` |
| Event-uncertainty breakdown | `event_uncertainty_breakdown_sidecar.json` |
| Calibration-stability | `calibration_stability.json` |

---

## What was NOT quarantined (and why)

- **`backend/data/calibration/benchmark.json`** — the clean N=8 benchmark on the
  hand-authored event corpus; regenerated by the active harness. **Valid.**
- **Unsuffixed calibration JSONs** (`ablation.json`, `mechanism_trace.json`,
  `loeo_results.json`, `bootstrap_results.json`, `posterior.json`, `sobol.json`,
  `de_result.json`, `provenance.json`, `literature_priors.json`) — their lineage
  (clean-core vs. leaked-v2) could **not** be established from the repository
  alone. Per the project's no-guessing rule they were left in place rather than
  quarantined on suspicion. **Flagged for provenance review** (see
  `docs/SCIENTIFIC_STATUS.md` / implementation report).

## How a future expanded benchmark must avoid this

Shock magnitudes must come from a source independent of the target: a fixed
standardized shock per event class, an externally documented intensity (e.g. a
disaster/financial-stress index), or a hand-authored estimate with cited
provenance — never a transform of the observed outcome. The clean N=8 corpus in
`backend/app/data/seed_data.py` is the reference example (hand-authored shocks,
public observed magnitudes).
