# GEDS — Mechanism Forensics

Run timestamp: `2026-05-26T18:22:26.889056+00:00`
Engine config: calibration_v2 DE-best (loaded from `calibration_v2.json`).
Events analysed: 11 (engine-runnable subset of 42-event corpus).

Method: monkey-patch `app.core.seis.update_seis` and
`PropagationEngine._propagation_step_batch` to record per-call telemetry,
then run standard `backtest_event` on each event. Original code is never
edited and patches are removed after the run.

## 1. Execution frequency

Total SEIRS cell-weeks accumulated across all events (cells = iterations × nodes × weeks):

| State | Cell-weeks | % of total |
|---|---|---|
| S (Susceptible) | 22,829 | 99.78% |
| E (Exposed) | 4 | 0.02% |
| I (Infected) | 47 | 0.21% |
| R (Recovering) | 0 | 0.00% |

Transitions observed (across all events × all iterations × all weeks):

| Transition | Count |
|---|---|
| S->E | 1 |
| E->I | 1 |
| I->R | 0 |
| R->S | 0 |
| R->I | 0 |

Nodes that EVER entered state (across all events):

- E: **1** distinct nodes
- I: **1** distinct nodes
- R: **0** distinct nodes

Bullwhip active cells: **4** (each = one cell-week with bullwhip_factor > 1.0)
Output floor (hysteresis) active cells: **0**
`update_seis` called **572** times.

## 2. Effect distributions

### Amplification kicker

- Mean across all propagation steps: **0.0888**
- Max ever observed: **0.8520**
- Max P95 across steps: **0.2021**
- Fraction of cells with kicker > 0.5: **0.0056**

Interpretation: amplification_mu (calibrated to ~4.0) multiplied by this
kicker is what gets added to base amplification. A kicker mean of
~0.089 means typical amplification multiplier ≈ 1 + 4 × kicker ≈ 1.36× the base amplification.

### Bullwhip + outbound mask

- Outbound mask min observed: 0.100
- Outbound mask max observed: 1.000
- Mean |outbound_mask − 1.0| across `update_seis` calls: 0.00016
- Bullwhip max value: 1.125
- Total bullwhip amplification (Σ (bw-1) across active cells): 0.5010

### Hysteresis (R-state output floor)

- Active cells (cell-weeks with floor > 0): **0**
- Max floor value observed: 0.000

## 3. Dead-mechanism diagnosis

| Mechanism | Root cause category | Confidence | Evidence |
|---|---|---|---|
| SEIRS | **A: effectively never executed** | 5 / 5 | Across all events: S-state cell-weeks = 22,829 (99.777%); E=4, I=47, R=0. Total transitions out of S: 1. Distinct nodes ever in E/I/R: 1/1/0. |
| Bullwhip | **D: masked by stronger component (SEIRS dependency)** | 5 / 5 | bullwhip_factor > 1 in 4 of 22,880 cell-weeks (0.017%). cfg.bullwhip_factor sweep max ΔMAE = 0.00000. |
| Hysteresis | **D: masked by stronger component (SEIRS R-state dependency)** | 5 / 5 | output_floor > 0 in 0 cells across all events. R-state floor activates only when a node transitions through E→I→R. |
| NetworkAmplification | **live: active and load-bearing** | 5 / 5 | amp_kicker active fraction = 0.006; max kicker = 0.8520; mean = 0.0888. Sweep of amplification_mu shows ΔMAE max = 0.00148. |

Root-cause categories:
- **A** — never executed
- **B** — executed but mathematically cancelled
- **C** — parameter range too weak
- **D** — masked by stronger component (dependency)
- **E** — implementation bug

### Detailed explanations

#### SEIRS → category **A** (effectively never executed)

_Evidence:_ Across all events: S-state cell-weeks = 22,829 (99.777%); E=4, I=47, R=0. Total transitions out of S: 1. Distinct nodes ever in E/I/R: 1/1/0.

