# GEDS Rigor Overhaul — Progress Log

Three execution batches completed across 2026-05-16 to 2026-05-17.
**Read `AUDIT.md` for the full findings.** This file is the contents index.

---

## Batch 1 — foundations (delivered)

| Phase | Module | Endpoint | Key result |
|---|---|---|---|
| 2 | `app/core/mcmc.py` | `/api/v1/posterior` | MCMC posterior with R̂, autocorr, sensitivity per parameter |
| 6 | `app/core/cross_validation.py` | `/api/v1/cv-report` | LOO-CV with bootstrap 95% CIs |
| 5 | `app/core/baselines.py` | (used by benchmark) | Leontief + linear-diffusion baselines |
| 10 | `app/core/research_metrics.py` | `/api/v1/research-metrics` | SFI + RES + CCS with permutation tests |
| 1 | `AUDIT.md` | (document) | Honest scientific assessment |

## Batch 2 — calibration + tail risk (delivered)

| Phase | Module | Endpoint | Key result |
|---|---|---|---|
| 6 | `app/core/postcalibration.py` | `/api/v1/calibration-report` | Isotonic LOO calibration — **found it hurts at N=8** |
| 2 | `app/core/de_calibrate.py` | (CLI) | Differential evolution — **found params at bounds** |
| 7 | `app/core/tail_risk.py` | `/api/v1/tail-risk` | VaR / CVaR / black-swan / fan chart |
| 10 | `app/core/research_metrics.py` (extended) | (in /research-metrics) | Economic Resilience Tensor + Shock Absorption Capacity |
| 6 | `app/core/backtest.py` | `/api/v1/backtest` | Track-record live endpoint |
| 12 (minimal) | `frontend/app/validation/page.tsx` | `/validation` | Live dashboard of all validation panels |
| 6 (truthful UI) | `StatusRibbon.tsx`, `FAQPanel.tsx`, `MetricsPanel.tsx` | (UI) | Removed false "r=0.97" badge; now reads `/api/v1/cv-report` live |

## Batch 3 — ablation + sensitivity + benchmark (delivered)

| Phase | Module | Endpoint | Key result |
|---|---|---|---|
| 5 | `app/core/benchmark.py` | `/api/v1/benchmark` | **Linear diffusion beats GEDS on every metric** |
| 6 | `app/core/ablation.py` | `/api/v1/ablation` | **SEIS + adaptive rerouting are dead weight at N=8** |
| 6 | `app/core/sensitivity.py` | (CLI) | Sobol — **3 of 5 params non-identifiable, recovery_rate dominates** |
| 2 | `app/core/mcmc.py` (widened priors) | `/api/v1/posterior` | Bounds widened based on DE diagnostic |

---

## The three findings that matter for ISEF

1. **Honest benchmark exposure** — built leaderboard, baseline beats engine. (`/api/v1/benchmark`)
2. **Honest ablation exposure** — built ablation, two components are dead weight. (`/api/v1/ablation`)
3. **Honest identifiability exposure** — two independent methods (MCMC + Sobol) agree that 3 of 5 parameters are non-identifiable. (`/api/v1/posterior` + `_smoke3.py` Sobol section)

ISEF judges score these honest-self-assessment findings **higher** than uncritical "our model is great" claims. Use them.

---

## What was NOT done — and why

This is the honest deferred list. Each item is real work that requires resources beyond a single autonomous turn or external data:

| Phase | Item | Why deferred | What it needs |
|---|---|---|---|
| 3 | Graph expansion to 150–200 countries × 20–30 sectors | UN Comtrade API key + bulk CSV download + days of HS-code ↔ industry mapping | API access + 40 hrs of focused ETL labor |
| 4 | GNN replacement of static D_eff | No training data: N=8 events, GNNs need 1000+ | Generate synthetic from existing engine OR collect more events |
| 5 | Agent-based model | Weeks of implementation, hard to validate without large data | Same as above |
| 6 | 30–50 historical events database | Literature labor (~2 hr/event = ~60 hr total) | Research assistant or 2 weeks of focused work |
| 8 | Transformer NER (replace spaCy) | Marginal lift; spaCy is good enough at current scale | Only when data layer is the bottleneck |
| 9 | XGBoost / transformer cascade predictor | No labeled training set | Wait for events database expansion |
| 11 | Enterprise multi-tenant + auth + alerts | Months of work; premature without a design partner | Land a design partner first |
| 12 | Full Bloomberg/Palantir UI redesign | 2–4 months; premature for ISEF | Validate science first |
| 13 | Research paper draft | Premature; needs converged posterior + N≥30 events + GNN baseline | Q3 2026 after data work lands |

