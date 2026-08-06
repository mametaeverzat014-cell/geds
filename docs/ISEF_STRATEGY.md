# GEDS → ISEF: strategy, narrative, and prioritized work plan

*2026-07-18. All numbers in this document are reproducible from committed
artifacts; nothing here is aspirational. Where a number comes from a specific
file, the file is named.*

---

## 1. The honest starting position

**Assets** (already in the repo, already defensible):

| Asset | Evidence | Why judges care |
|---|---|---|
| 27-event primary-sourced calibration benchmark | `seed_data.HISTORICAL_EVENTS`, `historical_events.csv` (44 researched rows), tier-1 sources per event | Published cascade papers typically validate on 1–3 events; a curated, sourced, multi-event benchmark is a contribution in itself |
| Three-axis validation harness | Track A global LOO backtest; Track B node-level shape (`cascade_validation.py`); spatial reach/onset (`cascade_spatial.csv`) | "Predict the pattern, not one number" — methodologically ahead of single-metric validation |
| Honest 4-model leaderboard, golden-locked | `benchmark.py`, `test_reproducibility.py` GOLDEN | Reproducibility is enforced by CI, not promised |
| Statistical significance layer | `significance.json` (new, 2026-07-18) | Pre-empts the first technical attack at N=27 |
| Out-of-sample protocol | `loo_de_result.json` (LOO with per-fold DE recalibration; refreshed at N=27, 2026-07-18) | Answers "you tuned on your test set" |
| Data-integrity audit trail | `archive/leaked/README.md`, leak quarantine, `SCIENTIFIC_STATUS.md` | A self-caught, documented, quarantined leak is an integrity *credential*, not a liability — if told confidently |
| ICIO graph expansion result | Batch 16: spatial recall 0.29 → 0.79 on the 405-node OECD ICIO graph | A clean, parameter-free, positive structural result |
| Live interactive simulator | Next.js frontend + FastAPI engine, deployed | Booth demo; judges remember what they touched |

**Liabilities** (know them, own them, never hide them):

- On point magnitude, GEDS (default params) does NOT beat baselines: MAE 0.0242
  vs Leontief 0.0168 (golden snapshot).
- N=27 is small; three shape dimensions have n = 5 / 15 / 11; the magnitude
  shape dim (n=5) is too small to claim anything.
- The 12-country graph misses real-world producers (no France/aerospace, etc.)
  — documented in `PERPLEXITY_RESEARCH_PROMPT.md` Step 0.
- (RESOLVED 2026-07-23, Batch 19): `weeks_to_peak` WAS at chance (0.07
  [−0.43, +0.53]); forensics traced it to the engine having no rising forcing
  shape + a tie-handling bug in the cascade Spearman; a pre-registered ramp
  experiment passed all four gates and the axis is now significant: **0.69
  [0.20, 0.87]**. Tell this as the flagship methodology story, not as a fix.

## 2. The winning narrative (thesis inversion)

Do NOT frame the project as "I built a simulator and it wins." The evidence
does not support it, and a judge who spots overclaiming stops trusting
everything else. Frame it as:

> **"How should we validate global supply-chain disruption models? I built a
> three-axis validation harness and a 27-event primary-sourced benchmark,
> tested four models with it — including my own — and found that on the axis
> everyone reports (point magnitude), nothing statistically beats predicting
> the mean at N=27, while trajectory-level validation separates the models
> sharply."**

The three headline results, with today's significance numbers:

1. **Magnitude parity (the honest negative).** No pairwise MAE difference
   among the four models is significant: GEDS vs Leontief p=0.42, Leontief vs
   naive-mean p=0.09, all six pairs n.s. (sign-flip permutation, 20k perms,
   `significance.json`). Single-number validation cannot rank these models at
   this N — which is precisely why the field's habit of validating on 1–3
   events with one metric is inadequate.
2. **Shape separation (the positive).** GEDS is the only model of the four
   that predicts trajectories at all: recovery-duration ranking Spearman
   **0.88 [0.56, 0.99]** (n=11), onset-timing ranking **0.69 [0.20, 0.87]**
   (n=15, after the Batch 19 pre-registered ramp fix — it was at chance
   before, and the full diagnose→gate→adopt arc is itself the best
   methodology exhibit), event-severity ranking 0.45 [0.06, 0.73]
   (significant, N=27).
   The magnitude shape dim (n=5) stays unclaimed — that restraint is what
   makes the claimed numbers believable.
