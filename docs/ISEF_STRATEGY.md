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
| Out-of-sample protocol | `loo_de_result.json` (LOO with per-fold DE recalibration; N=27 refresh running) | Answers "you tuned on your test set" |
| Data-integrity audit trail | `archive/leaked/README.md`, leak quarantine, `SCIENTIFIC_STATUS.md` | A self-caught, documented, quarantined leak is an integrity *credential*, not a liability — if told confidently |
| ICIO graph expansion result | Batch 16: spatial recall 0.32 → 0.76 on the 405-node OECD ICIO graph | A clean, parameter-free, positive structural result |
| Live interactive simulator | Next.js frontend + FastAPI engine, deployed | Booth demo; judges remember what they touched |

**Liabilities** (know them, own them, never hide them):

- On point magnitude, GEDS (default params) does NOT beat baselines: MAE 0.0241
  vs Leontief 0.0168 (golden snapshot).
- N=27 is small; three shape dimensions have n = 5 / 15 / 11.
- `weeks_to_peak` prediction is currently indistinguishable from chance
  (Spearman 0.07, 95% CI [−0.43, +0.53] — `significance.json`).
- The 12-country graph misses real-world producers (no France/aerospace, etc.)
  — documented in `PERPLEXITY_RESEARCH_PROMPT.md` Step 0.

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
   among the four models is significant: GEDS vs Leontief p=0.43, Leontief vs
   naive-mean p=0.09, all six pairs n.s. (sign-flip permutation, 20k perms,
   `significance.json`). Single-number validation cannot rank these models at
   this N — which is precisely why the field's habit of validating on 1–3
   events with one metric is inadequate.
2. **Shape separation (the positive).** GEDS is the only model of the four
   that predicts trajectories at all, and on recovery-duration ranking it
   scores Spearman **0.88, 95% CI [0.56, 0.99]** (n=11) — significantly
   positive. Event-severity ranking is also significantly positive (Spearman
   0.46 [0.08, 0.74], N=27). `weeks_to_peak` is not (0.07 [−0.43, +0.53]) —
   reported as a limitation, which is what makes the 0.88 believable.
3. **Structure pays (the mechanism result).** Replacing the hand-authored
   12-country graph with the OECD ICIO 405-node graph lifts spatial recall
   0.32 → 0.76 with no parameter tuning (Batch 16) — evidence that what the
   model most lacks is network completeness, not better curve-fitting.

Supporting integrity beats: self-caught data leak → quarantined + rebuilt
clean; golden-snapshot regression locks; every observed number tier-1/tier-2
sourced with a written research protocol (`PERPLEXITY_RESEARCH_PROMPT.md`).

## 3. Judge attack surface — prepared answers

| Attack | Answer (with artifact) |
|---|---|
| "N=27 — is anything significant?" | Yes and no, and we computed exactly which: per-pair permutation p-values + paired bootstrap CIs in `significance.json`. Magnitude differences: none significant. Recovery-ranking and severity-ranking: significantly positive. We claim only the latter. |
| "Your model loses to a 1970s baseline" | On one axis, insignificantly (p=0.43); and that finding is the point — magnitude-only validation can't separate models, trajectory validation can. Leontief cannot produce a trajectory at all. |
| "You tuned on your test set" | Default-parameter results are reported untuned; the tuned story uses leave-one-out with per-fold DE recalibration (`loo_de_result.json`) — the held-out event never influences its own parameters. |
| "Why should I trust your observed values?" | Written source-tier protocol; every event carries named tier-1/tier-2 sources; events that failed sourcing were explicitly parked (`in_geds_graph=no` rows: Philips, Boeing) rather than wired in. |
| "Did an AI do this?" | AI tools were used as engineering/research assistants (and are acknowledged); every mechanism, number, and decision is documented in the repo and defensible by the presenter without notes. Practice until this is literally true — judges probe depth, and ISEF rules require the finalist to own the work. |
| "Overfitting to 2021?" | Event set spans 1999–2023, 10+ categories; the GFC 2008 demand-side event was added precisely to break the 2021 supply-shock monoculture, and it degraded every model's error honestly (golden comment, `test_reproducibility.py`). |
| "What's novel?" | See `NOVELTY_POSITIONING.md`: the SEIRS+bullwhip+hysteresis combination is plausibly novel, but the defended novelty is the benchmark + three-axis harness — verified claims only, framed "to the best of our knowledge". |
| "Weakest point?" | `weeks_to_peak` at chance level; graph coverage gaps (missing producers documented in Step 0 of the research prompt); N still small. Naming them first is the credibility move. |

## 4. Prioritized work plan

**Done (this batch):**
- [x] Significance layer: `app/core/significance.py`, `scripts/significance_analysis.py`,
  `data/calibration/significance.json`, 7 tests. Seed 20260718, 10k bootstrap,
  20k permutations, deterministic.

**Running:**
- [ ] LOO-DE refresh at N=27 (background, ~2 h; last run was 26 folds). On
  completion: update the out-of-sample story wherever it is cited.

**Next, in leverage order:**
1. **Results one-pager** — a single generated table (script, not hand-edited)
   with every headline number + CI, feeding the poster, paper, and interview.
2. **250-word official abstract** — draft in §6; freeze only after LOO-DE n=27.
3. **Poster/quad-chart structure** around the §2 narrative: Question → Harness
   → Benchmark → the three results → limitations up front.
4. **Grow N via the v3.1 research loop** (chokepoint events are the highest
   yield: CP:TaiwanStrait 2022, CP:Hormuz 2019 — see
   `PERPLEXITY_RESEARCH_PROMPT.md`). Each +1 event tightens every CI.
5. **`weeks_to_peak` diagnosis** — the one mechanism improvement worth
   attempting before ISEF: why is onset timing at chance while recovery
   ranking is at 0.88? (Hypothesis: inventory-buffer weeks dominate onset and
   are the least-sourced parameter; a sensitivity pass exists in `sobol.json`.)
   Only ship if it survives the pre-registered LOO protocol, per Batch 9b
   precedent (a mechanism that improved in-sample and failed LOO was rejected).
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

## 6. Abstract draft (≈240 words — rewrite in your own voice, update after LOO-DE n=27)

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
> other (all pairwise sign-flip permutation p ≥ 0.09, paired bootstrap,
> N=27) — single-number validation cannot separate these models. Trajectory
> validation can: GEDS, the only model producing full trajectories, ranked
> recovery durations with Spearman 0.88 (95% CI 0.56–0.99) and event
> severities at 0.46 (0.08–0.74), while onset timing remained at chance —
> a quantified limitation. Replacing the hand-built 12-country graph with an
> OECD ICIO 405-node graph raised spatial recall from 0.32 to 0.76 without
> retuning, showing network completeness, not parameter fitting, is the
> binding constraint. All results are seeded, golden-locked, and reproducible
> from a public repository.

---

*Maintenance note: regenerate the numbers in §2/§3/§6 from
`significance.json` and `loo_de_result.json` after any event-set change —
never hand-edit them independently of the artifacts.*
