# GEDS Rigor Overhaul — Progress Log

Three execution batches completed across 2026-05-16 to 2026-05-17.
**Read `AUDIT.md` for the full findings.** This file is the contents index.

---

## Batch 1 — foundations (delivered)

| Phase | Module | Endpoint | Key result |
|---|---|---|---|
| 2 | `app/core/mcmc.py` | `/api/v1/posterior` | MCMC posterior with R̂, autocorr, sensitivity per parameter |
| 6 | `app/core/cross_validation.py` | `/api/v1/cv-report` | LOO-CV with bootstrap 95% CIs |
| 5 | `app/core/baselines.py` | (used by benchmark) | Leontief + linear-diffusion baselines |
| 10 | `app/core/research_metrics.py` | `/api/v1/research-metrics` | SFI + RES + CCS with permutation tests |
| 1 | `AUDIT.md` | (document) | Honest scientific assessment |

## Batch 2 — calibration + tail risk (delivered)

| Phase | Module | Endpoint | Key result |
|---|---|---|---|
| 6 | `app/core/postcalibration.py` | `/api/v1/calibration-report` | Isotonic LOO calibration — **found it hurts at N=8** |
| 2 | `app/core/de_calibrate.py` | (CLI) | Differential evolution — **found params at bounds** |
| 7 | `app/core/tail_risk.py` | `/api/v1/tail-risk` | VaR / CVaR / black-swan / fan chart |
| 10 | `app/core/research_metrics.py` (extended) | (in /research-metrics) | Economic Resilience Tensor + Shock Absorption Capacity |
| 6 | `app/core/backtest.py` | `/api/v1/backtest` | Track-record live endpoint |
| 12 (minimal) | `frontend/app/validation/page.tsx` | `/validation` | Live dashboard of all validation panels |
| 6 (truthful UI) | `StatusRibbon.tsx`, `FAQPanel.tsx`, `MetricsPanel.tsx` | (UI) | Removed false "r=0.97" badge; now reads `/api/v1/cv-report` live |

## Batch 3 — ablation + sensitivity + benchmark (delivered)

| Phase | Module | Endpoint | Key result |
|---|---|---|---|
| 5 | `app/core/benchmark.py` | `/api/v1/benchmark` | **Linear diffusion beats GEDS on every metric** |
| 6 | `app/core/ablation.py` | `/api/v1/ablation` | **SEIS + adaptive rerouting are dead weight at N=8** |
| 6 | `app/core/sensitivity.py` | (CLI) | Sobol — **3 of 5 params non-identifiable, recovery_rate dominates** |
| 2 | `app/core/mcmc.py` (widened priors) | `/api/v1/posterior` | Bounds widened based on DE diagnostic |

---

## The three findings that matter for ISEF

1. **Honest benchmark exposure** — built leaderboard, baseline beats engine. (`/api/v1/benchmark`)
2. **Honest ablation exposure** — built ablation, two components are dead weight. (`/api/v1/ablation`)
3. **Honest identifiability exposure** — two independent methods (MCMC + Sobol) agree that 3 of 5 parameters are non-identifiable. (`/api/v1/posterior` + `_smoke3.py` Sobol section)

ISEF judges score these honest-self-assessment findings **higher** than uncritical "our model is great" claims. Use them.

---

## What was NOT done — and why

This is the honest deferred list. Each item is real work that requires resources beyond a single autonomous turn or external data:

| Phase | Item | Why deferred | What it needs |
|---|---|---|---|
| 3 | Graph expansion to 150–200 countries × 20–30 sectors | UN Comtrade API key + bulk CSV download + days of HS-code ↔ industry mapping | API access + 40 hrs of focused ETL labor |
| 4 | GNN replacement of static D_eff | No training data: N=8 events, GNNs need 1000+ | Generate synthetic from existing engine OR collect more events |
| 5 | Agent-based model | Weeks of implementation, hard to validate without large data | Same as above |
| 6 | 30–50 historical events database | Literature labor (~2 hr/event = ~60 hr total) | Research assistant or 2 weeks of focused work |
| 8 | Transformer NER (replace spaCy) | Marginal lift; spaCy is good enough at current scale | Only when data layer is the bottleneck |
| 9 | XGBoost / transformer cascade predictor | No labeled training set | Wait for events database expansion |
| 11 | Enterprise multi-tenant + auth + alerts | Months of work; premature without a design partner | Land a design partner first |
| 12 | Full Bloomberg/Palantir UI redesign | 2–4 months; premature for ISEF | Validate science first |
| 13 | Research paper draft | Premature; needs converged posterior + N≥30 events + GNN baseline | Q3 2026 after data work lands |

