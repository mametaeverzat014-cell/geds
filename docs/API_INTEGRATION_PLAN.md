# GEDS Data Layer — API Integration Plan

Generated from `backend/data/csv/dataset_catalog.csv` (53 datasets)
and the Dataset Registry API Quick Reference (10 APIs).

Only datasets whose `api_available == 'Yes'` are listed below. Datasets
lacking an API appear in the catalog with `api_available == 'No'` and are
expected to be ingested via scheduled flat-file download (see DATA_PIPELINE.md).

Difficulty ratings are derived from these observable signals:
- **Easy** = free public API + maintained Python package + no auth.
- **Medium** = free key required, OR Python package missing.
- **Hard** = bulk-only, key + rate-limit constraints, OR geospatial-only.

Time estimates are calendar-day estimates assuming 1 engineer with
existing GEDS Python infrastructure.

## UN Comtrade

- **Dataset ID:** 1
- **Provider:** United Nations Statistics Division
- **Category:** `trade`
- **Authentication:** Free API key
- **Rate limits:** 500 calls/day (free)
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://comtradeapi.un.org/data/v1/get/...`
- **Python package:** `comtradeapicall`
- **Expected response:** CSV, JSON, XML
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://comtradeplus.un.org
- **Known limitations:** Free API: 500 calls/day, 250 records/call. Premium for bulk. Pre-2017 data in Comtrade Legacy. Reporting gaps for smaller economies

## WITS — World Integrated Trade Solution

- **Dataset ID:** 3
- **Provider:** World Bank / UNCTAD
- **Category:** `trade`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** CSV, Excel, XML, JSON
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 1 week
- **Source URL:** https://wits.worldbank.org
- **Known limitations:** Not a primary data source — aggregates others. Some coverage gaps. API limited to UNCTAD TRAINS subset

## WTO Tariff & Trade Data (TTD)

- **Dataset ID:** 4
- **Provider:** World Trade Organization
- **Category:** `trade`
- **Authentication:** Free API key
- **Rate limits:** Moderate
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://api.wto.org/timeseries/v1/...`
- **Python package:** `python-wto`
- **Expected response:** CSV (zipped bulk)
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://ttd.wto.org/en/download
- **Known limitations:** Data depends on WTO member notifications; some countries lag years. Bound tariffs static.

## Global Trade Alert (GTA)

- **Dataset ID:** 6
- **Provider:** St. Gallen Endowment for Prosperity Through Trade (SGEPT)
- **Category:** `trade`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** CSV (bulk export)
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 1 week
- **Source URL:** https://www.globaltradealert.org/data_extraction
- **Known limitations:** Some interventions may not be discovered immediately; classification can be contested

## IMF World Economic Outlook (WEO) Database

- **Dataset ID:** 8
- **Provider:** International Monetary Fund
- **Category:** `macroeconomics`
- **Authentication:** None (no key)
- **Rate limits:** ~10 req/sec
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://dataservices.imf.org/REST/SDMX_JSON.svc/...`
- **Python package:** `imfp`
- **Expected response:** TSV/XLS, SDMX, CSV
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://www.imf.org/en/publications/sprolls/world-economic-outlook-databases
- **Known limitations:** Vintage data: download URL changes each release cycle; annual frequency only for most series

## World Development Indicators (WDI)

- **Dataset ID:** 9
- **Provider:** World Bank
- **Category:** `macroeconomics`
- **Authentication:** None
- **Rate limits:** None
- **Required keys:** None stated
- **Endpoint pattern:** `https://api.worldbank.org/v2/country/{iso}/indicator/{code}`
- **Python package:** `wbgapi, wbdata`
- **Expected response:** CSV, Excel
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data.worldbank.org
- **Known limitations:** Some indicators sparse for low-income countries; significant lags in national account revisions

## OECD National Accounts & GDP

- **Dataset ID:** 10
- **Provider:** OECD
- **Category:** `macroeconomics`
- **Authentication:** None
- **Rate limits:** None stated
- **Required keys:** None stated
- **Endpoint pattern:** `https://sdmx.oecd.org/public/rest/data/{AGENCY},{DATASET}/{FILTER}`
- **Python package:** `pandasdmx, OECD R package`
- **Expected response:** CSV, XML, JSON
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data-explorer.oecd.org
- **Known limitations:** Coverage primarily OECD countries; methodological revisions create breaks in series; limited sub-annual data for many countries

