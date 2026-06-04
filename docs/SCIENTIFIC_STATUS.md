# Scientific Status Inventory

A subsystem-by-subsystem disposition for GEDS, produced during the
foundation-stabilization pass. Every row is classified **KEEP / REWRITE /
ARCHIVE / DELETE** and justified by evidence that can be re-derived from the
repository — import graphs, grep results, and file provenance — **not** by
opinion or expectation.

This document is descriptive of the repository **as it stands after WP1–WP4**
(reproducibility lockdown, leak quarantine, ranking-metrics, deterministic
harness). It is the companion to `docs/REPRODUCIBILITY.md` and
`archive/leaked/README.md`.

---

## How each verdict was derived (method, so it can be checked)

1. **Live reachability.** A module is "live" if it is import-reachable from the
   running application's three entry points — `app/main.py`, `app/api/routes.py`,
   `app/api/websocket.py` — following `from .` / `from ..` imports transitively.
2. **Leak membership.** The two leak roots are
   `remap_events_for_oecd_graph` and `translate_event` (they derive the model
   **input** `magnitude` from the observed **target**; see
   `archive/leaked/README.md`). A file is leak-tainted if it (a) contains the
   transform, (b) imports a leak function, or (c) consumes a leaked output
   artifact as a data input.
3. **Provenance.** For generated/catalogue files, the disposition of the
   **generator** is inherited by the artifact unless the artifact can be shown
   independent of the leak.
4. **No-guessing rule.** Where lineage cannot be established from the repository
   alone, the item is **KEEP + FLAG (REVIEW)** — neither blessed nor deleted on
   suspicion. This mirrors the treatment of ambiguous JSONs in the quarantine
   README.

### Label legend

| Label | Meaning |
|---|---|
| **KEEP** | Clean and correct; either live or a legitimate offline tool. Safe to rely on. |
| **KEEP + FLAG** | Code is clean/usable, but a wiring or provenance question must be resolved before it is trusted or relied upon. Not a leak. |
| **REVIEW** | Strong, specific provenance/contamination concern. Do not run or cite until reconciled; likely ARCHIVE after confirmation. |
| **REWRITE** | Present and needed, but contains a defect that requires code change. |
| **ARCHIVE** | Leaked or scientifically invalid; preserved under `archive/leaked/` for audit. (All WP2 moves are already done.) |
| **DELETE** | No scientific or operational value (developer scratch); recommended for removal. |

---

## Headline findings

- **The leak never reached `app/`.** A grep for the leak transform
  (`magnitude = max(0.1, … abs(gdp…)/50)`) returns **zero** hits in `app/` and
  in every script left in `backend/scripts/`. All occurrences live only in the
  16 quarantined files under `archive/leaked/`. **The core engine and evaluation
  layer (`app/core/`, 22 modules) are clean.**
- **The honest benchmark result stands and is locked.** On the clean,
  hand-authored N=8 corpus, the textbook **Linear Diffusion baseline wins every
  metric** (MAE 0.0152, RMSE 0.0179, R² 0.765, Pearson 0.879). **GEDS does not
  beat it** (MAE 0.0248, Pearson 0.720); GEDS ranks events well (Spearman 0.83)
  but is second on error and correlation. This is enforced by
  `tests/test_reproducibility.py::test_winner_is_linear_diffusion`.
- **The contamination that remains is in the `scripts/` layer**, and it is of a
  weaker kind: a handful of audit/report scripts **consume** leaked artifacts as
  inputs (or sit in the v2/v4 lineage). None contain the leak transform. These
  are flagged for review, not silently kept.
- **No `app/core` subsystem requires a REWRITE.** The one code-level defect
  found during stabilization — the `argsort-of-argsort` Spearman that mishandled
  ties — was already replaced by `metrics.spearman_rho` in WP3/WP4 and is
  covered by tests. No other live module shows a defect on inspection.

---

## A. Core engine & evaluation — `backend/app/core/` (22 modules)

All 22 are **KEEP**. None contain or import the leak. The split below is only
between *live* (reachable from the app) and *offline* (clean, reachable today
only from developer scripts).

### A.1 Live — KEEP

