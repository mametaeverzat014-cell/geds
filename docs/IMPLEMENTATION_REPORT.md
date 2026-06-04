# Foundation Stabilization — Implementation Report

**Scope.** Make GEDS a reproducible, leakage-free, scientifically defensible
baseline, and leave the repository in a working state. No new theoretical
frameworks, no invented metrics, no AI/LLM additions, no model redesign, no V3 —
**stabilize and clean only.** Every claim below is backed by code, grep, or the
git change set.

**Baseline.** All work is measured against git HEAD
`602597f` *("Mission 1+2: spectral-normalized OECD/WIOD benchmark engine +
honest V4 verdict")* — notably, the commit that introduced the OECD/WIOD/v4
benchmark lineage now quarantined as leaked.

**Status: complete.** Full test suite green (60 tests); the FastAPI app imports
cleanly (36 routes); `python -m app.core.benchmark --check` passes (determinism).

---

## 1. Outcome in one paragraph

The target leak was isolated to the **expansion/benchmark script layer** and
fully quarantined; **`app/` was never affected** (the leak transform appears
nowhere in `app/` or in any remaining script). The benchmark harness is now
deterministic, rank-aware, and runnable with one command, writing a
machine- and human-readable leaderboard to `reports/benchmark/`. The honest
result is preserved and **locked by test**: on the clean hand-authored N=8
corpus, the textbook **Linear Diffusion baseline wins every metric; GEDS does
not beat it.** Every subsystem is classified in `docs/SCIENTIFIC_STATUS.md`, and
items whose provenance could not be established from the repository are flagged
for review rather than guessed.

---

## 2. Work packages

### WP1 — Reproducibility lockdown ✅
- Pinned the engine config behind one frozen constant
  `BENCHMARK_CONFIG = EngineConfig(seed=0, stochastic_sigma=0.0)`
  (`stochastic_sigma=0.0` ⇒ the cascade takes **no** RNG draws).
- Isolated the only nondeterministic field (`timestamp`) out of the determinism
  contract via `scored_payload()`.
- Wrote **`docs/REPRODUCIBILITY.md`** (environment, single-command repro, pinned
  config rationale, full nondeterminism audit, leaked-variant warning).
- Added **`backend/tests/test_reproducibility.py`** (config pinned, determinism,
  golden snapshot, persistence-has-no-ranking, honest-winner lock).

### WP2 — Leak quarantine ✅
- Identified the two leak roots (input derived from target):
  `run_oecd_benchmark.remap_events_for_oecd_graph` (`:370`) and
  `phase3_benchmark_v2.translate_event` (`:119`), plus
  `phase_validation_expansion.py:303` setting the observation from the target.
- Moved **16 scripts + 28 JSON artifacts** to `archive/leaked/` via `git mv`
  (history preserved) and wrote **`archive/leaked/README.md`** documenting the
  defect, a per-item justification table, and the no-guessing rationale.
- **Verified the cluster is closed:** every importer of the two leak functions
  is quarantined, and no file remaining in `backend/` imports any quarantined
  module (grep-confirmed).

### WP3 — Metrics modernization ✅
- Appended to **`backend/app/core/metrics.py`** (additive — all existing
  CSI/ECV/financial metrics untouched): `spearman_rho` (average-rank,
  tie-corrected), `kendall_tau` (τ-b), `ndcg_at_k`, `precision_at_k`,
  `top_k_overlap`. Pure-NumPy; degenerate input → `nan`; length mismatch →
  `ValueError`.
- Added **`backend/tests/test_ranking_metrics.py`** (22 tests) cross-validating
  Spearman/Kendall against `scipy.stats` including ties; hand-computed
  NDCG/precision/overlap; edge cases.

### WP4 — Benchmark harness ✅
- Rewrote **`backend/app/core/benchmark.py`** preserving the public API
  (`run_benchmark`, `save_benchmark`) so `routes.py`'s `GET /benchmark` keeps
  working. Replaced the buggy local `_spearman` with `metrics.spearman_rho`;
  added Kendall + NDCG; added `winner_by_spearman`.
- Single command: `python -m app.core.benchmark` →
  `reports/benchmark/{benchmark.json, summary.md}`; flags `--check` (determinism
  self-test), `--out`, `--ndcg-k`, `--quiet`. JSON is always valid (NaN/inf →
  `null`).

### WP5 — Scientific inventory ✅
- Wrote **`docs/SCIENTIFIC_STATUS.md`**: every subsystem classified
  KEEP / REWRITE / ARCHIVE / DELETE with re-derivable evidence (import
  reachability, leak-membership grep, generator provenance), plus a consolidated
  review register for items deliberately left to human judgment.

### WP6 — This report ✅

---

## 3. File-level change set (vs HEAD `602597f`)

### Modified (2 source files)
| File | Change |
|---|---|
| `backend/app/core/benchmark.py` | Deterministic, rank-aware, single-command harness; tie-correct Spearman via `metrics`; +Kendall, +NDCG, +`winner_by_spearman`; `reports/` output; `--check`. Public API preserved. |
| `backend/app/core/metrics.py` | +5 ranking metrics (additive; existing metrics untouched). |

*(`.claude/settings.local.json` also shows as modified — local tooling config,
not part of this work.)*

### Created (deliverables)
- `docs/REPRODUCIBILITY.md`
- `docs/SCIENTIFIC_STATUS.md`
- `docs/IMPLEMENTATION_REPORT.md` (this file)
- `archive/leaked/README.md`
- `backend/tests/test_reproducibility.py`
- `backend/tests/test_ranking_metrics.py`
- `reports/benchmark/{benchmark.json, summary.md}` (regenerable output)

### Archived (44 items, `git mv` → `archive/leaked/`)
16 scripts + 28 JSON artifacts. Full enumeration: `archive/leaked/README.md`.

### Recommended DELETE (not yet removed — flagged for sign-off)
- `backend/scripts/_smoke.py`, `_smoke2.py`, `_smoke3.py` (dev scratch; only
  callers of the clean offline tools `de_calibrate` / `sensitivity` — preserve a
  usage example as a test before deleting).
- `backend/scripts/calibration/loeo_v4_run.log` (stray run log of a quarantined
  producer).

> **Not committed.** All of the above is uncommitted working-tree state (the
> archive moves are staged renames; source edits and new files are not staged).
> I have not committed, per standing policy to commit only on explicit request.

---

## 4. Benchmark: before → after

The scoring formulas for **MAE / RMSE / R² / Pearson were not changed**; the
pinned config equals the historical `EngineConfig()` defaults, so previously
published error/correlation numbers are preserved (verified by the golden
snapshot test). What changed: a **tie-handling correction** in Spearman and
**two added rank metrics**.

| Aspect | Before (HEAD `602597f`) | After (this pass) |
|---|---|---|
| Spearman | `argsort(argsort())` — mishandles ties | `metrics.spearman_rho` — average-rank, matches SciPy |
| Kendall τ-b | absent | added (`metrics.kendall_tau`) |
| NDCG@k | absent | added (`metrics.ndcg_at_k`, default k=5) |
| `winner_by_spearman` | absent | added |
| Determinism | timestamp inside payload | `timestamp` excluded; `--check` self-test; reproducibility test |
| Run interface | function call only | `python -m app.core.benchmark` → `reports/benchmark/` |
| Expanded benchmarks | leaked v2/v3/v4/oecd/wiod JSONs present in `data/calibration/` | quarantined under `archive/leaked/` |

**Tie-correction effect (the only numeric movement on the clean set):** e.g.
Naive Persistence Spearman corrected from a spurious **−0.5238 → 0.0** (a
constant predictor cannot rank); GEDS/Leontief/Diffusion Spearman shifted only
in tie-affected digits (see `docs/REPRODUCIBILITY.md` §5).

### After — current honest leaderboard (clean N=8, `reports/benchmark/benchmark.json`)

| Model | MAE | RMSE | R² | Pearson | Spearman | Kendall | NDCG@5 |
|---|---|---|---|---|---|---|---|
| SEIRS (GEDS) | 0.0248 | 0.0361 | 0.0451 | 0.7196 | 0.8264 | 0.6183 | 0.9422 |
| Leontief | 0.0301 | 0.0478 | −0.6696 | 0.0753 | 0.6347 | 0.4001 | 0.7005 |
| **Linear Diffusion** | **0.0152** | **0.0179** | **0.7647** | **0.8790** | **0.8503** | **0.6910** | **0.9905** |
| Naive Persistence | 0.0305 | 0.0370 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — |

**Honest reading:** Linear Diffusion wins every metric. GEDS is second on error
and correlation; it ranks events well (Spearman 0.83) but does **not** beat the
simplest network baseline. This is locked by
`test_reproducibility.py::test_winner_is_linear_diffusion`.

---

## 5. Remaining risks

1. **Provenance-uncertain catalogue layer.** `scientific_registry.py` (generator
   quarantined) and `bootstrap_scientific_layer.py` (reads v2 lineage) cannot be
   certified clean from the repo alone. Left in place and flagged — **do not
   cite their outputs** until provenance is reconciled.
2. **Leaked-artifact consumers in `scripts/`.** `phase5_regenerate_state.py`
   (broken: reads moved v2 JSONs), `bootstrap_benchmark.py`,
   `gen_event_mapping_report.py`, `write_uncertainty_reports.py`, and the v4 trio
   read v2/v3/v4 artifacts. None contain the leak transform, but their outputs
   can echo leaked numbers. Re-point at `reports/benchmark/` or archive.
3. **Untracked OECD/WIOD/raw data.** A large set of untracked files under
   `backend/data/csv/` (`*_oecd*`, `*_wiod*`, `expanded_graph_*_v2`) and
   `backend/data/raw/` (inspection dumps, parsed comtrade/oecd/wiod) predates
   this pass and belongs to the leaked "Mission 1+2" lineage. **Left untouched**
   (deleting untracked data is destructive); a reviewer should decide keep vs.
   purge.
4. **Uncommitted state.** Nothing is committed. A reviewer should commit the
   stabilization as a reviewable unit (suggested: one commit for the archive
   moves, one for the harness/metrics/docs/tests).
5. **Ambiguous-lineage calibration JSONs** (`ablation.json`,
   `mechanism_trace.json`, `loeo_results.json`, `bootstrap_results.json`,
   `posterior.json`, `sobol.json`, `de_result.json`, `provenance.json`,
   `literature_priors.json`) were **kept** (no-guessing) and remain flagged.
6. **Cross-platform floats.** Determinism is guaranteed for a fixed NumPy
   version + platform; the last ULP may differ across platforms (documented).
7. **Small corpus.** N=8 is honest but statistically thin; any expansion must
   follow the leak-free recipe (shock magnitude from a source independent of the
   target).

---

## 6. Recommended next sprint (bounded; no new frameworks)

1. **Resolve the review register** in `docs/SCIENTIFIC_STATUS.md` §G: certify or
   archive `scientific_registry.py`; archive `phase5_regenerate_state.py`;
   re-point or archive the leaked-artifact consumers; delete dev scratch (after
   moving a `de_calibrate`/`sensitivity` example into tests).
2. **Decide on untracked OECD/WIOD/raw data** (risk #3): keep-and-track or purge.
3. **Commit the stabilization** as reviewable units (risk #4).
4. **If expanding the corpus**, do it the leak-free way: standardized shock per
   event class, an externally documented intensity index, or hand-authored cited
   estimates — **never** a transform of the observed outcome
   (`archive/leaked/README.md` final section).
5. **Investigate why GEDS trails Linear Diffusion** as a *scientific* question on
   the clean set (mechanism analysis), not by changing the benchmark — the
   honest-winner test must keep passing unless a reviewed, deliberate change is
   made.

---

## 7. How to verify

```bash
cd backend
python -m pytest -q                              # full suite (expect 60 passed)
python -m app.core.benchmark --check             # determinism self-test (exit 0)
python -m app.core.benchmark                     # regenerate reports/benchmark/
python -c "from app.main import app; print(len(app.routes), 'routes')"
```

Leak/quarantine spot-checks:

```bash
# leak transform must appear ONLY under archive/leaked/
grep -rnE 'abs\([a-z_]*gdp[a-z_]*\).*/\s*50|magnitude = max\(0\.1' backend/ archive/
# no remaining file imports a quarantined module
grep -rnE 'import (run_oecd_benchmark|phase3_benchmark_v2|translate_event|remap_events_for_oecd_graph)' backend/
```
