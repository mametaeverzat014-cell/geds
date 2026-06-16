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

### Batch 9b — per-node recovery dynamics (2026-06-12)

The Batch-7/8 top-priority engine change, with its pre-registered
falsification test ("fix Chi-Chi without breaking COVID"). Shock decay is now
coupled to each node's `recovery_delay_weeks`:
`rate_i = recovery_rate × (8w reference / delay_i)`, capped at 0.95/week —
`recovery_rate` keeps its calibrated meaning (it IS the 8-week-node rate), so
a node at the historical 8.0 default behaves bit-identically to the old
engine, and the calibrator keeps 5 parameters. `per_node_recovery=False`
restores the uniform rate (new ablation row). One grounded override ships
with the mechanism: `TWN:semiconductors` = 2 weeks, from the already-cited
TSMC Chi-Chi restoration timeline (full power day 5, 90% wafer output day 8);
chokepoints' existing 4-week delays now also heal 2× faster than factories,
consistent with the PortWatch catch-up surges. All other nodes remain at the
ungrounded 8.0 default — flagged as open authoring work.

**Default-param result (N=26): improved, NOT fixed — honestly recorded.**
Chi-Chi prediction 0.1605 → 0.1349 (observed 0.005; still ~27× over), COVID
events moved −0.0003, nothing degraded; benchmark GEDS MAE 0.0220 → 0.0211,
RMSE 0.0446 → 0.0414, Pearson +0.07 → +0.09, winners table unchanged (golden
snapshot updated in the same commit). The mechanism is necessary but not
sufficient at default params: the downstream peak forms DURING the 2-week
forcing window, so faster source healing trims only the tail. The remaining
Chi-Chi error is a within-forcing absorption problem — the same wall the
Batch-8 inventory experiment hit from the other side.

Ablation on the new engine: `no_per_node_recovery` costs +0.0010 MAE (the
component earns its keep at default params, unlike SEIS/adaptive-rerouting
which remain exactly zero-effect). Honest side-finding pinned in
`ablation.json`: `no_r_state_floor` IMPROVES MAE 0.0211 → 0.0135 on the
adversarial set — the R-state hysteresis floor is now the top removal
candidate for the next ablation-driven cleanup.

**Out-of-sample verdict (26-fold LOO-DE, 66 min): the pre-registered test
FAILED — mechanism NOT adopted as engine default.**

| | MAE | RMSE | Pearson | Spearman | R² |
|---|---|---|---|---|---|
| LOO-DE, uniform recovery (Batch 7) | **0.0170** | 0.0395 | **0.166** | **0.525** | −1.525 |
| LOO-DE, per-node recovery (9b) | 0.0176 | **0.0389** | 0.127 | 0.474 | **−1.458** |

Chi-Chi fold: 0.185 → 0.176 (observed 0.005) — not fixed. The fold
calibrator still pins `recovery_rate` at the 0.0103 floor, so even 4× faster
TWN:semi decay (0.041/week) is irrelevant inside a 12-week horizon whose
downstream peak forms DURING the 2-week forcing. Worse, the coupling lets
other folds raise the global rate (auto-chip fold: recovery_rate 0.014 →
0.053), gutting the 30-week chip-shortage prediction 0.033 → 0.011 (observed
0.077). COVID itself held (0.047 → 0.049). Pooled error/rank metrics
slightly worse; only RMSE/R² marginally better.