## IMF Financial Soundness Indicators (FSI)

- **Dataset ID:** 11
- **Provider:** International Monetary Fund
- **Category:** `macroeconomics`
- **Authentication:** None (no key)
- **Rate limits:** ~10 req/sec
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://dataservices.imf.org/REST/SDMX_JSON.svc/...`
- **Python package:** `imfp`
- **Expected response:** CSV, SDMX
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data.imf.org/en/datasets/IMF.STA:FSIC
- **Known limitations:** Significant reporting lag (up to 12 months); coverage varies substantially across jurisdictions

## IMF Primary Commodity Price System (PCPS)

- **Dataset ID:** 13
- **Provider:** International Monetary Fund
- **Category:** `macroeconomics`
- **Authentication:** None (no key)
- **Rate limits:** ~10 req/sec
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://dataservices.imf.org/REST/SDMX_JSON.svc/...`
- **Python package:** `imfp`
- **Expected response:** CSV, SDMX
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data.imf.org/en/datasets/IMF.RES:PCPS
- **Known limitations:** Monthly frequency; no granular product-level breakdown beyond top-line categories

## OECD Trade in Value Added (TiVA)

- **Dataset ID:** 16
- **Provider:** OECD / WTO
- **Category:** `supply_chain`
- **Authentication:** None
- **Rate limits:** None stated
- **Required keys:** None stated
- **Endpoint pattern:** `https://sdmx.oecd.org/public/rest/data/{AGENCY},{DATASET}/{FILTER}`
- **Python package:** `pandasdmx, OECD R package`
- **Expected response:** CSV, XLSX
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://www.oecd.org/en/data/datasets/trade-in-value-added.html
- **Known limitations:** Significant publication lag (3–4 years); 2020 is latest coverage; does not capture recent GVC restructuring

## OECD Inter-Country Input-Output (ICIO) Tables

- **Dataset ID:** 17
- **Provider:** OECD
- **Category:** `supply_chain`
- **Authentication:** None
- **Rate limits:** None stated
- **Required keys:** None stated
- **Endpoint pattern:** `https://sdmx.oecd.org/public/rest/data/{AGENCY},{DATASET}/{FILTER}`
- **Python package:** `pandasdmx, OECD R package`
- **Expected response:** CSV (zipped), XLSX
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html
- **Known limitations:** 3–4 year publication lag; Chinese and Mexican tables have special disaggregation requiring aggregation

## World Bank Logistics Performance Index (LPI 2.0)

- **Dataset ID:** 19
- **Provider:** World Bank
- **Category:** `logistics`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** CSV, Excel
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 1 week
- **Source URL:** https://lpi.worldbank.org
- **Known limitations:** Only biennial; 2025 methodology change breaks comparability with 2007–2023 series; subjective (survey-based edition)

## OECD Composite Leading Indicators (CLI)

- **Dataset ID:** 20
- **Provider:** OECD
- **Category:** `logistics`
- **Authentication:** None
- **Rate limits:** None stated
- **Required keys:** None stated
- **Endpoint pattern:** `https://sdmx.oecd.org/public/rest/data/{AGENCY},{DATASET}/{FILTER}`
- **Python package:** `pandasdmx, OECD R package`
- **Expected response:** CSV, XML, JSON
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data-explorer.oecd.org
- **Known limitations:** Not directly about logistics; useful for early-warning of demand-driven supply chain pressures

## US International Trade Administration (ITA) Trade Data

- **Dataset ID:** 21
- **Provider:** US International Trade Administration
- **Category:** `logistics`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** JSON, CSV
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 3–5 days (incl. key request)
- **Source URL:** https://www.trade.gov/data
- **Known limitations:** US-centric; limited to one reporter country

## IMF PortWatch