3. **Structure pays (the mechanism result).** Replacing the hand-authored
   12-country graph with the OECD ICIO 405-node graph lifts spatial recall
   0.29 → 0.79 with no parameter tuning (Batch 16) — evidence that what the
   model most lacks is network completeness, not better curve-fitting.

Supporting integrity beats: self-caught data leak → quarantined + rebuilt
clean; golden-snapshot regression locks; every observed number tier-1/tier-2
sourced with a written research protocol (`PERPLEXITY_RESEARCH_PROMPT.md`).

## 3. Judge attack surface — prepared answers

| Attack | Answer (with artifact) |
|---|---|
| "N=27 — is anything significant?" | Yes and no, and we computed exactly which: per-pair permutation p-values + paired bootstrap CIs in `significance.json`. Magnitude differences: none significant. Recovery-ranking and severity-ranking: significantly positive. We claim only the latter. |
| "Your model loses to a 1970s baseline" | On one axis, insignificantly (p=0.43); and that finding is the point — magnitude-only validation can't separate models, trajectory validation can. Leontief cannot produce a trajectory at all. |
| "You tuned on your test set" | Default-parameter results are reported untuned; the tuned story uses leave-one-out with per-fold DE recalibration (`loo_de_result.json`) — the held-out event never influences its own parameters. At N=27 on the ramp specs: out-of-sample MAE 0.0192 vs Leontief's 0.0168, gap n.s. (paired sign-flip p=0.89); Spearman 0.56, Pearson 0.25. Same conclusion as the default story: magnitude parity, honestly reported both ways. |
| "Why should I trust your observed values?" | Written source-tier protocol; every event carries named tier-1/tier-2 sources; events that failed sourcing were explicitly parked (`in_geds_graph=no` rows: Philips, Boeing) rather than wired in. |
| "Did an AI do this?" | AI tools were used as engineering/research assistants (and are acknowledged); every mechanism, number, and decision is documented in the repo and defensible by the presenter without notes. Practice until this is literally true — judges probe depth, and ISEF rules require the finalist to own the work. |
| "Overfitting to 2021?" | Event set spans 1999–2023, 10+ categories; the GFC 2008 demand-side event was added precisely to break the 2021 supply-shock monoculture, and it degraded every model's error honestly (golden comment, `test_reproducibility.py`). |
| "What's novel?" | See `NOVELTY_POSITIONING.md`: the SEIRS+bullwhip+hysteresis combination is plausibly novel, but the defended novelty is the benchmark + three-axis harness — verified claims only, framed "to the best of our knowledge". |
| "Weakest point?" | The magnitude shape dim has n=5 (unclaimable); graph coverage gaps (missing producers documented in Step 0 of the research prompt); N still small; and until Batch 19 the onset-timing axis was at chance — walk them through how it was diagnosed and fixed under a pre-registered gate. Naming weaknesses first is the credibility move. |

## 4. Prioritized work plan

**Done (this batch):**
- [x] Significance layer: `app/core/significance.py`, `scripts/significance_analysis.py`,
  `data/calibration/significance.json`, 7 tests. Seed 20260718, 10k bootstrap,
  20k permutations, deterministic.

- [x] LOO-DE refresh at N=27 (81 min, 2026-07-18): out-of-sample MAE 0.0188 /
  RMSE 0.0413 / Pearson 0.29 / Spearman 0.58 / R² −0.62. Versus the 26-fold
  run: error slightly up (the GFC fold is under-predicted 0.051 vs 0.130 —
  demand-side shocks are structurally unlike the supply cascades the engine
  models), every rank metric up (Spearman 0.53→0.58, R² −1.53→−0.62). Paired
  vs Leontief: ΔMAE +0.0020, n.s. (p=0.87) — magnitude parity holds in the
  tuned story too. Chi-Chi remains the worst fold (0.191 vs 0.005), consistent
  with the Batch 8/9b/9d structural diagnosis.

- [x] **Results one-pager** (2026-07-23): `scripts/results_onepager.py` →
  `docs/RESULTS.md`, generated-only (never hand-edited), every headline number
  + CI from artifacts. The poster, paper, and interview quote THIS file.
- [x] **Poster figures** (2026-07-23): `scripts/isef_figures.py` → 4 PNG+CSV
  pairs in `data/calibration/figures/` (parity forest, pred-vs-obs 2×2,
  timing before/after ramp, spatial-recall dumbbell) — colorblind-safe
  validated palette, every graphic with its numeric table per repo rule.