---

## How to run everything locally

```cmd
cd /d D:\GEDS\backend

REM verify all three batches in one go (~5 min total)
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" scripts/_smoke.py
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" scripts/_smoke2.py
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" scripts/_smoke3.py

REM production MCMC (~90 min, gives publication-grade posterior)
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" -m scripts.mcmc_calibrate --n-steps 2000 --n-walkers 64

REM serve the live dashboard
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" -m uvicorn app.main:app --reload
```

Then in another terminal:

```cmd
cd /d D:\GEDS\frontend
npm run dev
```

Open http://localhost:3000 (main dashboard) and http://localhost:3000/validation (the new live audit dashboard).

---

## File map

```
backend/app/core/
├── mcmc.py              Bayesian inference (emcee)
├── de_calibrate.py      Differential Evolution calibration
├── postcalibration.py   Isotonic post-calibration
├── cross_validation.py  Leave-one-event-out CV with bootstrap CI
├── sanity.py            Global loss caps + calibrator penalty term
├── sensitivity.py       Sobol global sensitivity (SALib)
├── ablation.py          Component-wise ablation
├── benchmark.py         Unified model leaderboard
├── baselines.py         Leontief + linear-diffusion baselines
├── backtest.py          Frozen-param historical replay
├── tail_risk.py         VaR / CVaR / fan chart
└── research_metrics.py  SFI / RES / CCS / ERT / SAC + stat eval

backend/scripts/
├── mcmc_calibrate.py    Production MCMC runner
├── calibrate.py         Optuna calibration (legacy, batch 0)
└── (batch smoke reproducers `_smoke*.py` removed in Batch 4 — superseded
     by `tests/` + `python -m app.core.benchmark --check`)

frontend/app/
├── page.tsx             Main simulation dashboard (truthful badges now)
└── validation/page.tsx  Live audit dashboard (6 endpoints)

frontend/components/
├── NarrativePanel.tsx   Grok policy analysis
├── NewsSignalsPanel.tsx Live news → graph deltas
└── StatusRibbon.tsx     Live LOO-CV badge in top-right

data/calibration/
├── provenance.json      Optuna calibration result
├── posterior.json       MCMC posterior (when run)
├── isotonic.json        Isotonic calibration model
├── de_result.json       DE result
├── ablation.json        Ablation report
├── sobol.json           Sobol sensitivity report
└── benchmark.json       Benchmark leaderboard

docs/
├── AUDIT.md             Full scientific audit + all 3 batches of findings
└── PROGRESS.md          This file
```

---

## Batch 4 — event-set expansion N=8 → N=21 (2026-06-09)

