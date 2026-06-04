# GEDS Benchmark v2 (N=42 Validation Expansion)

Run timestamp: `2026-05-26T18:10:34.178715+00:00`
Engine config: calibration_v2 DE best params (loaded from calibration_v2.json)
Engine graph: 40 nodes (default 40-node MVP)

## 1. Sample sizes

- **Total events in corpus:** 42 (`master_event_registry.csv`)
- **Events with a GDP target (peer-reviewed OR docx aggregate):** 40
- **Peer-reviewed targets:** 7
- **Targets with explicit uncertainty band:** 4
- **Engine mapping `OK`:** 11
- **Engine mapping `UNCERTAIN`:** 30
- **Scenario events (excluded):** 1
- **Benchmarked this run:** 11
  - Excluded for no target: 2
  - Excluded for no engine mapping: 29

## 2. Headline scores (with 95% bootstrap CIs on MAE)

| Model | N | MAE | MAE 95% CI | RMSE | R² | Pearson | MAPE % | Calib err | Skill |
|---|---|---|---|---|---|---|---|---|---|
| SEIRS-Bullwhip-Hysteresis (GEDS) | 11 | 0.1469 | [0.0250, 0.2948] | 0.2727 | -0.215 | 0.829 | 83.2 | 0.0079 | -0.215 |
| Leontief | 11 | 0.1490 | [0.0277, 0.2989] | 0.2747 | -0.233 | 0.801 | 68.2 | 0.0079 | -0.233 |
| Linear Diffusion | 11 | 0.1479 | [0.0261, 0.2962] | 0.2729 | -0.217 | 0.791 | 74.1 | 0.0082 | -0.217 |
| Naive Persistence | 11 | 0.2006 | [0.1287, 0.2942] | 0.2473 | 0.000 | nan | 1043.4 | 0.0000 | +0.000 |

**Winner by MAE:** `SEIRS-Bullwhip-Hysteresis (GEDS)`
**Winner by R²:** `SEIRS-Bullwhip-Hysteresis (GEDS)`

## 3. Model ranking

By MAE (lower is better):

1. **SEIRS-Bullwhip-Hysteresis (GEDS)** — MAE 0.1469, R² -0.215
2. **Linear Diffusion** — MAE 0.1479, R² -0.217
3. **Leontief** — MAE 0.1490, R² -0.233
4. **Naive Persistence** — MAE 0.2006, R² 0.000

## 4. Where GEDS wins (per-event)

Events where SEIRS-Bullwhip-Hysteresis is the *single closest* model: **4** / 11

