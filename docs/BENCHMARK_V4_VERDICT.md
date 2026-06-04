# GEDS Benchmark V4 — Scientific Verdict

**Mission:** STRICT RESEARCH MISSION — GEDS BENCHMARK V4.
**Rules enforced verbatim:** *never fabricate data; never create synthetic benchmark targets; preserve NULL when mapping is impossible; every benchmark event must have provenance; if confidence is low, mark UNMAPPABLE instead of guessing.*

**Date:** 2026-06-03
**Inputs:** `EVENT_EXPANSION_REPORT.md`, `event_expansion_candidates.csv` (90 candidates). `RECOMMENDED_BENCHMARK_CORPUS.md` **was not provided / does not exist** — not used.
**Artifacts produced this mission:**
`docs/event_mapping_report.md` (Phase 1), `backend/data/csv/benchmark_event_matrix_v4.csv` (Phase 2),
`backend/data/calibration/{benchmark_v4.json, bootstrap_v4.json, uncertainty_v4.json, loeo_v4.json}` (Phase 3).

---

## 0. What "expansion" actually yielded (Phases 1–2 recap)

The expansion premise — grow the benchmark from N=21 to N≈80–90 — **is not achievable from the supplied candidates without fabrication.** Of the 90 expansion candidates:

| Category | Count |
|---|---|
| Total candidates | 90 |
| Duplicates of an event already in the registry | 35 |
| Money / physical units only (no GDP %) | 37 |
| Carry an actual extracted GDP % phrase | 22 |
| **MAPPED** (clean single-country national-output target) | **1** |
| **PARTIAL** (ambiguous / reconstructed; sensitivity-only) | **2 candidate rows → 6 country-events** |
| **UNMAPPABLE** | **87** |

Almost every GDP-bearing candidate reports a **non-comparable figure-type** — damages-as-%GDP (e.g. Thailand floods "12.6% of GDP"), institution-size-to-GDP ("20% of Swiss GDP"), sub-national figures ("13% of Maryland's GDP", "60% of Puerto Rico's GDP"), growth-rate deltas ("GDP growth was 2.4%"), or cumulative multi-year collapses ("-46.7%"). The benchmark target is specifically a **single-country annual national-output loss fraction**; none of those types are comparable to it.

**Net engine-eligible expansion: 21 → 22 (primary) or 21 → 28 (maximally generous).** Three evaluation corpora are therefore defined and run under one frozen calibration (the controlled-comparison design — only the event set varies):

- **current** — N=21 (the Mission-1 corpus, unchanged).
- **v4_primary** — N=22 = current + the one cleanly-MAPPED event (1994 Mexican Peso Crisis, WB-projected −4.8% 1995 output, MEX:banking).
- **v4_max** — N=28 = v4_primary + 6 PARTIAL events (Turkey Izmit 1999; Asian Financial Crisis 1997 for KOR/THA/MYS/IDN/PHL), targets drawn from World Bank GEP 1998-99 country tables and flagged approximate.

---

## PHASE 4 — Quantitative comparison (current N=21 vs expanded N=22 / N=28)

All models share the frozen Mission-1 GEDS configuration and Linear-Diffusion parameters (α=0.3, β=0.03) on the spectrally-normalised OECD+WIOD graph (1204 nodes, ρ=1.0). Bootstrap = 5000 non-parametric resamples, seed 20260603.

### 4.1 Point accuracy

| Metric | Model | current (N=21) | v4_primary (N=22) | v4_max (N=28) |
|---|---|---|---|---|
| **MAE** ↓ | GEDS-SEIRS | 0.15940 | 0.15431 | 0.13526 |
|  | Leontief | **0.15708** | **0.15210** | **0.13351** |
|  | Linear-Diffusion | 0.21951 | 0.21563 | 0.17871 |
|  | Naive-mean | 0.17829 | 0.17310 | 0.14610 |
| **RMSE** ↓ | GEDS-SEIRS | 0.26732 | 0.26137 | 0.23450 |
|  | Naive-mean | **0.21941** | **0.21576** | **0.19616** |
| **R²** ↑ | GEDS-SEIRS | −0.4843 | −0.4674 | −0.4291 |
|  | Leontief | −0.4672 | −0.4505 | −0.4129 |
|  | Linear-Diffusion | −0.5371 | −0.5348 | −0.4722 |
|  | Naive-mean | 0.0 | 0.0 | 0.0 |
| **Pearson r** ↑ | GEDS-SEIRS | 0.4557 | 0.4630 | 0.4868 |
|  | Leontief | 0.3382 | 0.3467 | 0.3752 |
|  | Linear-Diffusion | −0.2697 | −0.2743 | −0.1441 |

