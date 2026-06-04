# OECD vs OECD+WIOD — Scientific Comparison

Generated: `2026-05-29T17:07:08.963365+00:00`

## Graph topology comparison

| Graph | Nodes | Edges | Spectral radius ρ(A) | Density | R₀ proxy (μ=4) |
|---|---|---|---|---|---|
| OECD+WIOD | 1204 | — | 0.740925 | 0.002087 | 2.9637 |
| OECD-only | 1128 | — | 0.328712 | 0.001918 | 1.3148 |
| heuristic (v2-expanded) | 595 | — | 0.954748 | 0.006048 | 3.819 |

Augmentation: OECD baseline 1128 nodes/2440 edges → +76 nodes/+585 edges from WIOD K65/K66.
(0 WIOD cells already had OECD K-aggregate banking node; preserved without overwrite.)

## Benchmark comparison (95% bootstrap CIs)

### MAE

| Model | Heuristic v3 | OECD-only | OECD+WIOD |
|---|---|---|---|
| SEIRS | 0.17987 [0.10294, 0.26279] | 0.15297 | 0.16847 [0.09154, 0.24927] |
| Leontief | 0.16528 [0.09185, 0.24661] | 0.15943 | 0.1589 [0.07454, 0.24371] |
| Linear | 0.18065 [0.10322, 0.26355] | 0.14889 | 0.25506 [0.19649, 0.31383] |
| Naive | 0.17481 [0.13012, 0.22511] | 0.17829 | 0.17829 [0.12983, 0.23284] |

### R²

| Model | Heuristic v3 | OECD-only | OECD+WIOD |
|---|---|---|---|
| SEIRS | -0.6436 | -0.4178 | -0.3778 [-0.9182, -0.063] |
| Leontief | -0.5684 | -0.4836 | -0.4799 [-0.9647, -0.2113] |
| Linear | -0.6506 | -0.25 | -0.7483 [-3.0873, -0.2837] |
| Naive | 0.0 | 0.0 | 0.0 [-0.4565, -0.0001] |

### Pearson

| Model | Heuristic v3 | OECD-only | OECD+WIOD |
|---|---|---|---|
| SEIRS | -0.1539 | 0.3042 | -0.0957 |
| Leontief | 0.6548 | 0.462 | 0.4263 |
| Linear | -0.1564 | 0.2783 | -0.332 |
| Naive | nan | 0.0 | 0.0 |

## Mechanism telemetry: OECD-only vs OECD+WIOD

| Metric | OECD-only | OECD+WIOD | Δ |
|---|---|---|---|
| S->E transitions | 130 | 1189 | +1059 |
| E->I transitions | 89 | 761 | +672 |
| I->R transitions | 0 | 0 | +0 |
| R->S transitions | 0 | 0 | +0 |
| R->I transitions | 1 | 15 | +14 |
| Nodes ever E | 95 | 190 | +95 |
| Nodes ever I | 70 | 188 | +118 |
| Nodes ever R | 1 | 9 | +8 |
| Bullwhip active cells | 911 | 7755 | +6844 |
| Hysteresis floor cells | 22 | 265 | +243 |
| Amp kicker mean | — | 0.1939 | — |

## Ablation comparison: OECD-only vs OECD+WIOD

Composite ΔMAE when removing each component:

| Component | OECD-only ΔMAE | OECD+WIOD ΔMAE |
|---|---|---|
| no_seirs | 0.0 | 0.0 |
| no_bullwhip | 3e-05 | -0.00035 |
| no_hysteresis | 0.0 | 0.0 |
| no_network_amp | 0.00592 | -0.01424 |

## What became evidence-backed (vs OECD-only)

- **+76 country×sector nodes** for insurance and capital_markets (sectors previously NULL in OECD-only because OECD bundles into K).
- **+585 bilateral edges** from WIOD 2014 K65/K66 intermediate-use flows ≥ $100.0M.
- WIOD's K-sector split is the **only meaningful gain** of WIOD over OECD on this graph.

## What remains heuristic

- Chokepoint connectivity (8 chokepoint nodes, 30 manual edges).
- Per-node vulnerability, amplification, recovery_delay (sector-default heuristics).
- WIOD edge dependency weights normalised to inbound share (same convention as OECD).

## Sectors still unsupported

- **`semiconductors`**: bundled in C26 in both OECD and WIOD.
- **`gas`**: bundled in OECD B06 and WIOD B (with oil and coal).
- True **`employment_share`** column: NULL everywhere — WIOD-SEA files absent from repo. `value_added_share` is reported in its place as a labour-cost proxy.

## Countries still missing

WIOD covers 44 countries (vs OECD's 81). Countries in OECD but NOT in WIOD include SAU, ARE, HKG, SGP, VNM, THA, EGY, KAZ, NZL, plus ~28 more. Events tied to these countries gain nothing from WIOD.

## Publication-risk severity change

The audit `publication_risk_report.md` flagged finance-sector parameters as HIGH priority (uncalibrated to ECB/BIS data). WIOD K64/K65/K66 split is a partial fix: the structural separation now exists, but the per-node behavioural parameters (vulnerability, recovery_delay) are still sector-defaults, not data-derived. Severity: HIGH → MEDIUM-HIGH.
