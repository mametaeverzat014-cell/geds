# GEDS Dataset Registry — Audit

Source: `D:/GEDS Dataset Registry  Global Economic Disruption Propagation (All Categories).docx`
Catalogue: `backend/data/csv/dataset_catalog.csv` (53 datasets)

## Confidence score — derivation rules

Confidence is **derived**, not extracted. Score in [1, 5]:
- baseline 1
- +1 if provider is a major standards body (UN, IMF, World Bank, OECD, Fed, ECB, BIS, WTO, EIA, FAO, CEPII)
- +1 if a free API exists (`api_available == 'Yes'`)
- +1 if a Python/R package is documented
- +1 if coverage span ≥10y AND update frequency at least annual

## Cross-reference / alias entries

10 entries reference other entries rather than carrying
their own data. These were **excluded from the catalog** to avoid
duplicate `dataset_id` rows. Track them here:

| Entry # | Name | Category | Points to |
|---|---|---|---|
| 31 | IMF Primary Commodity Price System (PCPS) | energy | (See Category 2, entry 13) — energy sub-indices particularly valuable |
| 32 | World Bank Pink Sheet — Energy Commodities | energy | (See Category 2, entry 12) — monthly energy spot prices going back to 1960 |
| 36 | IMF Financial Soundness Indicators (FSI) | financial | (See Category 2, entry 11) — financial market stability and banking sector health |
| 45 | Global Trade Alert (GTA) | geopolitical | (See Category 1, entry 6) — also a geopolitical risk instrument tracking trade weaponisation |
| 46 | GDELT Event Database | news | (See Category 10, entry 44) — primary real-time news/event data source |
| 54 | IMF PortWatch — Port Traffic | transportation | (See Category 5, entry 22) — the primary transportation-specific real-time dataset |
| 58 | OECD TiVA — Value-Chain Dependency | supply_chain | (See Category 3, entry 16) — reveals true trade dependencies via value-added linkages rather than gross trade |
| 59 | OECD ICIO — Input-Output Network | supply_chain | (See Category 3, entry 17) — sector × country flow matrix for supply-chain propagation / network analysis |
| 60 | CEPII BACI — Bilateral Product Trade Network | supply_chain | (See Category 1, entry 2) — enables bilateral trade dependency network construction at HS6 level |
| 61 | CEPII GeoDep — Import Dependency Flags | supply_chain | (See Category 3, entry 18) — strategic import dependency identification at HS6 level |

## Duplicate datasets

- Duplicate URLs: **7**
  - `https://comtradeplus.un.org` → dataset_ids [1, 29]
  - `https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/H8SFD2` → dataset_ids [5, 63]
  - `https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele.asp` → dataset_ids [7, 18]
  - `https://www.imf.org/en/publications/sprolls/world-economic-outlook-databases` → dataset_ids [8, 40, 49]
  - `https://data.worldbank.org` → dataset_ids [9, 50]
  - `https://data-explorer.oecd.org` → dataset_ids [10, 20, 39, 57]
  - `https://fred.stlouisfed.org` → dataset_ids [25, 34, 38]
- Duplicate names (case-insensitive): **0**

## Possibly dead / unparseable URLs

Datasets with no parseable HTTPS URL: **0**

## Paywalled / restricted-access sources

Count: **2**

- 1 (UN Comtrade): Free API: 500 calls/day, 250 records/call. Premium for bulk. Pre-2017 data in Comtrade Legacy. Reporting gaps for smaller economies
- 25 (Baltic Exchange Indices (via FRED)): Baltic Exchange primary data is proprietary and paid; FRED provides daily index only; route-specific rates require paid subscription

## Low-confidence datasets (score ≤ 2)

Count: **12**

- 5 (Harvard Growth Lab — Atlas of Economic Complexity (SITC Rev.2 & HS)): conf=2, provider=Harvard Growth Lab
- 7 (CEPII Gravity Dataset): conf=2, provider=CEPII
- 18 (CEPII GeoDep — Trade Dependency Database): conf=2, provider=CEPII
- 24 (Kiel Trade Indicator (KTI)): conf=1, provider=Kiel Institute for the World Economy (IfW)
- 26 (SIA Factbook (Annual)): conf=2, provider=Semiconductor Industry Association (SIA)
- 27 (WSTS Global Semiconductor Sales Data): conf=2, provider=World Semiconductor Trade Statistics (WSTS)
- 28 (CEPII PLAID — Product-Level AI-Derived Indicators): conf=2, provider=Kiel Institute + CEPII
- 33 (Bruegel Energy Policy Tracker): conf=1, provider=Bruegel Institute
- 42 (Global Economic Policy Uncertainty Index (GEPU)): conf=2, provider=Baker, Bloom & Davis / policyuncertainty.com
- 51 (GFDRR Disaster Risk Data): conf=2, provider=World Bank Global Facility for Disaster Reduction and Recovery
- 53 (NBER Historical Macroeconomic Data): conf=1, provider=National Bureau of Economic Research
- 63 (Atlas of Economic Complexity — Product Space): conf=2, provider=Harvard Growth Lab

## Missing variables / fields

Per-field missing-value counts:

| Field | Missing |
|---|---|
| dataset_id | 0 |
| dataset_name | 0 |
| provider | 0 |
| category | 0 |
| description | 0 |
| coverage_start | 3 |
| coverage_end | 39 |
| update_frequency | 0 |
| geographic_scope | 0 |
| variables | 0 |
| format | 0 |
| api_available | 6 |
| download_url | 0 |
| citation | 0 |
| limitations | 0 |
| confidence | 0 |

## Coverage gaps

Datasets with no parseable `coverage_start`: **3**
- 35 (BIS Statistics — Banking, Debt, Derivatives)
- 51 (GFDRR Disaster Risk Data)
- 53 (NBER Historical Macroeconomic Data)

## Coverage by category

| Category | Dataset count |
|---|---|
| macroeconomics | 10 |
| trade | 7 |
| supply_chain | 7 |
| historical_events | 5 |
| shipping | 4 |
| semiconductors | 4 |
| logistics | 3 |
| financial | 3 |
| geopolitical | 3 |
| transportation | 3 |
| energy | 2 |
| news | 2 |

## Note on file naming

The requested filename `docs/DATA_AUDIT.md` was already in use by the
historical-events extraction. To avoid overwriting that output, this
audit was written to `docs/DATA_AUDIT_DATASETS.md`. The event-level
audit is preserved at `docs/DATA_AUDIT.md`.
