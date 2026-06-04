# Ensemble Forecasting — Monte Carlo Parameter Uncertainty

Generated: `2026-06-03T16:23:08.687573+00:00`


- **N ensemble samples:** 500
- **Sampling rule:** independent truncated Gaussians (clamped to prior ranges).
- **μ source:** `cmaes_best_params.json::best_params`
- **σ source:** `loeo_results.json::fold_variance` (LOEO fold std)
- **Graph:** OECD+WIOD spectrally normalised (ρ=1.0)
- **N events:** 21
- **Seed:** 20260529

## Sampling diagnostics

| Parameter | Calibrated μ | LOEO σ | Prior |
|---|---|---|---|
| `amplification_mu` | 0.05410 | 0.98275 | [0.0, 4.0] |
| `amplification_eps` | 0.10349 | 0.02121 | [0.01, 0.2] |
| `propagation_decay` | 0.50022 | 0.15638 | [0.5, 0.99] |
| `recovery_rate` | 0.21147 | 0.05067 | [0.01, 0.3] |
| `bullwhip_factor` | 1.60998 | 0.14827 | [1.0, 2.0] |
| `inventory_scale` | 1.18502 | 0.61040 | [0.3, 2.0] |
| `r_output_floor` | 0.25497 | 0.10384 | [0.05, 0.4] |

## Coverage diagnostic (calibrated)

- Observed value falls inside the ensemble 95 % prediction band for **0 / 21 = 0.0%** events.
- A well-calibrated forecast would land near 95 %. The actual coverage is the empirical calibration of the ensemble.

## Ensemble metric distribution (MAE / Pearson / R² over the 500 samples)

| Metric | mean | std | p2.5 | p50 | p97.5 |
|---|---|---|---|---|---|
| `mae` | 0.15913 | 0.00035 | 0.15826 | 0.15926 | 0.15938 |
| `rmse` | 0.26712 | 0.00024 | 0.26640 | 0.26722 | 0.26731 |
| `r_squared` | -0.48215 | 0.00271 | -0.48421 | -0.48326 | -0.47416 |
| `pearson` | 0.43800 | 0.02585 | 0.37916 | 0.44734 | 0.45478 |

## Per-event prediction bands (50 % and 95 %)

| Event | Observed | Mean pred | 50 % band | 95 % band | Obs in 95 % ? |
|---|---|---|---|---|---|
| 1. Dot-com Bubble Collapse & US Recession | 0.0480 | 0.00302 | [0.00300, 0.00300] | [0.00300, 0.00310] | NO |
| 2. Argentine Sovereign Default & Currency Cri | 0.1100 | 0.00020 | [0.00020, 0.00020] | [0.00020, 0.00020] | NO |
| 3. SARS Epidemic | 0.0260 | 0.00753 | [0.00730, 0.00750] | [0.00730, 0.00780] | NO |
| 4. Iraq War & Associated Oil Price Spike | 0.0050 | 0.00770 | [0.00770, 0.00770] | [0.00770, 0.00770] | NO |
| 5. Indian Ocean Earthquake and Tsunami | 0.1500 | 0.00232 | [0.00230, 0.00230] | [0.00230, 0.00240] | NO |
| 6. Hurricane Katrina & Rita | 0.0310 | 0.00446 | [0.00440, 0.00450] | [0.00440, 0.00460] | NO |
| 9. European Sovereign Debt Crisis | 0.2600 | 0.00030 | [0.00030, 0.00030] | [0.00030, 0.00030] | NO |
| 10. Arab Spring Political Upheaval | 0.5000 | 0.00030 | [0.00030, 0.00030] | [0.00030, 0.00030] | NO |
| 11. Tōhoku Earthquake, Tsunami & Fukushima Nuc | 0.0035 | 0.00324 | [0.00320, 0.00330] | [0.00320, 0.00330] | NO |
| 12. Russia Crimea Annexation & Western Sanctio | 0.0220 | 0.00060 | [0.00060, 0.00060] | [0.00060, 0.00060] | NO |
| 14. China Stock Market Crash | 0.0690 | 0.00970 | [0.00940, 0.00970] | [0.00930, 0.01020] | NO |
| 15. UK Brexit Referendum and Departure | 0.0700 | 0.00334 | [0.00310, 0.00340] | [0.00300, 0.00410] | NO |
| 16. US–China Trade War | 0.0260 | 0.00250 | [0.00250, 0.00250] | [0.00250, 0.00250] | NO |
| 21. Russia Invasion of Ukraine & Global Sancti | 0.0150 | 0.00020 | [0.00020, 0.00020] | [0.00020, 0.00020] | NO |
| 22. European Natural Gas & Energy Crisis | 0.0070 | 0.00100 | [0.00100, 0.00100] | [0.00090, 0.00100] | NO |
| 23. Post-COVID Global Inflation Surge & Centra | 0.0140 | 0.00230 | [0.00220, 0.00230] | [0.00210, 0.00265] | NO |
| 24. China Real Estate & Evergrande Crisis | 0.2750 | 0.04112 | [0.03790, 0.04110] | [0.03705, 0.05855] | NO |
| 26. Red Sea Houthi Attacks / Shipping Crisis | 0.5000 | 0.00130 | [0.00130, 0.00130] | [0.00130, 0.00130] | NO |
| 27. Panama Canal Drought & Traffic Restriction | 0.7300 | 0.03947 | [0.03940, 0.03950] | [0.03940, 0.03970] | NO |
| 28. Trump 2025 "Liberation Day" Tariffs & Trad | 0.0140 | 0.00428 | [0.00420, 0.00430] | [0.00420, 0.00440] | NO |
| 30. Global Food & Energy Crisis (Post-COVID /  | 0.6000 | 0.00450 | [0.00450, 0.00450] | [0.00450, 0.00450] | NO |

## Brutally honest verdict (one paragraph)

With the parameter-uncertainty model defined by the LOEO fold std, the ensemble 95 % band covers only **0.0% of observations** (0/21). A well-calibrated forecast would land near 95 %. This says the parameter perturbation produces predictions that remain near the calibrated near-zero baseline regardless of which sample is drawn — so the band itself is narrow, sits well below the observed distress magnitudes, and rarely contains the truth. In plain terms: the engine's output is dominated by the topology and the small amplification term it found, not by which corner of param space we sample. The ensemble narrative should be framed as 'predictions are robust to plausible re-calibration noise' — **not** as 'these intervals contain the realised loss with 95 % probability', because they manifestly do not.

## Files preserved (not overwritten)

- `benchmark_spectral_normalized.json`
- `bootstrap_results.json`
- `ablation_post_normalization.json`