# GEDS — Graph Evidence Comparison

Snapshot: `2026-05-27T08:05:42.502009+00:00`

Comparison of the heuristic country×sector graph (`country_sector_presence.csv`) against the real-data graph (`country_sector_presence_real.csv`).

## Ingestion pipeline status

| Pipeline | Status | Notes |
|---|---|---|
| `ingest_oecd_icio.py` | NO_DATA / parser stub |   Downstream country_sector_presence_real.csv will have NULL gdp_share for all rows. |
| `ingest_wiod.py` | NO_DATA / parser stub |   Downstream country_sector_presence_real.csv will have NULL employment_share for all rows. |
| `ingest_un_comtrade.py` | OK |   wrote: D:\GEDS\backend\data\raw\comtrade\parsed\sectoral_trade_share_2019.csv |

Provenance files:

- `backend/data/raw/oecd_icio/parsed/provenance.json`: status=`NO_DATA`, reason=`source file not found`
- `backend/data/raw/wiod/parsed/provenance.json`: status=`NO_DATA`, reason=`source file not found`
- `backend/data/raw/comtrade/parsed/provenance.json`: status=`OK`, reason=`—`

## Heuristic vs real (headline)

| Metric | Heuristic | Real | Δ |
|---|---|---|---|
| Countries covered | 59 | 12 | -47 |
| Sectors covered | 19 | 3 | -16 |
| Total (country, sector) rows | 1121 | 228 | — |
| Rows marked `present`/`DATA_PRESENT` | 587 | 36 | -551 |
| Rows with real trade_share | NA | 36 | — |
| Rows with real gdp_share | NA | 0 | — |
| Rows with real employment_share | NA | 0 | — |

**Headline finding:** the heuristic graph claims presence for **587** (country, sector) pairs across **59** countries × **19** sectors. The real-data graph confirms only **36** pairs across **12** countries × **3** sectors. The shortfall is not because the heuristic was wrong — it is because real source data (OECD ICIO, WIOD, full Comtrade) is mostly missing from the repo.

## Per-sector real-data coverage

| GEDS Sector | Real-data (country, sector) rows | Source |
|---|---|---|
| semiconductors | 12 | UN Comtrade 2019 |
| automotive | 12 | UN Comtrade 2019 |
| electronics | 12 | UN Comtrade 2019 |
| aerospace | 0 | NONE (OECD/WIOD absent) |
| shipping | 0 | NONE (OECD/WIOD absent) |
| energy | 0 | NONE (OECD/WIOD absent) |
| consumer_goods | 0 | NONE (OECD/WIOD absent) |
| banking | 0 | NONE (OECD/WIOD absent) |
| insurance | 0 | NONE (OECD/WIOD absent) |
| capital_markets | 0 | NONE (OECD/WIOD absent) |
| oil | 0 | NONE (OECD/WIOD absent) |
| gas | 0 | NONE (OECD/WIOD absent) |
| utilities | 0 | NONE (OECD/WIOD absent) |
| aviation | 0 | NONE (OECD/WIOD absent) |
| ports | 0 | NONE (OECD/WIOD absent) |
| telecommunications | 0 | NONE (OECD/WIOD absent) |
| agriculture | 0 | NONE (OECD/WIOD absent) |
| tourism | 0 | NONE (OECD/WIOD absent) |
| government | 0 | NONE (OECD/WIOD absent) |

## What this means for the engine

### Node count

- **Heuristic graph (`expanded_graph_nodes_v2.csv`):** 595 nodes (country×sector + chokepoints). Country×sector presence derived from SPECIALTY_PRESENCE map — i.e., the heuristic.
- **Real-data graph (would-be):** ~36 country×sector nodes + chokepoints. Limited by Comtrade-only sector coverage (3 of 19 sectors).
- **Gain from switching:** −551 nodes lost. **This would shrink the graph, not grow it**, because real data is sparse.

### Edge count

- **Heuristic graph:** 2145 edges (intra-country financial mesh + credit + telecom + energy supply + chokepoint + Comtrade-real bilateral).
- **Real-data graph:** edges already exist from Comtrade (414 bilateral rows in `comtrade_edges.csv`). Intra-country sector coupling (banking→all, utilities→all, telecom→all) was heuristic and would need OECD ICIO to derive.

### Coverage gain (events benchmarkable)

- **Heuristic graph benchmarks N=23 events** (per benchmark_v3.json).
- **Real-data graph would benchmark fewer**, because:
  - Only 3 sectors have real Comtrade data (electronics, semiconductors, automotive)
  - Events with sectors financial, energy, tourism, agriculture, etc. would lose mapping
- **No coverage gain in this pass.** Real data is more credible per row but covers fewer (country, sector) cells than the heuristic.

### Benchmark change (projected, NOT measured)

- A real-data-only benchmark is not run in this pass because the resulting graph would have fewer than the current 23 eligible events. Running it would conflate 'real-data effect' with 'small-N noise'.
- To realise the benefit of real data: ingest OECD ICIO 2018 (free, ~125 MB) and WIOD 2016 (free, ~150 MB). After both are present, this script auto-populates gdp_share and employment_share columns; then a benchmark comparison becomes meaningful.

## Brutally honest conclusion

1. **The 'circular evidence' problem in `country_sector_presence.csv` is real.** It was derived from the SPECIALTY_PRESENCE heuristic in `expanded_graph_nodes_v2.csv`.
2. **This pass cannot fully fix it.** OECD ICIO and WIOD are required and not present in the repo.
3. **What this pass DOES fix:** trade_share for 3 sectors × 12 countries is now derived from real UN Comtrade 2019 parquet pulls (`backend/data/raw/comtrade/*.parquet`).
4. **Everything else stays NULL.** The output CSV has `MISSING_NO_DATA` in 192 of 228 rows. No values were inferred.
5. **Next concrete action:** download OECD ICIO 2018 and WIOD 2014 manually (free, no auth), drop the files in `backend/data/raw/oecd_icio/` and `backend/data/raw/wiod/`, re-run `build_country_sector_presence_real.py`. At that point gdp_share and employment_share columns get populated and the comparison numbers above can be re-generated.

## What was NOT done (transparent)

- **Network ingestion**: this script does NOT fetch from external URLs. The OECD and WIOD downloads must be done manually (or by a separate fetch script with explicit user authorization).
- **WIOD xlsx parser** is a stub even when the file is present — the WIOT excel format requires careful per-version cell-offset handling. Stub returns PARSER_INCOMPLETE rather than fabricate.
- **GDP-share imputation** is not done. OECD ICIO publishes per-country, per-sector value-added; without that file, gdp_share is NULL for every row.
- **No engine modification.** Engine still uses `expanded_graph_nodes_v2.csv` loaded by `seed.py`. To switch the engine to use `country_sector_presence_real.csv` would require a new toggle in `seed.py`, which was not done in this pass because the real graph is too sparse to benchmark meaningfully.
