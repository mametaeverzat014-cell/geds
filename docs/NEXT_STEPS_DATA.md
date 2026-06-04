# GEDS Data Layer — Implementation Roadmap

Derived from `dataset_catalog.csv` (53 datasets) and
`dataset_priority.csv` (35 HIGH / 16 MEDIUM /
2 LOW).

Effort estimates assume 1 engineer working in the existing GEDS
Python codebase. Times are calendar days, not pure-coding days.

## Immediate (1–3 days)

Goal: bootstrap the fetcher infrastructure on the 5 highest-leverage
HIGH-priority datasets — the ones GEDS already needs but does not yet
ingest. Everything else mechanical-scales from this foundation.

1. **Stand up the fetcher registry**: `backend/app/data/fetchers/__init__.py`
   with the `comtrade_fetcher.py` pattern. _0.5 day._
2. **Manifest schema**: per-dataset JSON with `sha256`, `last_fetch`,
   `coverage_end`, `source_url`. _0.5 day._
3. **`/api/v1/data/sources` rewrite**: enumerate catalog rows live
   instead of the hardcoded stub. _0.5 day._

Then wire these 5 fetchers (one per major API family):

- **1. UN Comtrade** (United Nations Statistics Division) — wire fetcher + validator. _Effort: 0.5 day._
- **8. IMF World Economic Outlook (WEO) Database** (International Monetary Fund) — wire fetcher + validator. _Effort: 0.5 day._
- **9. World Development Indicators (WDI)** (World Bank) — wire fetcher + validator. _Effort: 0.5 day._
- **34. FRED — Federal Reserve Economic Data** (Federal Reserve Bank of St. Louis) — wire fetcher + validator. _Effort: 0.5 day._
- **44. GDELT — Global Database of Events, Language and Tone** (GDELT Project (Leetaru & Schrodt)) — wire fetcher + validator. _Effort: 0.5 day._

## Short-term (1–2 weeks)

Goal: complete HIGH-priority ingestion (the remaining free-API datasets)
and start on MEDIUM (key-required + flat-file). Once the fetcher pattern
exists, each new dataset is mostly mechanical.

### Remaining HIGH-priority free-API datasets

- **3. WITS — World Integrated Trade Solution** (World Bank / UNCTAD) — _~0.5 day each, parallelisable._
- **4. WTO Tariff & Trade Data (TTD)** (World Trade Organization) — _~0.5 day each, parallelisable._
- **6. Global Trade Alert (GTA)** (St. Gallen Endowment for Prosperity Through Trade (SGEPT)) — _~0.5 day each, parallelisable._
- **10. OECD National Accounts & GDP** (OECD) — _~0.5 day each, parallelisable._
- **11. IMF Financial Soundness Indicators (FSI)** (International Monetary Fund) — _~0.5 day each, parallelisable._
- **13. IMF Primary Commodity Price System (PCPS)** (International Monetary Fund) — _~0.5 day each, parallelisable._
- **16. OECD Trade in Value Added (TiVA)** (OECD / WTO) — _~0.5 day each, parallelisable._
- **17. OECD Inter-Country Input-Output (ICIO) Tables** (OECD) — _~0.5 day each, parallelisable._
- **19. World Bank Logistics Performance Index (LPI 2.0)** (World Bank) — _~0.5 day each, parallelisable._
- **20. OECD Composite Leading Indicators (CLI)** (OECD) — _~0.5 day each, parallelisable._
- **21. US International Trade Administration (ITA) Trade Data** (US International Trade Administration) — _~0.5 day each, parallelisable._
- **22. IMF PortWatch** (International Monetary Fund) — _~0.5 day each, parallelisable._
- **23. UNCTAD Liner Shipping Connectivity Index (LSCI)** (UNCTAD / MDS Transmodal) — _~0.5 day each, parallelisable._
- **29. UN Comtrade HS Chapter 85 (Electrical Machinery / Semiconductors)** (UN Statistics Division) — _~0.5 day each, parallelisable._
- **30. EIA International Energy Statistics** (US Energy Information Administration) — _~0.5 day each, parallelisable._
- **35. BIS Statistics — Banking, Debt, Derivatives** (Bank for International Settlements) — _~0.5 day each, parallelisable._
- **37. IMF International Financial Statistics (IFS)** (International Monetary Fund) — _~0.5 day each, parallelisable._
- **38. FRED — CPI and PCE Series** (Federal Reserve Bank of St. Louis) — _~0.5 day each, parallelisable._
- **39. OECD Consumer and Producer Price Indices** (OECD) — _~0.5 day each, parallelisable._
- **40. IMF World Economic Outlook — Inflation Forecasts** (IMF) — _~0.5 day each, parallelisable._
- **41. FAO Food Price Index (FFPI)** (UN Food and Agriculture Organization) — _~0.5 day each, parallelisable._
- **43. ACLED — Armed Conflict Location & Event Data** (Armed Conflict Location & Event Data Project) — _~0.5 day each, parallelisable._
- **47. GDELT Global Knowledge Graph (GKG)** (GDELT Project) — _~0.5 day each, parallelisable._
- **48. GDELT Stability Index (Instability Score)** (GDELT Project) — _~0.5 day each, parallelisable._
- **49. IMF WEO Historical Database** (IMF) — _~0.5 day each, parallelisable._
- **50. World Bank WDI — Historical Panel** (World Bank) — _~0.5 day each, parallelisable._
- **52. EM-DAT — International Disaster Database** (Centre for Research on the Epidemiology of Disasters (CRED), Université Catholique de Louvain) — _~0.5 day each, parallelisable._
- **56. World Bank — Air Transport Data (WDI)** (World Bank / ICAO) — _~0.5 day each, parallelisable._
- **57. OECD Infrastructure Investment Statistics** (OECD) — _~0.5 day each, parallelisable._
- **62. WITS — UNCTAD TRAINS Tariff & NTM Data** (World Bank / UNCTAD) — _~0.5 day each, parallelisable._