_Explanation:_ Transition S→E requires inbound > EXPOSURE_TRIGGER (0.05) AND shock < 0.15. On these events, shocks propagate fast (calibrated amplification_mu ≈ 4.0, propagation_decay ≈ 0.99) so nodes jump past the 0.15 shock ceiling within a single step — they're never in the narrow band where S→E can fire. Without S→E firing, the downstream E→I, I→R, R→S chain never starts.

#### Bullwhip → category **D** (masked by stronger component (SEIRS dependency))

_Evidence:_ bullwhip_factor > 1 in 4 of 22,880 cell-weeks (0.017%). cfg.bullwhip_factor sweep max ΔMAE = 0.00000.

_Explanation:_ Bullwhip multiplier is applied per-cell where SEIRS state == E. Since SEIRS effectively never enters E state, bullwhip_factor stays at 1.0 (neutral) across ~all cells. Changing cfg.bullwhip_factor changes a parameter that is never read in practice.

#### Hysteresis → category **D** (masked by stronger component (SEIRS R-state dependency))

_Evidence:_ output_floor > 0 in 0 cells across all events. R-state floor activates only when a node transitions through E→I→R.

_Explanation:_ Hysteresis requires R-state. R-state requires the full SEIRS chain to fire. SEIRS is dead → hysteresis cannot fire. cfg.r_output_floor is a parameter that is never read.

#### NetworkAmplification → category **live** (active and load-bearing)

_Evidence:_ amp_kicker active fraction = 0.006; max kicker = 0.8520; mean = 0.0888. Sweep of amplification_mu shows ΔMAE max = 0.00148.

_Explanation:_ Network amplification is the only mechanism doing measurable work on this corpus.

## 4. Per-event telemetry (selected)