**Reading the MAE trend.** GEDS MAE falls from 0.159 → 0.154 → 0.135 as events are added — but this is **not model improvement**. The Naive-mean MAE falls in lockstep (0.178 → 0.173 → 0.146), as does Leontief's. The added events (Mexico 0.048, Turkey 0.05, Philippines 0.005, Malaysia 0.05, …) have **small targets close to the near-zero value every structural model predicts**, so they mechanically lower the average error scale for everyone. The *ranking* is unchanged. RMSE confirms this: the **Naive-mean has the lowest RMSE in every corpus**, and every structural model's R² is **strongly negative** throughout — i.e. all of them are worse than simply predicting the mean under squared error.

### 4.2 Confidence intervals (GEDS MAE, 5000-resample bootstrap)

| Corpus | GEDS MAE point | 95% CI | GEDS Pearson 95% CI |
|---|---|---|---|
| current (21) | 0.1594 | [0.0765, 0.2567] | [−0.378, 0.817] |
| v4_primary (22) | 0.1543 | [0.0724, 0.2508] | [−0.346, 0.824] |
| v4_max (28) | 0.1353 | [0.0696, 0.2110] | [−0.267, 0.832] |

The CIs are wide and overlap heavily across corpora. The Pearson CI **includes 0** in all three corpora — the apparent rank-correlation (r≈0.46–0.49) is **not significantly different from zero** even after expansion.

### 4.3 Pairwise significance — paired bootstrap of ΔMAE = MAE(baseline) − MAE(GEDS)

(ΔMAE > 0 ⇒ GEDS better; "frac" = fraction of resamples where GEDS strictly wins; significant if 0 ∉ CI.)

| Comparison | Corpus | ΔMAE point | 95% CI | frac GEDS better | Significant? | Winner |
|---|---|---|---|---|---|---|
| GEDS vs **Leontief** | current | −0.00232 | [−0.0055, −0.0003] | 0.000 | **yes** | **Leontief** |
|  | v4_primary | −0.00221 | [−0.0052, −0.0003] | 0.000 | **yes** | **Leontief** |
|  | v4_max | −0.00175 | [−0.0041, −0.0002] | 0.0002 | **yes** | **Leontief** |
| GEDS vs **Linear-Diffusion** | current | +0.06012 | [0.0049, 0.1121] | 0.984 | **yes** | **GEDS** |
|  | v4_primary | +0.06131 | [0.0089, 0.1100] | 0.988 | **yes** | **GEDS** |
|  | v4_max | +0.04345 | [0.0005, 0.0851] | 0.977 | **yes** | **GEDS** |
| GEDS vs **Naive-mean** | current | +0.01889 | [−0.0372, 0.0708] | 0.748 | no | tie |
|  | v4_primary | +0.01878 | [−0.0345, 0.0688] | 0.751 | no | tie |
|  | v4_max | +0.01084 | [−0.0280, 0.0481] | 0.714 | no | tie |

**The three verdicts are identical in all three corpora.** Expansion did not flip, narrow-to-significance, or otherwise alter a single pairwise conclusion.

### 4.4 Coverage / calibration of uncertainty

| Diagnostic | current (21) | v4_primary (22) | v4_max (28) |
|---|---|---|---|
| Empirical 95% PI coverage (pred ± 1.96·resid_std) | 17/21 = 0.810 | 18/22 = 0.818 | 24/28 = 0.857 |
| Monte-Carlo ensemble coverage (obs in p2.5–p97.5) | **0/21 = 0.000** | 0/21 (carried) | 0/21 (carried) |
| SVD condition number κ | 34.29 | 34.29 | 34.29 |
| Effective rank / n_params | 7 / 7 | 7 / 7 | 7 / 7 |