- **Dataset ID:** 22
- **Provider:** International Monetary Fund
- **Category:** `shipping`
- **Authentication:** None
- **Rate limits:** None stated
- **Required keys:** None stated
- **Endpoint pattern:** `GeoServices REST/WMS/WFS`
- **Python package:** `Manual CSV download`
- **Expected response:** CSV, GeoJSON, KML, PNG
- **Implementation difficulty:** Hard
- **Estimated implementation time:** 2–3 weeks (GIS plumbing)
- **Source URL:** https://portwatch.imf.org
- **Known limitations:** AIS signals can be spoofed or missed; dark shipping not captured; some ports have sparse signals

## UNCTAD Liner Shipping Connectivity Index (LSCI)

- **Dataset ID:** 23
- **Provider:** UNCTAD / MDS Transmodal
- **Category:** `shipping`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** CSV
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 1 week
- **Source URL:** https://unctadstat.unctad.org/datacentre/dataviewer/US.LSCI
- **Known limitations:** Does not capture port efficiency or inland logistics; index value not additive across countries

## Baltic Exchange Indices (via FRED)

- **Dataset ID:** 25
- **Provider:** Baltic Exchange / St. Louis Fed
- **Category:** `shipping`
- **Authentication:** Free API key
- **Rate limits:** 120 req/60s
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://api.stlouisfed.org/fred/series/observations?series_id={ID}&api_key={KEY}`
- **Python package:** `fredapi`
- **Expected response:** CSV, JSON, XML
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 3–5 days (incl. key request)
- **Source URL:** https://fred.stlouisfed.org
- **Known limitations:** Baltic Exchange primary data is proprietary and paid; FRED provides daily index only; route-specific rates require paid subscription

## UN Comtrade HS Chapter 85 (Electrical Machinery / Semiconductors)

- **Dataset ID:** 29
- **Provider:** UN Statistics Division
- **Category:** `semiconductors`
- **Authentication:** Free API key
- **Rate limits:** 500 calls/day (free)
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://comtradeapi.un.org/data/v1/get/...`
- **Python package:** `comtradeapicall`
- **Expected response:** CSV, JSON
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 3–5 days (incl. key request)
- **Source URL:** https://comtradeplus.un.org
- **Known limitations:** As per UN Comtrade limitations; country self-reporting inconsistencies for high-tech products

## EIA International Energy Statistics

- **Dataset ID:** 30
- **Provider:** US Energy Information Administration
- **Category:** `energy`
- **Authentication:** Free API key
- **Rate limits:** None stated
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://api.eia.gov/v2/{category}?api_key={KEY}`
- **Python package:** `eia-python`
- **Expected response:** CSV, Excel, JSON
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://www.eia.gov/international/data/world
- **Known limitations:** US-focused primary data; international data sourced from IEA/IEA for non-US countries with potential lags

## FRED — Federal Reserve Economic Data

- **Dataset ID:** 34
- **Provider:** Federal Reserve Bank of St. Louis
- **Category:** `financial`
- **Authentication:** Free API key
- **Rate limits:** 120 req/60s
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://api.stlouisfed.org/fred/series/observations?series_id={ID}&api_key={KEY}`
- **Python package:** `fredapi`
- **Expected response:** CSV, JSON, XML
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://fred.stlouisfed.org
- **Known limitations:** US-centric primary coverage; international series may be sourced from other providers with different update timing

## BIS Statistics — Banking, Debt, Derivatives

- **Dataset ID:** 35
- **Provider:** Bank for International Settlements
- **Category:** `financial`
- **Authentication:** None
- **Rate limits:** None
- **Required keys:** None stated
- **Endpoint pattern:** `https://data.bis.org/static/bulk/{DATASET}.zip`
- **Python package:** `BISdata (R)`
- **Expected response:** CSV, SDMX (bulk downloads)
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data.bis.org/bulkdownload
- **Known limitations:** Banking statistics based on reporting country data which may not capture offshore centers fully; some data confidential at bilateral level

## IMF International Financial Statistics (IFS)

- **Dataset ID:** 37
- **Provider:** International Monetary Fund
- **Category:** `financial`
- **Authentication:** None (no key)
- **Rate limits:** ~10 req/sec
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://dataservices.imf.org/REST/SDMX_JSON.svc/...`
- **Python package:** `imfp`
- **Expected response:** CSV, SDMX
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data.imf.org
- **Known limitations:** Monthly data may have 3–6 month lag for some countries; exchange rate data quality varies for countries with dual rates

