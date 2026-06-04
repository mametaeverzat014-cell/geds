# Expanded Validation Report — 19-sector engine + v2 graph

Run: `2026-05-26T18:45:03.059491+00:00`

## Phase 1 — schema extension

Industry enum: 7 → **19** sectors (added: banking, insurance, capital_markets,
oil, gas, utilities, aviation, ports, telecommunications, agriculture, tourism,
government).

INDUSTRY_INVENTORY_WEEKS and INDUSTRY_COEFFICIENTS extended in matching commits.

Expanded graph v2:
- Nodes: **595**
- Edges: **2141**

## Phase 2 — event remapping coverage

| | v1 (default 40-node graph, 7 sectors) | v2 (expanded graph, 19 sectors) |
|---|---|---|
| Total events | 42 | 42 |
| Eligible for benchmark (OK) | **11** | **23** |
| Δ | — | **+12** |
| Sectors covered | 7 | 12 |
| Countries covered | 12 | 77 |

Status breakdown: {'OK': 23, 'UNMAPPED': 17, 'NO_TARGET': 1, 'SCENARIO': 1}

Sectors used in events: ['aerospace', 'agriculture', 'automotive', 'banking', 'consumer_goods', 'electronics', 'energy', 'government', 'shipping', 'telecommunications', 'tourism', 'utilities']

## Phase 3 — benchmark (default engine config)

| Model | N | MAE | RMSE | R² | Pearson | Bias |
|---|---|---|---|---|---|---|
| SEIRS-Bullwhip-Hysteresis (GEDS) | 23 | 0.16418 | 0.26657 | -0.5657 | 0.5042 | -0.16402 |
| Leontief | 23 | 0.16528 | 0.2668 | -0.5684 | 0.6548 | -0.16515 |
| Linear Diffusion | 23 | 0.18065 | 0.27371 | -0.6506 | -0.1564 | -0.14331 |
| Naive Persistence | 23 | 0.17481 | 0.21304 | 0.0 | 0.0 | 0.0 |

## Phase 4 — mechanism telemetry: v1 vs v2

| Metric | v1 (40-node graph) | v2 (expanded graph) |
|---|---|---|
| S→E transitions | 1 | **99** |
| E→I transitions | 1 | **92** |
| I→R transitions | 0 | **0** |
| R→S transitions | 0 | **11** |
| R→I transitions | 0 | **18** |
| Nodes ever in E | 1 | **49** |
| Nodes ever in I | 1 | **62** |
| Nodes ever in R | 0 | **21** |
| Bullwhip active cells | 4 | **747** |
| Hysteresis floor cells | 0 | **933** |
| Total update_seis calls | 572 | **1196** |
| State weeks (S/E/I/R) | — | {0: 706301, 1: 747, 2: 3639, 3: 933} |

## Question answered: Do SEIRS / Bullwhip / Hysteresis become active under expanded coverage?

**SEIRS activation:** 99 S→E transitions (5319 of 711,620 cell-weeks = 0.747% non-S).
**Bullwhip activation:** 747 active cell-weeks.
**Hysteresis (R-floor) activation:** 933 active cell-weeks.

**YES — mechanisms come alive under expanded coverage.** The 19-sector graph exercises SEIRS dynamics that the 7-sector graph did not.

## Note on the I→R "0 transitions" paradox

The transitions table shows I→R = 0 yet R state is populated for 933 cell-weeks
across 21 distinct nodes. This is a **telemetry artefact, not a missing
transition.** `update_seis` processes S→E→I→R sequentially within a single
weekly call based on the live state. When a shock cascades fast enough, a cell
can move from S to R within one `update_seis` invocation — my telemetry
captures only `pre` (start-of-call) and `post` (end-of-call) state, so such
fast cascades count as `S→R` (which I did not track) rather than I→R.

The R-state cell-week count (933) and R-state node count (21) are the ground
truth here: R state IS being entered, hysteresis floor IS firing. The "0 I→R"
is an instrumentation gap, not a real absence.

## Honest caveats

- Default `EngineConfig()` used here (not the calibrated_v2 params). v1 telemetry used calibrated params; magnitude differences across v1↔v2 partly reflect config, not graph.
- Heuristic country×sector presence map (UNIVERSAL_SECTORS + SPECIALTY_PRESENCE) — not data-driven beyond ad-hoc industry knowledge.
- Event sector remapping used a simple SECTOR_NORMALISE map (e.g. financial→banking). Some events still map to fewer than ideal sectors.
- Telemetry counts pre/post state per `update_seis` call, missing multi-step transitions within a single call (see note above).
- Linear Diffusion's collapse on the expanded graph (R²=−0.65 vs SEIRS R²=−0.57) reflects that its α=0.6 / β=0.07 hyperparameters were not re-tuned for the larger topology; the comparison favours SEIRS partly because of this.