The empirical Gaussian-proxy band looks ~80–86% covered, but the **parameter-uncertainty ensemble covers 0%** of observations: when the calibrated parameter posterior (from LOEO fold variance) is propagated, the model's own predictive distribution never contains the truth. That is a severe mis-calibration and is **invariant to the +1…+7 event change** (it is a property of the model + frozen calibration, not of the corpus size).

### 4.5 Leave-One-Event-Out cross-validation

Mission-1 LOEO (5 folds, per-fold recalibration): **LOEO-MAE = 0.0646, LOEO-R² = −1.476, LOEO-Pearson = −0.807**, overfitting gap ≈ 0. The negative held-out R² and **negative** held-out Pearson mean that, out-of-sample, the model's event-to-event ordering is *anti-correlated* with truth — it generalises no structure.

**V4 LOEO (6 folds = new Mexico event + 5 existing, per-fold CMA-ES recalibration, `loeo_v4.json`):** **LOEO-MAE = 0.0619 (std 0.0509), RMSE = 0.0801**, train-MAE mean 0.1586, overfitting gap **−0.097** (held-out error *lower* than train). Per-fold held-out prediction vs observed:

| Fold | Held-out event | pred | obs | abs err |
|---|---|---|---|---|
| 0 | 1994 Mexico Peso Crisis | 0.0004 | 0.048 | 0.0476 |
| 1 | Dot-com Collapse | 0.0031 | 0.048 | 0.0449 |
| 2 | Argentine Default | 0.0002 | 0.110 | 0.1098 |
| 3 | SARS Epidemic | 0.0073 | 0.026 | 0.0187 |
| 4 | Iraq War / Oil Spike | 0.0077 | 0.005 | 0.0027 |
| 5 | Indian Ocean Tsunami | 0.0023 | 0.150 | 0.1477 |

This number must not be read as success. **Every recalibrated fold predicts ≈0** (0.0002–0.0077), so the model has no out-of-sample dynamic range. The reason LOEO-MAE (0.062) looks far better than the in-corpus MAE (~0.15) is purely that the six held-out targets are themselves small (mean |obs| = 0.0645) — a **constant zero-predictor scores MAE = 0.0645 on the identical folds**, so GEDS beats "predict nothing" by only 0.0026 (≈4%) while reproducing none of the cross-event variation. The **negative overfitting gap** confirms this is a target-size artifact, not generalization: the held-out events happen to be the easy (small-target) ones. This is fully consistent with Mission-1 LOEO's negative held-out Pearson (−0.807) — out-of-sample, GEDS generalises no usable structure.

---

## PHASE 5 — Scientific verdict

### Q1. Does increasing the event count materially change the conclusions?
**No.** Going 21 → 22 → 28 leaves every pairwise verdict identical (§4.3), every model's R² strongly negative (§4.1), the Pearson CI still spanning 0 (§4.2), and the ensemble coverage at 0% (§4.4). MAE drops only because the added events are small-target "easy" cases that lower the error scale for *all* models equally, including Naive. More fundamentally, the count **cannot** be pushed materially higher: the candidate pool is exhausted at +1 clean event (+6 generous), so "more events" is not an available lever without fabricating targets.

### Q2. Does GEDS outperform Leontief?
**No — Leontief is significantly better in every corpus.** ΔMAE(Leontief−GEDS) is negative with a 95% CI strictly below 0 in all three corpora, and GEDS wins in essentially 0% of bootstrap resamples (0.000 / 0.000 / 0.0002). GEDS's nominally higher Pearson (0.46 vs 0.34) is not significant (CI includes 0) and does not translate into lower error. The expensive SEIRS-bullwhip-hysteresis machinery is **beaten by a one-line Leontief inverse**.