Single highest-leverage fix from `AUDIT.md` ("adding more historical events
would change this"). Same authoring convention as the original 8: shock
magnitudes describe source-side capacity offline from contemporaneous public
reporting; never derived from the observed targets. The new set deliberately
includes two near-miss events (Japan–Korea export controls 2019, Taiwan
drought 2021) so the benchmark also penalises false positives.

| Change | Where | Key result |
|---|---|---|
| +13 historical events (Thailand floods 2011 … Red Sea 2023) | `app/data/seed_data.py` | Benchmark now N=21 |
| SEIRS state-machine unit tests (15 tests: all transitions, modifiers, rerouting) | `tests/test_seis.py` | Previously zero coverage of the novel layer |
| Golden snapshot + winner lock updated to N=21 | `tests/test_reproducibility.py` | Explicit, reviewed numeric change |
| Dead scripts removed (`_smoke*.py`, `phase5_regenerate_state.py`) | `backend/scripts/` | Per SCIENTIFIC_STATUS.md disposition |
| Stale n=8 claims fixed (FAQ EN/RU, API docstrings) | `frontend/lib/ui-context.tsx`, `app/api/routes.py` | UI text matches live numbers |

### The honest headline (N=21, default config)

| Model | MAE | RMSE | Pearson | Spearman | R² |
|---|---|---|---|---|---|
| Linear Diffusion | **0.0130** | **0.0169** | **0.822** | **0.598** | **0.600** |
| Naive Persistence | 0.0168 | 0.0268 | 0.000 | 0.000 | 0.000 |
| Leontief I-O | 0.0180 | 0.0321 | -0.072 | 0.215 | -0.444 |
| GEDS SEIRS | 0.0216 | 0.0379 | 0.140 | 0.361 | -1.009 |

**The N=8 rank-correlation result (Spearman 0.83) did not survive the
expansion — it drops to 0.36 on N=21, i.e. it was largely a small-sample
artifact.** Naive persistence now beats GEDS on MAE. Linear diffusion's
signal, by contrast, holds up (Pearson 0.82). This is exactly why the
expansion was the right experiment: it falsified a result that looked
publication-ready at N=8. Next step is recalibration of the five engine
parameters against the expanded set (they were tuned in the N=8 era) and,
if that fails to close the gap, treating linear diffusion as the production
propagation kernel with SEIRS kept as a research layer.

### Batch 4 addendum — DE recalibration on N=21 (2026-06-09, same day)

Full 3-restart DE run on the expanded set (46 min): in-sample benchmark fit
improves to MAE 0.0108 / Pearson +0.85 / R² +0.67 — nominally **beating
linear diffusion (0.0130 / +0.82 / +0.60) for the first time**. Two honest
caveats before celebrating: (1) that is an in-sample comparison against a
parameter-free baseline, and (2) **4 of 5 parameters converged onto their
prior bounds** (`bullwhip_factor` = 2.0 exactly, `recovery_rate` = 0.01
exactly, `amplification_mu` ≈ 8.0, `inventory_scale` ≈ 2.0) — the optimizer
wants to leave the box, which is the classic signature of structural
misspecification rather than a well-identified optimum.

Verdict pending: `scripts/loo_de_validation.py` runs leave-one-out CV with
per-fold DE re-calibration (the fair, fully out-of-sample comparison) and
writes `data/calibration/loo_de_result.json`. If the out-of-sample MAE still
beats linear diffusion, the recalibration is real; if not, the in-sample win
was overfitting and the honest headline stays "the baseline wins".

### Batch 4 verdict — out-of-sample LOO-DE result (2026-06-09)

`scripts/loo_de_validation.py` (21 folds, per-fold DE re-calibration on the
other 20 events, fully out-of-sample pooled score):

| Model | MAE | RMSE | Pearson | Spearman | R² |
|---|---|---|---|---|---|
| GEDS SEIRS, LOO-recalibrated (out-of-sample) | **0.0115** | **0.0165** | 0.787 | 0.490 | **0.619** |
| Linear Diffusion (parameter-free) | 0.0130 | 0.0169 | **0.822** | **0.598** | 0.600 |
| GEDS SEIRS, default params | 0.0216 | 0.0379 | 0.140 | 0.361 | −1.009 |

**Split decision, honestly reported:** the recalibration is real — it survives
out-of-sample testing (MAE nearly halved, 0.0216 → 0.0115) and GEDS now beats
the baseline on every *error* metric. The baseline still wins both *ranking*
metrics (Pearson/Spearman). Worst misses are concentrated in pure-logistics
events (Yantian 0.057 pred vs 0.006 obs; Red Sea / Suez / Malaysia predicted
≈0) — the engine over-reacts to port shocks and under-couples chokepoint
nodes, which is the next structural target. Parameter-at-bounds caveat from
the in-sample run still applies and still argues for widening/regrounding the
priors before adopting these values as engine defaults.
