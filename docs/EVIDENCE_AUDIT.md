# GEDS Evidence Audit (peer-reviewed ingestion)

Source: hand-transcribed from user-supplied peer-reviewed evidence table.
Output: `backend/data/csv/event_evidence_registry.csv`

**Note:** this REPLACES the prior `EVIDENCE_AUDIT.md` (which audited the
auto-mined evidence with looser criteria). The auto-mined evidence remains
in `event_evidence.csv`; this audit governs the manual peer-reviewed pass.

## 1. Events with direct peer-reviewed support

**7** of 7 events ingested this pass have ≥1 paper with
confidence ≥4 that provides a quantitative GDP / trade / inflation estimate.

## 2. Events with GDP estimates

**5** of 7 events have a non-NULL GDP estimate from at least one paper.

## 3. Events with trade estimates

**5** of 7 events have a non-NULL trade estimate.

## 4. Events with uncertainty ranges

**4** of 7 events have an explicit uncertainty band (lower or upper bound).

## 5. Coverage gaps

Per-event metrics where ALL ingested papers return NULL:

| Event ID | Event | Missing metric |
|---|---|---|
| 17 | COVID-19 Global Pandemic | `inflation_impact_pct` |
| 17 | COVID-19 Global Pandemic | `market_impact_pct` |
| 7 | Global Financial Crisis | `inflation_impact_pct` |
| 7 | Global Financial Crisis | `market_impact_pct` |
| 11 | Tōhoku Earthquake, Tsunami & Fukushima Nuclear Cri | `inflation_impact_pct` |
| 11 | Tōhoku Earthquake, Tsunami & Fukushima Nuclear Cri | `market_impact_pct` |
| 19 | Ever Given Suez Canal Blockage | `gdp_impact_pct` |
| 19 | Ever Given Suez Canal Blockage | `inflation_impact_pct` |
| 19 | Ever Given Suez Canal Blockage | `market_impact_pct` |
| 21 | Russia Invasion of Ukraine & Global Sanctions | `trade_impact_pct` |
| 21 | Russia Invasion of Ukraine & Global Sanctions | `inflation_impact_pct` |
| 21 | Russia Invasion of Ukraine & Global Sanctions | `market_impact_pct` |
| 18 | Global Semiconductor Chip Shortage | `gdp_impact_pct` |
| 18 | Global Semiconductor Chip Shortage | `trade_impact_pct` |
| 18 | Global Semiconductor Chip Shortage | `market_impact_pct` |
| 22 | European Natural Gas & Energy Crisis | `market_impact_pct` |

Interpretation: NULL ≠ 'no impact'. NULL = the cited peer-reviewed papers
in this pass did not provide a quantitative value for that metric. Other
literature may; that work was not in the user-supplied table.

## 6. Top missing papers (events with weak quantitative anchors)

Events where market-impact or inflation estimates rely on indirect work:

- Event 17 (COVID-19 Global Pandemic): no direct `inflation_impact_pct` in cited papers
- Event 17 (COVID-19 Global Pandemic): no direct `market_impact_pct` in cited papers
- Event 7 (Global Financial Crisis): no direct `inflation_impact_pct` in cited papers
- Event 7 (Global Financial Crisis): no direct `market_impact_pct` in cited papers
- Event 11 (Tōhoku Earthquake, Tsunami & Fukushima Nuclear Cri): no direct `inflation_impact_pct` in cited papers
- Event 11 (Tōhoku Earthquake, Tsunami & Fukushima Nuclear Cri): no direct `market_impact_pct` in cited papers
- Event 19 (Ever Given Suez Canal Blockage): no direct `gdp_impact_pct` in cited papers
- Event 19 (Ever Given Suez Canal Blockage): no direct `inflation_impact_pct` in cited papers
- Event 19 (Ever Given Suez Canal Blockage): no direct `market_impact_pct` in cited papers
- Event 21 (Russia Invasion of Ukraine & Global Sanctions): no direct `trade_impact_pct` in cited papers
- Event 21 (Russia Invasion of Ukraine & Global Sanctions): no direct `inflation_impact_pct` in cited papers
- Event 21 (Russia Invasion of Ukraine & Global Sanctions): no direct `market_impact_pct` in cited papers
- Event 18 (Global Semiconductor Chip Shortage): no direct `gdp_impact_pct` in cited papers
- Event 18 (Global Semiconductor Chip Shortage): no direct `trade_impact_pct` in cited papers
- Event 18 (Global Semiconductor Chip Shortage): no direct `market_impact_pct` in cited papers

## 7. Top unsupported events (not in this evidence pass)

35 events in `master_event_registry.csv` have **no peer-reviewed
evidence ingested in this pass**. These remain backed only by their original
docx aggregate values (confidence ≤ 4) and any auto-mined paper rows from
`event_evidence.csv` (which used heuristic regex matching, not curated DOIs).

