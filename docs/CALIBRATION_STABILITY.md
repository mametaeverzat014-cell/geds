# Calibration Stability — Sensitivity, Identifiability, Correlation

Generated: `2026-06-03T16:23:08.687573+00:00`


- **Calibrated point:** `cmaes_best_params.json` (best loss 0.15940)
- **Local σ:** LOEO fold std
- **Graph:** OECD+WIOD spectrally normalised (ρ=1.0)
- **N events:** 21

## [1] Local sensitivity ranking (finite-difference around calibrated point)

Each parameter perturbed by ±1 σ (LOEO fold std), holding others at calibrated value.

| Rank | Parameter | θ ± σ range | MAE @ θ-σ | MAE @ θ* | MAE @ θ+σ | ΔMAE (low) | ΔMAE (high) | max|Δpred| |
|---|---|---|---|---|---|---|---|---|
| 1 | `propagation_decay` | [0.5000, 0.6566] | 0.15940 | 0.15940 | 0.15931 | +0.00000 | -0.00009 | 0.00080 |
| 2 | `amplification_mu` | [0.0000, 1.0369] | 0.15940 | 0.15940 | 0.15933 | +0.00000 | -0.00007 | 0.00110 |
| 3 | `recovery_rate` | [0.1608, 0.2621] | 0.15938 | 0.15940 | 0.15941 | -0.00002 | +0.00001 | 0.00010 |
| 4 | `amplification_eps` | [0.0823, 0.1247] | 0.15940 | 0.15940 | 0.15940 | +0.00000 | +0.00000 | 0.00000 |
| 5 | `bullwhip_factor` | [1.4617, 1.7583] | 0.15940 | 0.15940 | 0.15940 | +0.00000 | +0.00000 | 0.00000 |
| 6 | `inventory_scale` | [0.5746, 1.7954] | 0.15940 | 0.15940 | 0.15940 | +0.00000 | +0.00000 | 0.00000 |
| 7 | `r_output_floor` | [0.1511, 0.3588] | 0.15940 | 0.15940 | 0.15940 | +0.00000 | +0.00000 | 0.00000 |

## [2] Variance decomposition — first-order Sobol approximation

Univariate R² between each sampled parameter and each per-event prediction (averaged across events). Read as: "fraction of event-prediction variance explained by varying this single parameter".

| Parameter | mean R² across events |
|---|---|
| `propagation_decay` | 0.09839 |
| `recovery_rate` | 0.07667 |
| `amplification_mu` | 0.01676 |
| `r_output_floor` | 0.01068 |
| `amplification_eps` | 0.00124 |
| `inventory_scale` | 0.00119 |
| `bullwhip_factor` | 0.00056 |

## [3] Identifiability (SVD of param→pred linear map)

- Singular values: [1.8386, 0.5026, 0.4232, 0.1491, 0.1212, 0.0837, 0.0536]
- Effective rank: **7 / 7**
- Condition number κ: **34.29**
- Interpretation: Condition number is moderately ill-conditioned (30 ≤ κ < 100); effective rank is full (7/7): in the linearised map every parameter moves predictions along a distinct direction, so the parameters are *formally* distinguishable. This does NOT contradict the near-zero local-sensitivity result — the parameters shift individual event predictions in independent directions, but the shifts are negligible in magnitude versus the observed-loss scale and cancel at the aggregate, so the calibration is *practically* weakly-determined rather than *formally* rank-deficient.

## [4] Pairwise correlation summary

- Input-input max |off-diagonal| = 0.1084 (small ⇒ independent sampling worked as intended).

### Input × Output correlations (param vs per-event prediction)

| Parameter \ Event | 1 | 2 | 3 | 4 | 5 | 6 | 9 | 10 | 11 | 12 | 14 | 15 | 16 | 21 | 22 | 23 | 24 | 26 | 27 | 28 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `amplification_mu` | +0.088 | +0.000 | -0.018 | -0.000 | +0.169 | +0.064 | — | — | +0.029 | — | +0.004 | +0.016 | +0.085 | +0.000 | +0.005 | -0.006 | +0.207 | -0.000 | +0.503 | -0.006 | +0.081 |
| `amplification_eps` | +0.025 | +0.000 | +0.003 | -0.000 | +0.046 | +0.063 | — | — | +0.042 | — | +0.011 | +0.022 | +0.084 | +0.000 | -0.005 | +0.012 | -0.027 | -0.000 | +0.054 | +0.017 | +0.076 |
| `propagation_decay` | +0.544 | +0.000 | +0.181 | -0.000 | +0.399 | +0.512 | — | — | +0.592 | — | +0.229 | +0.331 | +0.268 | +0.000 | +0.202 | +0.258 | +0.372 | -0.000 | +0.641 | +0.265 | +0.070 |
| `recovery_rate` | -0.574 | -0.000 | -0.188 | +0.000 | -0.345 | -0.368 | — | — | -0.616 | — | -0.202 | -0.334 | -0.172 | -0.000 | -0.243 | -0.275 | -0.300 | +0.000 | -0.377 | -0.237 | -0.079 |
| `bullwhip_factor` | -0.009 | +0.000 | -0.001 | -0.000 | +0.069 | +0.006 | — | — | +0.032 | — | -0.001 | -0.001 | +0.002 | +0.000 | -0.010 | -0.002 | -0.008 | -0.000 | +0.041 | -0.002 | -0.064 |
| `inventory_scale` | +0.053 | +0.000 | +0.029 | -0.000 | -0.077 | +0.036 | — | — | +0.040 | — | +0.032 | +0.040 | +0.073 | +0.000 | +0.041 | +0.033 | +0.009 | -0.000 | -0.025 | +0.034 | -0.002 |
| `r_output_floor` | -0.107 | -0.000 | -0.056 | +0.000 | -0.094 | -0.064 | — | — | +0.004 | — | -0.056 | -0.067 | -0.061 | -0.000 | -0.047 | -0.061 | +0.406 | +0.000 | -0.068 | -0.055 | -0.084 |

## Brutally honest verdict (one paragraph)

The most-influential parameter at the calibrated point is `propagation_decay` (max |ΔMAE| under ±1 σ = 0.00009). The SVD of the parameter → prediction map gives effective rank 7 / 7, κ = 34.3. Full rank means the 7 parameters are *formally* distinguishable in the linearised map — yet the local-sensitivity sweep shows ±1 σ moves MAE by < 0.00009. The reconciliation: parameters do shift *individual* event predictions (input-output correlations reach ~0.64 for `propagation_decay` / `recovery_rate`), but the shifts are negligible in magnitude and cancel in the aggregate error — so the fit is *practically* weakly-determined, not *formally* rank-deficient. Practically: the optimiser can move several parameters within their LOEO σ without measurably changing the engine's output, so any single-point calibration should be interpreted as a *family* of equally-good calibrations, not a unique fit. This is consistent with the ablation result that mechanisms are decorative — if multiple mechanisms can be turned off without changing predictions, the parameter space they live in is necessarily under-identified.

## Files preserved (not overwritten)

- `benchmark_spectral_normalized.json`
- `bootstrap_results.json`
- `ensemble_predictions.json`
- `ensemble_statistics.json`
- `ablation_post_normalization.json`
- `loeo_results.json`