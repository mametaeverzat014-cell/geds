# GEDS Historical Events — Data Audit

Generated from `backend/data/csv/historical_events_expanded.csv` (42 events).

Source document: `D:/GEDS-Historical-Economic-Disruption-Dataset-2000-2026.docx`
Extracted via: `backend/scripts/extract_events_from_docx.py`

## Missing-value counts

| Field | Missing |
|---|---|
| year_start | 1 |
| affected_countries | 7 |
| affected_sectors | 13 |
| gdp_impact_percent | 2 |
| trade_impact_percent | 22 |
| recovery_time_months | 41 |

## Graph coverage

- Event-derived rows mapped to a node IN the current GEDS graph: **39**
- Event-derived rows whose (country, sector) is NOT in the current GEDS graph: **618**

## Duplicates

Events sharing an identical name: **0**
- (none)

## Cross-reference events (no own data, point to another)

- Event 37: `2021 Evergrande Default (See Event 24 for full)`

## Low-confidence events (confidence ≤ 2)

- Event 34 (`2016 North Korea Nuclear Tests & Sanctions`) — confidence=2

## Scenario / forward-looking events (not historical observations)

- Event 41 (`2024–2025 Taiwan Strait Tensions & Semiconductor Risk`)

## Overlapping time windows

Pairs of events whose year ranges intersect: **59**
(showing only same-start or same-end overlaps to limit noise)

- Event 8 (`H1N1 Swine Flu Pandemic`) overlaps Event 29 (`Haiti Earthquake`)
- Event 9 (`European Sovereign Debt Crisis`) overlaps Event 10 (`Arab Spring Political Upheaval`)
- Event 9 (`European Sovereign Debt Crisis`) overlaps Event 13 (`Nepal Earthquake`)
- Event 9 (`European Sovereign Debt Crisis`) overlaps Event 29 (`Haiti Earthquake`)
- Event 10 (`Arab Spring Political Upheaval`) overlaps Event 29 (`Haiti Earthquake`)
- Event 12 (`Russia Crimea Annexation & Western Sanct`) overlaps Event 32 (`2014–2016 Oil Price Collapse`)
- Event 13 (`Nepal Earthquake`) overlaps Event 14 (`China Stock Market Crash`)
- Event 13 (`Nepal Earthquake`) overlaps Event 33 (`2015–2016 Global Trade Slowdown`)
- Event 14 (`China Stock Market Crash`) overlaps Event 32 (`2014–2016 Oil Price Collapse`)
- Event 14 (`China Stock Market Crash`) overlaps Event 33 (`2015–2016 Global Trade Slowdown`)
- Event 14 (`China Stock Market Crash`) overlaps Event 34 (`2016 North Korea Nuclear Tests & Sanctio`)
- Event 15 (`UK Brexit Referendum and Departure`) overlaps Event 16 (`US–China Trade War`)
- Event 15 (`UK Brexit Referendum and Departure`) overlaps Event 34 (`2016 North Korea Nuclear Tests & Sanctio`)
- Event 17 (`COVID-19 Global Pandemic`) overlaps Event 18 (`Global Semiconductor Chip Shortage`)
- Event 17 (`COVID-19 Global Pandemic`) overlaps Event 19 (`Ever Given Suez Canal Blockage`)
- Event 18 (`Global Semiconductor Chip Shortage`) overlaps Event 20 (`Post-COVID Global Supply Chain Disruptio`)
- Event 18 (`Global Semiconductor Chip Shortage`) overlaps Event 22 (`European Natural Gas & Energy Crisis`)
- Event 18 (`Global Semiconductor Chip Shortage`) overlaps Event 30 (`Global Food & Energy Crisis (Post-COVID `)
- Event 18 (`Global Semiconductor Chip Shortage`) overlaps Event 39 (`2022 Pakistan Economic Crisis & IMF Bail`)
- Event 18 (`Global Semiconductor Chip Shortage`) overlaps Event 40 (`2023 Israel-Gaza Conflict & MENA Economi`)
- Event 19 (`Ever Given Suez Canal Blockage`) overlaps Event 20 (`Post-COVID Global Supply Chain Disruptio`)
- Event 19 (`Ever Given Suez Canal Blockage`) overlaps Event 22 (`European Natural Gas & Energy Crisis`)
- Event 19 (`Ever Given Suez Canal Blockage`) overlaps Event 23 (`Post-COVID Global Inflation Surge & Cent`)
- Event 19 (`Ever Given Suez Canal Blockage`) overlaps Event 24 (`China Real Estate & Evergrande Crisis`)
- Event 20 (`Post-COVID Global Supply Chain Disruptio`) overlaps Event 22 (`European Natural Gas & Energy Crisis`)
- ... and 34 more

