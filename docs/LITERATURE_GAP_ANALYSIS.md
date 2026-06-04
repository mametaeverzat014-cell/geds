# GEDS Literature Gap Analysis
*Evidence-based gap mapping — GEDS v2 — 2026-05-27*

---

## 1. What Existing Literature Has Solved

### Supply Chain Propagation
- **Network amplification**: Acemoglu et al. (2012, Econometrica, DOI:10.3982/ECTA9623) proved sector-level shocks propagate via input-output linkages and generate aggregate fluctuations.
- **Upstream amplification**: Barrot & Sauvagnat (2016, QJE, DOI:10.1093/qje/qjw018) documented -5 pp sales for hit firms; -2 pp for direct customers; both upstream and downstream confirmed.
- **Tohoku multiplier 3-4x**: Carvalho et al. (2021, QJE, DOI:10.1093/qje/qjab010) — indirect effects amplify total losses 3-4x beyond direct damage; automotive recovery ~12 months.
- **Near-perfect input complementarity**: Boehm et al. (2019, REStat, DOI:10.1162/rest_a_00750) — elasticity of US affiliate output to Japanese parent disruption ≈ -1 in automotive/electronics.
- **Nonlinear cascade threshold**: MIT 2025 working paper — small shocks barely amplify; large shocks trigger cascading relationship dissolution.

### Bullwhip Effect
- **Foundational theory solid**: Lee et al. (1997, Management Science, DOI:10.1287/mnsc.43.4.546) — four causes; variance ratio formula analytically derived.
- **Robust replication**: Wang & Disney 2016 review; confirmed across industries.

### Hysteresis
- **Permanent output losses all recessions**: Cerra & Saxena (2008, AER) and Cerra, Fatas, Saxena (2020, IMF WP, DOI:10.5089/9781513537559.001).
- **Investment slump mechanism**: IMF WP/2021/170 (DOI:10.5089/9781513537559.001).
- **War hysteresis**: IMF WP/24/039 (DOI:10.5089/9798400229206.001) — ~1.5% GDP below no-war baseline at 5 years.

### Chokepoints
- **Systemic risk quantified**: Verschuur et al. (2025, Nature Communications, DOI:10.1038/s41467-025-65403-w) — $192B trade at risk/year; $14B economic losses/year; Taiwan Strait + Suez dominate.
- **TSMC concentration**: TrendForce data — 69.9% foundry share 2025.

### Financial Contagion
- **Extreme value framework**: IMF Book Ch.21 — logit model for cross-bank spillover; home bias documented.
- **Eurozone bilateral spillover**: ECB WP1558 + WP1666 (DOI:10.2866/55530) — Belgium/Italy/Spain central in contagion network.

---

## 2. What Remains Unsolved

### 2.1 SEIRS Re-Susceptibility Rate (xi) for Economic Networks
- No peer-reviewed paper empirically estimates xi for supply chain firms.
- GEDS SEIRS model cannot be calibrated without xi; risk of spurious results.
- Closest: DRPRESS 2024 (SEIR theoretical simulation); Nature 2021 (coupled model).

### 2.2 Heterogeneous Sector Recovery Dynamics
- Recovery duration varies: automotive ~12 months post-Tohoku; financial 3-5 years post-GFC; government potentially permanent.
- No unified cross-sector empirical recovery rate taxonomy exists in published literature.

### 2.3 Multi-Hazard Chokepoint Co-occurrence
- Verschuur et al. 2025 note co-occurrence limits rerouting options but quantitative joint probability distributions do not yet exist.
- GEDS cannot model simultaneous Suez + Hormuz + Malacca without fabricating co-occurrence parameters.

### 2.4 Supply Chain Re-entry After Disruption
- How quickly do new supplier-customer relationships form post-disruption?
- No peer-reviewed empirical study with quantified relationship formation rates found.

### 2.5 Healthcare-to-Economy Feedback Calibration
- Nature 2021 provides a model but no country-specific or GEDS-sector-compatible parameters.