### MEDIUM-priority datasets (top 10 by confidence)

- **12. World Bank Commodity Prices — "Pink Sheet"** (World Bank, conf=3) — scheduled HTTP download, validator, normalizer. _1–2 days each._
- **14. NY Fed Global Supply Chain Pressure Index (GSCPI)** (Federal Reserve Bank of New York, conf=3) — scheduled HTTP download, validator, normalizer. _1–2 days each._
- **15. World Bank Global Supply Chain Stress Index (GSCSI-M)** (World Bank, conf=3) — scheduled HTTP download, validator, normalizer. _1–2 days each._
- **2. BACI — Bilateral Trade Flows** (CEPII (Centre d'Études Prospectives et d'Informations Internationales), conf=3) — scheduled HTTP download, validator, normalizer. _1–2 days each._
- **55. UNCTAD Review of Maritime Transport** (UNCTAD, conf=3) — scheduled HTTP download, validator, normalizer. _1–2 days each._
- **18. CEPII GeoDep — Trade Dependency Database** (CEPII, conf=2) — scheduled HTTP download, validator, normalizer. _1–2 days each._
- **27. WSTS Global Semiconductor Sales Data** (World Semiconductor Trade Statistics (WSTS), conf=2) — scheduled HTTP download, validator, normalizer. _1–2 days each._
- **28. CEPII PLAID — Product-Level AI-Derived Indicators** (Kiel Institute + CEPII, conf=2) — scheduled HTTP download, validator, normalizer. _1–2 days each._
- **42. Global Economic Policy Uncertainty Index (GEPU)** (Baker, Bloom & Davis / policyuncertainty.com, conf=2) — scheduled HTTP download, validator, normalizer. _1–2 days each._
- **5. Harvard Growth Lab — Atlas of Economic Complexity (SITC Rev.2 & HS)** (Harvard Growth Lab, conf=2) — scheduled HTTP download, validator, normalizer. _1–2 days each._

Cross-cutting:
- Implement schema-drift detection in the validator layer.
- Wire the existing GitHub Actions cron to call each new fetcher.
- Add `backend/scripts/refresh_all.py` as the local equivalent.

## Medium-term (1 month)

Goal: edge-merger expansion. The current engine uses 64 hardcoded
edges + 137 Comtrade edges (opt-in). With CEPII BACI and OECD ICIO
ingested, the graph can grow to thousands of bilateral edges, and the
Sobol / MCMC calibration must be re-run on the larger topology.

- BACI bilateral trade ingestion + merge into `edge_merger.py`.
- OECD ICIO 2023 edition ingest → derive industry-to-industry weights.
- OECD TiVA layer for value-added (vs gross) trade dependencies.
- Re-run MCMC (production: 100 walkers × 2000 steps) on expanded graph.
- Re-run Sobol; check if `propagation_decay` / `amplification_mu` are
  still non-identifiable with more edges.
- Re-run benchmark vs Leontief / Linear Diffusion / Naive.

_Depends on: short-term ingestion infrastructure being stable._
_Effort: ~3 weeks (data 1w + calibration 1w + benchmark 1w)._

## Long-term (multi-month)

- **Real-time event detection layer**: GDELT + ACLED + GTA streams,
  with a debounced event-clustering step before triggering simulation
  re-runs. Requires a small Kafka/Redis-like buffer (not yet built).
- **Geospatial layer**: IMF PortWatch + Kiel Trade Indicator integration
  for daily port-level signals. Needs GIS plumbing (GeoServices/WMS).
- **Vintage-pinned IMF WEO archive**: backtesting against historical
  WEO forecasts requires download of every vintage since 2007 and a
  schema-versioning layer (TSV pre-2023 → SDMX post-2023).
- **News stream → shock signal pipeline**: GDELT + Grok narrative
  classifier with confidence scoring. Already partially exists
  (`narrative` endpoint with Grok stub).

_Depends on: medium-term graph expansion + calibration._
_Effort: 2–3 months each._

## Datasets explicitly NOT in scope for first 6 months

These are LOW priority by the derivation rules — paywalled, members-only,
or requiring GIS-only access:

- 25 (Baltic Exchange Indices (via FRED)): Baltic Exchange primary data is proprietary and paid; FRED provides daily index only; route-specific rates require paid 
- 26 (SIA Factbook (Annual)): Full databook requires SIA membership; PDF figures not machine-readable; sales data rather than production/capacity data
