# GEDS Validation Data Audit

Inputs:
- `historical_events_expanded.csv` (42 events)
- `validation_targets_expanded.csv` (94 rows)
- `papers_catalog.csv` (25 papers)

## Duplicate events

Events sharing a name: **0**
- (none)

## Conflicting values across sources

Same (event, country) reported with disagreeing GDP numbers across
event-aggregate and paper-derived sources: **3**

- Event 9 GRC: values [-26.0, -6.0]; sources: ['docx event 9 GDP Impact field (from_freetext)', 'docx event 9 GDP Impact field (from_freetext)']
- Event 11 JPN: values [-0.9, -0.47]; sources: ['docx event 11 aggregate (no country-specific values in source)', 'Paper 2: Carvalho, Nirei, Saito, Tahbaz-Salehi (2021). "Supply Chain Disruptions']
- Event 21 RUS: values [14.0, -3.9]; sources: ['docx event 21 GDP Impact field (from_freetext)', 'docx event 21 GDP Impact field (from_freetext)']

## Impossible / suspect values

Magnitude > 100% in fields other than market_impact_percent: **1**

Note: source text frequently expresses 'X% of GDP' for cumulative damage
(e.g. Haiti earthquake = 120% of pre-shock GDP), which is mathematically
valid but visually suspect. These rows are kept in the catalog but
flagged here for human review.

- Event 29 (Haiti Earthquake): `gdp_impact_percent` = 120.0

## Missing values per field

| Field | Missing | % |
|---|---|---|
| recovery_time_months | 41 | 97.6% |
| inflation_impact_percent | 27 | 64.3% |
| trade_impact_percent | 22 | 52.4% |
| market_impact_percent | 22 | 52.4% |
| duration_months | 20 | 47.6% |
| affected_sectors | 13 | 31.0% |
| affected_countries | 7 | 16.7% |
| gdp_impact_percent | 2 | 4.8% |
| year_start | 1 | 2.4% |
| event_type | 1 | 2.4% |
| confidence | 1 | 2.4% |

## Source inconsistencies — observed across docx sources

1. **Event 4 (Iraq War & oil spike)** GDP Impact text describes both
   `~−0.5% per year` (the impact channel) and `~$275 billion cumulative`
   (a stock measure). These are non-comparable; parser keeps the % value.
2. **Event 7 (Global Financial Crisis)** quotes both `−1.3%` (global GDP)
   and country-specific figures (`US −2.5%`, `DEU −5.6%`). All preserved
   in `validation_targets_expanded.csv` as separate rows.
3. **Event 27 (Panama Canal drought)** `73%` appears as 'US share of
   canal traffic' but the parser reads it into `gdp_impact_percent`.
   Audit-flag — should be reviewed manually.

## Weak-evidence flags

Papers with self-declared limitations include:

- Paper 6 (Allen, Gale, 2000, rel=8): Three-region stylized model; no empirical application; abstracts from asset price dynamics and fire sales
- Paper 10 (Gabaix, 2011, rel=8): US-centric; firm-level data quality dependent on Compustat coverage; macro identification challenges
- Paper 19 (Coquidé, Lages, Shepelyansky, 2020, rel=8): Stylized bankruptcy model; no price or financial mechanisms; no agent heterogeneity
- Paper 21 (di Giovanni, Levchenko, 2012, rel=8): Abstracting from financial channels; firm data incomplete for many developing countries; model abstracts from services trade
- Paper 22 (Eaton, Kortum, 2002, rel=8): 19 OECD countries only; no intermediate goods; no services; assumes balanced trade
- Paper 23 (Caliendo, Parro, Rossi-Hansberg, Sarte, 2018, rel=8): US only; annual frequency; no financial frictions; labor mobility is simplified

## Note on file naming

The historical-events audit is at `docs/DATA_AUDIT.md`; the dataset-
registry audit is at `docs/DATA_AUDIT_DATASETS.md`. This validation-
specific audit is `docs/VALIDATION_DATA_AUDIT.md` to avoid clobbering.
