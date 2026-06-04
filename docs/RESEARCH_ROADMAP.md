# GEDS Research Roadmap
*Evidence-based opportunities — GEDS v2 — 2026-05-27*

---

## Immediate Opportunities (0-4 weeks)

### R.1 Ingest OECD ICIO 2018 to Fix Edge Weights
- **Source**: OECD Inter-Country Input-Output Tables 2018 (65 countries x 45 sectors). Download: stats.oecd.org/Index.aspx?DataSetCode=ICIO2018
- **Action**: Map 45 OECD sectors to GEDS 19-sector taxonomy; replace heuristic edge weights with Leontief technical coefficients.
- **Expected impact**: Root cause of R² = -0.566; calibrated IO weights should substantially improve fit.
- **Evidence basis**: Acemoglu et al. 2012 (Econometrica); Carvalho et al. 2021 (QJE).

### R.2 Replace SEIRS with SEIR or Document xi as NULL
- **Action**: (a) Remove re-susceptibility (xi=0) since no empirical calibration exists, OR (b) Keep SEIRS but document xi as unknown assumption with sensitivity analysis.
- **Evidence basis**: No peer-reviewed paper empirically estimates xi for supply chains — literature search exhaustive.

### R.3 Calibrate Bullwhip Amplification Using Lee et al. 1997 Formula
- **Action**: Use Var(orders)/Var(demand) = 1 + 2*alpha*L + 2*alpha^2*L^2 where L = sector lead time from World Bank LPI; alpha = smoothing parameter.
- **Evidence basis**: Lee, Padmanabhan, Whang (1997) Management Science DOI:10.1287/mnsc.43.4.546.

### R.4 Source Hysteresis Parameters from IMF
- **Action**: Persistent output loss = 1-2% per recession; financial crisis: 1.5-4%; war: 1.5% at 5-year horizon.
- **Evidence basis**: Cerra Fatas Saxena 2020; Cerra Saxena 2008 AER; IMF WP/24/039.

---

## Short-Term Opportunities (1-3 months)

### R.5 Ingest Real-Time Chokepoint Data via IMF PortWatch API
- **Source**: IMF PortWatch (portwatch.imf.org) — daily satellite vessel tracking.
- **Action**: Connect GEDS shock detection module to PortWatch; auto-flag disruptions exceeding threshold.
- **Evidence basis**: IMF Blog Nov 2023; Verschuur et al. 2025 Nature Comms.

### R.6 Integrate ECB WP1666 Bilateral Spillover Coefficients
- **Source**: ECB Working Paper 1666 — bilateral spillover matrix: Belgium/France/Germany/Greece/Ireland/Italy/Netherlands/Portugal/Spain.
- **Action**: Replace finance sector heuristic propagation with ECB bilateral coefficients.

### R.7 Healthcare Node Calibration from Nature 2021
- **Source**: Nature Scientific Reports DOI:10.1038/s41598-021-94619-1.
- **Action**: Parameterize healthcare to economy feedback; calibrate using IMF COVID sectoral output data.

### R.8 Validate All 23 Benchmarked Events
- **Action**: For each event, document primary source for benchmark GDP impact; flag low-confidence benchmarks; upgrade using missing_event_mapping.csv.

---

## Long-Term Opportunities (3-12 months)

### R.9 Extend to 50+ Events with Full Calibration
- Systematic coverage of all GEDS event types using UN/IMF/World Bank/OECD/UNCTAD/BIS/NBER primary sources. No heuristic event data.

### R.10 Empirical SEIR R0 Estimation for Economic Networks
- **Action**: Use panel data on supplier-customer relationships (Compustat supply chain linkages or Factset) to estimate empirical beta and gamma.
- **Evidence basis**: DRPRESS 2024 framework + Nature 2021 coupled model provide starting structure.
- **Expected output**: First empirically calibrated SEIR economic network R0 — potential peer-review contribution.

### R.11 Climate-Chokepoint Integration
- **Action**: Map IPCC climate scenarios (RCP 4.5 and 8.5) to Panama Canal water levels; estimate future closure probabilities.
- **Evidence basis**: Panama Canal Authority drought data 2023-2024; UNCTAD LAC 2024; Verschuur et al. 2025 climate hazard component.

### R.12 Geopolitical Risk Index Integration
- **Action**: Connect GEDS to Baker-Bloom-Davis GPR Index or GDELT API for early-warning shock activation.
- **Evidence basis**: Caldara & Iacoviello 2022 AER GPR Index; GDELT real-time news events.

---

## High-Risk / High-Reward Opportunities

### R.HR1 First Cross-Event Validated Multi-Mechanism Model
- No published paper runs SEIRS + Bullwhip + Hysteresis combined on 20+ events simultaneously.
- Risk: Requires R² > 0 after OECD ICIO calibration.
- Reward: Publishable in Journal of International Economics, QJE, Economic Modelling if R² > 0.5 on held-out events.

### R.HR2 Empirical SEIR R0 for Supply Chain Networks
- First empirically-estimated R0 for economic shock propagation in supply chain networks.
- Risk: Requires firm-level supply chain data; computationally intensive.
- Reward: HIGH — confirmed literature gap; Nature/Science level if executed rigorously.

### R.HR3 Real-Time Economic Disruption Early-Warning System
- GEDS as real-time policy tool: IMF PortWatch + GDELT + ACLED → GDP impact probability distributions within hours.
- Risk: Significant engineering; validation required.
- Reward: Policy relevance very high; ISEF Grand Award potential.

### R.HR4 Multi-Chokepoint Simultaneous Disruption Scenarios
- First quantitative estimate of GDP impact from simultaneous Suez + Hormuz + Taiwan Strait disruption.
- Risk: Verschuur et al. 2025 quantified individual disruptions; simultaneous triple-closure modeled by no published paper.
- Reward: Nature Communications or Risk Analysis publication target.
