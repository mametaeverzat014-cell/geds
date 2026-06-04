# GEDS — Next Priority Actions

Ranked HIGH / MEDIUM / LOW by combined `scientific impact ÷ effort`
score. Numbers below come from `MASTER_STATE.md`, the prior `NEXT_STEPS_*`
docs, and the inconsistency-detection pass.

## HIGH priority

These unblock multiple downstream tasks AND have evidence in the repo
that the current state is broken / suboptimal.

### 1. Re-run the benchmark with all 42 events (currently N=8)

- **Why:** the headline 'Linear Diffusion beats GEDS' result is
  computed on N=8 events from `benchmark_inputs.csv`. We now have 42.
  Re-running may flip the result OR confirm it — either is publishable.
- **Effort:** 1–2 days. Existing `app/core/benchmark.py` already accepts
  `benchmark_inputs.csv` rows.
- **Blockers:** none.

### 2. Map the 8 v2 events into the 42-event corpus

- **Why:** v2 docx has 178 institutional-source rows but they use
  `event_num` 1..8, not the expanded `event_id`. Until linked,
  v2's ground-truth quality (`5_official_outturn` flags) cannot be
  used in scoring. Linking already specified in `V2_TO_EXPANDED` —
  needs to be enforced in code.
- **Effort:** 0.5 day. Modify `cross_validation.py` to read both
  v2 and expanded rows under the same `event_id`.
- **Blockers:** none.

### 3. Fix the 3 non-identifiable SEIRS parameters

- **Why:** prior Sobol run flagged 3 of 5 parameters as having
  total-order index Sₜ < 0.05. Until fixed, MCMC calibration is
  unstable, which downstream affects every benchmark claim.
- **Effort:** 3 days. Either fix them at literature-derived values
  or remove them from the parameter vector.
- **Blockers:** none.

### 4. Wire 5 anchor fetchers (UN Comtrade, IMF WEO, World Bank WDI, FRED, GDELT)

- **Why:** `master_dataset_registry.csv` has 35 HIGH-priority
  datasets but only Comtrade is currently ingested.
  See `NEXT_STEPS_DATA.md` for the canonical list.
- **Effort:** 2–3 days for the 5 anchors (already specified per
  dataset in `BENCHMARK_IMPLEMENTATION.md`).
- **Blockers:** none.

### 5. Reproduce Carvalho et al. (2021) Tōhoku result on Event 11

- **Why:** Carvalho's `−0.47 pp Japan GDP` is the gold standard for
  the 2011 Tōhoku event. If GEDS produces the same number on Event 11,
  we have credible cross-validation against a peer-reviewed paper.
  If we miss it materially, that informs the calibration fix.
- **Effort:** 2 days.
- **Blockers:** depends on Action 3 (calibration fix).

## MEDIUM priority

Useful but either harder or less central than HIGH items.

### 6. OECD ICIO ingest → expand graph from 40 to ~3,400 nodes

- **Why:** unlocks publication-grade I-O baselines (Leontief). Also
  enables BACI + TiVA merger as follow-ups.
- **Effort:** 6 weeks (data 1w + recalibration 2w + benchmark 1w +
  validation 2w).
- **Blockers:** Action 3 (calibration must be stable first).

### 7. Replicate Inoue & Todo (2019) Nankai 10.6% / 0.5% ratio

- **Why:** validates GEDS' indirect-loss amplification against the
  most-cited supply-chain ABM result in the literature.
- **Effort:** 2 days.
- **Blockers:** none.

### 8. XGBoost early-warning baseline on the 42-event corpus

- **Why:** XGBoost AUROC 0.97 is the published SOTA (IJEFS 2024).
  Until GEDS is compared head-to-head, novelty claims about
  'GEDS beats ML baselines' cannot be made.
- **Effort:** 1 week.
- **Blockers:** Action 4 (FRED / WDI fetchers).

### 9. Dedup duplicate dataset URLs and cross-ref papers

- **Why:** 7 URLs are shared
  by ≥2 dataset_ids; 5 papers appear
  in both `papers_catalog` and `literature_catalog`. Both inflate
  catalog counts. Resolved in master registries but the source CSVs
  still drift.
- **Effort:** 0.5 day each.
- **Blockers:** none.

### 10. Multi-shock pairwise stress test on the 59 overlapping pairs

- **Why:** literature gap (no paper covers multi-shock interaction).
  Most-novel achievable result this quarter per `NOVELTY_POSITIONING.md`.
- **Effort:** 1 week.
- **Blockers:** Actions 1–3 (benchmark + v2 link + calibration).

## LOW priority

Worth doing but only after HIGH/MEDIUM blockers clear.

### 11. Synthetic-control counterfactuals for the worst overlap events

- **Why:** mitigates the attribution problem flagged in
  `UNCERTAINTY_ANALYSIS.md`. 5 events overlap with ≥3 others; each
  would benefit from a counterfactual.
- **Effort:** 1 week per event.
- **Blockers:** Action 1 (need clean benchmark numbers to compare).

### 12. AIS → GDP structural shipping propagation model

- **Why:** addresses literature gap #2 (no published structural
  Red Sea / Suez / Panama propagation paper).
- **Effort:** 6 months.
- **Blockers:** IMF PortWatch GIS ingest + new modeling work.

### 13. Real-time GDELT/ACLED stream → ShockSpec pipeline

- **Why:** turns GEDS into a live monitoring system.
- **Effort:** 3 months.
- **Blockers:** Actions 1–8 (need a stable, validated engine first).

### 14. Publication-ready N=42 benchmark release

- **Why:** infrastructure contribution (no comparable open-source
  benchmark exists in the literature). Publishable even if GEDS does
  not win the benchmark.
- **Effort:** 2 weeks (after Actions 1–3 are complete).
- **Blockers:** Actions 1, 3, 5, 8.

## Out-of-scope for next 3 months

Explicitly *not* a priority right now (still listed so it doesn't fall off):

- GNN / TGNN training (requires GPU + labelled crisis data; 3+ weeks)
- Causal-inference layer (do-calculus / SCM) on the propagation engine
- Cryptocurrency contagion (literature gap, but no data)
- Multi-tenant auth + persistent storage (engineering not science)
