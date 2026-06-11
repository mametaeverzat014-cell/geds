# GEDS — Global Economic Dependency Simulator

**Live demo:** https://geds1.vercel.app · **Validation dashboard:** https://geds1.vercel.app/validation

GEDS simulates how one economic shock — a chip-fab shutdown, a blocked
shipping strait, a trade war — cascades week-by-week through the global
trade and supply-chain network, and is **honestly validated against 21
historical crises** (2011 Tōhoku → 2023 Red Sea).

## What makes it different

Most "economic simulators" are demos with hand-tuned outputs. GEDS is built
the opposite way:

- **Real primary data.** UN Comtrade 2019 bilateral flows, World Bank LPI,
  OECD STAN sector shares, IMF WEO — every graph parameter traces to a
  published source (`backend/data/provenance.json`), refreshed daily by a
  GitHub Action.
- **Nothing on the site is hardcoded.** Every accuracy number the UI shows
  is computed live by the backend (`/api/v1/cv-report`, `/benchmark`,
  `/loo-de-report`) or served from a reproducible artifact with its
  generation command attached.
- **Honest benchmarks, including the unflattering ones.** The model is
  scored against a parameter-free linear-diffusion baseline and naive
  persistence on every run. When the baseline wins a metric, the UI and the
  docs say so. A regression test (`tests/test_reproducibility.py`) locks the
  published numbers so they cannot drift silently.

## The model

A vectorized SEIRS-with-hysteresis cascade engine over a weighted trade
graph (12 economies × 7 industries, 4 maritime chokepoints):

- discrete-time shock propagation over Comtrade-derived dependency weights,
- per-industry inventory buffers (Exposed state), bullwhip amplification,
  recovery hysteresis (70% production cap in Recovering state),
- chokepoint rerouting cost surcharges (Suez ×1.35, Hormuz ×2.0),
- Monte-Carlo ensembles, Bayesian (MCMC) + differential-evolution
  calibration, isotonic post-calibration.

Full formalism: [`docs/mathematical-framework.md`](docs/mathematical-framework.md) §13.

## Current honest results (N=21 events, out-of-sample)

Leave-one-out cross-validation with per-fold re-calibration
(`python -m scripts.loo_de_validation`):

| Model | MAE | Pearson | Spearman | R² |
|---|---|---|---|---|
| GEDS SEIRS, LOO-recalibrated | **0.0115** | 0.787 | 0.490 | **0.619** |
| Linear-diffusion baseline | 0.0130 | **0.822** | **0.598** | 0.600 |

Split decision, reported as such: the recalibrated engine wins every
*error* metric out-of-sample; the simple baseline still wins *rank*
correlation. Known weak spots (port/logistics events; 4 of 5 calibrated
parameters at prior bounds) are documented in [`PROGRESS.md`](PROGRESS.md)
and [`AUDIT.md`](AUDIT.md) — finding and fixing them is the project.

## Architecture

```
frontend/   Next.js 14 + Tailwind + D3 (Vercel)      — animated cascade map, live validation UI
backend/    FastAPI + NumPy/SciPy (Render)           — engine, calibration, 75-test suite
  app/core/      propagation, SEIRS, baselines, benchmark, MCMC/DE calibration
  app/data/      seed graph + 21 hand-sourced historical events (citations inline)
  scripts/       reproducible pipelines (Comtrade fetch, LOO-DE validation, MCMC)
reports/    deterministic benchmark artifacts (json + md)
docs/       40+ working documents: audits, verdicts, math framework
```

## Reproduce everything

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -q              # 75 tests
python -m app.core.benchmark --check    # determinism self-test
python -m app.core.benchmark            # leaderboard → reports/benchmark/
python -m scripts.loo_de_validation     # out-of-sample verdict (~30 min)
python -m scripts.mcmc_calibrate        # Bayesian posterior (~1-2 h)
```

The AI features (Claude crisis radar, Grok narrative) are presentation-only:
they narrate the engine's numeric signals and are prompt-forbidden from
inventing numbers. The science never depends on an LLM.