| Module | Verdict | Evidence |
|---|---|---|
| `types.py` | KEEP | Foundation dataclasses/enums (`EngineConfig`, `Scenario`, `ShockSpec`, `Industry`). Imported by virtually every core module + `main.py`. No I/O, no RNG. |
| `graph.py` | KEEP | Deterministic graph compile from a hard-coded seed graph; imported by `main.py` and most core modules. No file I/O, no randomness. |
| `seis.py` | KEEP | Engine kernel constants/functions (`INDUSTRY_INVENTORY_WEEKS`, distress logic). Imported by `propagation.py` and `graph.py`. |
| `propagation.py` | KEEP | The SEIRS-Bullwhip-Hysteresis engine. Deterministic when `stochastic_sigma=0` (the benchmark/default config). Imported by `main`, `routes`, `websocket`, `monte_carlo`, `tail_risk`, `validation`, `backtest`. |
| `metrics.py` | KEEP | CSI/ECV/financial metrics **plus** the WP3 ranking metrics (`spearman_rho`, `kendall_tau`, `ndcg_at_k`, `precision_at_k`, `top_k_overlap`). Tested by `test_metrics.py` + `test_ranking_metrics.py` (cross-checked against SciPy). |
| `baselines.py` | KEEP | `leontief_predict`, `linear_diffusion_predict`. Imported by `benchmark`, `ablation`. Linear Diffusion is the **honest winner** on the clean set — load-bearing for the benchmark's integrity. |
| `benchmark.py` | KEEP | Rewritten in WP4: deterministic, rank-aware, single-command (`python -m app.core.benchmark`). The **only** valid benchmark. Tested by `test_reproducibility.py`. |
| `backtest.py` | KEEP | `backtest_event` / `run_track_record`. Operates on the clean `HISTORICAL_EVENTS`. Imported by `routes` and by `mcmc`, `cross_validation`, `de_calibrate`, `sensitivity`, `postcalibration`, `research_metrics`, `ablation`, `benchmark`. |
| `sanity.py` | KEEP | `is_within_sanity` physical-bound guard; imported by `backtest`. |
| `scenarios.py` | KEEP | Scenario registry; imported by `routes` and `websocket`; tested by `test_scenarios.py`. |
| `advisor.py` | KEEP | `analyze()`; imported by `routes`; tested by `test_advisor.py`. |
| `ablation.py` | KEEP | `run_ablation_study` / `save_ablation`; imported by `routes`; runs on clean `HISTORICAL_EVENTS` + `baselines`. |
| `cross_validation.py` | KEEP | `loo_cross_validate_fast` / `save_cv`; imported by `routes`; clean corpus. |
| `mcmc.py` | KEEP | Bayesian calibration + `load_result` (posterior); imported by `routes` (`load_posterior`), `sensitivity`, `de_calibrate`. Source of truth for `PARAM_BOUNDS` / `PARAM_NAMES`. |
| `postcalibration.py` | KEEP | `loo_calibration_report`; imported by `routes`; clean corpus. |
| `research_metrics.py` | KEEP | Imported by `routes`; clean corpus. |
| `tail_risk.py` | KEEP | `compute_tail_risk`; imported by `routes`; builds on `monte_carlo`. |
| `centrality.py` | KEEP | `full_centrality_report`; imported by `routes`. |
| `monte_carlo.py` | KEEP | `run_monte_carlo`; imported by `routes` and `tail_risk`. |
| `validation.py` | KEEP | `run_all`; imported by `routes`; tested by `test_validation.py`; runs on clean corpus. |

### A.2 Offline (clean) — KEEP

| Module | Verdict | Evidence |
|---|---|---|
| `de_calibrate.py` | KEEP (offline) | Differential-evolution calibration on the **clean** `HISTORICAL_EVENTS`. Clean imports (`backtest`/`mcmc`/`graph`/`types`/`seed_data`). Not imported by the running app; today its only caller is `scripts/_smoke2.py`. A legitimate offline calibration utility. |
| `sensitivity.py` | KEEP (offline) | Sobol sensitivity (`run_sobol`/`save_sobol`) over the clean corpus and `mcmc.PARAM_BOUNDS`. Clean imports. Not live; only caller is `scripts/_smoke3.py`. Legitimate offline analysis utility. |

---

## B. Data layer — `backend/app/data/` (8 modules)

| Module | Verdict | Evidence |
|---|---|---|
| `seed_data.py` | KEEP | The clean, hand-authored corpus: `HISTORICAL_EVENTS` (N=8), `EDGES_RAW`, `CHOKEPOINT_LINKS`. Shock magnitudes are public, hand-authored estimates — **not** target-derived. The reference example for leak-free design. Imported by 11 core modules + `test_validation.py`. |
| `seed.py` | KEEP | `load_graph()`; imported by `main.py`; composes `edge_merger` + `seed_data`. |
| `edge_merger.py` | KEEP | `merge_edges`; imported by `seed.py`. |
| `csv_loader.py` | KEEP | Imported directly by `routes.py`. |
| `comtrade_fetcher.py` | KEEP (offline ETL) | UN Comtrade fetch helpers; used by `comtrade_processor` and `scripts/fetch_comtrade.py`. Raw-data ingestion, no benchmark coupling. |
| `comtrade_processor.py` | KEEP (offline ETL) | Used by `scripts/fetch_comtrade.py`. Raw-data processing. |
| `data_registry.py` | **KEEP + FLAG** | Read-only master-CSV catalogue. Generator `scripts/build_master_registries.py` is **clean** (not quarantined). **But** no live module imports it — the only repository reference is a *comment* in its generator. Decision needed: **wire it in or retire it.** Not a leak concern. |
| `scientific_registry.py` | **KEEP + FLAG (provenance)** | Read-only scientific-evidence catalogue. **Zero importers** anywhere in the repo. Its generator `integrate_scientific_layer.py` is **quarantined** (it imported the leaked `phase_expanded_validation`). The registry loads evidence CSVs (citations/mechanisms, **not** benchmark targets), so it is **not provably leaked**, but its provenance **cannot be certified from the repo alone**. Per the no-guessing rule: review provenance; do not bless, do not delete on suspicion. |