**Next, in leverage order:**
1. **250-word official abstract** — draft in §6; numbers now final
   (post-ramp, post-LOO-DE); the student rewrites it in their own voice.
3. **Poster/quad-chart structure** around the §2 narrative: Question → Harness
   → Benchmark → the three results → limitations up front.
4. **Grow N via the v3.1 research loop** (chokepoint events are the highest
   yield: CP:TaiwanStrait 2022, CP:Hormuz 2019 — see
   `PERPLEXITY_RESEARCH_PROMPT.md`). Each +1 event tightens every CI.
5. ~~`weeks_to_peak` diagnosis~~ — DONE (Batch 19, 2026-07-23). Cause was not
   inventory buffers: the engine had no rising forcing shape (all three decay
   curves peak at onset) and the ratchet update renders declining forcing as a
   rectangular pulse; plus a tie-handling bug inflated the cascade Spearman.
   `ramp` curve added, 4 events flipped by a mechanism-selection rule, all
   four pre-registered gates passed, axis now 0.69 [0.20, 0.87]. Artifacts:
   `ramp_experiment.json`, PROGRESS Batch 19. LOO-DE re-run on the ramp
   specs: MAE 0.0192 (was 0.0188), all shifts n.s. (paired vs Leontief
   p=0.89); the WC-ports fold became near-exact (0.0079 vs observed 0.0080).
6. **Booth demo hardening** — scripted 90-second walkthrough: pick Suez 2021 →
   watch cascade → overlay observed markers → switch to ICIO graph to show
   recall jump. (Frontend already supports all of this; needs a rehearsed path,
   not new code.)

**Explicitly NOT doing:** inflating N with unsourced events (poisons the
benchmark — the project's core asset is that every number is real), switching
the headline to any single-metric "win", or hiding the negative results. The
negative results, honestly quantified, ARE the contribution.

## 5. Category and logistics

- Recommended category: **Systems Software (SOFT)** — the contribution is a
  software system + validation methodology. Defensible alternates: MATH
  (applied modeling) or BEHA/econ if the fair's category guide steers there.
  Decide with the affiliated-fair guide, not from this document.
- Verify current-season Regeneron ISEF rules (forms, AI-use policy, abstract
  format) against the official rules wiki / student handbook before the
  regional deadline — rules change year to year; this document does not
  substitute for them.
- The finalist must be able to re-derive any number in the interview. The
  repo's provenance discipline (golden tests, seeds, source tiers) makes that
  possible; rehearse it.

## 6. Abstract draft (≈245 words — rewrite in your own voice; numbers verified 2026-07-18 incl. LOO-DE n=27)

> Global supply-chain disruptions cascade across industries, yet published
> simulation models are typically validated against one or two events with a
> single error metric. This project asks whether such validation can
> distinguish good models from naive baselines at all — and builds the
> infrastructure to answer it. I assembled a benchmark of 27 historical
> disruption events (1999–2023, ten categories: earthquakes, floods, port
> closures, chokepoint blockages, financial crises), each calibrated from
> primary sources under a written source-tier protocol, and a three-axis
> validation harness scoring (1) global magnitude, (2) node-level cascade
> shape (peak, timing, recovery), and (3) spatial reach. Four models were
> tested: a novel SEIRS-bullwhip-hysteresis epidemic-style simulator (GEDS),
> a Leontief input-output model, linear network diffusion, and a naive mean
> predictor. On point magnitude, no model significantly outperformed any
> other (all pairwise sign-flip permutation p ≥ 0.09, N=27), and the result
> persists under leave-one-out per-fold recalibration (p = 0.89) —
> single-number validation cannot separate these models. Trajectory
> validation can: GEDS, the only model producing full trajectories, ranked
> recovery durations with Spearman 0.88 (95% CI 0.56–0.99) and event
> severities at 0.45. Onset timing was initially at chance; error forensics
> traced this to the simulator lacking any rising forcing shape, and a
> pre-registered fix (a ramp curve applied to slow-accumulation events by a
> mechanism rule) lifted it to 0.69 (0.20–0.87) at a cost of +0.0001 MAE.
> Replacing the hand-built 12-country graph with an
> OECD ICIO 405-node graph raised spatial recall from 0.29 to 0.79 without
> retuning, showing network completeness, not parameter fitting, is the
> binding constraint. All results are seeded, golden-locked, and reproducible
> from a public repository.

---

*Maintenance note: regenerate the numbers in §2/§3/§6 from
`significance.json` and `loo_de_result.json` after any event-set change —
never hand-edit them independently of the artifacts.*
