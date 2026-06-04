# GEDS — Master State

Single source of truth for what currently exists in the repository,
aggregated from the 4 master registries.

## Current graph size

- **Nodes:** 40 (36 country×sector + 4 chokepoints)
- **Edges (default):** 64 (hardcoded MVP)
- **Edges (Comtrade-merged, opt-in):** 201 (set `GEDS_USE_COMTRADE_EDGES=1`)
- **Sectors in taxonomy:** 23 (`GEDS_SECTORS` in `data_registry.py`)
- **Country codes in graph nodes:** ~15 unique ISO3 (TWN, USA, CHN, JPN, DEU, KOR, NLD, VNM, MYS, THA, IND, MEX, plus 4 chokepoints)

## Historical event coverage

- **Events catalogued:** 42
- **Events with GDP impact value:** 40 (95.2%)
- **Scenario / forward-looking events:** 1
- **Events with peer-reviewed literature corroboration:** 1 (2.4%)
- **Events with v2 institutional ground-truth (≥1 row):** 8 (19.0%)
- **Events whose affected (country, sector) maps to ≥1 GEDS graph node:** 11 (26.2%)
- **Average source-rated confidence:** 4.24 / 5

## Dataset coverage

- **Datasets catalogued:** 53
- **HIGH priority (free API + Python package):** 35
- **MEDIUM priority (key required or flat-file):** 16
- **LOW priority (paywalled or geospatial-only):** 2
- **Datasets with a public API:** 36
- **Average derived confidence:** 3.26 / 5

Coverage by category (top 5):

- `macroeconomics`: 10
- `trade`: 7
- `supply_chain`: 7
- `historical_events`: 5
- `shipping`: 4

## Model coverage

- **Benchmark models catalogued:** 10
- `graph_neural_networks`: 2
- `network_models`: 2
- `machine_learning`: 2
- `economic_models`: 1
- `linear_models`: 1
- `agent_based_models`: 1
- `hybrid_models`: 1

Models by implementation difficulty:

- `Easy`: 6
- `Hard`: 3
- `Medium`: 1

## Validation coverage

- **`validation_targets_v2.csv`** (institutional ground-truth from v2 docx): **178 rows** across 8 events
- **`validation_targets_expanded.csv`** (event aggregates + literature): **94 rows** across 42 events
- **`benchmark_inputs.csv`** (event-level aggregates for benchmark scoring): 42 rows
- **`event_to_graph_mapping.csv`** (country × sector cross-product): 724 rows
- **Peer-reviewed corroborations attached to events:** 2 paper-event links across 1 events

## Research coverage

- **Total literature entries:** 61
- **Deeply-cataloged (full author/year/DOI):** 25 (from `papers_catalog.csv`)
- **Title-only references:** 36 (from `literature_catalog.csv`)
- **Average confidence:** 3.26 / 5
- **BibTeX file:** `docs/CITATIONS.bib` (25 full entries + title-only `@misc` entries)

## Known gaps

From the inconsistency-detection pass:

- **Duplicate event names** (legacy vs expanded): 0
- **Validation rows missing ISO3:** 2
- **v2 event_num with no expanded event_id mapping:** 0
- **Sectors outside GEDS taxonomy:** 0 distinct terms
- **Duplicate dataset URLs:** 7 URLs shared by ≥2 dataset_ids
- **Cross-referenced papers (paper appears in both papers_catalog and literature_catalog):** 5
- **Validation rows with NO observed numeric value at all:** 0

Top non-taxonomy sectors encountered:


Persistent gaps from prior audits (not new):

- **`recovery_time_months` 97.6% blank** — source docx had no explicit Recovery Time field.
- **3 of 5 SEIRS parameters non-identifiable** per the prior Sobol run (see `STATE.md`).
- **Linear Diffusion beats GEDS** on the N=8 benchmark (see `STATE.md`).
- **Production backend** (`geds-backend.onrender.com`) returned 503 on last probe.

## Confidence metrics (aggregate, per registry)

| Registry | N | Mean confidence (1–5) |
|---|---|---|
| master_event_registry | 42 | 4.24 |
| master_dataset_registry | 53 | 3.26 |
| master_literature_registry | 61 | 3.26 |

## Files this state was built from

Inputs (CSVs in `backend/data/csv/`):

- `historical_events_expanded.csv`, `historical_events.csv` (legacy)
- `validation_targets_v2.csv`, `validation_targets_expanded.csv`, `validation_targets.csv` (V0)
- `benchmark_inputs.csv`, `model_event_mapping.csv`, `event_to_graph_mapping.csv`
- `dataset_catalog.csv`, `dataset_priority.csv`, `validation_datasets.csv` (legacy)
- `model_catalog.csv`, `method_catalog.csv`, `benchmark_matrix.csv`
- `papers_catalog.csv`, `literature_catalog.csv`

Audit references:

- `DATA_AUDIT.md` (events), `DATA_AUDIT_DATASETS.md` (datasets),
- `VALIDATION_DATA_AUDIT.md` (validation), `UNCERTAINTY_ANALYSIS.md`