## Unmapped country names encountered

- (all countries mapped to ISO3)

## Unmapped sector terms encountered

- (all sectors mapped to taxonomy)

## Per-event parse notes (rounding, missing units, etc.)

- Event 1: infl[no_pct_unit_in_source]: 'Deflationary pressure in tech goods; CPI broadly stable'
- Event 3: expanded aggregate region terms: ['global via trade channels']
- Event 3: trade[range_midpoint]: "China's export growth slowed; ASEAN tourist arrivals fell 40–60%"
- Event 3: infl[no_pct_unit_in_source]: 'Modest deflationary pressure on services (travel, hospitality)'
- Event 4: expanded aggregate region terms: ['global via oil markets']
- Event 4: trade[no_pct_unit_in_source]: 'Oil trade routes disrupted; global oil prices roughly doubled 2003–2008'
- Event 4: infl[range_midpoint]: 'Global CPI elevated by ~0.5–1.0% annually attributable to oil channel'
- Event 4: market[no_pct_unit_in_source]: 'S&P 500 rose post-invasion on "rally"; oil-related equities surged; non-energy sectors pressured by cost inflation'
- Event 5: trade[no_pct_unit_in_source]: 'Regional fisheries exports disrupted; tourism earnings collapsed in affected areas for 1–2 years'
- Event 5: infl[no_pct_unit_in_source]: 'Food price increases locally; global impact minimal'
- Event 5: market[no_pct_unit_in_source]: 'Modest equity market reaction globally; affected country markets briefly fell'
- Event 6: trade[no_pct_unit_in_source]: 'US agricultural export disruptions; Port of New Orleans (5th largest US port) closed for weeks'
- Event 6: market[no_pct_unit_in_source]: 'Insurance sector equities fell; energy sector rose; S&P 500 broadly resilient'
- Event 7: expanded aggregate region terms: ['Global']
- Event 8: expanded aggregate region terms: ['Global']
- Event 8: infl[no_pct_unit_in_source]: 'Minimal direct inflation impact'
- Event 8: market[range_midpoint]: 'Airline and hospitality stocks fell 10–20% temporarily; markets quickly recovered'
- Event 9: expanded aggregate region terms: ['broader Eurozone']
- Event 9: trade[no_pct_unit_in_source]: 'Intra-EU trade compressed due to austerity and demand contraction'
- Event 9: infl[no_pct_unit_in_source]: 'Deflationary pressure in austerity countries; Greece CPI fell below zero 2013–2014'
- Event 9: market[range_midpoint]: 'Peripheral sovereign bond spreads spiked (Greek 10-year spread exceeded 3,500 bps over German Bund); European bank equities fell 40–70%'
- Event 10: expanded aggregate region terms: ['broader MENA region']
- Event 10: duration not parseable: 'Acute phase: 2011; ongoing instability: 2011–present in some countries'
- Event 10: trade[no_pct_unit_in_source]: 'Libya oil exports halted (~1.5 mb/d removed from market 2011); Egypt Suez Canal revenues briefly threatened'
- Event 10: infl[no_pct_unit_in_source]: 'Oil price spike fed into global food and energy inflation; MENA food import costs surged'
- Event 11: expanded aggregate region terms: ['EU', 'Southeast Asia']
- Event 11: trade[no_pct_unit_in_source]: 'Japanese auto exports fell sharply Q2 2011; semiconductor and electronics shipments disrupted'
- Event 11: infl[no_pct_unit_in_source]: 'Electricity costs surged in Japan; nuclear phase-out triggered energy import boom, contributing to Japan trade deficit'
- Event 12: expanded aggregate region terms: ['EU', 'Eastern Europe']
- Event 12: duration not parseable: 'Initial sanctions package: July 2014; ongoing with escalation in 2022'
- Event 12: trade[range_midpoint]: 'Russia food import ban reduced EU agricultural exports; Russian-EU goods trade fell ~20–30% 2014–2015'
- Event 13: infl[no_numeric_found]: 'Construction material prices surged locally; remittance inflows (large % of GDP) partially cushioned shock'
- Event 14: expanded aggregate region terms: ['global via risk sentiment', 'commodity demand']
- Event 14: infl[no_pct_unit_in_source]: 'Commodity price deflation globally; China CPI broadly stable'
- Event 15: expanded aggregate region terms: ['European Union']
- Event 15: gdp[range_midpoint]: 'By 2025, Brexit reduced UK GDP per capita by 6–8%[52][53][^54]; investment reduced 12–18%; employment 3–4% lower; immediate 2016–2018 impact ~−2.1% of UK GDP level from uncertainty channel[^55]'
- Event 15: infl[range_midpoint]: 'GBP fell ~10–15% post-referendum, feeding into import price inflation'
- Event 16: duration not parseable: 'March 2018 – January 2020 (Phase 1 deal); tariffs remained post-deal'
- Event 16: infl[range_midpoint]: 'US consumer prices elevated by estimated 0.3–0.5%; tariff pass-through to consumers: 80–100%[^60]'
- Event 17: expanded aggregate region terms: ['Global']
- Event 17: duration not parseable: 'Acute economic shock: Q1–Q2 2020; recovery: 2021; long COVID effects ongoing'
- Event 17: infl[no_numeric_found]: 'Deflationary 2020; then explosive inflation surge 2021–2022 as demand recovered vs. supply constraints'
- Event 18: gdp[currency_only_no_pct]: 'US economy lost estimated ~$240 billion in 2021[^70]; global automotive revenue loss ~$210 million USD in 2021[^71]; >11 million vehicles removed from global production 2021[^71]; S&P Global Mobility estimates 9.5 million light vehicles lost in 2021[^69]'
- Event 18: trade[no_pct_unit_in_source]: 'Automotive exports fell globally; semiconductor trade flows shifted toward consumer electronics'
- Event 18: market[no_pct_unit_in_source]: 'Automotive equities fell; semiconductor equipment and fab stocks surged; TSMC market cap doubled 2020–2021'
- Event 19: expanded aggregate region terms: ['Global']
- Event 19: infl[no_numeric_found]: 'Minor marginal inflation pressure; primarily absorbed by shipping companies'
- Event 19: market[no_numeric_found]: 'Maersk and shipping equities spiked on freight rate expectations; oil price briefly rose'
- Event 20: expanded aggregate region terms: ['Global']
- Event 20: infl[range_midpoint]: 'Supply chain shocks were dominant driver of euro area core inflation in 2022[^79]; contributed 2–3 percentage points to global headline inflation'
- Event 20: market[range_midpoint]: 'Shipping stocks (Maersk, ZIM, Hapag-Lloyd) rose 400–700%; semiconductor equipment firms surged; retail and consumer goods stocks volatile'
- Event 21: expanded aggregate region terms: ['EU', 'Global']
- Event 21: duration not parseable: 'Ongoing (as of 2026)'
- Event 22: expanded aggregate region terms: ['EU27']
- Event 22: market[currency_only_no_pct]: 'European natural gas futures (TTF) spiked above €340/MWh in August 2022; energy stocks surged; industrial stocks fell; EUR/USD fell below parity'
- Event 23: expanded aggregate region terms: ['Global', 'most severely: USA', 'EU', 'emerging markets with USD-denominated debt']
- Event 23: trade[no_pct_unit_in_source]: 'Global trade volumes grew but at below-trend rate; trade disruptions from rate hikes reduced EM import capacity'
- Event 24: expanded aggregate region terms: ['commodity exporters via demand channel']
- Event 24: duration not parseable: '2021–ongoing; property market in 4th year of downturn as of 2025[^102]'
- Event 24: gdp[range_midpoint]: 'Real estate sector = ~25–30% of China GDP at peak[103][101]; new residential property sales halved over 4 years[^102]; total Evergrande net losses: $81 billion for 2021–2022 combined[^101]; new home prices fell 3.2% YoY in June 2024 (steepest in 9 years)'
- Event 24: trade[no_pct_unit_in_source]: 'Chinese steel and iron ore imports fell; Australian commodity exports to China impacted; Chinese construction materials trade contracted'
- Event 24: infl[no_pct_unit_in_source]: 'Deflationary pressure in China (real estate prices falling); producer price deflation transmitted globally via lower Chinese export prices'
- Event 25: duration not parseable: 'Acute default: April–May 2022; IMF program: 2023–ongoing'
- Event 25: market[range_midpoint]: 'Sovereign bonds fell 70–90% on secondary market; credit rating collapsed to selective default (SD) by Fitch, S&P'
- Event 26: expanded aggregate region terms: ['Global', 'most affected: EU', 'East Africa']
- Event 26: infl[no_pct_unit_in_source]: 'Contributed to re-acceleration of European goods inflation early 2024; Maersk CEO warned of "considerable implications for global growth"[^113]; developing countries in East Africa and Red Sea region faced worsened food security'
- Event 26: market[no_numeric_found]: 'Container shipping stocks surged; Middle East equities fell; oil prices temporarily elevated'
- Event 27: infl[no_pct_unit_in_source]: 'Marginal upward pressure on US and Asian consumer goods prices; LNG prices in Asia temporarily elevated'
- Event 27: market[no_numeric_found]: 'Shipping equities benefited; LNG tanker rates spiked; agricultural commodity prices elevated'
- Event 28: expanded aggregate region terms: ['EU']
- Event 28: duration not parseable: 'Ongoing (as of May 2026)'
- Event 28: infl[range_midpoint]: 'Tariff pass-through 80–100%[^60]; US consumer prices elevated; Fed constrained from cutting rates; BBC: 4 ways trade war changed global economy[^120]'
- Event 29: expanded aggregate region terms: ['regional aid economy']
- Event 29: trade[no_pct_unit_in_source]: 'Export capacity nearly eliminated; Port-au-Prince port severely damaged; trade dependency on aid increased dramatically'
- Event 29: infl[no_pct_unit_in_source]: 'Reconstruction demand triggered local food and material price surges'
- Event 29: market[no_numeric_found]: 'Not applicable (no significant financial markets in Haiti); aid flows from multilateral institutions surged'
- Event 30: expanded aggregate region terms: ['Sub-Saharan Africa', 'South Asia', 'Latin America', 'global']
- Event 30: trade[no_pct_unit_in_source]: 'World food trade prices hit record highs (FAO Food Price Index: 159.7 in March 2022); fertilizer prices doubled/tripled'
- Event 30: market[no_pct_unit_in_source]: 'Frontier market sovereign bonds collapsed; Pakistan, Ghana, Ethiopia, Zambia in debt distress; IMF emergency lending surged'
- Event 31: gdp[range_midpoint]: 'EM currencies fell 10–20%; growth slowed 1–2% in fragile-five economies'
- Event 33: expanded aggregate region terms: ['Global']
- Event 35: expanded aggregate region terms: ['Caribbean islands']
- Event 35: trade[no_pct_unit_in_source]: 'Caribbean logistics disrupted; US agricultural exports temporarily curtailed'
- Event 38: expanded aggregate region terms: ['EU']
- Event 38: gdp[range_midpoint]: 'Accelerated European energy crisis; Germany permanently lost ~€15 billion/year in gas supply infrastructure; added 1–2 pp to European energy cost trajectory'
- Event 40: expanded aggregate region terms: ['regional MENA']
- Event 40: trade[no_pct_unit_in_source]: 'Suez Canal disruption (see Event 26); Egypt Suez revenues collapsed'
- Event 41: expanded aggregate region terms: ['EU']
- Event 42: expanded aggregate region terms: ['EU', 'Middle East']