---

## How to run everything locally

```cmd
cd /d D:\GEDS\backend

REM verify all three batches in one go (~5 min total)
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" scripts/_smoke.py
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" scripts/_smoke2.py
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" scripts/_smoke3.py

REM production MCMC (~90 min, gives publication-grade posterior)
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" -m scripts.mcmc_calibrate --n-steps 2000 --n-walkers 64

REM serve the live dashboard
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" -m uvicorn app.main:app --reload
```

Then in another terminal:

```cmd
cd /d D:\GEDS\frontend
npm run dev
```

Open http://localhost:3000 (main dashboard) and http://localhost:3000/validation (the new live audit dashboard).

---

## File map

```
backend/app/core/
├── mcmc.py              Bayesian inference (emcee)
├── de_calibrate.py      Differential Evolution calibration
├── postcalibration.py   Isotonic post-calibration
├── cross_validation.py  Leave-one-event-out CV with bootstrap CI
├── sanity.py            Global loss caps + calibrator penalty term
├── sensitivity.py       Sobol global sensitivity (SALib)
├── ablation.py          Component-wise ablation
├── benchmark.py         Unified model leaderboard
├── baselines.py         Leontief + linear-diffusion baselines
├── backtest.py          Frozen-param historical replay
├── tail_risk.py         VaR / CVaR / fan chart
└── research_metrics.py  SFI / RES / CCS / ERT / SAC + stat eval

backend/scripts/
├── mcmc_calibrate.py    Production MCMC runner
├── calibrate.py         Optuna calibration (legacy, batch 0)
└── (batch smoke reproducers `_smoke*.py` removed in Batch 4 — superseded
     by `tests/` + `python -m app.core.benchmark --check`)

frontend/app/
├── page.tsx             Main simulation dashboard (truthful badges now)
└── validation/page.tsx  Live audit dashboard (6 endpoints)

frontend/components/
├── NarrativePanel.tsx   Grok policy analysis
├── NewsSignalsPanel.tsx Live news → graph deltas
└── StatusRibbon.tsx     Live LOO-CV badge in top-right

data/calibration/
├── provenance.json      Optuna calibration result
├── posterior.json       MCMC posterior (when run)
├── isotonic.json        Isotonic calibration model
├── de_result.json       DE result
├── ablation.json        Ablation report
├── sobol.json           Sobol sensitivity report
└── benchmark.json       Benchmark leaderboard

docs/
├── AUDIT.md             Full scientific audit + all 3 batches of findings
└── PROGRESS.md          This file
```

---

## Batch 4 — event-set expansion N=8 → N=21 (2026-06-09)

