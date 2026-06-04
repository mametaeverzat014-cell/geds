# GEDS — Architecture Decision (post-forensics)

## Context

Mechanism Forensics (`MECHANISM_FORENSICS.md`) measured:
- SEIRS S→E transitions across all events × iterations × weeks: **1**
- Nodes that ever entered E: **1**; I: **1**; R: **0**
- Bullwhip-active cell-weeks: **4**
- R-state floor active cell-weeks: **0**

Parameter sweeps confirmed: SEIRS, Bullwhip, Hysteresis show ΔMAE < 0.001
across their full documented parameter ranges.

## Options considered

### Option A — Remove dead mechanisms

_Pros:_ Code becomes smaller, faster (no `update_seis` call per week), easier
to defend ('what we ship is what we measure'). Honest branding: 'Amplified
Network Propagation Engine'.

_Cons:_ Loses the conceptual hooks that make GEDS distinctive on paper.
Future events with slow-burn cascades (months-long shipping disruptions,
slow-onset financial contagion) might actually need SEIRS dynamics — removal
is irreversible without a code rewrite.

### Option B — Repair dead mechanisms

_Pros:_ Keeps the branded model. If repaired, GEDS could differentiate itself
from pure linear diffusion baselines.

_Cons:_ The diagnosis says category **A** (never executed) for SEIRS. Repair
means lowering EXPOSURE_TRIGGER from 0.05 to ~0.01, or relaxing the shock<0.15
precondition. Both are tuning hacks — they would activate SEIRS but we have NO
empirical basis for the new thresholds. Risk of introducing parameters that
are even less identifiable than the existing ones.

### Option C — Replace with different mechanisms

_Pros:_ The dead-mechanism category list (A/B/C/D) suggests specific replacements:
an inventory-buffer model from operations research (Lee et al. bullwhip), a
balance-sheet contagion model from financial networks (Gai-Kapadia), or a
demand-side shock-spreading model.

_Cons:_ Each replacement is its own research project. Without a working baseline,
we cannot tell whether replacement mechanisms actually add predictive value.

## Recommendation: **Option A — Remove dead mechanisms** (with caveats)

Evidence-driven justification:

1. **Measured zero contribution.** Three mechanisms have ΔMAE < 0.001 across
   every parameter we can tune. They literally do not affect outputs.
2. **Diagnosis category A (never executed)** for SEIRS — repair requires
   thresholds we have no empirical basis for.
3. **Cost of keeping them.** Each week of simulation runs `update_seis` over
   (I × N) = (1 × 40) = 40 cells. For 572 weeks across the
   benchmark, that's wasted compute. More importantly, every reader of the
   codebase has to understand a four-state machine that does nothing.
4. **Honest branding.** The Phase 6 verdict already said the engine is
   functionally 'Amplified Network Propagation'. Code should match.

**Caveat:** keep the `seis.py` module as `legacy_seirs.py` (commented out,
explained in docs) so the dynamics can be re-introduced if the corpus expands
to events that exercise slow-burn cascades (currently 0 of 11 do).

## Concrete action items

1. In `propagation.py`:
   - Remove the unconditional `seis = build_seis_state(...)` fallback in `_init_state`
     (line 351–357). When `seis_enabled=False`, set `state.seis = None` and skip
     all SEIS-dependent steps.
   - Replace `shock_eff = state.shock * state.seis.outbound_mask` with
     `shock_eff = state.shock` when seis is None.
   - Remove the `impact = impact * state.seis.bullwhip_factor` step when seis is None.
   - Skip `update_seis` call when seis is None.
   - Replace `np.maximum(raw_loss, state.seis.output_floor)` with `raw_loss` when seis is None.
2. Default `EngineConfig.seis_enabled = False`.
3. Rename the class internally to `AmplifiedNetworkPropagationEngine` (keep
   `PropagationEngine` as an alias for back-compat).
4. Update README + STATE.md to reflect honest model name.
5. Move `seis.py` to `legacy/seis.py` with a top-of-file note explaining why.

## Final question answered

**Is GEDS actually SEIRS-Bullwhip-Hysteresis or Amplified Network Propagation Engine?**

**Amplified Network Propagation Engine.** The SEIRS-Bullwhip-Hysteresis components
are present in the source code but are demonstrably inactive on the N=11 benchmark
events under both default and calibrated parameters. The model that produces our
actual numbers is:

  linear network diffusion × sigmoid amplification kicker × chokepoint rerouting × recovery decay

and nothing else. The branded name overstates the model.
