# Phase 6 — Brutally Honest Verdict

**Sample size benchmarked:** 11 of 42 events (engine sector/graph limits).
**Engine config:** calibration_v2 DE-best parameters loaded from `calibration_v2.json`.

## The headline finding (read this first)

**SEIRS, bullwhip, and hysteresis contribute exactly zero to GEDS predictions.**

Ablation MAE values, to 5 decimal places:

| Configuration | MAE | Δ vs baseline |
|---|---|---|
| Full GEDS (calibrated) | 0.14685 | — |
| GEDS without **SEIRS** | 0.14685 | **+0.00000** |
| GEDS without **bullwhip** | 0.14685 | **+0.00000** |
| GEDS without **hysteresis** | 0.14685 | **+0.00000** |
| GEDS without **network amplification** | 0.14811 | +0.00126 |

Three of the four branded components leave the answer unchanged. Only the network amplification term (which is also present in Linear Diffusion in a simpler form) makes any measurable difference, and even there the delta is 0.13% relative.

**Interpretation:** the model's predictions on this 11-event corpus are essentially determined by network propagation through the graph, not by the SEIRS / bullwhip / hysteresis machinery layered on top. The branding "SEIRS-Bullwhip-Hysteresis" overstates the model.

## Does GEDS become stronger with N=42?

**No — and N=42 didn't actually happen.** Of 42 corpus events, only 11 could be benchmarked. The other 31 were excluded because:

- Engine `Industry` enum has 7 sectors; sectors like `financial`, `government`, `tourism`, `agriculture` aren't in it (cannot construct a shock).
- 5 events have a peer-reviewed target but no engine graph node to put the shock on.
- 2 events have no GDP target at all.
- 1 event is a forward-looking scenario (excluded by design).

**The structural bottleneck is the engine itself, not the data.** Until the `Industry` enum and graph are extended, N is capped at ~11 regardless of how many events the corpus contains.

## Does Linear Diffusion still dominate?

**Statistically: tie.**

| Model | MAE | MAE 95% bootstrap CI | R² | Pearson |
|---|---|---|---|---|
| **GEDS (SEIRS calibrated)** | **0.14685** | [0.02500, 0.29480] | −0.215 | +0.829 |
| Linear Diffusion | 0.14786 | [0.02611, 0.29624] | −0.217 | +0.791 |
| Leontief | 0.14903 | [0.02765, 0.29892] | −0.233 | +0.801 |
| Naive Persistence | 0.20065 | [0.12870, 0.29424] | 0.000 | NaN |

GEDS edges out Linear Diffusion by **0.00101 MAE** — a difference that is well inside both models' bootstrap CIs. Calling this a "GEDS win" would be sample-noise-chasing.

What CAN be said:
- All three structural models beat Naive Persistence on MAE (and CIs are clearly separated from Naive's).
- All three have **negative R²** — they explain *less* variance than predicting the mean. They are worse than the naive baseline on MSE.
- Pearson +0.79 to +0.83 means the models correctly rank events by impact magnitude but mispredict the absolute scale (right shape, wrong scale).

## How is this consistent with the previous N=8 result?

| Benchmark | N | Linear Diffusion R² | SEIRS R² | Winner by MAE |
|---|---|---|---|---|
| Prior `benchmark.json` | 8 | **+0.7647** | +0.0451 | Linear Diffusion |
| This run | 11 | −0.217 | −0.215 | GEDS (barely) |

**The R² collapse from +0.76 to −0.22 is the most important number in this report.** A model that looked publication-grade on N=8 (variance explained 76%) doesn't survive expanding to N=11. The prior result was a small-sample artefact — likely overfit to the specific event distribution in seed_data's HISTORICAL_EVENTS list.

This is itself a useful finding: cherry-picking 8 events lets you publish almost any number; expanding to a slightly larger, more diverse sample shows the underlying model has no real predictive variance.

## What the ablation says

Read the table at the top again. The interpretation is:

- **SEIRS layer:** does literally nothing on this corpus. Whether the SEIS state transitions through Susceptible → Exposed → Infected → Susceptible-again is irrelevant to the industry-loss output that backtest_event measures.
- **Bullwhip factor:** likewise zero impact. Either the parameter setting (1.125, near 1.0 = off) makes it inactive, or the events aren't long enough for bullwhip to accumulate.
- **Hysteresis:** zero impact. The distress-week-threshold path isn't being triggered on these events.
- **Network amplification:** −0.13% relative MAE. Tiny but non-zero. This is the only piece doing measurable work.

The Sobol result from Phase 4 calibration was already a warning: 3 of 5 calibrated parameters are non-identifiable. The ablation confirms that *as run today, on this corpus, with this graph,* most of the GEDS engine machinery is decorative.

## Honest summary in one paragraph

On 11 events that the engine can actually run, GEDS's calibrated MAE (0.14685) is statistically indistinguishable from Linear Diffusion (0.14786) and Leontief (0.14903). All three beat Naive Persistence on MAE but lose to it on R² — they capture event *ordering* (Pearson ≈ 0.80) but not *magnitude*. The ablation reveals that SEIRS, bullwhip, and hysteresis change the GEDS prediction by 0.00000 on this corpus; only network amplification has any measurable effect. The earlier N=8 benchmark's R²=+0.76 for Linear Diffusion was sample-cherry-picking; on a slightly larger, more diverse N=11 the same model scores R²=−0.22. The largest gap in the project is not between models but between the 42-event corpus and the 11 events the engine can actually consume.

## What to do next (concrete, ranked by ROI)

1. **Extend the `Industry` enum.** Add `financial`, `agriculture`, `tourism`, `healthcare`, `government`, `telecommunications`, `defense`. This single change unlocks ~25–30 more benchmarkable events. **Highest ROI of any action.**
2. **Investigate why SEIRS/bullwhip/hysteresis contribute zero.** Either the parameters need wider bounds during calibration, or the components are correctly implemented but the events in scope don't exercise the relevant dynamics (acute supply shocks vs slow-burn macro cascades). Either finding is worth a paper section.
3. **Hold out a test set.** Calibration is currently in-sample; even the 0.14685 MAE is biased downward.
4. **Restrict the 3 non-identifiable parameters** at literature values; calibrate only on the 2 identifiable ones.
5. **Stop branding the model "SEIRS-Bullwhip-Hysteresis"** until those components measurably contribute. The current effective model is "Linear network propagation with amplification" — call it that.
6. **Publish the negative result.** "Naive baseline beats SEIRS on R² for N=11 historical disruption events" is more publishable (and more honest) than another iteration that hides this.

## What this work was NOT

This was not a model improvement. The headline GEDS MAE went from 0.1607 (default config, prior session) to 0.14685 (calibrated, this session) — a 9% improvement. That's real, but it's also entirely attributable to calibration finding better hyperparameters for the same underlying engine, not to any new modelling capability. The ablation tells us the engine has one functional component (network amplification) and three decorative ones. Calibrating an engine with three dead components doesn't make those components live.