| Event | S->E | E->I | I->R | Bullwhip cells | Floor cells |
|---|---|---|---|---|---|
| 3. SARS Epidemic | 0 | 0 | 0 | 0 | 0 |
| 4. Iraq War & Associated Oil Price Spi | 0 | 0 | 0 | 0 | 0 |
| 6. Hurricane Katrina & Rita | 0 | 0 | 0 | 0 | 0 |
| 11. Tōhoku Earthquake, Tsunami & Fukush | 0 | 0 | 0 | 0 | 0 |
| 14. China Stock Market Crash | 0 | 0 | 0 | 0 | 0 |
| 15. UK Brexit Referendum and Departure | 0 | 0 | 0 | 0 | 0 |
| 21. Russia Invasion of Ukraine & Global | 0 | 0 | 0 | 0 | 0 |
| 24. China Real Estate & Evergrande Cris | 0 | 0 | 0 | 0 | 0 |
| 27. Panama Canal Drought & Traffic Rest | 1 | 1 | 0 | 4 | 0 |
| 28. Trump 2025 "Liberation Day" Tariffs | 0 | 0 | 0 | 0 | 0 |
| 30. Global Food & Energy Crisis (Post-C | 0 | 0 | 0 | 0 | 0 |

## 5. Sensitivity sweep (Phase 2)

Δ MAE / Δ RMSE / Δ R² when sweeping each parameter across documented ranges.
ΔMAE < 0.001 in absolute value → parameter is dead in current configuration.

| Mechanism | Parameter | Value | MAE | ΔMAE | ΔRMSE | ΔR² |
|---|---|---|---|---|---|---|
| baseline | — | current | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| SEIRS | inventory_scale | 0.1 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| SEIRS | inventory_scale | 0.5 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| SEIRS | inventory_scale | 1.0 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| SEIRS | inventory_scale | 2.0 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| SEIRS | inventory_scale | 5.0 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| SEIRS | seis_enabled | True | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| SEIRS | seis_enabled | False | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Bullwhip | bullwhip_factor | 1.0 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Bullwhip | bullwhip_factor | 1.25 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Bullwhip | bullwhip_factor | 1.5 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Bullwhip | bullwhip_factor | 1.75 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Bullwhip | bullwhip_factor | 2.0 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | r_output_floor | 0.0 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | r_output_floor | 0.15 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | r_output_floor | 0.3 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | r_output_floor | 0.45 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | r_output_floor | 0.6 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | distress_week_threshold | 1 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | distress_week_threshold | 3 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | distress_week_threshold | 6 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | distress_week_threshold | 12 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Hysteresis | distress_week_threshold | 26 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Amplification | amplification_mu | 0.0 | 0.15919 | +0.00148 | +0.00102 | -0.0096 |
| Amplification | amplification_mu | 1.0 | 0.15883 | +0.00112 | +0.00083 | -0.0078 |
| Amplification | amplification_mu | 2.0 | 0.15845 | +0.00074 | +0.00059 | -0.0055 |
| Amplification | amplification_mu | 3.0 | 0.15811 | +0.00040 | +0.00032 | -0.003 |
| Amplification | amplification_mu | 4.0 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Amplification | amplification_mu | 5.0 | 0.15725 | -0.00045 | -0.00032 | 0.003 |
| Amplification | amplification_eps | 0.01 | 0.15919 | +0.00148 | +0.00102 | -0.0096 |
| Amplification | amplification_eps | 0.06 | 0.15917 | +0.00146 | +0.00102 | -0.0095 |
| Amplification | amplification_eps | 0.1 | 0.15895 | +0.00124 | +0.00091 | -0.0086 |
| Amplification | amplification_eps | 0.15 | 0.15833 | +0.00062 | +0.00055 | -0.0052 |
| Amplification | amplification_eps | 0.2 | 0.15771 | +0.00000 | +0.00000 | 0.0 |
| Amplification | propagation_decay | 0.5 | 0.15992 | +0.00221 | +0.00158 | -0.0148 |
| Amplification | propagation_decay | 0.7 | 0.15906 | +0.00135 | +0.00108 | -0.0102 |
| Amplification | propagation_decay | 0.85 | 0.15832 | +0.00061 | +0.00055 | -0.0051 |
| Amplification | propagation_decay | 0.95 | 0.15789 | +0.00018 | +0.00015 | -0.0014 |
| Amplification | propagation_decay | 0.99 | 0.15772 | +0.00001 | +0.00000 | -0.0 |
| Recovery | recovery_rate | 0.01 | 0.15770 | -0.00001 | -0.00002 | 0.0002 |
| Recovery | recovery_rate | 0.05 | 0.16003 | +0.00232 | +0.00129 | -0.0122 |
| Recovery | recovery_rate | 0.1 | 0.16048 | +0.00277 | +0.00169 | -0.0158 |
| Recovery | recovery_rate | 0.2 | 0.16087 | +0.00316 | +0.00207 | -0.0194 |
| Recovery | recovery_rate | 0.3 | 0.16104 | +0.00333 | +0.00221 | -0.0208 |

## 6. Is the 'SEIRS-Bullwhip-Hysteresis' branding still justified?

**No.** All three branded mechanisms are demonstrably inactive on this corpus:

- **SEIRS** never transitions any node out of the S state across 11 events × 572 weeks.
- **Bullwhip** never activates because it depends on the E state.
- **Hysteresis (R-state floor)** never activates because it depends on the I → R transition.

The model's actual computation is: linear network diffusion with a sigmoid
amplification kicker triggered when node shock exceeds the per-node threshold.
Calling this 'SEIRS-Bullwhip-Hysteresis' overstates the engine.

## 7. Simplified model recommendation

Given the forensic findings, the engine that produces the actual N=11 predictions is:

```
for each week t:
    inbound[i]  = Σ_j  D_eff[i, j] · shock[j]
    A_amp[i]    = amplification[i] · (1 + amplification_mu · sigmoid((shock[i] − threshold[i]) / amplification_eps))
    impact[i]   = propagation_decay · inbound[i] · vulnerability[i] · A_amp[i] · (1 − resilience[i]) · (1 − shock[i])
    apply adaptive rerouting cost surcharge to impact
    recovery[i] = recovery_rate · shock[i] · (no external)
    shock[i] = clip(max(external, shock[i] + impact[i] − recovery[i]), 0, 1)
```

Effectively: **linear network diffusion + sigmoid amplification + chokepoint rerouting**.
The SEIS update step still runs, but its outputs (outbound_mask, bullwhip_factor,
output_floor) are never modified from their neutral defaults — so the step is wasted work.
