# GEDS — Final State (after scientific-layer integration)

Snapshot: `2026-05-27T07:49:46.525352+00:00`

## Headline counts

- **Graph nodes:** 595 (`expanded_graph_nodes_v2.csv`)
- **Graph edges:** 2145 (`expanded_graph_edges_v2.csv`)
- **Sectors active in engine:** 19 (`Industry` enum) of which 19 are present in ≥1 country in `country_sector_presence.csv`
- **Events catalogued:** 42 (`master_event_registry.csv`)
- **Events benchmarkable:** 23 (engine sector + graph filter)
- **Peer-reviewed papers (catalog):** 25
- **Literature references (extended):** 41
- **Datasets catalogued:** 53
- **Event-evidence rows:** 13 (peer-reviewed ingestion pass)
- **Propagation-mechanism papers (new):** 10
- **Chokepoints (new):** 8
- **Mechanism validation rows:** 9
- **Country-sector presence rows:** 1121
- **Missing-event-mapping rows (gap log):** 19

## Benchmark v3 (engine + 95% bootstrap CIs)

Same engine config as v2-expanded (calibrated_v2 DE-best params; not changed).
N = 23 events. 19 events excluded for sector/graph/target gaps.

| Model | MAE | MAE 95% CI | R² | R² 95% CI | Pearson |
|---|---|---|---|---|---|
| SEIRS-Bullwhip-Hysteresis (GEDS) | 0.17987 | [0.10294, 0.26279] | -0.6436 | [-1.2274, -0.3869] | -0.1539 |
| Leontief | 0.16528 | [0.09185, 0.24661] | -0.5684 | [-1.1104, -0.3141] | 0.6548 |
| Linear Diffusion | 0.18065 | [0.10322, 0.26355] | -0.6506 | [-1.2391, -0.3938] | -0.1564 |
| Naive Persistence | 0.17481 | [0.13012, 0.22511] | 0.0 | [-0.3342, -0.0001] | nan |

## Critical finding: calibration does not transfer across graph topologies

Compare benchmark v2-expanded (default `EngineConfig()`) vs v3 (calibrated_v2 params, same graph + events):

| Model | v2-expanded MAE (default cfg) | v3 MAE (calibrated cfg) | Δ |
|---|---|---|---|
| GEDS (SEIRS) | 0.16418 | **0.17987** | **+0.01569 worse** |
| Leontief | 0.16528 | 0.16528 | 0 (no parametric dep on EngineConfig) |
| Linear Diffusion | 0.18065 | 0.18065 | 0 (uses its own α, β only) |
| Naive Persistence | 0.17481 | 0.17481 | 0 |

The calibration_v2 best params were fit on the 40-node graph (Phase 4 of the validation-expansion session). Applied to the 595-node expanded graph they **degrade** GEDS performance by ~10% relative MAE. Calibration does not transfer.

Two further observations:

- **Leontief is now the best structural model** at MAE=0.16528, ahead of GEDS (0.180) and Linear Diffusion (0.181). Leontief has no `EngineConfig`-tunable parameters and is unaffected by the calibration mismatch.
- **GEDS Pearson collapsed to −0.154** under calibrated config on the expanded graph, vs +0.504 under default config. The ordering of events is now anti-correlated with truth. This is worse than uncalibrated.

**Implication:** the calibration_v2 posterior is a 40-node artefact, not a transferable model. Any benchmark claim using calibrated params on the expanded graph is misleading until calibration is re-run on the expanded topology.

## Remaining limitations (do NOT hide these)

1. **Negative R²** for all structural models. Root cause per `publication_risk_report.md`: heuristic edge weights. OECD ICIO / WIOD ingestion is the documented fix.
2. **Bootstrapped CSVs**: the 6 new scientific-layer CSVs were built from existing repo evidence (`publication_risk_report.md`, `papers_catalog.csv`, `expanded_graph_nodes_v2.csv`). Each row has a `_source_origin` column. Some cells are NULL where the source provided no value.
3. **No new events benchmarkable** in this pass. v3 has the same 23 OK events as v2-expanded. Gaining events requires real OECD ICIO data or extended engine enum.
4. **`country_sector_presence.csv` is circular** — derived from the same heuristic map that produced `expanded_graph_nodes_v2.csv`. Replacing the heuristic at source requires OECD ICIO 2018 ingestion.
5. **`missing_event_mapping.csv` lists gaps, not new mappings**. 19 events remain UNMAPPED / NO_TARGET / SCENARIO.
6. **2 mechanisms UNSUPPORTED** per `mechanism_validation.csv`: SEIRS re-susceptibility rate (ξ), country×sector heuristic weights.
7. **3 mechanisms UNCERTAIN**: SEIRS supply-chain threshold, financial contagion extreme-value parameters, healthcare sector propagation.
8. **4 mechanisms SUPPORTED**: supply-chain network propagation (Carvalho 2021 QJE), bullwhip amplification (Lee 1997), hysteresis (Cerra 2020), chokepoint systemic risk (Verschuur 2025 Nature Comms).

## What changed in this pass

- **Source files:** none (engine code unchanged).
- **New module:** `backend/app/data/scientific_registry.py` exposes 5 frozen dataclasses + 9 lookup helpers.
- **New CSVs:** 6 bootstrapped from existing evidence (every row provenanced).
- **New JSONs:** `literature_priors.json` documents per-mechanism priors (engine not modified).
- **New docs:** `PUBLICATION_READINESS_V2.md` reports SUPPORTED/UNCERTAIN/UNSUPPORTED labels.

## Reproducibility

```
python backend/scripts/bootstrap_scientific_layer.py
python backend/scripts/integrate_scientific_layer.py
```

Both scripts are deterministic given the same input CSVs and a fixed numpy seed (42).
