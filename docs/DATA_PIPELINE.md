# GEDS Data Pipeline — Architecture

End-to-end ingestion design for the dataset catalog.

```
Source  →  Fetch  →  Validate  →  Normalize  →  Store  →  Graph Builder  →  Simulation Engine
```

## Layer 1 — Source

- **53 datasets** catalogued in
  `backend/data/csv/dataset_catalog.csv`.
- **35 HIGH-priority** datasets are the target for the first
  automated pipeline (free API + Python package available).
- **16 MEDIUM** require scheduled download or key registration.
- **2 LOW** are paywalled or require GIS infrastructure
  and are deferred until the data layer matures.

## Layer 2 — Fetch

Two fetch modes coexist:

1. **API mode** (HIGH priority datasets): a thin wrapper around each
   provider's REST endpoint, plus its Python package where available
   (e.g. `comtradeapicall`, `fredapi`, `wbgapi`, `imfp`, `pandasdmx`).
   Implementation lives in `backend/app/data/fetchers/` (one module per
   provider). Existing example: `backend/app/data/comtrade_fetcher.py`.
2. **Flat-file mode** (MEDIUM priority): scheduled HTTP GET of XLSX/CSV
   bulk dumps. Files land in `backend/data/raw/<provider>/<dataset_id>/`
   with the date in the filename. Existing example: the daily Comtrade
   cron in `.github/workflows/refresh-data.yml`.

## Layer 3 — Validate

Each fetch is followed by a per-dataset validator that checks:

- file is non-empty and parseable as its declared `format`
- expected variables (from catalog `variables` column) are present
- coverage_end has not regressed vs. the previous successful fetch
- counts are within ±50% of the last 4-week median (anomaly guard)

Failure mode: validator writes an `.error` file alongside the fetched
artefact and the cron job exits non-zero. The previous successful
artefact remains the active one (no silent overwrite).

## Layer 4 — Normalize

All sources are normalised into the GEDS canonical schema before
they touch the graph:

- **Countries**: ISO3 (see `historical_events_expanded.csv` for the
  reference mapping table, including region expansions).
- **Sectors**: GEDS fixed taxonomy (see `extract_events_from_docx.py`
  `SECTOR_TAXONOMY`).
- **Time**: ISO weekly bucket (Sunday-start), since the propagation
  engine runs in weekly time steps.
- **Units**: USD nominal for value, TEUs for shipping, % for indices.

Normalisation modules live in `backend/app/data/normalize/`.

## Layer 5 — Store

Raw and normalised artefacts both go to disk; no DB required for v1.

```
backend/data/
├── raw/                    # provider-formatted dumps
│   └── <provider>/<dataset_id>/YYYY-MM-DD.<ext>
├── csv/                    # canonical CSVs for the engine
│   ├── dataset_catalog.csv
│   ├── historical_events_expanded.csv
│   └── comtrade_edges.csv
├── parquet/                # parquet mirrors for ML
└── manifests/              # provenance records
    └── <dataset_id>.json   # last_fetch, sha256, source_url
```

## Layer 6 — Graph Builder

`backend/app/data/edge_merger.py` already merges Comtrade edges into
the engine graph; the same module pattern will extend to other
bilateral-trade and supply-chain datasets (BACI, OECD ICIO, OECD TiVA).
Macroeconomic datasets (IMF WEO, World Bank WDI, FRED) feed node
attributes, not edges, and update the per-node baseline shock vector
rather than the topology.

## Layer 7 — Simulation Engine

The engine consumes the canonical CSVs at boot via `seed.load_graph()`
and never reads raw provider files directly. This isolates engine
correctness from data-source churn.

## Daily refresh logic

GitHub Actions (`.github/workflows/refresh-data.yml`) runs a cron daily.
Per dataset:

1. Read last-fetch timestamp from `manifests/<dataset_id>.json`.
2. If older than `update_frequency` (catalog column), fetch.
3. Run the validator. On failure, leave previous artefact in place.
4. On success, write artefact + updated manifest, sha256 the file,
   and commit the manifest (but NOT the raw artefact — too large).
5. Open a PR labelled `data-refresh` for the manifest commits.

## Failure handling

- **Network failure during fetch**: retry 3× with exponential backoff,
  then skip the dataset for the day and log an `.error` file. Cron
  continues with remaining datasets.
- **Validator failure**: emit a Sentry-style alert (post to a dedicated
  channel; not yet wired). Previous artefact remains active.
- **Schema drift** (variable disappeared upstream): validator flags it;
  human triage required. The catalog `confidence` may need downgrade.

## Caching strategy

- Raw dumps are kept indefinitely on disk (gitignored).
- The engine reads from `backend/data/csv/*.csv`. These are committed.
- API responses are NOT cached in-memory at request time; the engine
  reloads from CSV on cold boot only.

## Versioning

- Each dataset artefact has a fetch date in the filename.
- The manifest tracks `coverage_start`, `coverage_end`, `sha256`, and
  `provider_release_date` so we can pin a model to a specific data
  vintage (important for IMF WEO comparisons across vintages).

## Deduplication

Cross-reference entries flagged in `DATA_AUDIT_DATASETS.md` are
**not** fetched twice — the alias points to the canonical entry's
dataset_id and shares its artefacts.

## Monitoring

- `/api/v1/data/last-refresh` already exposes the manifest layer over HTTP.
- `/api/v1/data/provenance` returns per-dataset citation + last-fetch sha.
- A weekly summary email of refresh successes/failures is **not yet built**
  — listed in NEXT_STEPS_DATA.md.
