# Uncertainty Analysis — GEDS vs Baselines (spectrally-normalised OECD+WIOD)

Generated: `2026-06-03T16:23:08.687573+00:00`


- **Source benchmark:** `benchmark_spectral_normalized.json`
- **Graph:** OECD+WIOD spectrally normalised (ρ=1.0)
- **N events:** 21
- **Bootstrap:** 5000 non-parametric event-level resamples (seed=20260529)

## Brutally honest verdict (one paragraph)

At α = 0.05 the paired-bootstrap analysis says: **Leontief actually beats GEDS** on MAE (Δ = -0.00232, CI = [-0.00565, -0.00029], frac = 100.0%). GEDS does beat Linear Diffusion (Δ = +0.06012, CI = [+0.00504, +0.11199], frac_b_better = 1.6%); the CI does not contain 0, so the linear-baseline claim survives. GEDS vs Naive-mean: Δ = +0.01889, CI = [-0.03805, +0.07207] — **CI contains 0**, so the 'GEDS beats Naive' claim is **not significant** at N = 21. GEDS vs the zero predictor (predict zero loss everywhere): Δ = +0.00610, CI = [+0.00228, +0.01117] — the gain is statistically real but only 6.10‰ MAE.


## Per-model bootstrap 95 % CIs

| Model | MAE | MAE 95 % CI | Pearson | Pearson 95 % CI |
|---|---|---|---|---|
| `GEDS-SEIRS` | 0.15940 | [0.07667, 0.26314] | +0.4557 | [-0.3731, +0.8280] |
| `Leontief` | 0.15708 | [0.07441, 0.26080] | +0.3382 | [-0.3333, +0.7498] |
| `Linear-Diffusion` | 0.21951 | [0.15389, 0.29035] | -0.2697 | [-0.6412, +0.1432] |
| `Naive-Mean` | 0.17829 | [0.12902, 0.23929] | +0.0000 | [-0.0000, +0.0000] |
| `Zero-Predictor` | 0.16550 | [0.08045, 0.27139] | +nan | [+nan, +nan] |

## Pairwise paired bootstrap (Δ MAE = b − a)

Negative Δ ⇒ b has lower MAE than a. `frac_b_better` is the bootstrap probability that b's MAE is strictly lower than a's.

| a | b | Δ MAE point | Δ MAE 95 % CI | frac_b_better | CI contains 0? |
|---|---|---|---|---|---|
| `GEDS-SEIRS` | `Leontief` | -0.00232 | [-0.00565, -0.00029] | 100.0% | NO |
| `GEDS-SEIRS` | `Linear-Diffusion` | +0.06012 | [+0.00504, +0.11199] | 1.6% | NO |
| `GEDS-SEIRS` | `Naive-Mean` | +0.01889 | [-0.03805, +0.07207] | 25.2% | YES |
| `GEDS-SEIRS` | `Zero-Predictor` | +0.00610 | [+0.00228, +0.01117] | 0.0% | NO |
| `Leontief` | `Linear-Diffusion` | +0.06244 | [+0.00857, +0.11364] | 1.2% | NO |
| `Leontief` | `Naive-Mean` | +0.02121 | [-0.03471, +0.07410] | 22.3% | YES |
| `Linear-Diffusion` | `Naive-Mean` | -0.04123 | [-0.07998, -0.00153] | 98.0% | NO |

## CI-overlap analysis vs publication claims

- **"GEDS beats Leontief"** — false at this N. Leontief's bootstrapped MAE is lower in 0.0% of resamples (paired bootstrap), point Δ = -0.00232. The CI excludes 0, so the (small) Leontief advantage is statistically real, not a coincidence.
- **"GEDS beats Linear Diffusion"** — supported. CI = [+0.00504, +0.11199] excludes 0; GEDS' MAE is lower in 98.4% of resamples.
- **"GEDS beats Naive-mean"** — NOT supported. CI = [-0.03805, +0.07207] contains 0; GEDS' MAE is lower in only 74.8% of resamples.
- **"GEDS beats Zero-predictor"** — barely. CI = [+0.00228, +0.01117] excludes 0; the gain is significant but only ~6.10‰ in absolute MAE.

## Implications for publication claims

1. A headline of *'GEDS outperforms standard linear baselines'* requires careful framing — GEDS only outperforms the **linear diffusion baseline** at significance; it loses (by a small margin) to the **Leontief** input-output baseline, and it is **statistically indistinguishable** from the naive mean-predictor.
2. The dominant uncertainty is *sample size* (N = 21). Bootstrap CIs are wide because the corpus is small; no engineering trick can shrink them — only collecting more events does.
3. The CI spans for Pearson include 0 for every model, so claiming any model has positive correlation with observed losses is **not** statistically defensible from this corpus alone.