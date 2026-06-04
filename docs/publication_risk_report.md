# GEDS Publication Risk Report
*GEDS v2 | Evidence-based audit | 2026-05-27*

---

## 1. Risk Summary Matrix

| Risk Area | Level | Evidence Gap | Priority |
|---|---|---|---|
| Negative R² on structural models | CRITICAL | Models not calibrated to empirical IO parameters; heuristic edge weights | P0 |
| SEIRS re-susceptibility rate (ξ) | HIGH | No peer-reviewed empirical calibration for supply chain networks found | P1 |
| Country-sector presence (heuristic) | HIGH | OECD ICIO/WIOD not yet ingested; presence inferred heuristically | P1 |
| Bullwhip amplification factor | MEDIUM | Theoretical ratio from Lee et al. 1997; no universal empirical ratio | P2 |
| Hysteresis persistence parameter | MEDIUM | IMF range 1-2% per recession; country heterogeneity large | P2 |
| Chokepoint failure probabilities | MEDIUM | Nature Comms 2025 provides annual expected values; event-specific PDFs absent | P2 |
| Healthcare sector propagation | MEDIUM | Nodes present; cross-sector feedback parameters not calibrated to literature | P2 |
| Finance sector propagation | HIGH | Contagion logic present; extreme-value spillover parameters not from ECB/BIS data | P1 |
| COVID magnitude accuracy | MEDIUM | GDP -3.0% global well-sourced; sectoral decomposition heuristic in current GEDS | P2 |
| Novel SEIRS economic network claim | MEDIUM-HIGH | DRPRESS 2024 and Nature 2021 support theory; empirical calibration gap remains | P1 |

---

## 2. Supported Assumptions (ISEF/publication defensible)

### 2.1 Supply Chain Propagation
- **Upstream amplification**: Barrot & Sauvagnat (2016) QJE — -5 pp sales for supplier; -2 pp for customer. DOI: 10.1093/qje/qjw018. [CONFIDENCE: HIGH]
- **Network multiplier 3-4x**: Carvalho et al. (2021) QJE — Tohoku indirect effects 3-4x direct damage. DOI: 10.1093/qje/qjab010. [CONFIDENCE: HIGH]
- **Near-perfect input complementarity**: Boehm et al. (2019) REStat — elasticity ≈ -1 in automotive/electronics. DOI: 10.1162/rest_a_00750. [CONFIDENCE: HIGH]
- **Nonlinear cascade threshold**: MIT 2025 working paper — small shocks barely amplify; large shocks cause relationship dissolution. [CONFIDENCE: MEDIUM — not yet peer-reviewed]

### 2.2 Hysteresis
- **Permanent losses all recessions**: Cerra, Fatas, Saxena (2020) IMF WP. DOI: 10.5089/9781513537559.001. [CONFIDENCE: HIGH]
- **Financial crises 1.5-4% permanent GDP below trend**: IMF WP/2021/170. DOI: 10.5089/9781513537559.001. [CONFIDENCE: HIGH]
- **War: 1.5% GDP below baseline at 5 years**: IMF WP/24/039. [CONFIDENCE: HIGH for cross-country]

### 2.3 Bullwhip
- **Order variance amplification upstream**: Lee, Padmanabhan, Whang (1997) Management Science. DOI: 10.1287/mnsc.43.4.546. [CONFIDENCE: HIGH]
- **Formula**: Var(orders)/Var(demand) ≥ 1 + 2α·L + 2α²·L²
- **Information sharing reduces bullwhip**: Confirmed by Wang & Disney 2016 review. [CONFIDENCE: HIGH]

### 2.4 Chokepoints
- **Suez ~15% global trade; Ever Given 6.5 days**: UNCTAD 2024. [CONFIDENCE: HIGH]
- **TSMC 69.9% global foundry 2025**: TrendForce; Taipei Times March 2026. [CONFIDENCE: HIGH]
- **Hormuz ~25% global seaborne oil**: UNCTAD March 2026; EIA 2017. [CONFIDENCE: HIGH]
- **Malacca 23.7% global seaborne trade**: Ballast Markets May 2025; EIA 2017. [CONFIDENCE: HIGH]
- **Chokepoint losses $14B/year**: Verschuur, Lumma, Hall (2025) Nature Communications. DOI: 10.1038/s41467-025-65403-w. [CONFIDENCE: HIGH]

---

## 3. Unsupported or Weakly Supported Assumptions

### 3.1 SEIRS Re-Susceptibility Rate (ξ) — CRITICAL GAP
- **Status**: UNSUPPORTED empirically.
- **Evidence found**: DRPRESS 2024 (SEIR supply chain, MATLAB simulation); Nature 2021 (theoretical coupled model).
- **Missing**: Empirical ξ (re-susceptibility rate) for supplier firms in real supply chain data.
- **Risk**: Arbitrary ξ produces spurious model fit. This likely contributes to R² = -0.566.
- **Recommendation**: Set ξ = 0 (plain SEIR, not SEIRS) or explicitly label ξ as an assumption with sensitivity analysis table. Calibrate γ from Barrot & Sauvagnat (2016): ~2-3 quarter recovery ≈ γ ≈ 0.33-0.50/quarter.