Disposition, per the Batch-8 precedent for negative results: default
reverted to the uniform rate (`per_node_recovery=False`), golden snapshot
unchanged from 2026-06-11; the mechanism stays implemented and measured by
ablation (`with_per_node_recovery`: would give −0.0010 MAE at default
params — the in-sample/out-of-sample split is itself recorded). Experiment
artifact: `data/calibration/loo_de_per_node_recovery_experiment.json`
(canonical `loo_de_result.json` restored to the Batch-7 run). The grounded
TWN:semi `recovery_delay_weeks` 8 → 2 stays in the data layer (it only
shortens that node's R-state hysteresis; no scored metric moves).

**Refined diagnosis after two failed mechanisms:** Batch 8 attacked
within-forcing absorption downstream (inventory interception — benchmark got
worse), 9b attacked post-forcing source healing (OOS worse). The impulse
near-miss over-prediction lives in the inbound→shock conversion *during*
forcing, and the single strongest lever the ablation keeps flagging is
`r_output_floor`: removing the R-state output floor improves default MAE
0.0220 → **0.0144** — within noise of linear diffusion (0.0147). Next
mechanism candidate is therefore subtractive, not additive: drop or rethink
the hysteresis floor, re-run LOO-DE as the gate.

### Batch 9c — C26 semi/electronics split overlay (2026-06-12, same day)

The one mapping collision flagged in Batch 9 (ICIO C26 bundles semis with
computers/phones/displays) resolved with data already in the repo: the
committed UN Comtrade 2019 pull measures, per (importer, exporter) pair,
the semiconductor share of C26-type goods — (HS 8541+8542)/(+8471/8517/8528).
`scripts/icio_c26_split.py` → `data/calibration/icio_c26_split.json`;
importer world-shares match known trade structure (TWN 0.85, MYS 0.83,
CHN 0.82 — chip-importing assemblers; USA 0.17 — finished-goods importer).

**Headline: the semi-family hand weights are validated.** Rescoring all 28
cross-border semi edges with a semi-specific import penetration (exporter
C26 flows × pair semi-share): manual vs measured **Pearson 0.842 /
Spearman 0.792 (n=25)** once the three NLD/ASML edges — the proven
capital-account channel that flow shares cannot represent — are excluded.
The raw Batch-9 comparator showed only ~0.30 for this family; the gap was
the C26 collision, not the hands. Spot checks land within authoring noise:
TWN→JPN:auto 0.240 manual vs 0.246 measured, TWN→DEU:auto 0.070 vs 0.077,
TWN→THA:auto 0.150 vs 0.165. One under-weight surfaced: MYS→USA:auto 0.060
manual vs 0.182 measured (Malaysia's ATP role) — joins the Batch-9
correction-candidate list. Pinned by `test_c26_split_overlay`.

### Batch 9d — pre-registered experiment: removing the R-state output floor (2026-06-12, running)

The subtractive candidate from the 9b post-mortem, instrumented and
PRE-REGISTERED before the out-of-sample run completes (protocol identical
to 9b; `scripts/loo_de_validation.py` gained `--r-output-floor/--out`
overrides so experiments never touch engine defaults).

**Mechanism trace (default params).** `r_output_floor=0.30` pins
`output_loss ≥ 0.30` for every node in R-state until its
`recovery_delay_weeks` hysteresis elapses. Exactly four events move when
the floor is removed, and they explain the entire ablation gain
(MAE 0.0220 → 0.0144, RMSE 0.0446 → 0.0276):

| event | obs | floor 0.30 | floor 0 |
|---|---|---|---|
| vietnam-covid-lockdown-2021 (worst miss in the set) | 0.0120 | 0.1399 | **0.0070** |
| taiwan-chichi-earthquake-1999 | 0.0050 | 0.1605 | **0.0650** |
| suez-canal-2021 | 0.0080 | 0.0193 | **0.0063** |
| covid-semiconductor-2020-2021 | 0.1150 | 0.0435 | 0.0142 ⚠ |

This is the impulse/near-miss over-prediction engine-wide: not shock decay
(9b), not missing inventory absorption (Batch 8) — nodes that brush
through I→R drag a hard-coded 30% output loss for ~8 weeks regardless of
how small the shock was. The floor's one real service is carrying part of
COVID-semi's persistent loss (⚠ under-prediction deepens 0.0435 → 0.0142);
in LOO the per-fold calibrator may compensate (e.g. via lower
recovery_rate) — that is what the experiment measures.

**Pre-registered decision rule.** Adopt `r_output_floor=0.0` as engine
default only if the 26-fold LOO-DE with the floor off improves pooled
out-of-sample MAE vs the canonical 0.0170 without collapsing rank metrics
(Spearman must stay ≥ ~0.45); the COVID-semi fold movement is recorded
either way. Negative result ⇒ same disposition as 9b: keep the mechanism,
document, don't adopt. Artifact will land at
`data/calibration/loo_de_floor_experiment.json`.

**Batch 9d verdict (26-fold LOO-DE, 65 min): REJECTED at the pre-registered
gate — the floor stays.**

| | MAE | RMSE | Pearson | Spearman | R² |
|---|---|---|---|---|---|
| floor 0.30 (canonical Batch 7) | **0.0170** | **0.0395** | **+0.166** | **0.525** | **−1.525** |
| floor 0 (9d experiment) | 0.0183 | 0.0427 | −0.009 | 0.419 | −1.952 |

Every pooled metric got worse; Pearson collapsed to zero and Spearman fell
below the 0.45 gate. The fold autopsies explain why the default-param gain
was a mirage: (1) the COVID-semi fold cratered 0.0469 → 0.0062 (observed
0.115) — without the floor the fold calibrator went degenerate
(recovery_rate 0.165, inventory_scale 0.36) and the one service the floor
provided (persistent-crisis loss) has no replacement; (2) Chi-Chi did not
move at all out-of-sample (0.1850 → 0.1848) — the calibrator rebuilt the
same over-prediction through amplification_mu 7.26 + bullwhip 1.99 at their
bounds; (3) vietnam-covid was ALREADY fine in LOO (0.0111) — per-fold
recalibration had quietly absorbed the floor's worst in-sample distortion
all along. Artifact: `loo_de_floor_experiment.json`. No engine change;
`r_output_floor` keeps its 0.30 default.

**Conclusion after three pre-registered mechanism experiments (B8
inventory absorption, 9b per-node recovery, 9d floor removal): the 5-param
calibration layer is flexible enough to mask, route around, or rebuild any
single-component structural edit at N=26.** In-sample/default-config gains
systematically do not survive per-fold recalibration. This closes the
"one more mechanism will fix it" road and leaves the two honest exits that
Batch 4 already flagged: (a) adopt linear diffusion as the production
propagation kernel (it wins ranking out-of-sample with zero parameters)
and keep SEIRS as the research layer, or (b) grow N — the ICIO-grounded
graph expansion plus a 30+ event set — before touching engine structure
again. Both are data/architecture decisions, not mechanism patches.

---

## Batch 10 — Event database expansion N=18 → N=43

**Status: DONE (2026-06-14)**

Three Perplexity research files (31 source-validated queries each) were
processed into 25 new historical disruption events appended to
`backend/data/csv/historical_events.csv`.

### Event database summary (N=43)

| in_geds_graph | count | notes |
|---|---|---|
| yes | 11 | Directly calibratable against current 12-country graph |
| partial | 10 | Mappable to a node with documented caveats |
| no | 22 | Out-of-graph (countries/industries not yet in GEDS) |

### New IN-graph events (key additions)
| slug | target_node | shock_magnitude | delta_output_pct | source |
|---|---|---|---|---|
| chichi-earthquake-1999 | TWN:semiconductors | 0.50 | 0.040 | Preventionweb/TSMC/SIA 1999 |
| shanghai-lockdown-2022 | CHN:electronics | 0.20 | 0.029 | China NBS April 2022; Fortune |
| wuhan-lockdown-2020 | CHN:automotive | 0.15 | 0.015 | World Bank COVID Logistics 2020 |

### New events by type
- **Pandemic-logistics** (4): Yantian, Ningbo, Shanghai, Wuhan
- **Natural disaster logistics** (6): Rhine 2018, Rhine 2022, Panama Canal, BC floods, Mississippi, Hokkaido
- **Geopolitical-logistics** (2): Red Sea crisis, NotPetya
- **Industrial accidents** (3): Renesas fire, Freeport LNG, Colonial Pipeline
- **Natural disaster manufacturing** (5): Chi-Chi 1999, Taiwan 2024, Thailand 2011, Harvey, Katrina
- **Infrastructure** (2): LA Port congestion, Baltimore bridge
- **Near-miss documented** (3): Taiwan drought 2021, Kaohsiung 2016, Taiwan earthquake 2024

### What these unlock
- Chi-Chi 1999 + Shanghai 2022 + Wuhan 2020 add 3 new in-graph calibration
  points, bringing the in-graph total from 8 to 11.
- 10 "partial" events become fully calibratable once the ICIO graph
  expansion (Batch 8, 405 nodes) is wired into the engine.
- Near-miss events (taiwan-drought-2021, kaohsiung-2016, taiwan-2024)
  provide ground-truth FALSE POSITIVES for specificity testing.
- The Rhine drought pair (2018 + 2022) offers a natural repeat-event
  calibration check for the DEU:automotive demand node.

### Data provenance
All measurements extracted from primary sources cited per-row in the CSV
`sources` column. Values flagged `missing` where no clean published number
exists. Methodology follows the Batch 5 convention: source-side
`shock_magnitude_geds` only; demand-side and macroeconomic effects in
`delta_gdp_pct` / `delta_cpi_pct` columns separately.

---

## Batch 11 — ICIO 81×5 expanded graph wired into the live engine

**Status: DONE (2026-06-14) — opt-in, default unchanged**

This is exit (b) from the Batch 9 conclusion: grow N (graph) rather than
patch engine mechanism. The expansion prototype (`core.icio.run_graph_expansion`,
405 nodes / 1964 edges, committed as `expanded_graph_{nodes,edges}_v3.csv`) is
now loadable by the running engine.

### What landed
- `app/data/expanded_graph.py` — `build_expanded_snapshot()` reads the v3 CSVs
  and produces an engine-ready `GraphSnapshot` (81 economies × 5 sectors:
  electronics_c26, automotive, consumer_goods, aerospace, shipping).
- `app/data/seed.py` — `load_graph()` dispatches to the expanded snapshot when
  `GEDS_GRAPH_VERSION=v3`; default `v2` is byte-for-byte unchanged.
- `tests/test_expanded_graph.py` — 3 smoke tests (shape, industry/resilience
  mapping, compiles-and-cascades).

### Parameter derivation (uncalibrated structural priors)
The v3 CSVs carry only ICIO structure (output, flow, input_share, penetration);
the engine's behavioral parameters are derived:
| param | source |
|---|---|
| industry | ICIO label → `Industry` enum (electronics_c26 → ELECTRONICS) |
| resilience | LPI 2018 where available (same formula as seed); neutral 0.50 for the 69 economies LPI 2018 doesn't cover in-repo |
| amplification / threshold | per-sector defaults mirroring the seed graph ranges |
| dependency_weight | import penetration, clipped [0,1] |
| gdp_usd | node output_usd_m × 1e6 |

### Verification
- v3: 405 nodes, 1964 edges, full centrality, 81 ECV-geo origins; a 0.6 shock on
  `TWN:electronics_c26` cascades to 44 affected nodes at peak.
- v2 regression: golden reproducibility snapshot + propagation suite pass
  unchanged (88/88 non-portwatch tests green; the 6 portwatch failures are a
  pre-existing missing-external-CSV issue, untracked in git).
- Only 60 of 405 nodes (12 LPI-covered countries × 5 sectors) have real
  resilience; the rest use the neutral default.

### Honest limitations / next steps
- **Not calibrated.** The seed parameters were fit to the sparse 12-country
  topology; the v3 priors are structural, not tuned. A dedicated DE/MCMC
  recalibration on the dense graph is required before v3 predictions are
  trustworthy — that is the follow-up, not this PR.
- **LPI gap.** Full LPI 2018 ingestion for all 81 economies (the WB endpoint
  already returns them; the fetcher just filtered to 12) replaces the neutral
  default.
- **Scenarios still target v2 IDs.** Mapping the historical-event shocks onto
  v3 node IDs (so the 10 "partial" events from Batch 10 become in-graph
  calibration points) is the payoff step that this wiring unlocks.

---

## Batch 12 — Standardized production-impact target (Task #2)

**Status: DONE (2026-06-15) — data + finding; engine targets NOT changed**

Deep-research pass (Perplexity, primary/official sources only) to replace the
heterogeneous per-event `observed` dict with ONE consistently-defined target:
peak % decline in real production volume of the directly-shocked sector in the
source country (or, for chokepoint/logistics events, peak % throughput loss).
Artifacts: `data/csv/standardized_targets.csv` (engine-facing, 23 events),
`data/raw/external/perplexity_events/standardized_targets_2026-06.json` (raw
provenance), loader + 4 tests.

### Result: 14 measured, 9 null

**Finding 1 — semiconductor-source shocks have no measurable source-side target.**
Of the five chip-source events, four are NULL and the fifth is a weak proxy:

| event | status | why |
|---|---|---|
| covid-semiconductor-2020-2021 | **null** | Taiwan semi output GREW +20.7% YoY in 2020 — no source decline at all |
| auto-chip-shortage-2021 | **null** | no agency isolated a production-volume loss (only consultant estimates) |
| texas-winter-storm-2021 | **null** | full fab shutdown confirmed, but no published Austin fab output index |
| taiwan-chichi-earthquake-1999 | **null** | TSMC lost ~2–3 weeks, but no 1999 monthly semi production index exists |
| malaysia-semiconductor-2021 | weak proxy | DOSM −6.5% is FULL manufacturing; the E&E sub-sector actually +8.6% YoY |

Root cause: statistics agencies publish monthly **vehicle** production indices
but **not** monthly **fab-output** indices. So a chip shock is only observable
through its **downstream auto effect** — which the engine already targets
(`auto_production_loss_pct`). This *confirms* the cascade-centric design but
proves the "source magnitude" for chip events is a **latent input, not a measured
target** — you cannot calibrate it against a source-side number because none is
published.

**Finding 2 — every clean source-side target is automotive.** The only five
events with a direct, high/medium-confidence node-level production-loss number:

| node | peak loss | event |
|---|---|---|
| CHN:automotive | 0.790 | wuhan-lockdown-2020 (Feb 2020, CAAM) |
| THA:automotive | 0.875 | thailand-floods-2011 (Nov 2011, BOT/FTI) |
| JPN:automotive | 0.601 | japan-triple-disaster-2011 (Apr 2011, JAMA) |
| CHN:automotive | 0.461 | shanghai-lockdown-2022 (Apr 2022, CAAM) |
| DEU:automotive | 0.380 | eu-energy-crisis-2021 (Oct 2021, VDA) |

**Finding 3 — standardization moves the numbers a lot.** Example: the engine's
current `observed` for japan-2011 is 0.039 (a GLOBAL-ANNUAL figure); the
standardized node-level monthly peak is 0.601. Adopting these as engine targets
is therefore NOT a drop-in — it requires re-calibration and is gated, not
automatic.

### Two target families (the structural takeaway)
The single scalar `delta_output_pct` was silently pooling two different things:
- **source-side output loss** (supply-destruction: quakes, floods, fires,
  producer-region lockdowns) — measurable, all automotive here;
- **downstream / chokepoint loss** (demand/allocation/logistics: COVID-semi,
  Suez, Red Sea) — the source node may be flat or growing; the meaningful
  target is the propagated auto loss or the throughput cut.

`standardized_targets.csv` now tags every event with `target_class` and
`usability` so the two families are never compared in the same MAE again.

### Deliberately NOT done (needs a decision + Task #3 data)
The engine's `observed` targets were left untouched. Swapping in node-level peak
targets changes calibration and the golden snapshot, and the right target for
chip events is downstream (pairs with the Task #3 spatiotemporal-pattern data,
incoming). Recommendation: adopt standardized targets only inside the new
multi-output validation harness (Task #3), keep the v2 engine targets as the
calibrated baseline until a full recalibration is run.

---

## Batch 13 — Multi-output cascade-shape validation (Task #3)

**Status: DONE (2026-06-15)**

Stops collapsing each event to one scalar. The engine is now scored against the
*shape* of the cascade on three dimensions, using primary-source research:

| dimension | observed source |
|---|---|
| magnitude (peak source-sector output loss) | standardized_targets.csv (Batch 12) |
| weeks_to_peak | cascade_timing.csv (Batch 13) |
| recovery_weeks_to_90% | cascade_timing.csv |

`core/cascade_validation.py` reads the directly-shocked **node's** trajectory
(not the GDP-weighted industry-global average — that diluted JPN auto's −60% peak
to ~0.02) and scores each dimension only where a clean observed value exists.
`backtest._aggregate_industry` now also exposes `peak_week`.

### Engine result (default config, node-level)
| dim | MAE | Spearman | n |
|---|---|---|---|
| magnitude | 0.43 | **+0.80** | 4 |
| weeks_to_peak | 8.4 | +0.60 | 14 |
| recovery_weeks | 8.0 | **+0.85** | 10 |

**The honest read:** the engine **ranks** cascade shape well on all three axes
(Spearman 0.60–0.85) — it gets *relative* ordering right — but has two systematic
biases the single scalar hid:
1. **Under-predicts source magnitude.** Predicts 0.10–0.30 where measured is
   0.38–0.88. Consistent with Batch 12: the engine was tuned to smaller
   (global-annual) targets, not node-level monthly peaks.
2. **Mis-times slow-building events.** Sharp shocks (quakes, fires, lockdowns)
   correctly peak at week 0–1, but droughts/congestion (panama obs 20w,
   us-west-coast obs 52w) also peak at week 0 in the engine — it has no
   slow-accumulation mechanism for gradual chokepoint stress.

### Structural prediction tested (and not assumed)
The research review claimed "chokepoints recover faster than production shocks."
In *this* sample it does NOT hold — chokepoint mean recovery 21.5w > production
13.8w — because the panama drought (40w) dominates the small chokepoint set. The
engine reproduces the same non-separation (30.0w vs 26.9w) rather than falsely
imposing the generalization. Honest both ways.

### Scope
Read-only validation layer; does not change the engine or its calibrated
targets. The two biases above (magnitude scaling, slow-accumulation timing) are
concrete, measurable recalibration targets — the first quantitative use of the
expanded target set. Spatial cascade dimension (ordered affected-node set) is
pending the Task #3 affected-nodes JSON, which did not come through in the
upload (only the temporal CSV did).

---

## Batch 14 — Baseline comparison inline + LOO forecast band (Tasks #4 & #5)

**Status: DONE (2026-06-15)**

Two honesty features moved from the aggregate validation dashboard into the
live run view, so they're visible with the actual scenario, not buried.

### #4 — per-scenario baseline comparison
`core/forecast_ensemble.baseline_compare()` runs SEIRS, linear diffusion and
Leontief on the *same* scenario and returns peak industry-loss + recovery for
each, with parameter counts (SEIRS 5, baselines 0). Endpoint
`POST /api/v1/baseline-compare`. The aggregate leaderboard (`/benchmark`)
already existed; this makes the zero-parameter reference visible per run, so when
SEIRS doesn't beat linear diffusion that's on screen, not hidden. (Example:
Taiwan-semi-75 → SEIRS 4.8% loss / 22w recovery vs linear diffusion 4.1% / 3w —
the engine's extra machinery mostly buys a longer, more realistic recovery tail.)

### #5 — leave-one-out forecast band
`core/forecast_ensemble.loo_forecast_band()` re-runs the scenario under each of
the 26 LOO fold parameter sets and returns the median + 10/90 percentile band of
peak CSI. Endpoint `POST /api/v1/forecast-band`. With N=26 the point estimate is
not exact; the band shows the *parametric* uncertainty honestly (and the UI notes
that structural uncertainty is larger and not captured). On most scenarios the
band is tight (rel-width ~1–10%) — the 5 calibrated params barely move peak CSI,
which is itself an honest signal that structure, not parameter tuning, dominates.

### Frontend
`components/ModelComparisonPanel.tsx` (right column, under MetricsPanel) fetches
both after a run completes: a SEIRS-vs-baseline bar chart and the LOO band bar.
`backtest._aggregate_industry` exposing `peak_week` (Batch 13) is reused.

Tests: `tests/test_forecast_ensemble.py` (3). Full backend suite 99/99
(ex-portwatch); frontend `tsc --noEmit` clean.

---

## Batch 15 — Spatial cascade axis: did the cascade reach the right nodes? (Task #3 finish)

**Status: DONE (2026-06-15)**

The spatial half of "predict the pattern, not one number." Perplexity returned a
flat, one-row-per-affected-node table (62 rows / 17 events, every row primary-
source-cited) — `data/csv/cascade_spatial.csv`. `cascade_validation.run_spatial_
validation()` maps each observed downstream node to a graph node, runs the engine,
and scores **reach** (does the node's output loss cross a threshold) and **onset
order** (does the engine's first-touch week ordering track the observed ordering).
Endpoint: `GET /api/v1/cascade-validation` (both shape + spatial axes); rendered
on `/validation`.

### Result (reach_threshold 0.01)
| metric | value | reading |
|---|---|---|
| graph coverage | **0.76** | 47/62 observed nodes representable in the 12-country graph |
| spatial recall | **0.38** | of in-graph hit nodes, the engine reaches only 38% |
| onset Spearman | **+0.79** | for nodes it reaches, ordering tracks observed onset well |
| onset MAE | 9.2 wk | …but absolute timing is ~9 weeks too fast |
| out-of-graph | 15 nodes | UK/Italy/Belgium/Spain autos, chemicals, energy, agriculture |

### Two findings
1. **Low recall is a topology problem, not a dynamics problem.** Per-event the
   engine reaches 0/4 Renesas, 0/3 Malaysia, 0/2 Vietnam downstream auto nodes —
   because the sparse hand-authored graph has *no edge* from those semi/parts
   nodes to foreign automotive. This is the first **quantitative** case for the
   ICIO 81×5 expansion (Batch 11): the dense graph has those edges. Spatial
   recall is now the metric to re-run after wiring scenarios onto v3.
2. **Timing: right order, wrong clock.** Onset Spearman +0.79 with MAE 9.2w
   independently reproduces Batch 13's finding — the engine cascades too fast.
   The graph tells it *who's* downstream correctly; the dynamics fire too early.

### Coverage gap is itself data
The 15 out-of-graph nodes (UK/IT/BE/ES autos; chemicals; energy; agriculture)
are an honest map of what the current node taxonomy can't express — a concrete
target list for the next graph/sector expansion.

Tests: `test_cascade_validation.py` (+2 spatial). Backend 101/101 (ex-portwatch);
frontend `tsc` clean. This completes the four-axis pattern validation
(magnitude · weeks-to-peak · recovery · spatial reach/order).

---

## Batch 16 — The ICIO expansion pays off: spatial recall 0.32 → 0.76

**Status: DONE (2026-06-15) — headline result**

Batch 15 showed the engine reaches only ~38% of historically-hit nodes on the
sparse 36-node graph, and argued the dense v3 ICIO graph (Batch 11) should fix
it. `cascade_validation.compare_spatial_recall()` now *measures* it: same engine,
same shocks, only the graph changes (v2 shocks remapped to v3 node ids;
semiconductors+electronics → electronics_c26).

### Result (11 common production events, reach_threshold 0.01)
| graph | nodes | spatial recall |
|---|---|---|
| v2 hand-authored | 36 | **0.32** (11/34) |
| v3 OECD ICIO 2019 | 405 | **0.76** (26/34) |

Per-event, the dense graph closes exactly the gaps Batch 15 flagged:
Renesas 0/4 → 3/4, Shanghai 1/4 → 4/4, Japan-2011 2/3 → 4/4, auto-chip 1/3 → 3/3,
covid-semi 2/3 → 3/3, Thailand 1/4 → 3/4. The cascade now reaches the foreign
auto plants history recorded, because the ICIO table actually has those
intermediate-input edges and the hand-authored graph did not.

This is the quantitative justification for the whole Batch 11–15 arc: **grounding
the topology in real input-output data more than doubles the share of the
observed cascade the model can even reach** — a structural win that needs zero
parameter tuning. Chokepoint events are excluded (v3 has no chokepoint nodes);
Malaysia stays 0/3 even on v3 (its downstream auto edges are weak in ICIO too —
an honest remaining gap).

Exposed via `GET /api/v1/cascade-validation` (`expansion` block) and shown as a
before→after headline card on `/validation`. Tests: `test_cascade_validation.py`
(+1). Backend 102/102 (ex-portwatch); frontend `tsc` clean.

### Caveat
v3 params are uncalibrated structural priors, so this measures *reach* (does an
edge path exist that propagates), not calibrated magnitude. Reach is exactly the
right question for "did we expand the graph correctly" — magnitude calibration on
v3 is the separate next step.

---

## Batch 17 — the ICIO 81×5 graph becomes a runnable, user-selectable engine

**Status: DONE (2026-06-16) — shipped to production**

Until now the 405-node ICIO graph was opt-in only via an env var and invisible to
users — it could be validated but not *run*. This makes it a first-class choice in
the product: a visitor can flip the graph selector and run any production scenario
on the dense 81-economy graph, watching the (much wider) cascade on the map.

### What landed
- **`expanded_graph.py`**: country centroids for all 81 economies → every v3 node
  gets map coordinates (400/405; the 5 ROW aggregate nodes have none), with a small
  per-sector angular offset so a country's 5 nodes form a legible cluster. Promoted
  `to_v3_node()` (v2 id → v3 id; chokepoints / chemicals / energy / agriculture →
  None) as the shared mapping, reused by `cascade_validation`.
- **`seed.py`**: `compiled_graph_for(version)` — lazily builds + caches the v3
  compiled graph on first request, so the v2 default boot is untouched.
- **WebSocket** (`/ws/simulate`): honours a `graph_version` field. For `v3` it
  remaps the scenario's shocks onto v3 node ids, drops unmappable (chokepoint)
  ones, and errors cleanly if nothing maps. v2 path is byte-identical to before.
- **`/api/v1/graph?version=v3`**: serves the v3 snapshot for the map + node list.
- **Frontend**: a Graph selector (12-country · 41 nodes · calibrated  /  81-economy
  · 405 nodes · OECD ICIO) in the scenario panel; switching refetches the snapshot
  (the map re-renders 400 nodes by id, no map code change needed) and the Run
  button streams on the chosen graph. Chokepoint-only presets (Suez, Hormuz) are
  disabled + tagged "v2 only" when v3 is active; selection auto-falls-back.

### Honest framing surfaced in the UI
The selector explicitly labels v3 as "uncalibrated priors — cascade *reach* is far
wider; magnitudes aren't tuned to this topology yet." So users aren't misled into
reading v3 magnitudes as calibrated; the win it showcases is reach/connectivity
(Batch 16: 0.32 → 0.76), which is real and parameter-free.

### Verification
105/105 backend tests (ex-portwatch), frontend `tsc` + production build clean, v2
default behaviour unchanged. Tests added for centroids, the v2→v3 mapping, and the
exact `compiled_graph_for` + remap run-flow the WebSocket uses.

### Known limitation (honest)
The inline baseline-comparison and LOO-band panels still compute on the v2 engine
graph even when v3 is selected for the main run — they're about the calibrated
reference, so this is defensible, but it's a mild inconsistency to revisit if v3
ever gets its own calibration.
