# GEDS Benchmark — Experimental Design

This is the protocol for fairly comparing the 10 models in
`model_catalog.csv` against the GEDS engine on the 42-event corpus
from `historical_events_expanded.csv` + the new v2 validation
metrics from `validation_targets_v2.csv` (160 rows of institutional
ground-truth from the v2 docx).

## Training procedure

Six of the 10 models have **no training step** (Leontief I-O, Linear
Diffusion, Network Contagion SIR, Monte Carlo, DBN with hand-built
structure). For these, 'training' means parameter calibration only.

For the four trainable models (ABM, GNN, TGN/TGAT, XGBoost, RF —
five if you count RF separately):

- **Train split:** events 2000–2018 (29 events from
  `historical_events_expanded.csv`). Excludes COVID and post-COVID
  to leave them as honest out-of-sample tests.
- **Calibration split:** events 2019–2020 (3 events). For
  hyperparameter tuning and early stopping.
- **Test split:** events 2021–2026 (10 events). Strict temporal
  hold-out — never seen during training or calibration.

## Validation procedure

Three concentric layers:

1. **In-sample fit** on the train split — sanity check; high error
   here means the model cannot represent the data even with full
   information.
2. **Held-out validation** on the calibration split — diagnostic for
   overfitting (large gap from in-sample → overfit).
3. **Out-of-sample test** on the test split — the only metric that
   is reported externally. Everything before this is internal.

## Cross-validation

Use **leave-one-out (LOO)** on the train split: 29 folds, each
withholds one event, calibrates on the remaining 28, predicts the
held-out one. Aggregate metrics across 29 folds with bootstrap CIs.
Existing implementation: `app/core/cross_validation.py`.

## Sensitivity analysis (Sobol)

For each parametric model:

- Sample 1024 parameter vectors via Sobol sequence
- Compute first-order (S₁) and total-order (Sₜ) indices per parameter
- Flag any parameter with Sₜ < 0.05 as non-identifiable

Existing implementation: `app/core/sensitivity.py` (SALib).

The previous Sobol run flagged 3 of 5 SEIRS parameters as
non-identifiable. Repeat for every new model that gets added.

## Ablation study

Disable one component at a time, re-run the full LOO, report Δ in
headline metric. For GEDS specifically:

- Disable SEIRS layer → Linear Diffusion baseline
- Disable bullwhip amplification (set μ=0)
- Disable hysteresis (set recovery rate to constant)
- Disable chokepoint nodes

Existing implementation: `app/core/ablation.py`.

## Hyperparameter search

Per model:

| Model | Method | Budget |
|---|---|---|
| XGBoost | Optuna (TPE) | 200 trials |
| Random Forest | Random search | 100 trials |
| GNN / TGN | Hand-tuned + 20-trial random | 20 trials |
| ABM | Grid over 4 parameters | 81 combinations |
| GEDS (SEIRS) | emcee MCMC | 100 walkers × 2000 steps |

Hyperparameter search is done on the **calibration split only** —
never on the test split.

## Baseline comparison

Every reported number must include comparison to:

1. **Naive Persistence** (predict mean of training set)
2. **Linear Diffusion** (currently winning the GEDS N=8 benchmark)
3. **Leontief Equilibrium** (closed-form I-O)

A model is reportable as 'beating baselines' only if it beats all
three on the test split.

## Statistical significance testing

- **Paired Wilcoxon signed-rank test** on per-event errors when
  comparing two models on the same test events.
- Report p-values, NOT just point estimates.
- For multiple model comparisons, use **Bonferroni-corrected α** or
  Holm step-down procedure.
- For metric comparisons across uncertainty bootstrap, report the
  fraction of bootstrap samples in which model A beats model B.

## Reporting format

Every benchmark report must include:

- Model name + model_id from `model_catalog.csv`
- Metric value with 95% bootstrap CI (N=1000)
- Baseline comparison (Naive / Linear Diffusion / Leontief)
- p-value vs strongest baseline
- N of test events
- Exclusion criteria (scenario events excluded?, low-conf excluded?)