### 3.2 Sector-to-Sector Edge Weights — CRITICAL GAP
- **Status**: Heuristic per GEDS v2 self-report.
- **Evidence**: OECD ICIO (2018, 65 countries × 45 sectors) and WIOD (2016, 43 countries × 56 sectors) exist and are publicly downloadable.
- **Risk**: Heuristic weights produce any R² depending on assumption; will not generalize.
- **Recommendation**: Ingest OECD ICIO 2018 tables. Map 45 OECD sectors → GEDS 19-sector taxonomy. Use Leontief coefficients as edge weights.

### 3.3 Bullwhip Amplification Magnitude
- **Status**: PARTIALLY SUPPORTED.
- **Evidence**: Lee et al. 1997 proves amplification exists. Formula: Var(orders)/Var(demand) = 1 + 2αL + 2α²L² requires sector-specific L (lead time) and α (smoothing).
- **Missing**: GEDS amplification factor not referenced to empirical sector lead times.
- **Recommendation**: Use World Bank LPI lead time data per sector to parameterize formula.

### 3.4 Healthcare Sector
- **Status**: WEAK.
- **Evidence**: Nature 2021 coupled model exists but parameters not calibrated to GEDS sectors.
- **Risk**: Healthcare node may propagate incorrectly without proper feedback coefficients.
- **Recommendation**: Parameterize from Nature 2021 (DOI:10.1038/s41598-021-94619-1) + IMF COVID sectoral output data.

### 3.5 Financial Contagion Parameters
- **Status**: WEAKLY SUPPORTED.
- **Evidence**: ECB WP1666 bilateral spillover coefficients available for EU; IMF Ch.21 extreme-value framework.
- **Missing**: GEDS finance sector parameters not pulled from ECB/BIS data.
- **Recommendation**: Ingest ECB WP1666 bilateral spillover matrix for EU finance nodes; IMF Ch.21 logit parameters for global banking.

---

## 4. ISEF Defense Readiness

| Claim | Defensibility | Likely Examiner Question | Counter-Evidence Available |
|---|---|---|---|
| SEIRS model for economic propagation | MEDIUM | Show empirical calibration of reinfection rate | DRPRESS 2024 + Nature 2021 theoretical; acknowledge gap |
| Network propagation amplifies 3-4x | HIGH | Source? | Carvalho et al. 2021 QJE |
| Hysteresis produces permanent losses | HIGH | How large? | Cerra et al. 2020: 1-2% per recession |
| Bullwhip effect active | HIGH | Quantify amplification | Lee et al. 1997 variance formula |
| Chokepoints quantified | HIGH | Source? | Verschuur et al. 2025 Nature Comms |
| TSMC failure systemic risk | HIGH | Concentration data? | TrendForce 69.9%; Nature Comms 2025 Taiwan top risk |
| R² = -0.566 | RISKY | Why negative? | Identified root cause: heuristic edge weights; OECD ICIO fix path documented |
| Validated on 23 events | MEDIUM | How were benchmark values chosen? | Sources now documented in missing_event_mapping.csv |

---

## 5. Recommended Actions Before ISEF/Publication

1. **INGEST OECD ICIO 2018** → replace heuristic edge weights → likely to fix negative R²
2. **REPLACE SEIRS with SEIR** for supply chain nodes (ξ = NULL, not found empirically) OR explicitly note SEIRS limitation with sensitivity table
3. **CALIBRATE bullwhip amplification** using Lee et al. 1997 formula + World Bank LPI lead times per sector
4. **CITE Verschuur et al. 2025** (Nature Comms DOI:10.1038/s41467-025-65403-w) for all chokepoint claims
5. **CITE Carvalho et al. 2021** (QJE DOI:10.1093/qje/qjab010) for 3-4x network multiplier claim
6. **DOCUMENT all NULL evidence fields** explicitly in model specification; do not substitute assumptions
7. **FINANCE sector**: implement ECB WP1666 bilateral coefficients
8. **HEALTHCARE sector**: parameterize from Nature Scientific Reports 2021 (DOI:10.1038/s41598-021-94619-1)

---

## 6. Evidence Confidence Register

| Mechanism | Evidence Level | Key Paper | Confidence |
|---|---|---|---|
| Supply chain network propagation | STRONG | Acemoglu 2012; Carvalho 2021; Barrot & Sauvagnat 2016 | HIGH |
| Bullwhip amplification | STRONG | Lee et al. 1997 | HIGH |
| Hysteresis (permanent losses) | STRONG | Cerra Fatas Saxena 2020; IMF WP/2021/170 | HIGH |
| Chokepoint systemic risk | STRONG | Verschuur et al. 2025 Nature Comms | HIGH |
| SEIRS supply chain threshold | MODERATE | DRPRESS 2024; Nature 2021 | MEDIUM |
| Financial contagion extreme-value | MODERATE | ECB WP1666; IMF Ch.21 | MEDIUM |
| SEIRS re-susceptibility (ξ) | ABSENT | No empirical calibration found | NULL |
| Country-sector heuristic weights | ABSENT | OECD ICIO not yet ingested | NULL |

*All NULL entries must be resolved or explicitly labeled before ISEF submission or peer review.*