## FRED — CPI and PCE Series

- **Dataset ID:** 38
- **Provider:** Federal Reserve Bank of St. Louis
- **Category:** `macroeconomics`
- **Authentication:** Free API key
- **Rate limits:** 120 req/60s
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://api.stlouisfed.org/fred/series/observations?series_id={ID}&api_key={KEY}`
- **Python package:** `fredapi`
- **Expected response:** CSV, JSON, XML
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 3–5 days (incl. key request)
- **Source URL:** https://fred.stlouisfed.org
- **Known limitations:** US headline series; international via FRED may have different methodologies than source countries

## OECD Consumer and Producer Price Indices

- **Dataset ID:** 39
- **Provider:** OECD
- **Category:** `macroeconomics`
- **Authentication:** None
- **Rate limits:** None stated
- **Required keys:** None stated
- **Endpoint pattern:** `https://sdmx.oecd.org/public/rest/data/{AGENCY},{DATASET}/{FILTER}`
- **Python package:** `pandasdmx, OECD R package`
- **Expected response:** CSV, XML, JSON
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data-explorer.oecd.org
- **Known limitations:** Methodology differences across countries despite harmonization efforts; limited sub-annual breakdown for smaller OECD members

## IMF World Economic Outlook — Inflation Forecasts

- **Dataset ID:** 40
- **Provider:** IMF
- **Category:** `macroeconomics`
- **Authentication:** None (no key)
- **Rate limits:** ~10 req/sec
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://dataservices.imf.org/REST/SDMX_JSON.svc/...`
- **Python package:** `imfp`
- **Expected response:** TSV/XLS, SDMX
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://www.imf.org/en/publications/sprolls/world-economic-outlook-databases
- **Known limitations:** Annual frequency only in WEO; some high-inflation country data reported as estimates

## FAO Food Price Index (FFPI)

- **Dataset ID:** 41
- **Provider:** UN Food and Agriculture Organization
- **Category:** `macroeconomics`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** CSV, Excel
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 1 week
- **Source URL:** https://www.fao.org/worldfoodsituation/foodpricesindex/en/
- **Known limitations:** Aggregate index only; no bilateral or country-specific breakdowns; commodity basket based on trade weights

## ACLED — Armed Conflict Location & Event Data

- **Dataset ID:** 43
- **Provider:** Armed Conflict Location & Event Data Project
- **Category:** `geopolitical`
- **Authentication:** Free key (registration)
- **Rate limits:** None stated
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://api.acleddata.com/acled/read?...`
- **Python package:** `acled.api (R)`
- **Expected response:** CSV, Excel, GeoJSON
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://acleddata.com
- **Known limitations:** Requires registration; may undercount events in low-media-coverage areas; event taxonomy can be contested

## GDELT — Global Database of Events, Language and Tone

- **Dataset ID:** 44
- **Provider:** GDELT Project (Leetaru & Schrodt)
- **Category:** `geopolitical`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** CSV (daily/quarterly bulk downloads)
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 1 week
- **Source URL:** http://data.gdeltproject.org/events/index.html
- **Known limitations:** Extremely large volume (terabytes); automated extraction may produce false positives; tone measurement not validated against ground truth

## GDELT Global Knowledge Graph (GKG)

- **Dataset ID:** 47
- **Provider:** GDELT Project
- **Category:** `news`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** CSV (15-min update files)
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 1 week
- **Source URL:** http://data.gdeltproject.org/gkg/index.html
- **Known limitations:** Very large data volume; text processing intensive; requires NLP pipeline to extract economic signal

## GDELT Stability Index (Instability Score)

- **Dataset ID:** 48
- **Provider:** GDELT Project
- **Category:** `news`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** CSV via API
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 1 week
- **Source URL:** https://api.gdeltproject.org/api/
- **Known limitations:** Scores derived from news media density — areas with poor media coverage underrepresented

## IMF WEO Historical Database

