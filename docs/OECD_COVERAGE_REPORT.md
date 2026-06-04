# OECD ICIO Coverage Report

**Generated:** 2026-05-28 from `country_sector_presence_real.csv` (OECD-derived) compared to `country_sector_presence.csv` (heuristic).

## Headline numbers

| Metric | Heuristic graph | OECD ICIO (real) | Δ |
|---|---|---|---|
| Countries | 59 | **81** | +22 |
| Countries gained | — | 37 | — |
| Countries lost (heuristic-only) | — | 15 | — |
| (country, sector) `present` rows | 587 | **1,134** | **+547 (1.93×)** |
| Cells that intersect | — | 411 | — |
| Cells in OECD only | — | **723** | — |
| Cells in heuristic only | — | 176 | — |
| `MISSING_OECD_HAS_NO_SOURCE` rows | — | 405 | — |

The OECD graph **doubles** the evidence-backed coverage of (country, sector) pairs and adds 37 countries.

## Countries gained (37)

`AGO, AUT, BGR, BLR, BRN, CHL, CIV, CMR, COL, CRI, CYP, CZE, DNK, EST, FIN, HRV, HUN, ISL, JOR, KAZ, KGZ, KHM, LAO, LTU, LUX, LVA, MAR, MLT, MMR-already-heur, MUS, NZL, NOR-already, PER, ROU, SEN, SVK, SVN, SWE, TUN`

(plus `ROW` — Rest of World aggregate)

## Countries LOST (heuristic-only, 15)

`ETH, IRN, IRQ, KEN, LBN, LBY, LKA, MDV, NPL, PRK, PSE, QAT, SYR, VEN, YEM`

**This list matters for GEDS events.** These 15 countries drive several historical events:
- Sri Lanka 2022 default (LKA)
- Iran/Iraq sanctions and oil (IRN, IRQ)
- Yemen / Houthi disruption (YEM)
- Venezuela hyperinflation (VEN)
- Syria / Lebanon (SYR, LBN)
- North Korea sanctions (PRK)
- Russia-Ukraine cascade via Qatar gas (QAT)

OECD ICIO does NOT cover these economies. Switching to OECD-only graph would **lose 15 country nodes** that GEDS currently uses for events.

## Per-sector coverage comparison (countries with `DATA_PRESENT`)

| GEDS Sector | OECD | Heuristic | OECD source notes |
|---|---|---|---|
| agriculture | **81** | 59 | OECD A01+A02+A03 (clean) |
| automotive | **81** | 18 | OECD C29 (clean) |
| electronics | **81** | 14 | OECD C26+C27 (bundles semis in C26) |
| aerospace | **81** | 12 | OECD C302T309 (bundles rail/military) |
| shipping | **81** | 15 | OECD H49+H50 (land+sea combined) |
| aviation | **81** | 19 | OECD H51 (clean) |
| ports | **81** | 17 | OECD H52 (warehousing as proxy) |
| telecommunications | **81** | 59 | OECD J58T60+J61+J62_63 |
| utilities | **81** | 59 | OECD D+E |
| oil | **81** | 14 | OECD B06+C19 (bundles gas in B06) |
| banking | **81** | 59 | OECD K (bundles insurance + capital_markets) |
| consumer_goods | **81** | 59 | OECD C10–C28 aggregate (broad) |
| government | **81** | 59 | OECD O+P (bundles education) |
| tourism | **81** | 59 | OECD I (clean) |
| **semiconductors** | **0** | 11 | NULL — bundled in OECD C26 |
| **gas** | **0** | 11 | NULL — bundled in OECD B06 (with oil) |
| **insurance** | **0** | 14 | NULL — bundled in OECD K (with banking) |
| **capital_markets** | **0** | 13 | NULL — bundled in OECD K |
| **energy** (composite) | **0** | 16 | NULL — synthesise from oil+gas+utilities if needed |

**5 of 19 GEDS sectors have NO OECD evidence.** These remain heuristic. The 4 individual ones (semis/gas/insurance/capital_markets) are structurally absent from OECD ICIO because of its aggregation scheme; the 5th (`energy`) is a composite synonym.

## OECD-only coverage matrix per country (sample)

Showing 5 GDP-rich countries × the 14 OECD-mapped GEDS sectors:

| Country | Mapped sectors | Top sectors by gdp_share |
|---|---|---|
| USA | 14 / 14 | banking (financial+insurance combined), government, consumer_goods |
| CHN | 14 / 14 | consumer_goods (large mfg), oil, utilities |
| DEU | 14 / 14 | automotive, consumer_goods, banking |
| JPN | 14 / 14 | electronics, automotive, banking |
| FRA | 14 / 14 | tourism, banking, consumer_goods |

Per-country sector value-added shares are in `country_sector_presence_real.csv`. Every cell traces to a specific OECD ISIC code aggregation.

## Percentage of graph now evidence-backed

| Layer | Heuristic graph | OECD-backed graph |
|---|---|---|
| Country×sector cells with evidence | 0% | **74%** (1134 / 1539) |
| GEDS sectors with ≥1 evidence cell | 0% | 74% (14 / 19) |
| Countries with ≥1 evidence cell | 0% | 100% of OECD's 81 |

**74% of the OECD presence CSV is now backed by real OECD data.** The remaining 26% are the 5 sectors (semis/gas/insurance/capital_markets/energy) that OECD ICIO does not separate.

## Honest caveats

1. **Country coverage is not the same set** — 22 countries gained (good) but 15 lost (bad). Switching to OECD-only would lose events tied to lost countries (LKA default, IRN sanctions, YEM Houthi attacks, etc.). A hybrid policy (use OECD where available, fall back to heuristic for the 15) is recommended for Phase 5 graph integration.
2. **Sector aggregation is lossy.** Mapping OECD's 45 industries to GEDS's 19 sectors involves bundling (e.g. shipping = land + water + warehousing). The schema audit documents every bundle decision.
3. **No employment data.** WIOD is still absent; `employment_share` stays NULL in all 1539 rows.
4. **One-year snapshot.** Coverage analysis uses 2022 (latest year). For sensitivity, the parser stored all 7 years (2016-2022) in `oecd_country_sector_weights.csv`. Year choice affects which sectors look "dominant" but not the binary present/absent question.
5. **OECD ICIO is in current-USD millions.** No deflation applied. Shares (gdp_share, trade_share) are unaffected; absolute USD comparisons across years require deflation.

## Provenance

Source: `backend/data/csv/oecd_country_sector_weights.csv` (28,350 rows from real OECD ICIO 2016-2022).
Output: `backend/data/csv/country_sector_presence_real.csv` (1,539 rows; 1,134 with OECD data; 405 NULL).
Parser: `backend/scripts/ingestion/ingest_oecd_icio.py`.
Schema audit: `docs/OECD_ICIO_SCHEMA_AUDIT.md`.
