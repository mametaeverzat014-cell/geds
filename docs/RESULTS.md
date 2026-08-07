# GEDS — headline results (generated)

> GENERATED FILE — regenerate with `python -m scripts.results_onepager`;
> never hand-edit. Sources: live engine runs plus `significance.json`
> (seed 20260718, 10000 bootstrap / 20000 perms,
> generated 2026-08-07), `loo_de_result.json`
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

**Pairwise differences (paired bootstrap + sign-flip permutation, Holm-corrected across all 6 pairs):**

| Pair (first − second) | ΔMAE [95% CI] | p raw | p Holm | verdict |
|---|---|---|---|---|
| GEDS − Leontief | 0.0074 [-0.0031, 0.0218] | 0.42 | 1.00 | n.s. |
| GEDS − LinearDiffusion | 0.0071 [-0.0018, 0.0182] | 0.21 | 1.00 | n.s. |
| GEDS − NaivePersistence | 0.0034 [-0.0085, 0.0191] | 0.58 | 1.00 | n.s. |
| Leontief − LinearDiffusion | -0.0003 [-0.0120, 0.0111] | 0.97 | 1.00 | n.s. |
| Leontief − NaivePersistence | -0.0040 [-0.0083, 0.0005] | 0.09 | 0.54 | n.s. |
| LinearDiffusion − NaivePersistence | -0.0037 [-0.0143, 0.0090] | 0.58 | 1.00 | n.s. |

**Reading:** 0 of 6 pairwise magnitude differences are significant at N=27. The six pairs are published as one table and so form one family of tests; the Holm-adjusted column is the operative one. Single-number validation cannot rank these models — which is what motivates the trajectory axes below.

## 2. Trajectory shape (Track B, node-level; the axes only GEDS attempts)

| Dimension | n | Spearman [95% CI] | family-wise 98.3% CI | MAE | survives correction |
|---|---|---|---|---|---|
| peak magnitude | 6 | 0.71 [-0.09, 1.00] | [-1.00, 1.00] | 0.40 | no |
| weeks to peak | 15 | 0.69 [0.20, 0.87] | [0.00, 0.90] | 7.07 | no |
| recovery weeks | 11 | 0.88 [0.56, 0.99] | [0.40, 1.00] | 8.55 | **yes** |

**Reading:** the three dimensions are one published family, so a 95% interval on each does not give 95% confidence in all three. 1 of 3 excludes zero at the family-wise level: recovery_weeks. This is the strongest quantitative result in the project.

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

**Robustness — is this a threshold artifact?** v3 runs ~4× hot in magnitude, so a fixed reach threshold could favour it mechanically. Sweeping the threshold across two orders of magnitude (`spatial_recall_robustness.json`):

| reach threshold | v2 recall | v3 recall | v3 − v2 | v3 / v2 |
|---|---|---|---|---|
| 0.001 | 0.571 (20/35) | 0.895 (34/38) | +0.324 | 1.6× |
| 0.005 | 0.400 (14/35) | 0.816 (31/38) | +0.416 | 2.0× |
| 0.01 *(published)* | 0.286 (10/35) | 0.789 (30/38) | +0.503 | 2.8× |
| 0.02 | 0.171 (6/35) | 0.711 (27/38) | +0.540 | 4.2× |
| 0.0388 *(scale-corrected)* | 0.143 (5/35) | 0.526 (20/38) | +0.383 | 3.7× |
| 0.05 | 0.086 (3/35) | 0.474 (18/38) | +0.388 | 5.5× |
| 0.1 | 0.086 (3/35) | 0.421 (16/38) | +0.335 | 4.9× |

v3 leads at every threshold tested, including the scale-corrected point 0.0388 (= published threshold ÷ k, k=0.2578). The structural result is not a scale artifact.

## 5. Component ablation — and why the table is not a ranking