- **Dataset ID:** 49
- **Provider:** IMF
- **Category:** `historical_events`
- **Authentication:** None (no key)
- **Rate limits:** ~10 req/sec
- **Required keys:** Yes — register at provider
- **Endpoint pattern:** `https://dataservices.imf.org/REST/SDMX_JSON.svc/...`
- **Python package:** `imfp`
- **Expected response:** TSV (legacy), SDMX (new)
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://www.imf.org/en/publications/sprolls/world-economic-outlook-databases
- **Known limitations:** Download URL changes each release; must be scraped by vintage

## World Bank WDI — Historical Panel

- **Dataset ID:** 50
- **Provider:** World Bank
- **Category:** `historical_events`
- **Authentication:** None
- **Rate limits:** None
- **Required keys:** None stated
- **Endpoint pattern:** `https://api.worldbank.org/v2/country/{iso}/indicator/{code}`
- **Python package:** `wbgapi, wbdata`
- **Expected response:** CSV, Excel (bulk)
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data.worldbank.org
- **Known limitations:** See entry 9

## EM-DAT — International Disaster Database

- **Dataset ID:** 52
- **Provider:** Centre for Research on the Epidemiology of Disasters (CRED), Université Catholique de Louvain
- **Category:** `historical_events`
- **Authentication:** see source — not in quick reference
- **Rate limits:** see source — not in quick reference
- **Required keys:** None stated
- **Endpoint pattern:** `not in API quick reference — see download_url`
- **Python package:** `none documented`
- **Expected response:** CSV (free registration required)
- **Implementation difficulty:** Medium
- **Estimated implementation time:** 1 week
- **Source URL:** https://www.emdat.be
- **Known limitations:** Economic damage estimates incomplete and inconsistent across events; reporting heavily biased toward documented events

## World Bank — Air Transport Data (WDI)

- **Dataset ID:** 56
- **Provider:** World Bank / ICAO
- **Category:** `transportation`
- **Authentication:** None
- **Rate limits:** None
- **Required keys:** None stated
- **Endpoint pattern:** `https://api.worldbank.org/v2/country/{iso}/indicator/{code}`
- **Python package:** `wbgapi, wbdata`
- **Expected response:** CSV, Excel
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data.worldbank.org/indicator/IS.AIR.PSGR
- **Known limitations:** Annual only; no airline-specific or route-specific breakdown; ICAO data submission lags

## OECD Infrastructure Investment Statistics

- **Dataset ID:** 57
- **Provider:** OECD
- **Category:** `transportation`
- **Authentication:** None
- **Rate limits:** None stated
- **Required keys:** None stated
- **Endpoint pattern:** `https://sdmx.oecd.org/public/rest/data/{AGENCY},{DATASET}/{FILTER}`
- **Python package:** `pandasdmx, OECD R package`
- **Expected response:** CSV, XML
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://data-explorer.oecd.org
- **Known limitations:** OECD countries only; classification differences across countries; some gaps in capital stock data

## WITS — UNCTAD TRAINS Tariff & NTM Data

- **Dataset ID:** 62
- **Provider:** World Bank / UNCTAD
- **Category:** `supply_chain`
- **Authentication:** None
- **Rate limits:** None
- **Required keys:** None stated
- **Endpoint pattern:** `https://api.worldbank.org/v2/country/{iso}/indicator/{code}`
- **Python package:** `wbgapi, wbdata`
- **Expected response:** CSV (bulk via WITS)
- **Implementation difficulty:** Easy
- **Estimated implementation time:** 1–2 days
- **Source URL:** https://wits.worldbank.org/WITS/WITS/AdvanceQuery/RawTradeData/QueryDefinition.aspx
- **Known limitations:** NTM data very sparse; self-reported; not all countries submit to TRAINS regularly

## Unmatched entries in API Quick Reference

The following appear in the docx API quick-reference table but did not
match a dataset catalog name — record kept for audit:

| Dataset | Endpoint | Auth | Rate limit | Package |
|---|---|---|---|---|
| WTO Timeseries | `https://api.wto.org/timeseries/v1/...` | Free API key | Moderate | python-wto |
| EIA | `https://api.eia.gov/v2/{category}?api_key={KEY}` | Free API key | None stated | eia-python |
| BIS | `https://data.bis.org/static/bulk/{DATASET}.zip` | None | None | BISdata (R) |