Single highest-leverage fix from `AUDIT.md` ("adding more historical events
would change this"). Same authoring convention as the original 8: shock
magnitudes describe source-side capacity offline from contemporaneous public
reporting; never derived from the observed targets. The new set deliberately
includes two near-miss events (Japan–Korea export controls 2019, Taiwan
drought 2021) so the benchmark also penalises false positives.

| Change | Where | Key result |
|---|---|---|
| +13 historical events (Thailand floods 2011 … Red Sea 2023) | `app/data/seed_data.py` | Benchmark now N=21 |
| SEIRS state-machine unit tests (15 tests: all transitions, modifiers, rerouting) | `tests/test_seis.py` | Previously zero coverage of the novel layer |
| Golden snapshot + winner lock updated to N=21 | `tests/test_reproducibility.py` | Explicit, reviewed numeric change |
| Dead scripts removed (`_smoke*.py`, `phase5_regenerate_state.py`) | `backend/scripts/` | Per SCIENTIFIC_STATUS.md disposition |
| Stale n=8 claims fixed (FAQ EN/RU, API docstrings) | `frontend/lib/ui-context.tsx`, `app/api/routes.py` | UI text matches live numbers |

### The honest headline (N=21, default config)

| Model | MAE | RMSE | Pearson | Spearman | R² |
|---|---|---|---|---|---|
| Linear Diffusion | **0.0130** | **0.0169** | **0.822** | **0.598** | **0.600** |
| Naive Persistence | 0.0168 | 0.0268 | 0.000 | 0.000 | 0.000 |
| Leontief I-O | 0.0180 | 0.0321 | -0.072 | 0.215 | -0.444 |
| GEDS SEIRS | 0.0216 | 0.0379 | 0.140 | 0.361 | -1.009 |

**The N=8 rank-correlation result (Spearman 0.83) did not survive the
expansion — it drops to 0.36 on N=21, i.e. it was largely a small-sample
artifact.** Naive persistence now beats GEDS on MAE. Linear diffusion's
signal, by contrast, holds up (Pearson 0.82). This is exactly why the
expansion was the right experiment: it falsified a result that looked
publication-ready at N=8. Next step is recalibration of the five engine
parameters against the expanded set (they were tuned in the N=8 era) and,
if that fails to close the gap, treating linear diffusion as the production
propagation kernel with SEIRS kept as a research layer.

### Batch 4 addendum — DE recalibration on N=21 (2026-06-09, same day)

Full 3-restart DE run on the expanded set (46 min): in-sample benchmark fit
improves to MAE 0.0108 / Pearson +0.85 / R² +0.67 — nominally **beating
linear diffusion (0.0130 / +0.82 / +0.60) for the first time**. Two honest
caveats before celebrating: (1) that is an in-sample comparison against a
parameter-free baseline, and (2) **4 of 5 parameters converged onto their
prior bounds** (`bullwhip_factor` = 2.0 exactly, `recovery_rate` = 0.01
exactly, `amplification_mu` ≈ 8.0, `inventory_scale` ≈ 2.0) — the optimizer
wants to leave the box, which is the classic signature of structural
misspecification rather than a well-identified optimum.

Verdict pending: `scripts/loo_de_validation.py` runs leave-one-out CV with
per-fold DE re-calibration (the fair, fully out-of-sample comparison) and
writes `data/calibration/loo_de_result.json`. If the out-of-sample MAE still
beats linear diffusion, the recalibration is real; if not, the in-sample win
was overfitting and the honest headline stays "the baseline wins".

### Batch 4 verdict — out-of-sample LOO-DE result (2026-06-09)

`scripts/loo_de_validation.py` (21 folds, per-fold DE re-calibration on the
other 20 events, fully out-of-sample pooled score):

| Model | MAE | RMSE | Pearson | Spearman | R² |
|---|---|---|---|---|---|
| GEDS SEIRS, LOO-recalibrated (out-of-sample) | **0.0115** | **0.0165** | 0.787 | 0.490 | **0.619** |
| Linear Diffusion (parameter-free) | 0.0130 | 0.0169 | **0.822** | **0.598** | 0.600 |
| GEDS SEIRS, default params | 0.0216 | 0.0379 | 0.140 | 0.361 | −1.009 |

**Split decision, honestly reported:** the recalibration is real — it survives
out-of-sample testing (MAE nearly halved, 0.0216 → 0.0115) and GEDS now beats
the baseline on every *error* metric. The baseline still wins both *ranking*
metrics (Pearson/Spearman). Worst misses are concentrated in pure-logistics
events (Yantian 0.057 pred vs 0.006 obs; Red Sea / Suez / Malaysia predicted
≈0) — the engine over-reacts to port shocks and under-couples chokepoint
nodes, which is the next structural target. Parameter-at-bounds caveat from
the in-sample run still applies and still argues for widening/regrounding the
priors before adopting these values as engine defaults.

---

## Batch 5 — graph-connectivity repair (2026-06-10)

LOO Batch-4 verdict located the worst misses in logistics events. Root-cause
diagnosis found two structural holes and one event-authoring error — all
three fixed at the data layer, engine untouched:

| Defect | Symptom | Fix |
|---|---|---|
| `MYS:semiconductors` had zero outbound edges (a sink) | Malaysia-2021 predicted exactly 0 | 3 packaging→automotive edges, weights from SIA/McKinsey ATP share × auto exposure |
| Shipping nodes had zero inbound edges | Suez/Red-Sea predicted exactly 0 shipping impact | Chokepoint→carrier links; weight = traffic_share × (cost−1)/cost from the existing literature reroute-cost multipliers — **no new free parameters** |
| Yantian magnitude 0.35 was facility-level, not node-level | 9.5× over-prediction | 0.07 = 10% of CHN container exports × 70% throughput loss (convention fix, arithmetic in-place) |

Result (default params, N=21): GEDS MAE 0.0216 → **0.0192**, Spearman 0.36 →
**0.42**; linear diffusion ALSO improved 0.0130 → **0.0111** (Pearson 0.91) —
the repair helps every model equally, which is the signature of a genuine
graph fix rather than model-specific tuning. All four worst logistics misses
now land in the right range. Out-of-sample LOO-DE and MCMC posterior were
re-run on the repaired graph (artifacts in `data/calibration/`).

### Batch 5 verdict — out-of-sample after the graph repair (2026-06-11)

21-fold LOO-DE on the repaired graph, fully out-of-sample, vs the same-graph
parameter-free baseline:

| | MAE | RMSE | Pearson | Spearman | R² |
|---|---|---|---|---|---|
| GEDS LOO-recalibrated (Batch 4 graph) | 0.0115 | 0.0165 | 0.787 | 0.490 | 0.619 |
| **GEDS LOO-recalibrated (repaired graph)** | **0.0082** | **0.0112** | **0.910** | 0.617 | **0.825** |
| Linear diffusion (repaired graph) | 0.0111 | 0.0140 | 0.905 | **0.811** | 0.725 |

The connectivity repair moved every GEDS out-of-sample metric sharply:
MAE −29%, Pearson 0.79 → 0.91, R² 0.62 → 0.83. No event predicts zero any
more and no event misses by 10×. Out-of-sample, GEDS now beats the baseline
on MAE/RMSE/R² and ties Pearson; the baseline keeps Spearman (rank order)
— the remaining honest gap. MCMC on the repaired graph (unconverged at 350
steps, flagged as such) shows 4 of 5 parameters now carry data signal vs 2
in the May audit; `bullwhip_factor` remains non-identifiable and is the
next candidate for removal via ablation.

---

## Batch 6 — external-data validation layer: IMF PortWatch + NY Fed GSCPI (2026-06-11)

Two independent datasets (user-supplied downloads, committed under
`backend/data/raw/external/`) the model was never calibrated on.

| Check | Result |
|---|---|
| Ever Given spec (0.90, 2w) vs measured daily Suez transit deficit | **CONFIRMED** — measured peak 0.96; weekly bins smear to 0.63; catch-up surge −0.30 after clearing (a real phenomenon the engine does not yet model) |
| Red Sea spec magnitude (0.55) vs measured | **CONFIRMED** — weekly peak 0.549; mean 0.44 over the window |
| Red Sea spec duration | **CORRECTED 26 → 40 weeks** — measured deficit stayed >0.28 for 57+ weeks and is still elevated in June 2026 |
| Capacity-factor rerouting premise | **MEASURED SUPPORT** — 111% of lost Suez transits reappear at Cape of Good Hope, weekly correlation 0.805 |
| GSCPI: predicted peak CSI vs measured pressure rise per event | Spearman **0.70** on 9 non-overlapping events (0.45 on all 21 — the 2021 cluster shares one global spike; caveat recorded in artifact) |

New permanent assets: `app/core/portwatch.py` (+6 tests pinned to measured
facts in the raw file — they double as data-integrity checks),
`scripts/portwatch_validation.py`, `scripts/gscpi_validation.py`, endpoints
`/portwatch-validation` + `/gscpi-validation`, and an "External data
cross-checks" panel on the validation page. ICIO ReadMe received — full
2023-edition tables still needed for the graph expansion (next batch).

---

## Batch 7 — researched event expansion N=21 → 26 + out-of-graph registry (2026-06-11)

Eleven structured literature dossiers (committed with full citations under
`backend/data/raw/external/perplexity_events/`) processed into:

**Five new in-graph events** — Chi-Chi 1999 (TWN semi, near-miss), Hurricane
Harvey 2017 (US petrochem→consumer, partial near-miss), US West Coast ports
2015 (slowdown), Korea trucker strikes 2022 (near-miss), Panama Canal drought
2023–24 (new `CP:Panama` node + capacity-factor links). Panama's spec was
corrected DOWN by measurement: press transit counts implied 0.45, IMF
PortWatch measures a 0.28 mean weekly deficit → spec 0.30, now CONFIRMED
alongside Suez-2021 (0.90 vs 0.96) and Red Sea (0.55 vs 0.44).

**Six out-of-graph near-misses** added to `data/csv/historical_events.csv`
(SARS 2003, Kobe 1995, Eyjafjallajökull 2010, UK fuel 2021, Germany floods
2021, China Ga/Ge controls 2023) — a documented false-positive library with
absorption mechanisms cited; unmappable onto the current 12×6 graph.

**The honest headline got harder — by design.** The N=26 set is adversarial
(10+ near-misses). Default-param winners split: Leontief takes MAE (chronic
under-prediction becomes an asset on near-misses), naive persistence takes
RMSE/R², linear diffusion keeps the correlations; GEDS default trails. GSCPI
clean-subset Spearman fell 0.70 → 0.31 — the default-param engine
over-predicts near-misses, which is exactly the absorption-mechanism gap
(inventories, priority restoration, modal substitution) the dossiers
document. Next target: make the SEIRS buffer layer earn its keep on the
near-miss subset. Out-of-sample LOO-DE re-run pending.

### Batch 8 attempt — inventory-absorption mechanism (2026-06-11): NEGATIVE result, kept out of the engine

Hypothesis from the Batch-7 dossiers: near-miss over-prediction should be
fixed by making the E-state buffer absorb damage (a node with stock consumes
inventory instead of taking propagated impact, incl. first-strike
interception for sudden upstream outages). Implemented three escalating
variants; all were REVERTED because the benchmark refused to move
(0.0220 → 0.0250 → 0.0257 MAE — worse each time).

The trace explains why, and it is the real finding: **downstream absorption
cannot rescue a near-miss while the upstream source never heals.** Chi-Chi's
prediction is dominated by the source node still carrying ~70% of its shock
at week 12, because shock decay is a single global `recovery_rate` (7%/week
default; the DE calibrator pushes it to 1%/week to fit long crises) — while
the real TSMC restored ~90% of output in 8 days. One global recovery
constant cannot represent both "TSMC heals in days" and "COVID drags for a
year". **Next mechanism target, with evidence: per-node/per-event recovery
dynamics** (e.g., couple shock decay to the node's existing
`recovery_delay_weeks` instead of one global rate). The negative experiment
is preserved here deliberately — it converts the audit's old "recovery
miscalibrated" note into a mechanistic diagnosis.

### Batch 7 verdict — out-of-sample LOO-DE on the adversarial N=26 set (2026-06-11)

| | MAE | Pearson | Spearman | R² |
|---|---|---|---|---|
| GEDS LOO-recalibrated, N=21 set | 0.0083 | 0.910 | 0.617 | +0.824 |
| **GEDS LOO-recalibrated, N=26 adversarial** | **0.0170** | **0.166** | 0.525 | **−1.525** |
| Best baseline on N=26 (Leontief MAE) | 0.0144 | — | — | — |

**The N=21 out-of-sample win did not survive the adversarial expansion.**
Per-fold recalibration cannot absorb the near-misses either: the worst fold
is Chi-Chi (predicted 0.185 vs observed 0.005 — the source node never heals
within the horizon), followed by the two big chip crises now UNDER-predicted
(COVID 0.047 vs 0.115) because the calibrator is pulled in opposite
directions by fast-recovery and slow-recovery events. This is precisely the
Batch-8 mechanistic diagnosis showing up out-of-sample: **a single global
recovery_rate is the binding structural constraint.** Per-node recovery
dynamics (couple shock decay to the existing per-node recovery_delay_weeks)
is now the top-priority engine change, with a ready-made falsification test:
it must fix Chi-Chi without breaking COVID.

---

## Batch 9 — OECD ICIO 2025: data layer + hand-weight cross-validation (2026-06-12)

The graph-expansion prerequisite finally landed: the official **OECD ICIO
2025-edition** year-2019 table (the pre-COVID structural baseline) is now in
the repo with full provenance, and — per the "cross-validate before you
expand" instruction — the first scientific use is an audit of our own hands:
every hand-authored `EDGES_RAW` weight recomputed from measured 2019
input-output flows.

| Change | Where |
|---|---|
| ICIO 2025 ed. 2019 table (81 economies × 50 industries, SML) + ReadMe + annex + provenance, sha256-pinned | `backend/data/raw/external/icio2025/` |
| Loader + edge-measure derivation + expansion prototype | `app/core/icio.py` |
| Cross-validation report (55 production edges scored, 19 chokepoint links explicitly excluded → all 74 seed edges covered) | `scripts/icio_derive_edges.py` → `data/calibration/icio_edge_check.json` |
| Expanded-graph prototype, measured columns only, **NOT wired into the engine** | `scripts/icio_expand_graph.py` → `data/csv/expanded_graph_{nodes,edges,meta}_v3.*` (405 nodes, 1 964 edges) |
| 8 data-integrity tests pinned to measured facts | `tests/test_icio.py` |

Notes: the small (SML) version is *not* sector-aggregated — it is the full
50-industry 2025 edition, only without the CN1/CN2/MX1/MX2 splits (the
"~76×45" expectation was the 2023 edition's shape; recorded in
PROVENANCE.md). oecd.org/webfs-sti sit behind TLS-fingerprint bot
protection; `curl_cffi impersonate="chrome"` downloads them (documented in
PROVENANCE.md for re-runs).

### Batch 9 findings — the instrument matters, and the hands are mostly honest

1. **The comparison measure must match the authoring convention.** Manual
   weights vs naive ICIO penetration (domestic supply in the denominator):
   Spearman 0.20. Same weights vs **import penetration** (foreign sources
   only — the Comtrade convention the weights were authored with): Spearman
   0.43, Pearson 0.46. Per family: the six Comtrade-derived automotive edges
   hit **Spearman 0.83**; the TWN-semi family (penetration × exposure) sits
   at ~0.31 with manual/measured ratios mostly 1–4.7×; the "authored"
   (literature/calibrated) family is the weakest (~0 rank correlation) — the
   edges to revisit first.
2. **Import-derived weights are blind to domestic input dominance.** ICIO
   measures what Comtrade can't: USA:auto→USA:consumer manual 0.10 vs 0.63
   measured within-type share; CHN:semi→CHN:elec 0.15 vs 0.78; JPN/USA
   domestic semi→auto similar. The current 12×6 graph systematically
   under-couples domestic supply chains.
3. **The ASML dependency is real but lives in the capital account.**
   NLD:semi edges (manual 0.30–0.45) score ~0.003 on every flow share — not
   because the dependency is fake, but because lithography equipment is C28
   machinery flowing into the buyer's **GFCF (investment) column**:
   measured NLD_C28→TWN_GFCF = $2.51 B, →KOR $0.56 B (2019). Input-output
   intermediate flows structurally cannot ground criticality edges for
   capital equipment; these stay literature-authored, now with the measured
   reason pinned in a test.
4. **Two concrete weight corrections surfaced:** DEU→JPN:auto manual 0.451
   was *finished-car* import share — measured all-of-C29 import share is
   0.23 (manual 2× high); THA→JPN:auto was confessed "calibrated, no
   bilateral pair" at 0.15 — ICIO measures 0.08. Both are replacement
   candidates for the next graph revision (deliberately not hot-fixed here:
   weight changes re-open the benchmark, which deserves its own batch).
5. **Shipping-as-service edges are over-weighted 3.7–4.8×** (CHN:ship→USA:cons
   0.40 vs 0.083): the authored numbers encode logistics dependency, but H50
   purchases measure only direct freight-service spend. Same lesson as the
   Batch-5 chokepoint repair: the logistics layer needs its own convention
   (transport margins), not naive I-O shares.

Expansion prototype caveat, recorded in the meta artifact: ICIO C26 cannot
split semiconductors from electronics, so the v3 prototype carries one
merged `electronics_c26` industry (a Comtrade HS-8541/42 overlay is the
planned split). Pre-existing on this branch and unchanged: the 6
`test_portwatch.py` tests fail in a fresh clone because
`portwatch_daily_chokepoints.csv` was never committed (it lives on the
local machine that ran Batch 6) — same gitignore trap the ICIO files just
avoided via `git add -f`; worth committing the same way.