---

## 3. Common Weaknesses in Existing Literature

1. **Stylized networks vs. real supply chain data**: Most propagation models use IO matrices rather than firm-level data.
2. **Event-specific calibration problem**: Tohoku parameters (automotive/electronics Japan) may not transfer to Red Sea shipping (consumer goods, Europe-Asia).
3. **Endogeneity**: Countries with better institutions both experience fewer disruptions AND recover faster.
4. **Attribution in compound events**: COVID + semiconductor shortage + inflation shock occurred simultaneously; clean isolation impossible.
5. **Conflict data quality**: North Korea, Libya, Venezuela, Ukraine GDP data gaps; satellite proxies carry high uncertainty.

---

## 4. Contradictions Between Papers

| Topic | Paper A | Paper B | Tension |
|---|---|---|---|
| SARS GDP impact | Contemporary models: catastrophic global impact | Lee et al. 2008 Health Policy: far smaller than projections | Contemporary macro models substantially overestimated SARS |
| Hysteresis in non-financial recessions | Cerra & Saxena 2020: ALL recessions cause permanent losses | Some DSGE/RBC literature: cycles are trend-stationary | Ongoing methodological dispute; unit root vs trend-stationary |
| Trade war global GDP impact | IMF Blog 2019: relatively modest | BIS WP 1316 2025: -0.3 to -0.6% GDP | Different metrics: aggregate GDP vs welfare; different horizons |
| Tohoku recovery timeline | Boehm et al. 2019: 2-4 quarters | Carvalho et al. 2021: ~12 months automotive | Different measurement scope: firm-level vs sector-level |

---

## 5. Gaps GEDS Can Target

### 5.1 Cross-Event Validation Platform
No published platform validates the same shock propagation model across 20+ heterogeneous events simultaneously. If R² improves with OECD ICIO calibration, this is a genuine empirical contribution.

### 5.2 Chokepoint + Network GDP Propagation
Verschuur et al. 2025 quantifies systemic chokepoint risk. GEDS can extend by modeling downstream GDP and sector-level consequences across 595 nodes — a potential extension of the Nature paper.

### 5.3 SEIR Threshold Calibration for Economic Networks
DRPRESS 2024 + Nature 2021 provide theoretical structure. GEDS could contribute an empirically calibrated R0 estimate for economic network risk propagation — a confirmed gap in the literature.

### 5.4 Multi-Mechanism Interaction Modeling
No published paper models SEIRS + Bullwhip + Hysteresis simultaneously as complementary propagation layers in a single network model. This is GEDS's primary potential novelty contribution.

---

## 6. Missing Datasets for GEDS Calibration

| Dataset | Status | Why Needed |
|---|---|---|
| OECD ICIO 2018 sector weights | Not ingested | Replace heuristic edge weights |
| WIOD 2016 input-output tables | Not ingested | Alternative; more country coverage |
| World Bank LPI sector lead times | Not ingested | Calibrate bullwhip amplification |
| IMF PortWatch API (real-time) | Not connected | Live chokepoint disruption detection |
| ECB WP1666 bilateral spillover coefficients | Not structured | Financial contagion edge weights |
| ACLED / GDELT geopolitical risk indices | Not connected | Shock trigger detection |

---

## 7. Unexplored Directions

1. **Climate change → chokepoint disruption frequency**: Panama Canal 2023 is documented case. No model integrates IPCC climate scenarios with chokepoint closure probability distributions.
2. **Cyber / undersea cable disruption**: Not modeled in any published economic network paper found in search.
3. **AI chip concentration risk**: TSMC 69.9% creates concentration not modeled in economic shock literature before 2024.
4. **Simultaneous multi-chokepoint scenarios**: Verschuur et al. 2025 identifies co-occurrence risk but does not model full simultaneous closure GDP impact.
5. **Geopolitical decoupling as permanent shock**: US-China tech decoupling is a long-duration structural shock not captured by existing short-run propagation models.