---

## C. Scripts — `backend/scripts/` (29 `.py` files)

None of these contain the leak transform, and none import a quarantined module
(both verified by grep). The concern here is weaker and specific: some
**consume leaked artifacts** as inputs, or sit in the v2/v4 expansion lineage.

### C.1 Clean ETL / ingestion — KEEP (offline)

`fetch_comtrade.py`, `ingestion/ingest_oecd_icio.py`,
`ingestion/ingest_un_comtrade.py`, `ingestion/ingest_wiod.py`,
`build_country_sector_presence_oecd.py`, `merge_oecd_wiod.py`,
`compare_comtrade_vs_seed.py`.

**Evidence:** raw third-party data ingestion/merging. The leak was in benchmark
*remapping*, not in ingesting OECD/WIOD/Comtrade source data. No leak transform,
no leaked-artifact input.

> Note: `build_country_sector_presence_real.py` appears in the leaked-name grep,
> but only because it writes/reads a `*_oecd`-suffixed **presence** CSV (real
> trade data), not a leaked benchmark JSON. Classified **KEEP (offline ETL)**;
> confirm the suffix is the trade-data file, not a benchmark artifact, on next
> touch.

### C.2 Catalogue / extraction builders — KEEP (offline)

`build_master_registries.py` (generates `data_registry`), `extract_events_from_docx.py`,
`extract_literature_review.py`, `extract_dataset_registry.py`,
`extract_benchmark_framework.py`, `extract_benchmark_comparison.py`,
`ingest_peer_reviewed_evidence.py`, `gen_event_mapping_report.py`.

**Evidence:** read source documents/CSVs → emit catalogue CSVs/reports. No leak
transform; not importers of leak functions. `extract_benchmark_*` parse the
*framework/description*, not target-derived magnitudes.

### C.3 Calibration / reporting on the clean corpus — KEEP (offline)

`calibrate.py` (imports clean `HISTORICAL_EVENTS`), `mcmc_calibrate.py`
(drives `app.core.mcmc`).

### C.4 v4 audit/ledger generators — KEEP + FLAG (REVIEW)

| Script | Verdict | Evidence |
|---|---|---|
| `gen_benchmark_matrix_v4.py` | KEEP + FLAG | Docstring: *"No synthetic targets"*, NULL targets preserved verbatim. Builds the v4 corpus ledger. **Flag:** it defines the v4 evaluation sets; confirm it never sources `magnitude` from a target and that its inputs are clean before any reuse. |
| `v4_preaudit.py` | KEEP + FLAG | Docstring: *"NON-FABRICATING"* verbatim-evidence extractor. **Provenance tension:** its output `v4_preaudit.json` was quarantined under the `_v4` suffix rule, yet the generator looks clean. Reconcile (re-derive output cleanly, or confirm the quarantine) before reuse. |
| `v4_recon.py` | KEEP + FLAG | Read-only recon that **reads the v3 benchmark matrix targets**. v3 is leaked + has a provenance failure (`archive/leaked/README.md`). Any report it prints may echo leaked numbers. Review before citing. |

### C.5 Scripts that consume leaked artifacts — REVIEW

| Script | Verdict | Evidence |
|---|---|---|
| `phase5_regenerate_state.py` | **REVIEW → likely ARCHIVE** | Reads `benchmark_v2.json` + `calibration_v2.json` to regenerate `docs/STATE.md`. Both inputs are now in `archive/leaked/`, so the script is **both broken and contaminating** (its output would embed leaked v2 numbers). Do not run. Confirm nothing depends on STATE-doc regeneration, then archive. |
| `phase1_2_expand_and_mine.py` | REVIEW | Part of the v2 expansion lineage that ultimately fed the leak; reads `validation_targets_v2.csv`. No leak transform itself. Review the expansion inputs before reuse. |
| `bootstrap_scientific_layer.py` | REVIEW | Non-fabricating by docstring, but reads `benchmark_event_matrix_v2.csv` and produces the scientific-layer CSVs consumed by the flagged `scientific_registry.py`. Provenance chain ties to v2 lineage; review. |
| `bootstrap_benchmark.py`, `gen_event_mapping_report.py`, `write_uncertainty_reports.py` | REVIEW | Surface in the leaked-name grep as **consumers** of v2/v4 benchmark JSONs. No leak transform. Re-point at the clean harness output (`reports/benchmark/`) or archive. |

