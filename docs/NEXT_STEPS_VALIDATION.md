# GEDS Validation — Implementation Roadmap

Derived from `validation_targets_expanded.csv` (94 rows,
3 from literature) and `benchmark_inputs.csv`
(42 events).

## Immediate (1–3 days)

Goal: make the validation layer reproducible from CSV inputs alone.
Current state: `app/core/cross_validation.py` + `app/core/benchmark.py` exist but
consume hardcoded subsets of the events list. Wire them to the new CSVs.

- [ ] **Update `benchmark.py` to consume `benchmark_inputs.csv`** instead
  of its hardcoded N=8 list. _Effort: 0.5 day._
- [ ] **Filter scenario events** (`is_scenario == true`) from MAE/R²
  aggregates; report separately. _Effort: 0.5 day._
- [ ] **Wire `validation_targets_expanded.csv` into `loo_cv.py`** so
  paper-corroborated rows are scored against literature, not only
  event-aggregates. _Effort: 1 day._
- [ ] **Add `/api/v1/papers` endpoint** returning `papers_catalog.csv`
  so the frontend can cite the validation literature. _Effort: 0.5 day._

## Short-term (1–2 weeks)

Goal: address the core scientific weakness — Linear Diffusion beats
GEDS on the current N=8 benchmark. Two parallel tracks.

### Track A — bigger N for honest validation

- [ ] Re-run benchmark with all 42 events (minus the 1 scenario) = N=41.
  The current sub-selection masks model behaviour on noisy events.
  _Effort: 1 day._
- [ ] Implement synthetic-control counterfactuals for the top-5
  overlapping-crisis events (events 9, 10, 13, 14, 17, 18, 20, 21
  all overlap with at least 3 others). _Effort: 1 week._
- [ ] Bootstrap CIs for every metric in `/api/v1/research-metrics`.
  _Effort: 1 day._

### Track B — make the GEDS engine actually identifiable

Sobol indices from the prior session showed 3 of 5 parameters are
non-identifiable. Until that is fixed, calibration is unstable.

- [ ] Re-run Sobol on the expanded edge set (with Comtrade merger).
  _Effort: 0.5 day._
- [ ] Drop or fix the non-identifiable parameters; re-run MCMC.
  _Effort: 3 days._
- [ ] Re-run full benchmark; report whether GEDS now beats Linear
  Diffusion. _Effort: 0.5 day._

## Medium-term (1 month)

- [ ] **Paper-by-paper replication**: pick the 4 highest-relevance
  papers with reproducible code (papers 14, 15, 25 have GitHub repos
  per the docx) and reproduce their core figure inside GEDS as a
  validation regression-test. If GEDS produces the same numbers on the
  same data, we have credible cross-validation. _Effort: 1 week per paper._
- [ ] **Expand the event corpus to 100+ events** via the EM-DAT and
  ACLED feeds (already catalogued in `dataset_catalog.csv` dataset_ids
  43, 44, 52). Many low-magnitude events would shore up the statistics.
  _Effort: 1 week (ingest + label + recalibrate)._
- [ ] **Calibration error (ECE) reporting** per decile of forecast.
  The current benchmark only reports point R². _Effort: 2 days._

## Long-term (multi-month)

- [ ] **Out-of-sample temporal hold-out**: train on 2000–2020 events,
  test on 2021–2026 (12 events). This is the cleanest test of
  generalisation and the closest to real-world use. _Effort: 2–3 weeks._
- [ ] **Multi-shock simulation literature gap** — the docx review
  flags this as an open research area (no paper covers pandemic + war
  + energy crisis simultaneously). Build a stress-test suite combining
  events from `historical_events_expanded.csv` pairwise and measure
  emergent dynamics. _Effort: 1–2 months._
- [ ] **Cross-country panel validation**: replace the per-event scoring
  with a country×year panel and run the full battery on 200 countries ×
  26 years = 5,200 observations instead of 41 events. _Effort: 2 months._

## Out-of-scope for v1

Marked as 'long-term' but explicitly NOT a v1 commitment:

- **Real-time backtest** against live GDELT/ACLED streams.
- **Causal inference layer** with do-calculus / structural causal models.
- **Cryptocurrency / digital-asset contagion** (literature gap per docx).
- **GNN / transformer / XGBoost ML layer** (no training data; needs the
  100+ event corpus first).
