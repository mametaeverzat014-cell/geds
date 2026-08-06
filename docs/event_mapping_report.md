# GEDS Benchmark V4 — Phase 1: Event Mapping & Audit Report

> **SCOPE WARNING (added 2026-08 during repository audit).** This document
> describes the **archived V4 benchmark line** (N=21/22/28 on a 1204-node
> OECD+WIOD graph, targets named `target_gdp`), *not* the N=27 corpus in
> `app/data/seed_data.HISTORICAL_EVENTS` that every published number in
> `docs/PAPER.ru.md` and `docs/RESULTS.md` comes from.
>
> In particular, the target definition asserted below — `auto_production_loss_pct
> = |published GDP %| / 100`, "a single-country national output-loss fraction" —
> **does not describe the live corpus.** The live targets are global
> industry-level output-loss fractions attributable to the event (e.g.
> covid-semiconductor-2020-2021 = 0.115, a global vehicle-production loss, not a
> national GDP figure). Reading this file as documentation of the current
> benchmark will misidentify what the models are scored against.
>
> Kept unedited below because the adjudication of 90 expansion candidates is a
> real, reusable negative result: it is the audit that established the corpus
> could not be grown past ~22 from that candidate pool. Superseded as a
> definition of the target; still valid as a record of that search.

**Mission:** STRICT RESEARCH MISSION — GEDS BENCHMARK V4. Rules enforced verbatim: *never fabricate data; never create synthetic benchmark targets; preserve NULL when mapping is impossible; every benchmark event must have provenance; if confidence is low, mark UNMAPPABLE instead of guessing.*

**Generated:** read-only audit of `event_expansion_candidates.csv` (90 candidates, via `v4_preaudit.json`) + `benchmark_event_matrix_v3.csv` (42 existing events).

**Input note:** `EVENT_EXPANSION_REPORT.md` and `event_expansion_candidates.csv` were provided and audited. **`RECOMMENDED_BENCHMARK_CORPUS.md` does not exist** in the repository or the provided attachments — no recommended-corpus file was available to cross-check against, so the audit relies solely on the candidate CSV and the cited per-event sources.

## Adjudication method (the decisive test)

The benchmark target is `observed.auto_production_loss_pct = |published GDP %| / 100` — i.e. a **single-country national output-loss fraction** for the most-impacted economy. A candidate is only MAPPED if its source provides a figure of *that exact type*. The following figure-types are **NOT comparable** and force PARTIAL/UNMAPPABLE:

- damages or losses expressed as a share of GDP (a stock/asset figure, not an output drop);
- debt-to-GDP or deficit-to-GDP ratios;
- GDP **growth-rate deltas** (change in the growth rate, not the level drop);
- capital-flow / current-account swings expressed as % of GDP;
- sub-national, regional, or city-level figures;
- sector-specific losses (not the national aggregate);
- multi-country aggregates that are not decomposable to a single comparable economy.

A candidate is **UNMAPPABLE** when it (a) duplicates an event already in the registry, (b) reports only money or physical units (no GDP %), or (c) reports a GDP % of a non-comparable figure-type. It is **PARTIAL** when a plausibly-comparable figure exists but its type is ambiguous or must be reconstructed from a source the candidate row does not itself cite. It is **MAPPED** only with a clean, single-country national-output figure from the cited source.

## Summary of the 90 expansion candidates

| Metric | Count |
|---|---|
| Total expansion candidates | 90 |
| Carry a GDP **keyword** in the impact description | 49 |
| Carry an actual extracted **GDP % phrase** | 22 |
| Money / physical units only (no GDP %) | 37 |
| Flagged as **duplicate** of an existing registry event | 35 |
| Source confidence High / Medium / Low | 60 / 15 / 15 |

| **Mapping verdict** | **Count** |
|---|---|
| **MAPPED** (clean national-output target, engine-eligible) | **1** |
| **PARTIAL** (ambiguous/reconstructed; sensitivity-only) | **2** |
| **UNMAPPABLE** (duplicate / no-GDP% / wrong figure-type) | **87** |

**Net-new engine-eligible events: 1 MAPPED (Mexico) + 2 PARTIAL (Turkey + Asian-crisis aggregate → 5 per-country sensitivity events).** The corpus expands from **21 → 22** (primary) or **→ 28** (maximally generous), **not** to the 80–90 implied by the raw candidate count.

## Full audit — 90 expansion candidates