### Q3. Does GEDS outperform Linear-Diffusion?
**Yes — significantly, in every corpus.** ΔMAE(Linear−GEDS) ≈ +0.043…+0.061 with a 95% CI strictly above 0 and GEDS winning ~98% of resamples. This is GEDS's one genuine, robust win. Caveat: Linear-Diffusion is a weak straw-man here — it systematically *over*-predicts (its predictions sit near 0.18–0.32 while most targets are small), so beating it shows mainly that GEDS's near-zero predictions are closer to small targets, not that GEDS captures propagation structure.

### Q4. Are the previous uncertainty conclusions still valid?
**Yes, fully.** κ = 34.29 (moderately ill-conditioned), effective rank 7/7 (formally distinguishable but **practically weakly-determined**), Monte-Carlo ensemble coverage 0/21, and negative LOEO R²/Pearson all persist unchanged — they are properties of the model and frozen calibration, essentially invariant to a 1–7 event change. Expansion neither rescues nor worsens the identifiability/calibration story; it confirms it.

### Q5. Is sample size still the dominant limitation?
**Yes — and it is now demonstrably a hard ceiling, not just a small-N inconvenience.** The benchmark cannot grow past ~22–28 engine-eligible events without either (a) admitting non-comparable figure-types (damages-%GDP, debt ratios, sub-national, growth deltas) or (b) fabricating targets — both forbidden. With N this small and targets this skewed (a few large values like 0.5, 0.6, 0.73 dominate), MAE/R² are dominated by a handful of points and CIs are uninformative. Sample size is the binding constraint, **and the data needed to relieve it does not exist in comparable form.**

### Q6. Is GEDS publication-ready after benchmark expansion?
**No.** Against an honestly-built benchmark a model is publication-ready only if it (i) beats the strongest cheap baseline, (ii) beats the naive mean significantly, (iii) achieves R² > 0 / positive out-of-sample skill, and (iv) has calibrated uncertainty. GEDS fails (i) — loses to Leontief; fails (ii) — statistically tied with Naive; fails (iii) — R² ≈ −0.43…−0.48 in-sample and −1.48 in LOEO with *negative* held-out correlation; and fails (iv) — 0% ensemble coverage. Winning only against a deliberately weak diffusion baseline is not sufficient.

---

## BRUTALLY HONEST CONCLUSION

**Benchmark expansion *weakens* the scientific case for GEDS.**

The expansion was meant to be GEDS's best opportunity: more events, more statistical power, a chance to convert a suggestive Pearson correlation into a defensible result. Instead it did two things, both unfavourable.

1. **It removed the "small-N excuse."** Every previous weak result was defensible with "N=21 is too small to conclude anything." We now know the corpus is *intrinsically* capped at ~22–28 comparable events — the supplied 90-candidate pool, after honest auditing, yields exactly **one** clean new event and six approximate ones. The small-N limitation is therefore permanent and structural, not a temporary data-collection gap. "We just need more events" is no longer a viable defence, because the events do not exist in comparable form.

2. **The extra events confirmed, with more data, the unfavourable rankings.** Across N=21, 22, and 28 the story never changes: **GEDS is statistically indistinguishable from predicting the mean, is significantly *worse* than a plain Leontief inverse, and beats only a straw-man linear-diffusion model.** Its in-sample R² is strongly negative and its out-of-sample (LOEO) correlation is negative — the model carries no transferable predictive structure at the benchmarked scale, and its parameters are practically unidentifiable (0% ensemble coverage). Adding events did not move any of this; it merely made it harder to dismiss as noise.

The one defensible positive — GEDS beats Linear-Diffusion — survives expansion but is the weakest possible claim, since that baseline fails in the opposite direction (gross over-prediction).

**Bottom line:** GEDS is **not publication-ready as a predictive model** of national output loss on this benchmark. The honest contribution of this mission is negative and methodological: it proves the benchmark cannot be expanded into significance without fabrication, and that under a fair, frozen-calibration comparison a trivial Leontief baseline is the better model. Any publication should be reframed around (a) the rigorously-audited (un)mappability of macro-shock events to I-O graph targets, and (b) the controlled-comparison finding that the complex dynamics buy nothing over Leontief — not around GEDS as a validated forecasting engine.

_No synthetic targets were created at any stage. NULL/UNMAPPABLE was preserved wherever a comparable national-output figure could not be sourced. All targets trace to a cited source._