| Variant | MAE | ΔMAE vs full [95% CI] | p Holm | significant |
|---|---|---|---|---|
| full | 0.0242 | — | — | — |
| no_seis | 0.0166 | -0.0076 [-0.0206, +0.0018] | 1.00 | n.s. |
| no_bullwhip | 0.0266 | +0.0023 [-0.0009, +0.0079] | 1.00 | n.s. |
| no_adaptive_rerouting | 0.0242 | -0.0000 [-0.0001, +0.0001] | 1.00 | n.s. |
| no_r_state_floor | 0.0169 | -0.0074 [-0.0200, +0.0018] | 1.00 | n.s. |
| with_per_node_recovery | 0.0233 | -0.0009 [-0.0029, +0.0001] | 1.00 | n.s. |
| naive_diffusion | 0.0171 | -0.0071 [-0.0182, +0.0018] | 1.00 | n.s. |

**Reading:** NO ablation delta is distinguishable from zero after Holm correction: at N=27 this benchmark cannot tell any engine component apart from any other. The point-estimate ordering in this table is not a ranking of components; every delta is smaller than the benchmark's own minimum detectable effect (0.018 MAE at 80% power, power_analysis.json).

Negative ΔMAE means the variant had *lower* error than the full engine — i.e. the component removed was costing accuracy. Point estimates put the SEIRS state machine and the hysteresis floor in that category, but no delta clears the correction, so the honest statement is that this benchmark cannot resolve any component's contribution.

## 6. Parameter identifiability

| Parameter | global fit | prior box | pinned to bound | LOO range | range/median |
|---|---|---|---|---|---|
| `amplification_mu` | 7.9222 | [0.1, 8] | **yes** | [0.1706, 7.979] | 34.9× |
| `bullwhip_factor` | 2.0000 | [1, 2] | **yes** | [1.062, 1.704] | 0.6× |
| `recovery_rate` | 0.0100 | [0.01, 0.3] | **yes** | [0.01, 0.0181] | 0.6× |
| `inventory_scale` | 1.9548 | [0.3, 2] | no | [1.321, 1.929] | 0.3× |
| `distress_base` | 0.3787 | [0.2, 0.7] | no | [0.4346, 0.6971] | 0.4× |

**Reading:** 3/5 parameters are pinned to their search-box bounds and 1/5 move by more than their own median when a single event of 27 is removed. The five-parameter engine is NOT identified by this benchmark: the fitted values report the prior box and the resampling noise, not the data. Any claim that rests on a specific calibrated parameter value is unsupported.

The global fit falls outside the entire leave-one-out range for 3 of 5 parameters, and only 33% of DE restarts converged — both signatures of a flat or multimodal loss surface.

## 7. Figures

Regenerate with `python -m scripts.isef_figures` (PNG + numeric CSV pairs in `backend/data/calibration/figures/`):

- `parity_forest` — §1 pairwise CIs as a forest plot
- `pred_vs_obs` — §1 per-model scatter, N=27
- `timing_ramp` — §2 weeks_to_peak before/after the ramp
- `spatial_recall` — §4 per-event v2→v3 dumbbell

## 8. What this benchmark can and cannot support

Four independent lines of evidence converge on one ceiling:

1. **Power** — every observed pairwise |ΔMAE| is below its minimum detectable effect; ~166 events would be needed to resolve the GEDS/Leontief gap (`power_analysis.json`).
2. **Multiplicity** — 0/6 model pairs and 0/6 ablation deltas survive Holm correction.
3. **Identifiability** — 3/5 parameters are pinned to their search-box bounds; one moves 35× its own median under leave-one-out.
4. **Parsimony** — on the dense graph a single scale parameter outperforms five tuned ones in point terms (`v3_calibration_result.json`).

What survives all of it: the **recovery-duration ordering** (Track B, family-wise CI excludes zero) and the **structural graph result** (§4, robust across the full threshold sweep). Those two are the defensible contributions; the magnitude leaderboard is a measured null.