| # | Event | Year | ISO3 | Sector(s) | Benchmark target source / reason | Conf. | Status |
|---|---|---|---|---|---|---|---|
| 1 | 1990 Iraqi Invasion of Kuwait Oil Price Shock | 1990 | IRQ,KWT | banking,consumer_goods,en… | GDP% present but wrong figure-type: 'GNP by 0.25 percent' | High | UNMAPPABLE |
| 2 | 1992 European Exchange Rate Mechanism (Black … | 1992 | DEU,ESP,FRA,GBR,ITA | banking | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 3 | 1995 Kobe Earthquake (Great Hanshin Earthquak… | 1995 | JPN | aerospace,consumer_goods,… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 4 | 1999 Turkey Izmit (Kocaeli) Earthquake | 1999 | TUR | agriculture,banking,consu… | OECD 1999 Turkish earthquake report: '5 percent drop in GDP' (also '3 p… | High | PARTIAL |
| 5 | 1997 Asian Financial Crisis | 1997 | IDN,KOR,MYS,PHL,THA | banking,consumer_goods,ut… | World Bank GEP 1998-99 country output-contraction tables → target=per-c… | High | PARTIAL |
| 6 | 2000–2001 California Electricity Crisis | 2000 | USA | consumer_goods,energy,uti… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 7 | 1994 Mexican Peso Crisis (Tequila Crisis) | 1994 | MEX | banking,consumer_goods,go… | World Bank projected 1995 Mexico GDP decline -4.8% (IMF hist. vol. c10.… | High | MAPPED |
| 8 | 2001 September 11 Attacks Aviation and Insura… | 2001 | USA | aerospace,banking,shipping | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 9 | 1998 Russian Financial Crisis and Ruble Defau… | 1998 | RUS | banking,consumer_goods,go… | — duplicate of existing benchmark event (LIKELY_DUP::v3='russia crimea … | Low | UNMAPPABLE |
| 10 | Dot-com bubble burst | 2000 | USA | electronics,telecommunica… | — duplicate of existing benchmark event (LIKELY_DUP::v3='dot-com bubble… | High | UNMAPPABLE |
| 11 | 2003 SARS outbreak | 2002 | CHN,SGP,TWN | aerospace,consumer_goods,… | — duplicate of existing benchmark event (LIKELY_DUP::v3='sars epidemic') | High | UNMAPPABLE |
| 12 | 2003 Northeast Blackout | 2003 | CAN,USA | consumer_goods,shipping,u… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 13 | 2002 West Coast port lockout (ILWU-PMA) | 2002 | — | agriculture,consumer_good… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 14 | 2006 Russia-Ukraine Gas Dispute Supply Cutoff | 2006 | DEU,FRA,HUN,ITA,POL,R… | consumer_goods,energy,shi… | — duplicate of existing benchmark event (LIKELY_DUP::v3='russia crimea … | High | UNMAPPABLE |
| 15 | 2009 Eurozone Sovereign Debt Crisis (Greece) … | 2009 | GRC | banking,government | — duplicate of existing benchmark event (LIKELY_DUP::v3='european sover… | Medi | UNMAPPABLE |
| 16 | 2001 Argentine economic crisis and sovereign … | 2001 | ARG | banking,consumer_goods,go… | — duplicate of existing benchmark event (LIKELY_DUP::v3='argentine sove… | High | UNMAPPABLE |
| 17 | 2007 U.S. subprime mortgage crisis onset | 2007 | USA | banking,electronics,utili… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 18 | 2008 Global Financial Crisis (Lehman Brothers… | 2008 | DEU,FRA,GBR,HUN,ISL,J… | banking,electronics | — duplicate of existing benchmark event (LIKELY_DUP::v3='global financi… | High | UNMAPPABLE |
| 19 | 1999 Taiwan Chi-Chi Earthquake Semiconductor … | 1999 | TWN | consumer_goods,electronics | — duplicate of existing benchmark event (LIKELY_DUP::v3='global semicon… | Low | UNMAPPABLE |
| 20 | 2010 Deepwater Horizon Oil Spill | 2010 | USA | agriculture,consumer_good… | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | High | UNMAPPABLE |
| 21 | 2004 Indian Ocean Tsunami (Boxing Day Tsunami) | 2004 | BGD,IDN,IND,KEN,LKA,M… | agriculture,banking,shipp… | — duplicate of existing benchmark event (LIKELY_DUP::v3='indian ocean e… | High | UNMAPPABLE |
| 22 | 2005 Hurricane Katrina Gulf Coast Energy and … | 2005 | — | electronics,energy,shippi… | — duplicate of existing benchmark event (LIKELY_DUP::v3='hurricane katr… | High | UNMAPPABLE |
| 23 | 2011 Fukushima nuclear disaster supply chain … | 2011 | JPN | automotive,consumer_goods… | — duplicate of existing benchmark event (LIKELY_DUP::v3='tōhoku earthqu… | Medi | UNMAPPABLE |
| 24 | 2011 Thailand floods | 2011 | THA | agriculture,automotive,co… | GDP% present but wrong figure-type: '12.6% of GDP' | High | UNMAPPABLE |
| 25 | 2014 Russia Annexation of Crimea Sanctions | 2014 | RUS,UKR,USA | agriculture,banking,energ… | — duplicate of existing benchmark event (LIKELY_DUP::v3='russia crimea … | High | UNMAPPABLE |
| 26 | 2014-2016 Oil Price Collapse | 2014 | USA | banking,consumer_goods,en… | — duplicate of existing benchmark event (LIKELY_DUP::v3='2014–2016 oil … | Medi | UNMAPPABLE |
| 27 | 2011 Tōhoku earthquake and tsunami | 2011 | JPN | automotive,consumer_goods… | — duplicate of existing benchmark event (LIKELY_DUP::v3='tōhoku earthqu… | Low | UNMAPPABLE |
| 28 | 2010 Eyjafjallajökull Iceland volcanic ash av… | 2010 | BEL,DEU,ESP,FRA,GBR,I… | aerospace,shipping,tourism | — no GDP%-of-output figure (money/physical units only) | Low | UNMAPPABLE |
| 29 | 2013 United States federal government shutdown | 2013 | USA | government,tourism | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | High | UNMAPPABLE |
| 30 | 2012 Hurricane Sandy (Superstorm Sandy) | 2012 | JAM,PRI | banking,consumer_goods,el… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 31 | 2011 Libyan civil war oil supply disruption | 2011 | LBY | electronics,energy | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Low | UNMAPPABLE |
| 32 | 2015 Tianjin Port explosions | 2015 | CHN | automotive,banking,consum… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 33 | 2015 Volkswagen Dieselgate emissions scandal | 2015 | DEU,USA | automotive | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | High | UNMAPPABLE |
| 34 | Hurricane Harvey Texas petrochemical disrupti… | 2017 | USA | consumer_goods,electronic… | — no GDP%-of-output figure (money/physical units only) | Medi | UNMAPPABLE |
| 35 | 2016 Brexit Referendum Market Shock | 2016 | CAN,GBR,USA,ZAF | banking,electronics | — duplicate of existing benchmark event (LIKELY_DUP::v3='uk brexit refe… | Low | UNMAPPABLE |
| 36 | 2017 Hurricane Maria Puerto Rico | 2017 | PRI | agriculture,consumer_good… | GDP% present but wrong figure-type: '60 percent of Puerto Rico’s GDP' | High | UNMAPPABLE |
| 37 | 2016 Hanjin Shipping bankruptcy | 2016 | CHN,JPN,KOR,USA | consumer_goods,electronic… | — no GDP%-of-output figure (money/physical units only) | Medi | UNMAPPABLE |
| 38 | 2015 China stock market crash | 2015 | CHN | banking,electronics | — duplicate of existing benchmark event (LIKELY_DUP::v3='china stock ma… | High | UNMAPPABLE |
| 39 | 2017 WannaCry and NotPetya cyberattacks (Maer… | 2017 | DEU,GBR,UKR,USA | banking,consumer_goods,el… | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Medi | UNMAPPABLE |
| 40 | 2014–2016 West Africa Ebola outbreak | 2014 | — | agriculture,shipping,tour… | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | High | UNMAPPABLE |
| 41 | 2018 U.S.-China trade war tariffs | 2018 | CHN,USA | agriculture,automotive,co… | — duplicate of existing benchmark event (LIKELY_DUP::v3='us–china trade… | Medi | UNMAPPABLE |
| 42 | 2020 Beirut Port Explosion | 2020 | LBN | consumer_goods,electronic… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 43 | 2019 U.S.-China trade war escalation | 2019 | CHN,USA | agriculture,consumer_good… | — duplicate of existing benchmark event (LIKELY_DUP::v3='us–china trade… | Low | UNMAPPABLE |
| 44 | 2019 Saudi Aramco Abqaiq Drone Attack Oil Dis… | 2019 | SAU | energy | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Medi | UNMAPPABLE |
| 45 | 2020 Oil Price Crash and Negative WTI | 2020 | USA | banking,energy,shipping | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | High | UNMAPPABLE |
| 46 | 2018 Turkish currency and debt crisis | 2018 | — | banking,consumer_goods,go… | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Low | UNMAPPABLE |
| 47 | 2021 Colonial Pipeline ransomware attack | 2021 | USA | consumer_goods,energy,shi… | — no GDP%-of-output figure (money/physical units only) | Medi | UNMAPPABLE |
| 48 | Boeing 737 MAX Grounding | 2019 | CHN,USA | aerospace,consumer_goods | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Medi | UNMAPPABLE |
| 49 | COVID-19 Pandemic Global Lockdowns | 2020 | — | banking,consumer_goods,el… | — duplicate of existing benchmark event (LIKELY_DUP::v3='covid-19 globa… | High | UNMAPPABLE |
| 50 | 2021 Suez Canal Ever Given blockage | 2021 | EGY,IND,USA | consumer_goods,electronic… | — duplicate of existing benchmark event (LIKELY_DUP::v3='ever given sue… | High | UNMAPPABLE |
| 51 | 2021 Global Energy Crisis (Natural Gas Price … | 2021 | DEU,ESP,GBR,ITA,NLD | consumer_goods,energy,shi… | — duplicate of existing benchmark event (LIKELY_DUP::v3='european natur… | Medi | UNMAPPABLE |
| 52 | 2022 China Zero-COVID Shanghai Lockdown | 2022 | CHN | automotive,banking,consum… | — duplicate of existing benchmark event (LIKELY_DUP::v3='covid-19 globa… | High | UNMAPPABLE |
| 53 | 2022 European Energy Crisis (Gas Supply Cutof… | 2022 | — | banking,consumer_goods,en… | — duplicate of existing benchmark event (LIKELY_DUP::v3='european natur… | High | UNMAPPABLE |
| 54 | 2022 Russian invasion of Ukraine and sanctions | 2022 | RUS,UKR | agriculture,banking,elect… | — duplicate of existing benchmark event (LIKELY_DUP::v3='russia crimea … | High | UNMAPPABLE |
| 55 | 2021 Global Semiconductor Chip Shortage | 2021 | DEU,JPN,KOR,TWN,USA | automotive,electronics | — duplicate of existing benchmark event (LIKELY_DUP::v3='global semicon… | High | UNMAPPABLE |
| 56 | 2022 Nord Stream pipeline sabotage | 2022 | DEU | consumer_goods,electronic… | — duplicate of existing benchmark event (LIKELY_DUP::v3='2022 russia ga… | Medi | UNMAPPABLE |
| 57 | 2021 Texas Winter Storm Uri Power Crisis | 2021 | USA | agriculture,energy,utilit… | GDP% present but wrong figure-type: 'GDP loss: oil and gas extraction 1… | High | UNMAPPABLE |
| 58 | 2022 UK gilt market crisis (mini-budget) | 2022 | GBR | banking,electronics,gover… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 59 | 2021 China Evergrande Debt Crisis | 2021 | CHN,HKG | banking,consumer_goods,ut… | — duplicate of existing benchmark event (LIKELY_DUP::v3='china real est… | Medi | UNMAPPABLE |
| 60 | 2023 Panama Canal drought shipping restrictio… | 2023 | PAN | electronics,shipping | — duplicate of existing benchmark event (LIKELY_DUP::v3='panama canal d… | High | UNMAPPABLE |
| 61 | 2023 Turkey–Syria earthquakes | 2023 | SYR | agriculture,consumer_good… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 62 | Silicon Valley Bank collapse | 2023 | USA | banking,electronics | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | High | UNMAPPABLE |
| 63 | 2023 Credit Suisse Collapse and UBS Takeover | 2023 | CHE | banking | GDP% present but wrong figure-type: '20% of Swiss GDP' | High | UNMAPPABLE |
| 64 | 2024 Baltimore Key Bridge Collapse Port Closu… | 2024 | USA | electronics,shipping | GDP% present but wrong figure-type: '13% of Maryland’s GDP' | High | UNMAPPABLE |
| 65 | 2024 Noto Peninsula Earthquake | 2024 | JPN | agriculture,consumer_good… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 66 | 2022 Global Food Price Crisis (Grain Export D… | 2022 | RUS,UKR | agriculture,electronics,s… | — duplicate of existing benchmark event (LIKELY_DUP::v3='global food & … | High | UNMAPPABLE |
| 67 | 2024 Hualien earthquake | 2024 | TWN | electronics,shipping,tour… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 68 | 2023 US Debt Ceiling Standoff | 2023 | USA | banking,electronics | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Low | UNMAPPABLE |
| 69 | 2025 U.S. Reciprocal Tariff Policy | 2025 | CAN,CHN,JPN,KOR,MEX,T… | agriculture,automotive,co… | — duplicate of existing benchmark event (LIKELY_DUP::v3='trump 2025 "li… | Low | UNMAPPABLE |
| 70 | 1996 Mad Cow Disease (BSE) UK Beef Crisis | 1996 | GBR | agriculture,shipping | GDP% present but wrong figure-type: 'GDP growth was 2.4%' | Low | UNMAPPABLE |
| 71 | Sri Lanka economic crisis and sovereign debt … | 2022 | LKA | agriculture,banking,consu… | — duplicate of existing benchmark event (LIKELY_DUP::v3='sri lanka sove… | High | UNMAPPABLE |
| 72 | 1991 Soviet Union Dissolution Economic Collap… | 1991 | RUS,UKR | agriculture,banking,energ… | GDP% present but wrong figure-type: 'GDP declines of -46.7%' | High | UNMAPPABLE |
| 73 | 1993 World Trade Center bombing | 1993 | USA | banking,government,shippi… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 74 | 2024 CrowdStrike Global IT Outage | 2024 | AUS,CAN,GBR,USA | aerospace,banking,consume… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 75 | Hurricane Rita | 2005 | USA | energy,utilities | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 76 | 2008 Wenchuan earthquake | 2008 | CHN | banking,consumer_goods,go… | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | High | UNMAPPABLE |
| 77 | 2011 United States debt-ceiling crisis and St… | 2011 | USA | banking,electronics,gover… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 78 | 2010 Greece First Bailout Sovereign Debt Cris… | 2010 | GRC | banking,government | — duplicate of existing benchmark event (LIKELY_DUP::v3='european sover… | High | UNMAPPABLE |
| 79 | 2024 Red Sea Houthi Shipping Attacks | 2023 | EGY,ISR,JOR,SAU,YEM | banking,electronics,energ… | — duplicate of existing benchmark event (LIKELY_DUP::v3='red sea houthi… | Medi | UNMAPPABLE |
| 80 | 2012 U.S. Midwest drought (corn and soybean c… | 2012 | USA | agriculture,energy | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | High | UNMAPPABLE |
| 81 | 2019 California PG&E Public Safety Power Shut… | 2019 | USA | consumer_goods,electronic… | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Low | UNMAPPABLE |
| 82 | 2014 Ukraine Conflict Donbas Economic Disrupt… | 2014 | UKR | agriculture,banking,consu… | — duplicate of existing benchmark event (LIKELY_DUP::v3='russia invasio… | High | UNMAPPABLE |
| 83 | 2023 Maui wildfires | 2023 | USA | shipping,tourism,utilities | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 84 | 2018 Camp Fire | 2018 | USA | banking,consumer_goods,go… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 85 | Hurricane Helene and Hurricane Milton (U.S. S… | 2024 | USA | agriculture,banking,consu… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |
| 86 | 2013 Cyprus Banking Crisis and Bail-in | 2013 | CYP | banking,electronics,touri… | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Low | UNMAPPABLE |
| 87 | 2002 Argentine peso devaluation and corralito… | 2001 | ARG | banking,electronics | — duplicate of existing benchmark event (LIKELY_DUP::v3='argentine sove… | Low | UNMAPPABLE |
| 88 | 2021 Brazil drought energy and crop crisis | 2021 | BRA | agriculture,electronics,u… | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Low | UNMAPPABLE |
| 89 | 2020 Australia Black Summer Bushfires | 2019 | AUS | agriculture,banking,touri… | GDP% present but wrong figure-type: 'GDP keyword w/o usable % figure' | Medi | UNMAPPABLE |
| 90 | 2016 Fort McMurray Wildfire (Horse River wild… | 2016 | CAN | banking,energy,shipping,u… | — no GDP%-of-output figure (money/physical units only) | High | UNMAPPABLE |

## The 7 candidates with a usable target (detail)

Only these carry a figure that survives the adjudication test. Provenance is quoted from the cited candidate source; no target is invented.

| idx | Event | ISO3 | Target | Status | Provenance & caveat |
|---|---|---|---|---|---|
| 7 | 1994 Mexican Peso Crisis (Tequila… | MEX | 0.048 | MAPPED | World Bank projected 1995 Mexico GDP declin…. Single-country national-output figure. CAVEAT: this is the WB *projection*; realized 1995 contraction was steeper (~-6%) but that figure is not in th… |
| 4 | 1999 Turkey Izmit (Kocaeli) Earth… | TUR | ~0.05 | PARTIAL | OECD 1999 Turkish earthquake report: '5 per…. Figure-type ambiguous: the report mixes a damage-as-%GDP figure (3%) with a short-run output figure (5%); not an unambiguous annual national-output d… |
| 5 | 1997 Asian Financial Crisis | IDN,KOR,MYS,PHL,THA | per-country 0.005-0.15 (Korea 0.07 · Thailand 0.07 · Malaysia 0.05 · Indonesia 0.15 · Philippines 0.005) | PARTIAL | World Bank GEP 1998-99 country output-contr…. ONE aggregate candidate row spanning IDN/KOR/MYS/PHL/THA. Per-country targets are approximate, drawn from WB GEP country tables (NOT from this row's … |

**Primary corpus (V4-primary, N=22)** = 21 existing engine-eligible events + Mexico only. **Generous sensitivity corpus (V4-max, N=28)** additionally includes Turkey and the five Asian-crisis per-country events. The PARTIAL events are deliberately quarantined so the primary scientific claim rests only on clean provenance.

## Carried-forward existing benchmark events (42 in registry; 21 engine-eligible)

These are unchanged from the prior mission's audited matrix (`benchmark_event_matrix_v3.csv`). 'Engine-eligible' = has a non-null target AND its country:sector seed node exists on the spectrally-normalised OECD+WIOD graph (1204 nodes). The 21 eligible events are the N=21 evaluation corpus.

| event_id | Event | Countries | target_gdp | v3 status | Engine-eligible |
|---|---|---|---|---|---|
| 1 | Dot-com Bubble Collapse & US Recession | USA;DEU;JPN;KOR;GBR… | 0.04800 | OK | YES |
| 2 | Argentine Sovereign Default & Currency … | ARG;BRA;URY;BOL | 0.11000 | OK | YES |
| 3 | SARS Epidemic | CHN;HKG;TWN;SGP;CAN | 0.02600 | OK | YES |
| 4 | Iraq War & Associated Oil Price Spike | USA;IRQ | -0.00500 | OK | YES |
| 5 | Indian Ocean Earthquake and Tsunami | IDN;LKA;IND;THA;MDV… | 0.15000 | OK | YES |
| 6 | Hurricane Katrina & Rita | USA | 0.03100 | OK | YES |
| 7 | Global Financial Crisis |  | -0.00300 | UNMAPPED | no |
| 8 | H1N1 Swine Flu Pandemic |  | -0.00500 | UNMAPPED | no |
| 9 | European Sovereign Debt Crisis | GRC;PRT;IRL;ESP;CYP… | -0.26000 | OK | YES |
| 10 | Arab Spring Political Upheaval | TUN;EGY;LBY;YEM;SYR… | 0.50000 | OK | YES |
| 11 | Tōhoku Earthquake, Tsunami & Fukushima … | JPN;USA;DEU;FRA;ITA… | -0.00350 | OK | YES |
| 12 | Russia Crimea Annexation & Western Sanc… | RUS;UKR;DEU;FRA;ITA… | -0.02200 | OK | YES |
| 13 | Nepal Earthquake | NPL | 0.33000 | OK | no |
| 14 | China Stock Market Crash | CHN | 0.06900 | OK | YES |
| 15 | UK Brexit Referendum and Departure | GBR;DEU;FRA;ITA;ESP… | 0.07000 | OK | YES |
| 16 | US–China Trade War | USA;CHN;VNM;MEX;KOR… | 0.02600 | OK | YES |
| 17 | COVID-19 Global Pandemic |  | -0.03000 | UNMAPPED | no |
| 18 | Global Semiconductor Chip Shortage | USA;DEU;JPN;KOR;TWN… | NULL | NO_TARGET | no |
| 19 | Ever Given Suez Canal Blockage |  | -0.00200 | UNMAPPED | no |
| 20 | Post-COVID Global Supply Chain Disrupti… |  | 0.00200 | UNMAPPED | no |
| 21 | Russia Invasion of Ukraine & Global San… | UKR;RUS;DEU;FRA;ITA… | -0.01500 | OK | YES |
| 22 | European Natural Gas & Energy Crisis | DEU;FRA;ITA;ESP;NLD… | -0.00700 | OK | YES |
| 23 | Post-COVID Global Inflation Surge & Cen… | GBR;DEU;FRA;ITA;ESP… | 0.01400 | OK | YES |
| 24 | China Real Estate & Evergrande Crisis | CHN | 0.27500 | OK | YES |
| 25 | Sri Lanka Sovereign Default & Economic … | LKA | 0.08700 | OK | no |
| 26 | Red Sea Houthi Attacks / Shipping Crisis | EGY;KEN;ETH;TZA;UGA… | 0.50000 | OK | YES |
| 27 | Panama Canal Drought & Traffic Restrict… | USA;CHN;JPN;KOR;PAN | 0.73000 | OK | YES |
| 28 | Trump 2025 "Liberation Day" Tariffs & T… | USA;CHN;DEU;FRA;ITA… | -0.01400 | OK | YES |
| 29 | Haiti Earthquake | HTI | 1.20000 | UNMAPPED | no |
| 30 | Global Food & Energy Crisis (Post-COVID… | NGA;ZAF;KEN;ETH;AGO… | 0.60000 | OK | YES |
| 31 | 2013 "Taper Tantrum" EM Currency Crisis | BRA;IND;IDN;ZAF;TUR | 0.15000 | UNMAPPED | no |
| 32 | 2014–2016 Oil Price Collapse | SAU;RUS;NGA;VEN;CAN | -0.03700 | UNMAPPED | no |
| 33 | 2015–2016 Global Trade Slowdown |  | 0.02600 | UNMAPPED | no |
| 34 | 2016 North Korea Nuclear Tests & Sancti… | PRK;KOR;CHN | -0.04100 | UNMAPPED | no |
| 35 | 2017 Hurricane Season (Harvey, Irma, Ma… | USA;PRI;DOM;HTI;JAM… | -0.14000 | UNMAPPED | no |
| 36 | 2019 Hong Kong Protests | HKG | -0.02900 | UNMAPPED | no |
| 37 | 2021 Evergrande Default (See Event 24 f… |  | NULL | UNMAPPED | no |
| 38 | 2022 Russia Gas Nord Stream Pipeline Sa… | DEU;FRA;ITA;ESP;NLD… | 0.01500 | UNMAPPED | no |
| 39 | 2022 Pakistan Economic Crisis & IMF Bai… | PAK | 0.00200 | UNMAPPED | no |
| 40 | 2023 Israel-Gaza Conflict & MENA Econom… | ISR;PSE;JOR;LBN;EGY… | 0.01200 | UNMAPPED | no |
| 41 | 2024–2025 Taiwan Strait Tensions & Semi… | TWN;USA;KOR;JPN;DEU… | -0.02800 | SCENARIO | no |
| 42 | 2025–2026 Middle East Energy Shock | DEU;FRA;ITA;ESP;NLD… | 0.03000 | UNMAPPED | no |

## Net result

1. **The 90 expansion candidates do not yield an N≈80–90 benchmark.** After removing 35 duplicates of existing registry events and 37 candidates that report only money/physical units, the remainder either repeat existing events or report non-comparable GDP figure-types (damages-as-%GDP, debt ratios, growth deltas, regional/sector figures).
2. **Exactly one** candidate (1994 Mexican Peso Crisis) provides a clean, single-country national-output target with cited provenance and an existing graph node → **MAPPED**.
3. **Six** further candidate-events (Turkey Izmit; Asian Financial Crisis × 5 countries) have plausibly-comparable but ambiguous/reconstructed figures → **PARTIAL**, used only in the generous sensitivity corpus.
4. **The engine-eligible benchmark therefore expands from 21 to at most 22 (primary) or 28 (maximally generous).** Phases 2–5 are executed on exactly these sets.

_No synthetic targets were created. NULL/UNMAPPABLE was preserved wherever a comparable national-output figure could not be sourced._