- Event 3 (SARS Epidemic): target=+0.026, SEIRS=+0.011, LinDiff=+0.010, Leontief=+0.010
- Event 14 (China Stock Market Crash): target=+0.069, SEIRS=+0.015, LinDiff=+0.013, Leontief=+0.014
- Event 15 (UK Brexit Referendum and Departure): target=+0.070, SEIRS=+0.027, LinDiff=+0.016, Leontief=+0.005
- Event 30 (Global Food & Energy Crisis (Post-COVID ): target=+0.600, SEIRS=+0.034, LinDiff=+0.018, Leontief=+0.025

## 5. Where GEDS fails

Events where another model is closer: **7** / 11

- Event 4 (Iraq War & Associated Oil Price Spike): target=+0.005, SEIRS gap=0.002, Leontief closer (gap 0.002)
- Event 6 (Hurricane Katrina & Rita): target=+0.031, SEIRS gap=0.024, Linear closer (gap 0.022)
- Event 11 (Tōhoku Earthquake, Tsunami & Fukushima N): target=+0.004, SEIRS gap=0.007, Leontief closer (gap 0.000)
- Event 21 (Russia Invasion of Ukraine & Global Sanc): target=+0.015, SEIRS gap=0.013, Linear closer (gap 0.012)
- Event 24 (China Real Estate & Evergrande Crisis): target=+0.275, SEIRS gap=0.217, Leontief closer (gap 0.217)
- Event 27 (Panama Canal Drought & Traffic Restricti): target=+0.730, SEIRS gap=0.666, Linear closer (gap 0.651)
- Event 28 (Trump 2025 "Liberation Day" Tariffs & Tr): target=+0.014, SEIRS gap=0.006, Linear closer (gap 0.004)

## 6. Strongest events (peer-reviewed + smallest SEIRS error)

| Event | Target | SEIRS | Gap |
|---|---|---|---|
| 11. Tōhoku Earthquake, Tsunami & Fukush | +0.004 | +0.011 | 0.007 |
| 21. Russia Invasion of Ukraine & Global | +0.015 | +0.002 | 0.013 |

## 7. Weakest events (largest SEIRS error)

- Event 27 (Panama Canal Drought & Traffic Restricti): target=+0.730, SEIRS=+0.064, gap=0.666
- Event 30 (Global Food & Energy Crisis (Post-COVID ): target=+0.600, SEIRS=+0.034, gap=0.566
- Event 24 (China Real Estate & Evergrande Crisis): target=+0.275, SEIRS=+0.058, gap=0.217
- Event 14 (China Stock Market Crash): target=+0.069, SEIRS=+0.015, gap=0.055
- Event 15 (UK Brexit Referendum and Departure): target=+0.070, SEIRS=+0.027, gap=0.043
- Event 6 (Hurricane Katrina & Rita): target=+0.031, SEIRS=+0.007, gap=0.024
- Event 3 (SARS Epidemic): target=+0.026, SEIRS=+0.011, gap=0.015
- Event 21 (Russia Invasion of Ukraine & Global Sanc): target=+0.015, SEIRS=+0.002, gap=0.013
- Event 11 (Tōhoku Earthquake, Tsunami & Fukushima N): target=+0.004, SEIRS=+0.011, gap=0.007
- Event 28 (Trump 2025 "Liberation Day" Tariffs & Tr): target=+0.014, SEIRS=+0.008, gap=0.006

## 8. Unsupported events (cannot be benchmarked)

**33** of 42 events were excluded from this benchmark:

- 30 events with `UNCERTAIN` graph mapping (sectors outside engine `Industry` enum)
- 1 forward-looking scenario events
- 2 events with no GDP target at all

Top unsupported events (UNCERTAIN mapping with peer-reviewed targets — should be unblocked first):

- Event 7 (Global Financial Crisis): peer-reviewed but no engine sector match
- Event 17 (COVID-19 Global Pandemic): peer-reviewed but no engine sector match
- Event 18 (Global Semiconductor Chip Shortage): peer-reviewed but no engine sector match
- Event 19 (Ever Given Suez Canal Blockage): peer-reviewed but no engine sector match
- Event 22 (European Natural Gas & Energy Crisis): peer-reviewed but no engine sector match

## 9. Risk of overfitting

- **Engine calibration set:** the calibrated params used here ({'propagation_decay': 0.9890986444141316, 'rerouting_efficiency': 0.55, 'amplification_mu': 3.9941650267701454, 'amplification_eps': 0.19996098944271445, 'recovery_rate': 0.010108959224208736, 'stochastic_sigma': 0.0, 'seed': None, 'seis_enabled': True, 'adaptive_rerouting': True, 'bullwhip_factor': 1.1252532884436197, 'r_output_floor': 0.3, 'inventory_scale': 1.0, 'distress_base': 0.4, 'distress_week_threshold': 6, 'sanity_max_loss_fraction': 0.15}) were fit on the same N=11 engine-eligible subset that we benchmark on. **This is in-sample.** True out-of-sample claim requires a held-out fold.
- **Sample size:** N=11 is small. The bootstrap CIs above are wide.
- **Industry coverage:** all benchmarked events touch a narrow set (semis, auto, electronics, energy). Cross-sector generalisation is untested.
- **Target derivation:** events without peer-reviewed targets use docx aggregates (the same numbers the original docx extraction recorded). For those, the 'target' is itself a single source, not a triangulated estimate.

## 10. Publication-quality conclusions

What can be defensibly claimed:

- **GEDS, Leontief, and Linear Diffusion all outperform Naive Persistence on MAE** (skill scores: -0.215, -0.233, -0.217).
- **All three non-naive models track event ranking** (Pearson ≈ 0.83–0.79).
- **None of the three has positive R²** (-0.215 for SEIRS) — the models capture *ordering* but miss *magnitudes*.

What CANNOT be claimed:

- 'GEDS is the most accurate model on historical events.' — current MAE differences are within bootstrap CIs.
- 'GEDS generalises to N=42 events.' — only ~11 of 42 were benchmarked.
- 'GEDS is publication-grade on the current N.' — N is too small for strong claims; bootstrap CIs overlap.