- Event 1: Dot-com Bubble Collapse & US Recession
- Event 2: Argentine Sovereign Default & Currency Crisis
- Event 3: SARS Epidemic
- Event 4: Iraq War & Associated Oil Price Spike
- Event 5: Indian Ocean Earthquake and Tsunami
- Event 6: Hurricane Katrina & Rita
- Event 8: H1N1 Swine Flu Pandemic
- Event 9: European Sovereign Debt Crisis
- Event 10: Arab Spring Political Upheaval
- Event 12: Russia Crimea Annexation & Western Sanctions
- Event 13: Nepal Earthquake
- Event 14: China Stock Market Crash
- Event 15: UK Brexit Referendum and Departure
- Event 16: US–China Trade War
- Event 20: Post-COVID Global Supply Chain Disruption
- Event 23: Post-COVID Global Inflation Surge & Central Bank Tightening
- Event 24: China Real Estate & Evergrande Crisis
- Event 25: Sri Lanka Sovereign Default & Economic Collapse
- Event 26: Red Sea Houthi Attacks / Shipping Crisis
- Event 27: Panama Canal Drought & Traffic Restrictions
- Event 28: Trump 2025 "Liberation Day" Tariffs & Trade War
- Event 29: Haiti Earthquake
- Event 30: Global Food & Energy Crisis (Post-COVID / Ukraine)
- Event 31: 2013 "Taper Tantrum" EM Currency Crisis
- Event 32: 2014–2016 Oil Price Collapse
- ... and 10 more

## 8. Confidence histogram

| Confidence | # rows | Interpretation |
|---|---|---|
| 5 | 4 | peer-reviewed paper with direct quantitative estimates |
| 4 | 6 | IMF/OECD/BIS working paper with quantitative estimates |
| 3 | 3 | official report but indirect estimate |
| 2 | 0 | secondary source |
| 1 | 0 | speculative |
| total | 13 | |

## 9. Event → paper network

- Event 7 (Global Financial Crisis) → ['P-IMF-WEFS-2014-Ch7', 'P-CEPR-Baldwin-2009', 'P-OECD-2009-Reform']
- Event 11 (Tōhoku Earthquake, Tsunami & Fukushima Nuclear Cri) → ['P-Inoue-Todo-2016', 'P-Carvalho-QJE']
- Event 17 (COVID-19 Global Pandemic) → ['P-EAP-2023', 'P-ANU-GCubed-2023']
- Event 18 (Global Semiconductor Chip Shortage) → ['P-IMF-WP-22-061-Shipping']
- Event 19 (Ever Given Suez Canal Blockage) → ['P-Hummels-Schaur-AER-2013']
- Event 21 (Russia Invasion of Ukraine & Global Sanctions) → ['P-IMF-WP-24-039', 'P-IMF-FD-2022']
- Event 22 (European Natural Gas & Energy Crisis) → ['P-IMF-WP-24-027-EnergyResilience', 'P-SUERF-Energy-2022']

## Phase 4 graph-mapping summary

| Event | Sectors | Countries | Mapped nodes | Mapping status |
|---|---|---|---|---|
| 7. Global Financial Crisis | construction;durable_manufacturing;energ | EUR;GBR;JPN;USA | 0 | UNCERTAIN |
| 11. Tōhoku Earthquake, Tsunami & F | automotive;electronics | JPN | 2 | OK |
| 17. COVID-19 Global Pandemic | consumption;contact-intensive;government |  | 0 | UNCERTAIN |
| 18. Global Semiconductor Chip Shor | automotive;consumer_electronics;ict;indu | CHN;DEU;JPN;KOR;MEX;TWN;USA | 13 | PARTIAL |
| 19. Ever Given Suez Canal Blockage | bulk_commodities;container_shipping;jit_ |  | 0 | UNCERTAIN |
| 21. Russia Invasion of Ukraine & G | agriculture;agriculture_(grains;energy;f | RUS;SSA;UKR | 0 | UNCERTAIN |
| 22. European Natural Gas & Energy  | basic_metals;ceramics;chemicals;energy;e | AUT;CEE;DEU;ITA | 0 | UNCERTAIN |

## Honest interpretation

- This pass ingested **7 events** with **13 distinct papers**.
- 7 events qualify for 'direct quantitative support' under the rubric.
- The other 35 events in `master_event_registry.csv` remain backed only by
  docx aggregates + auto-mined rows. They should not be cited as having
  peer-reviewed corroboration until a future pass adds it.
- Suez/Ever Given anchors on Hummels & Schaur AER 2013, which is a general
  delay-cost framework, not a Suez-specific paper. The trade-impact figure
  is the framework's per-day cost range applied to Suez ~6.5-day blockage.
  Use with that caveat.
- Semiconductor shortage anchors only on IMF WP/22/61 shipping-cost paper
  which does NOT isolate the chip channel. The 0.7pp inflation figure is
  for a doubling of shipping costs broadly, not specifically chips.
