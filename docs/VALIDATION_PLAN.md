# GEDS Scientific Evaluation Plan

Derived from:
- `backend/data/csv/papers_catalog.csv` (25 peer-reviewed references)
- `backend/data/csv/validation_targets_expanded.csv` (94 validation rows)
- `backend/data/csv/benchmark_inputs.csv` (42 event-level targets)

## Performance metrics

All metrics are reported with bootstrap-resampled 95% CIs (N=1000).

### Regression metrics (per-event continuous outputs)

| Metric | Formula | Use |
|---|---|---|
| **MAE** | mean(\|y - ŷ\|) | scale-aware error, robust to outliers |
| **RMSE** | sqrt(mean((y - ŷ)²)) | penalises large errors |
| **R²** | 1 − SSE/SST | variance explained vs predict-the-mean |
| **Pearson r** | cov(y, ŷ) / (σy · σŷ) | linear correlation |
| **MAPE** | mean(\|y - ŷ\|/\|y\|) | only when y ≠ 0 |
| **Murphy skill** | 1 − MSE / MSE_clim | scaled vs climatology |

Reference benchmark already lives in `backend/data/benchmark.json`
(Linear Diffusion = in-sample winner with R² +0.7647 on N=8 events).

### Classification metrics (per-event binary signals)

Applied to: was a country/sector affected above a threshold? did peak
exceed VaR_95? did recovery occur within forecast window?

| Metric | Formula |
|---|---|
| **Precision** | TP / (TP + FP) |
| **Recall** | TP / (TP + FN) |
| **F1** | 2 · P · R / (P + R) |
| **Calibration error (ECE)** | Σᵦ \|acc(b) − conf(b)\| · w(b) |

ECE is reported per decile of forecasted probability. The model is
well-calibrated when |gap| < 0.05 in every decile.

## Validation procedure

### Leave-one-out (LOO)

For each of the N events in `historical_events_expanded.csv`:
1. Re-calibrate model parameters on remaining N−1 events.
2. Predict the held-out event.
3. Score with all regression + classification metrics above.
Aggregate metrics and CIs across the N folds.

Existing GEDS infrastructure: `app/core/cross_validation.py` (already implemented).

### Bootstrap (uncertainty bands on every metric)

Resample N events with replacement, recompute metrics, repeat 1000×.
Report 2.5 / 50 / 97.5 percentile bands.
Existing: bootstrap utility in `app/core/cross_validation.py` (LOO + bootstrap CI both live there).

### Sensitivity analysis (Sobol)

Variance-decomposition of model outputs against parameter uncertainty.
Already implemented: `app/core/sensitivity.py` (Sobol indices via SALib). Output: first-order + total-order
indices per parameter (propagation_decay, amplification_mu, recovery_rate, ...).
Re-run after each graph expansion (BACI / OECD ICIO integration).

### Ablation

Disable one model component at a time and re-run full LOO. Report
ΔR² and ΔMAE per ablated component (SEIRS, bullwhip, hysteresis,
amplification). Existing: `app/core/ablation.py`.

### Baseline comparison

Three baselines must be beaten or matched for GEDS to claim utility:
1. **Naive Persistence** (predict mean of historical events)
2. **Linear Diffusion** (network propagation without SEIRS/bullwhip)
3. **Leontief Equilibrium** (I-O fixed-point)

Current state (2026-05-21 benchmark): Linear Diffusion beats GEDS on
N=8 events. This **must be addressed** before publication-grade claims.
Action items in NEXT_STEPS_VALIDATION.md.

## Per-event scoring loop

Inputs are taken row-by-row from `benchmark_inputs.csv`:

```
for event in benchmark_inputs.csv:
    scenario  = build_scenario_from(historical_events_expanded[event.id],
                                    model_event_mapping[event.id])
    forecast  = engine.run(scenario)
    score(forecast, event)  # regression + classification metrics
```

Existing GEDS scoring entry-point: `app/core/benchmark.py::run_benchmark()`.

## Literature corroboration layer

For each event-level prediction, we cross-reference against the
peer-reviewed paper that measured that event (when one exists).
Corroboration count per event:

| Event ID | Event Name | Corroborating papers |
|---|---|---|
| 3 | SARS Epidemic | 5 |
| 8 | H1N1 Swine Flu Pandemic | 5 |
| 11 | Tōhoku Earthquake, Tsunami & Fukushima Nuclear Cri | 2, 14, 17 |
| 17 | COVID-19 Global Pandemic | 5 |