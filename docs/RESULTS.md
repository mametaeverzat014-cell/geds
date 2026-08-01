# GEDS — headline results (generated)

> GENERATED FILE — regenerate with `python -m scripts.results_onepager`;
> never hand-edit. Sources: live engine runs plus `significance.json`
> (seed 20260718, 10000 bootstrap / 20000 perms,
> generated 2026-08-01), `loo_de_result.json`
> (27 folds, 2026-07-23), `ramp_experiment.json`
> (2026-07-23). Benchmark config is the pinned deterministic
> config (`BENCHMARK_CONFIG`, stochastic_sigma=0, seed=0).

**Benchmark set:** N=27 primary-sourced historical events (1999–2023), golden-locked in `tests/test_reproducibility.py`.

## 1. Point magnitude (Track A): four models, default parameters

| Model | MAE [95% CI] | RMSE [95% CI] | Spearman [95% CI] |
|---|---|---|---|
| SEIRS-Bullwhip-Hysteresis (GEDS) | 0.0242 [0.0110, 0.0402] | 0.0464 [0.0208, 0.0669] | 0.45 [0.06, 0.73] |
| Leontief (input-output equilibrium) | 0.0168 [0.0079, 0.0278] | 0.0313 [0.0107, 0.0457] | 0.34 [-0.10, 0.67] |
| Linear Diffusion (network) | 0.0171 [0.0089, 0.0286] | 0.0317 [0.0116, 0.0495] | 0.72 [0.40, 0.91] |
| Naive Persistence (predict mean) | 0.0208 [0.0126, 0.0311] | 0.0324 [0.0138, 0.0473] | constant — no ranking |

**Pairwise differences (paired bootstrap + sign-flip permutation):**

| Pair (first − second) | ΔMAE [95% CI] | p (two-sided) | verdict |
|---|---|---|---|
| GEDS − Leontief | 0.0074 [-0.0031, 0.0218] | 0.42 | n.s. |
| GEDS − LinearDiffusion | 0.0071 [-0.0018, 0.0182] | 0.21 | n.s. |
| GEDS − NaivePersistence | 0.0034 [-0.0085, 0.0191] | 0.58 | n.s. |
| Leontief − LinearDiffusion | -0.0003 [-0.0120, 0.0111] | 0.97 | n.s. |
| Leontief − NaivePersistence | -0.0040 [-0.0083, 0.0005] | 0.09 | n.s. |
| LinearDiffusion − NaivePersistence | -0.0037 [-0.0143, 0.0090] | 0.58 | n.s. |

**Reading:** no pairwise magnitude difference is significant at N=27 — single-number validation cannot rank these models. This motivates the trajectory axes below.

## 2. Trajectory shape (Track B, node-level; the axes only GEDS attempts)

| Dimension | n | Spearman [95% CI] | MAE |
|---|---|---|---|
| peak magnitude | 5 | 0.60 [-1.00, 1.00] | 0.43 |
| weeks to peak | 15 | 0.69 [0.20, 0.87] | 7.07 |
| recovery weeks | 11 | 0.88 [0.56, 0.99] | 8.55 |

**Batch-19 ramp result:** weeks_to_peak was at chance (0.07) because the engine had no rising forcing shape; the pre-registered `ramp` adoption moved it to 0.69 at a benchmark cost of +0.0001 MAE (gate: all 4 criteria passed; see `ramp_experiment.json`).

## 3. Out-of-sample (leave-one-out, per-fold DE recalibration)

| | MAE | RMSE | Pearson | Spearman | R² |
|---|---|---|---|---|---|
| GEDS, LOO-recalibrated (27 folds) | 0.0192 | 0.0422 | 0.25 | 0.56 | -0.70 |

Paired vs Leontief (zero-parameter baseline): ΔMAE 0.0024 [-0.0073, 0.0167], p=0.89 — **magnitude parity holds out-of-sample too**, tuned or untuned.

## 4. Spatial reach (did the cascade hit the right nodes?)

| Graph | nodes | pooled spatial recall |
|---|---|---|
| v2 hand-authored | 36 | 0.29 (10/35) |
| v3 OECD ICIO 2019 | 405 | 0.79 (30/38) |

Same engine, same shocks — only the graph changes (12 comparable production events). Onset ordering on reached nodes: Spearman 0.79 (v2). Structure, not parameter tuning, is the binding constraint.

## 5. Figures

Regenerate with `python -m scripts.isef_figures` (PNG + numeric CSV pairs in `backend/data/calibration/figures/`):

- `parity_forest` — §1 pairwise CIs as a forest plot
- `pred_vs_obs` — §1 per-model scatter, N=27
- `timing_ramp` — §2 weeks_to_peak before/after the ramp
- `spatial_recall` — §4 per-event v2→v3 dumbbell

