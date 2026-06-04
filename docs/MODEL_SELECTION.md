# GEDS — Model Selection Guide

Recommendations derived from `benchmark_matrix.csv` (1–10 scores per
model per axis) + `model_catalog.csv` + `BENCHMARK_IMPLEMENTATION.md`
risk assessments.

Every recommendation cites the score that drove the choice. When two
models tie or are within 1 point, the model with lower implementation
risk wins.

## Best for **highest accuracy**

**Recommendation:** `XGBoost (Gradient-Boosted Trees)` (score: 9/10 on `prediction_accuracy`).

_When to use:_ When the only goal is maximising AUROC / R² on held-out crisis prediction. Trades interpretability for raw fit.

## Best for **interpretability**

**Recommendation:** `Leontief Input-Output (I-O)` (score: 10/10 on `interpretability`).

_When to use:_ When the model output must be defensible to a policymaker or regulator. Closed-form models dominate this axis.

## Best for **research value**

**Recommendation:** `Leontief Input-Output (I-O)` (score: 10/10 on `research_support`).

_When to use:_ When the work is going into a peer-reviewed paper and citation depth matters more than runtime.

## Best for **startup value**

**Recommendation:** `Leontief Input-Output (I-O)` (score: 9/10 on `expected_geds_value`).

_When to use:_ When the model needs to fit into the production GEDS engine and contribute to its real-time output.

## Best for **ISEF value**

**Recommendation:** `Leontief Input-Output (I-O)` (score: 9/10 on `expected_geds_value`).

_When to use:_ When the model demonstrates the GEDS thesis in front of a panel. Demos must run in seconds with visible outputs.

## Best for **limited hardware**

**Recommendation:** `Linear Network Diffusion` (score: 10/10 on `runtime`).

_When to use:_ When inference must run on a laptop without GPU. Closed-form and tree-based models dominate; deep learning needs GPU.

## Best for **large-scale deployment**

**Recommendation:** `Linear Network Diffusion` (score: 9/10 on `scalability`).

_When to use:_ When the model must scale to thousands of countries × sectors. Sparse-matrix and tree-ensemble methods scale; ABM and TGN do not.

## Best overall for GEDS production pipeline

**Recommendation:** Layered ensemble per the docx Recommended GEDS
Integration Architecture (Table 3 from benchmark-comparison docx):

- **Static propagation:** Leontief I-O + OECD ICIO (interpretable,
  closed-form, validated)
- **Dynamic propagation:** Acclimate-inspired ABM + Network Contagion
  SIR (captures non-linear cascades)
- **Uncertainty quantification:** Monte Carlo over the ABM/I-O
  composite
- **Crisis early warning:** XGBoost + SHAP (highest single-model
  AUROC = 0.97 per IJEFS 2024)
- **Real-time signal layer:** Temporal GNN (GConvGRU; F1 = 0.750 on
  183-country task per EconoGNN 2026)

No single model wins every axis — the composite hedges against the
weaknesses of each.

## What to NOT pick

- **Pure ABM** when you need closed-form CIs or fast iteration —
  parameter sensitivity and replication variance are too high
  (`risk: HIGH` in `BENCHMARK_IMPLEMENTATION.md`).
- **Pure TGN/TGAT** unless GPU and large dataset are both available
  — OOM failures on large graphs per the docx.
- **Pure XGBoost** when the question is *why* a country is exposed —
  SHAP gives feature importance but not causal mechanism.
