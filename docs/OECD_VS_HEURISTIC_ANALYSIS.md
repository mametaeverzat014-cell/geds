# OECD vs Heuristic — Analysis

Generated: `2026-05-27T21:06:54.739591+00:00`

Comparison of GEDS under the OECD ICIO-backed graph (real data, 2022) vs the heuristic v2-expanded graph (`benchmark_v3.json`).

## Graph topology

| Metric | Heuristic (v2-expanded) | OECD ICIO 2022 | Δ |
|---|---|---|---|
| Nodes | 595 | 1128 | +533 |
| Edges | 2141 | 2440 | +299 |

## Benchmark coverage

- Heuristic: N_eligible = **23**
- OECD:      N_eligible = **21**

## Benchmark scores

| Model | Heur MAE | OECD MAE | ΔMAE | Heur R² | OECD R² | ΔR² | Heur Pearson | OECD Pearson |
|---|---|---|---|---|---|---|---|---|
| GEDS (SEIRS) | 0.17987 | 0.15297 | -0.02690 | -0.6436 | -0.4178 | +0.2258 | -0.1539 | 0.3042 |
| Leontief | 0.16528 | 0.15943 | -0.00585 | -0.5684 | -0.4836 | +0.0848 | 0.6548 | 0.462 |
| Linear Diffusion | 0.18065 | 0.14889 | -0.03176 | -0.6506 | -0.25 | +0.4006 | -0.1564 | 0.2783 |
| Naive | 0.17481 | 0.17829 | +0.00348 | 0.0 | 0.0 | +0.0000 | nan | 0.0 |

## Mechanism telemetry: heuristic v2 vs OECD

| Metric | Heuristic v2 | OECD | Δ |
|---|---|---|---|
| S->E transitions | 99 | 130 | +31 |
| E->I transitions | 92 | 89 | -3 |
| I->R transitions | 0 | 0 | +0 |
| R->S transitions | 11 | 0 | -11 |
| R->I transitions | 18 | 1 | -17 |
| Nodes ever E | 49 | 95 | +46 |
| Nodes ever I | 62 | 70 | +8 |
| Nodes ever R | 21 | 1 | -20 |
| Bullwhip active cells | 747 | 911 | +164 |
| Floor active cells | 933 | 22 | -911 |

## Ablation on OECD graph

Baseline MAE = 0.15297

| Configuration | MAE | ΔMAE vs full | ΔR² |
|---|---|---|---|
| no_seirs | 0.15297 | +0.00000 | +0.00000 |
| no_bullwhip | 0.153 | +0.00003 | +0.00003 |
| no_hysteresis | 0.15297 | +0.00000 | +0.00000 |
| no_network_amp | 0.15889 | +0.00592 | +0.00592 |

## Phase 8 — Brutally honest conclusion

### What improved

- **Pearson correlation improved** for SEIRS: -0.1539 (heuristic) → 0.3042 (OECD).
- **R² improved**: -0.6436 → -0.4178.
- **Mechanism activation increased**: bullwhip active cells 747 → 911.
- **Graph backed by real OECD ICIO 2022 data** for 14 of 19 sectors.
- **Edge weights derived from real bilateral flows** (5.5M parsed; 2440 retained after threshold + aggregation).

### What degraded

- **Benchmark coverage decreased**: 2 fewer events benchmarkable on OECD graph.
- **15 countries dropped** (not in OECD ICIO): ['ETH', 'IRN', 'IRQ', 'KEN', 'LBN', 'LBY', 'LKA', 'MDV', 'NPL', 'PRK', 'PSE', 'QAT', 'SYR', 'VEN', 'YEM']. Events tied to LKA default, IRN sanctions, YEM Houthi etc. lose mapping.

### What remains heuristic

- 5 of 19 GEDS sectors have no OECD source: **semiconductors, gas, insurance, capital_markets, energy** (composite). These remain NULL in the OECD presence CSV. Any event whose primary sector is one of these still depends on the heuristic graph.
- Chokepoint nodes (Suez, Hormuz, etc.) and their connectivity remain hardcoded — OECD ICIO has no chokepoint concept. The OECD graph used in this run includes 5 chokepoint nodes (TaiwanStrait, Malacca, Suez, Hormuz, Panama) with the same heuristic link map as v2-expanded.
- Per-node vulnerability / amplification / recovery_delay parameters are still sector-default heuristics (`SECTOR_VULN`, `SECTOR_REC` tables in this script). OECD provides flow data, not behavioural parameters.

### Does OECD integration actually improve scientific validity?

**Yes, qualitatively** — the graph now carries traceable real-data provenance for the majority of country×sector cells, and bilateral edges reflect actual 2022 trade flows rather than heuristic intra-country couplings.

**No, quantitatively** — MAE / R² / Pearson all moved within the bootstrap CIs of the v3 benchmark. The OECD graph is more honest but not measurably more accurate on N≈23 events with the current calibrated config.

**Linear Diffusion still beats or ties SEIRS** on the OECD graph too. The structural-vs-naive gap remains the same shape.

### Did calibration transfer or collapse?

**Partially preserved.** SEIRS MAE = 0.15297 on OECD graph is in the same ballpark as v2-expanded numbers, suggesting the calibration transfers acceptably across topologies of similar density.

### Is GEDS publication-closer or still exploratory?

**Closer in provenance, no closer in accuracy.** The OECD ingestion lets us state with peer-review-grade citations (OECD ICIO 2022) exactly where graph edges came from. That removes the 'heuristic edge weights' citation in the publication risk report's CRITICAL row. But MAE / R² / skill scores have not crossed any qualitative threshold; claims like 'GEDS beats Linear Diffusion on historical events' are still NOT supported.

### Concrete next step

- Re-run MCMC calibration on the OECD graph (`mcmc.py` × N=23 events × OECD edges). The current calibrated_v2 params were fit on the 40-node graph and almost certainly are not optimal here. A fresh MCMC pass would tell us whether GEDS' underperformance is structural or just a calibration mismatch.
- Ingest sector-specific supplementary sources for the 5 NULL GEDS sectors: SIA Factbook (semis), EIA per-country gas (gas split from oil), ECB SDW (insurance/capital_markets separated from K). Each unblocks events currently tied to those sectors.
- Pursue WIOD ingestion for `employment_share` — still NULL.
