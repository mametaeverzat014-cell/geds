# Post-Normalisation Ablation — OECD+WIOD (ρ=1.0)

Generated: `2026-05-29T17:35:44.779285+00:00`

- **Graph:** OECD+WIOD spectrally normalised (ρ before = 0.7409, scale = 1.3497, ρ after = 1.0).
- **Events:** 21 (engine sector/graph filter on 42-event corpus).
- **Calibration:** loaded verbatim from `cmaes_best_params.json` (the same diagnostic-budget CMA-ES run that produced the spectral-normalised benchmark; best composite loss 0.5652).

## Brutally honest verdict (one paragraph)

At the calibrated point, every named mechanism (SEIRS, bullwhip, hysteresis, network
amplification) is **statistically and numerically inert on this corpus**. Turning each
component off changes per-event predictions by at most 0.0001 and aggregate MAE by 0
to the fourth decimal. The reason is mechanical: CMA-ES drove `amplification_mu` to
0.054 — small enough that the amplification term contributes <1 % of each prediction
— so the engine reduces to a slow linear diffusion of a tiny inbound shock. Predicted
losses average **0.0064**; observed losses average **0.1655**. The model therefore
under-predicts by a factor of **~26×**, which means its MAE (0.1594) is almost entirely
"distance from zero" — the zero-predictor MAE on this corpus is 0.1655, so calibrated
GEDS beats predicting-zero by 0.006. Ablating any combination of SEIRS / bullwhip /
hysteresis / amp on top of that floor produces no movement, because there is no signal
in the prediction for those mechanisms to amplify or distort. The honest publication
claim is: **on N=21 engine-eligible events at ρ=1.0, GEDS reduces to spectrally-normalised
linear diffusion at the calibrated point, and the four marketed mechanisms cannot be
shown to contribute.**

## Phase 1 — 7-configuration ablation (95 % bootstrap CIs)

| Config | MAE | MAE 95% CI | R² | Pearson | Pearson 95% CI |
|---|---|---|---|---|---|
| `full_geds` | 0.15940 | [0.07486, 0.24432] | -0.4843 | +0.4557 | [-0.3963, 0.8096] |
| `no_seirs` | 0.15940 | [0.07486, 0.24432] | -0.4843 | +0.4557 | [-0.3963, 0.8096] |
| `no_bullwhip` | 0.15940 | [0.07486, 0.24432] | -0.4843 | +0.4557 | [-0.3963, 0.8096] |
| `no_hysteresis` | 0.15940 | [0.07486, 0.24432] | -0.4843 | +0.4557 | [-0.3963, 0.8096] |
| `no_network_amp` | 0.15940 | [0.07486, 0.24432] | -0.4843 | +0.4561 | [-0.3963, 0.8096] |
| `diffusion_only` | 0.15940 | [0.07487, 0.24432] | -0.4844 | +0.4560 | [-0.3964, 0.8094] |
| `amplification_only` | 0.15940 | [0.07486, 0.24432] | -0.4843 | +0.4557 | [-0.3963, 0.8096] |

### Reference baselines (from `benchmark_spectral_normalized.json`)

| Model | MAE | Pearson |
|---|---|---|
| Leontief (parameter-free) | 0.15708 | +0.3382 |
| Linear Diffusion (α=0.3, β=0.03 grid-tuned) | 0.21951 | -0.2697 |
| Naive Persistence (predict mean) | 0.17829 | 0.0 |
| **Zero predictor** (sanity floor) | 0.16550 | – |

## Phase 2 — Per-component contribution

Positive ΔMAE = removing the component **raises** error → component helps the model.
Negative ΔMAE = removing the component **lowers** error → component hurts the model.

| Component removed | ΔMAE | ΔPearson | ΔR² | Verdict |
|---|---|---|---|---|
| `no_seirs` | +0.00000 | +0.0000 | +0.0000 | decorative |
| `no_bullwhip` | +0.00000 | +0.0000 | +0.0000 | decorative |
| `no_hysteresis` | +0.00000 | +0.0000 | +0.0000 | decorative |
| `no_network_amp` | +0.00000 | +0.0004 | +0.0000 | decorative |

### Interaction effects

- `diffusion_only` (all 4 OFF) MAE = 0.15940
- `amplification_only` (3 OFF, mu retained) MAE = 0.15940
- `full_geds` (all 4 ON) MAE = 0.15940
- Gain from network amplification alone (`diffusion_only` → `amplification_only`): **+0.00000**
- Gain from SEIRS+bullwhip+hysteresis on top of amp (`amplification_only` → `full_geds`): **+0.00000**
- Gain from full GEDS over diffusion-only: **+0.00000**

### Numerical proof that mechanisms are inert

Per-event max |prediction difference vs `full_geds`| across the 21 events:

| Config | max |Δprediction| |
|---|---|
| `no_seirs` | 0.000000 |
| `no_bullwhip` | 0.000000 |
| `no_hysteresis` | 0.000000 |
| `amplification_only` | 0.000000 |
| `no_network_amp` | 0.000100 |
| `diffusion_only` | 0.000100 |