### C.6 Developer scratch — DELETE (recommended)

| Script | Verdict | Evidence |
|---|---|---|
| `_smoke.py`, `_smoke2.py`, `_smoke3.py` | DELETE | End-to-end scratch scripts, not part of any pipeline. They are the *only* callers of `de_calibrate` / `sensitivity`; if deleted, fold a minimal invocation of those two into `tests/` so the offline tools keep a usage example. (Left in place by this pass — flagged, not yet removed.) |

### C.7 Stray artifact

`scripts/calibration/loeo_v4_run.log` — a leftover run log in the now-emptied
`scripts/calibration/` directory. **DELETE** (non-source log; its producer is
quarantined).

---

## D. Tests — `backend/tests/` (KEEP)

| Test file | Verdict | Covers |
|---|---|---|
| `test_reproducibility.py` | KEEP (new, WP1) | Config pinned, determinism, golden snapshot, persistence-has-no-ranking, honest-winner lock. |
| `test_ranking_metrics.py` | KEEP (new, WP3) | Spearman/Kendall vs SciPy (incl. ties); hand-computed NDCG/precision/overlap; degenerate + length-mismatch behavior. |
| `test_metrics.py` | KEEP | Existing CSI/ECV/financial metrics. |
| `test_propagation.py` | KEEP | Engine behavior. |
| `test_validation.py` | KEEP | `validation.run_all` on clean corpus. |
| `test_scenarios.py`, `test_advisor.py` | KEEP | Scenario registry, advisor. |
| `conftest.py`, `__init__.py` | KEEP | Fixtures/package marker. |

**Status:** full suite green (60 tests) as of this pass; app imports cleanly
(36 routes).

---

## E. Documentation & reports

| Item | Verdict | Note |
|---|---|---|
| `docs/REPRODUCIBILITY.md` | KEEP (new, WP1) | Single-command reproduction, pinned config, nondeterminism audit, leaked-variant warning. |
| `docs/SCIENTIFIC_STATUS.md` | KEEP (this file, WP5) | This inventory. |
| `archive/leaked/README.md` | KEEP (new, WP2) | Leak roots with line numbers, quarantine tables, no-guessing rationale. |
| `reports/benchmark/{benchmark.json, summary.md}` | KEEP | Current honest leaderboard, regenerated by the harness. |
| `docs/STATE.md` (if present) | REVIEW | If it was produced by `phase5_regenerate_state.py`, it may embed leaked v2 numbers. Regenerate from clean sources or annotate. |

---

## F. Already archived (WP2) — ARCHIVE (done)

16 scripts and 28 JSON artifacts under `archive/leaked/`. Full enumeration and
per-item justification: `archive/leaked/README.md`. The cluster is closed —
every importer of the two leak functions is included, and no file remaining in
`backend/` imports any quarantined module (verified by grep).

---

## G. Consolidated review register (the honest uncertainty list)

Items that are **not** clean-and-done and need a human decision, in priority
order:

1. **`scientific_registry.py` + `bootstrap_scientific_layer.py`** — provenance
   ties to a quarantined generator / v2 lineage. Certify the evidence CSVs or
   archive the registry.
2. **`phase5_regenerate_state.py`** — broken (inputs moved) and contaminating;
   confirm no dependency, then archive. Re-check `docs/STATE.md`.
3. **v4 trio** (`gen_benchmark_matrix_v4.py`, `v4_preaudit.py`, `v4_recon.py`) —
   non-fabricating by design but in the v4/v3 lineage; reconcile the quarantine
   of `v4_preaudit.json` with its clean-looking generator.
4. **Leaked-artifact consumers** (`bootstrap_benchmark.py`,
   `gen_event_mapping_report.py`, `write_uncertainty_reports.py`,
   `phase1_2_expand_and_mine.py`) — re-point at `reports/benchmark/` or archive.
5. **`data_registry.py`** — wire into the app or retire (clean; just orphaned).
6. **`_smoke{,2,3}.py` + `loeo_v4_run.log`** — delete scratch; preserve a
   `de_calibrate`/`sensitivity` usage example as a test.

None of the items in G are leaks in the strict sense; they are provenance,
wiring, or hygiene decisions deliberately left explicit rather than guessed.
