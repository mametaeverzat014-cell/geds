# Reproducibility

This document specifies how to reproduce the GEDS model benchmark exactly, what
guarantees determinism, and every source of nondeterminism that was found and
controlled during the foundation-stabilization pass.

The headline guarantee: **`python -m app.core.benchmark` produces identical
scores on every run.** This is enforced automatically by
`backend/tests/test_reproducibility.py`.

---

## 1. Environment

| Component | Pinned value |
|---|---|
| Python | 3.11 (developed/verified on 3.11.9) |
| NumPy | `>=1.26,<2.0` (verified 1.26.4) |
| SciPy | `>=1.14` (verified; used only in tests, for metric cross-validation) |
| Dependency manifest | `backend/pyproject.toml` |

> Note: the benchmark itself depends only on NumPy + the standard library.
> SciPy is a **test-only** dependency, used to cross-check the ranking metrics
> against a reference implementation.

### Install

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate     POSIX: source .venv/bin/activate
pip install -e .[dev]
```

---

## 2. Running the benchmark (single command)

From `backend/`:

```bash
python -m app.core.benchmark            # write reports/benchmark/{benchmark.json, summary.md}
python -m app.core.benchmark --check    # determinism self-test, no files written, exit 1 on drift
python -m app.core.benchmark --out DIR  # custom output directory
python -m app.core.benchmark --ndcg-k K # change the NDCG cutoff (default 5)
```

Outputs are written to `reports/benchmark/` at the repository root:

- `benchmark.json` — machine-readable: timestamp, pinned config, per-model
  scores (MAE, RMSE, MAPE, R², Pearson, Spearman, Kendall τ-b, NDCG@k, bias,
  Murphy skill), and per-metric winners. Always valid JSON (NaN/inf → `null`).
- `summary.md` — human-readable leaderboard table.

The legacy FastAPI endpoint `GET /benchmark` (`app/api/routes.py`) still calls
`run_benchmark()` + `save_benchmark()` and writes the served copy to
`data/calibration/benchmark.json`. Both paths share the same deterministic
scoring code.

---

## 3. What makes a run reproducible

### 3.1 Pinned engine configuration

The benchmark configures the SEIRS engine from a single frozen constant in
`app/core/benchmark.py`:

```python
BENCHMARK_CONFIG = EngineConfig(seed=0, stochastic_sigma=0.0)
```

- `stochastic_sigma = 0.0` means the cascade takes **no RNG draws** — the engine
  is a pure deterministic function of (graph, config, shocks).
- `seed = 0` is belt-and-suspenders: even if a stochastic term were ever
  enabled, the run would still be reproducible.

These values equal the historical `EngineConfig()` defaults, so pinning them did
**not** change any previously published number. This is verified by the golden
snapshot test (§4).

### 3.2 Fixed input data

- **Graph.** `load_graph()` returns a hard-coded seed graph; `compile_graph()`
  is a deterministic transform. No file I/O, network, or randomness.
- **Events.** The benchmark scores the `HISTORICAL_EVENTS` corpus in
  `app/data/seed_data.py` (the clean, **hand-authored** N=8 set). Shock
  magnitudes are public estimates authored by hand, **not** derived from the
  target — see §5.
- **Stable sorts.** All ranking metrics sort with `kind="mergesort"` (stable),
  so tie ordering is deterministic across runs and platforms.

### 3.3 The one nondeterministic field, isolated

`BenchmarkReport.timestamp` is `datetime.now(timezone.utc)` and therefore
changes every run. It is deliberately **excluded** from the scored payload. The
determinism contract is defined over `scored_payload(report)` (the per-model
scores only), not the wrapper. `--check` and the reproducibility test both
compare `scored_payload`, ignoring the timestamp.

---

## 4. Automated validation

`backend/tests/test_reproducibility.py` is the regression guard. Run it with:

```bash
cd backend
python -m pytest tests/test_reproducibility.py -q
```

It asserts:

1. **Config is pinned** — `stochastic_sigma == 0.0`, `seed == 0`.
2. **Determinism** — two back-to-back `run_benchmark()` calls produce identical
   `scored_payload`.
3. **Golden snapshot** — model scores match frozen expected values (the `GOLDEN`
   dict). If a code change legitimately changes results, update `GOLDEN` **in the
   same commit** so every numeric change is explicit and reviewable.
4. **Persistence has no ranking** — the constant predictor reports Spearman =
   Kendall = 0.0 and NDCG = `null` (a constant predictor cannot rank).
5. **Honest winner is locked** — Linear Diffusion wins MAE/RMSE/Pearson on the
   clean set; GEDS does not beat it. A future "win" cannot appear without a
   deliberate, reviewed change to this assertion.

### Frozen results (clean N=8 set, captured 2026-06-04)

| Model | MAE | RMSE | R² | Pearson | Spearman | Kendall | NDCG@5 |
|---|---|---|---|---|---|---|---|
| SEIRS (GEDS) | 0.0248 | 0.0361 | 0.0451 | 0.7196 | 0.8264 | 0.6183 | 0.9422 |
| Leontief | 0.0301 | 0.0478 | −0.6696 | 0.0753 | 0.6347 | 0.4001 | 0.7005 |
| Linear Diffusion | **0.0152** | **0.0179** | **0.7647** | **0.8790** | **0.8503** | **0.6910** | **0.9905** |
| Naive Persistence | 0.0305 | 0.0370 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — |

Honest reading: on the clean hand-authored set, the **textbook linear-diffusion
baseline wins every metric**. GEDS ranks events well (Spearman 0.83) but does
not beat the simplest network baseline on error or correlation.

---

## 5. Nondeterminism & validity audit

Sources examined during stabilization and their disposition:

| Source | Status | Control |
|---|---|---|
| SEIRS engine RNG | Controlled | `stochastic_sigma=0.0` ⇒ no draws; `seed=0` pinned |
| Report timestamp | Isolated | Excluded from `scored_payload`; not part of the contract |
| Graph construction | Deterministic | Hard-coded seed graph, no I/O |
| Event corpus | Deterministic | Version-controlled `seed_data.py` |
| Rank-metric tie ordering | Controlled | Stable mergesort in all ranking metrics |
| Spearman tie handling (old) | **Fixed** | Old `argsort-of-argsort` mishandled ties; replaced with average-rank `spearman_rho` (matches SciPy). Changed only tie-affected values; e.g. persistence Spearman corrected from a spurious −0.5238 to 0.0 |
| Float reproducibility | Pinned by env | Same NumPy version + platform ⇒ identical; cross-platform may differ in the last ULP. Pin NumPy via `pyproject.toml` |

### Leaked benchmark variants — do not use for reproducibility

Several expanded benchmark scripts derive the shock **input** from the observed
**target** (e.g. `magnitude = clip(|target|·k, 0.1, 0.9)`), which makes the
input a deterministic function of the answer. Their outputs are scientifically
invalid regardless of reproducibility and have been quarantined under
`archive/leaked/` (see `archive/leaked/README.md`). The only valid, reproducible
benchmark is the clean N=8 corpus run via `app/core/benchmark.py` documented
here.