Disabling SEIRS, bullwhip, and hysteresis produces **bit-identical predictions** at
the calibrated point. Only disabling `amplification_mu` moves any prediction at all,
and the largest single-event movement is 0.0001 (i.e. 0.01 %-of-output).

### Why everything is decorative — the diagnosis

| Quantity | Value |
|---|---|
| Observed loss mean (n=21) | 0.1655 |
| Observed loss median | 0.0480 |
| Observed loss max | 0.7300 |
| `full_geds` predicted mean | 0.0064 |
| `full_geds` predicted median | 0.0030 |
| `full_geds` predicted max | 0.0394 |
| Predicted/observed mean ratio | 0.0384 (predictions ~26× smaller) |
| Zero-predictor MAE | 0.16550 |
| `full_geds` MAE | 0.15940 |
| Gain over zero-predictor | 0.00610 |

The calibrated `amplification_mu = 0.054` and `amplification_eps = 0.103` produce
predicted-loss magnitudes that are an order of magnitude below the observations.
At that scale, none of the post-propagation mechanisms (SEIRS thresholding,
bullwhip multiplier, hysteresis floor) can possibly trigger — there is nothing
for them to thresh on, multiply, or floor.

## Phase 3 — Publication interpretation

### Q1. Is SEIRS still decorative?

**YES — STRONGER THAN BEFORE.** ΔMAE = +0.00000, ΔPearson = +0.0000, predictions
**bit-identical** to `full_geds`. SEIRS adds no information at the calibrated point
on the spectrally-normalised graph.

### Q2. Did bullwhip become beneficial after normalisation?

**NO.** ΔMAE = +0.00000, predictions bit-identical to `full_geds`. The bullwhip
multiplier (`bullwhip_factor = 1.610`) is calibrated, but it only multiplies a
near-zero amplification signal, so its observable effect is zero. Normalisation
did not rescue bullwhip.

### Q3. Is network amplification still dominant?

**NO.** ΔMAE = +0.00000 (out to 5 decimals). Network amplification is the only
component that moves predictions at all (max per-event |Δ| = 0.0001), but the
aggregate effect is below noise on N=21. "Dominant" was a pre-normalisation
property driven by uncontrolled ρ(A); after normalisation, amplification has
no detectable effect on the model's fit.

### Q4. Is GEDS fundamentally more than normalised diffusion?

**NO.** `full_geds` MAE = `diffusion_only` MAE = 0.15940 to the fifth decimal,
ΔPearson = 0.0003. The mechanism-rich engine and the four-mechanisms-off
"diffusion" config produce statistically and numerically indistinguishable
fits on this corpus.

### Q5. Which mechanisms justify inclusion in publications?

**None of the four marketed mechanisms (SEIRS, Bullwhip, Hysteresis, Network
Amplification) shows measurable benefit at the 0.005 MAE threshold or any
threshold larger than 0.0001.** The honest publication claim has to be one of:

1. *"GEDS, calibrated on this corpus, is functionally equivalent to spectrally-
   normalised linear diffusion. The marketed mechanisms remain in the engine
   for theoretical generality but did not contribute to observed fit."*
2. *"GEDS cannot be claimed to outperform linear baselines on this dataset.
   A larger event corpus (N >> 21) and shocks that probe larger propagation
   regimes are needed before any mechanism can be claimed to contribute."*

Publishing GEDS as a SEIRS-Bullwhip-Hysteresis model without these caveats
would overstate what the data supports.

## Uncertainty disclosure (mandatory)

- **N = 21 events.** Bootstrap 95 % CIs span ~0.17 MAE units; any ΔMAE < 0.01 is
  inside noise. Even the 0.0061 gain over the zero-predictor sits inside that CI.
- Calibration came from a **diagnostic-budget CMA-ES** (8 iter × 6 pop, σ_end ≈ 0.25).
  A longer optimisation could yield a materially different optimum — and could in
  principle land at a higher `amplification_mu` where mechanisms do contribute.
- The OECD+WIOD graph still has NULL sectors (semiconductors, gas, finance splits
  for 2 of 3 codes) — events touching those sectors use heuristic fallbacks.
- This ablation only tests the **calibrated point**. Mechanisms could still matter
  at uncalibrated regimes (e.g. higher μ). What is shown here is that the optimiser,
  given the present corpus and topology, prefers a regime where they don't.

## Files preserved (not overwritten by this run)

- `ablation.json`, `ablation_v2.json`, `ablation_oecd.json`, `ablation_wiod.json`
- `benchmark_*.json` (every prior benchmark intact)
- `calibration_v2.json`, `posterior_v2.json`, `spectral_metrics.json`, `cmaes_best_params.json`

## Files generated this run

- `backend/data/calibration/ablation_post_normalization.json`
- `docs/POST_NORMALIZATION_ABLATION.md` (this file)
