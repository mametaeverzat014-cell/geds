# GEDS Novelty Positioning
*Evidence-based ISEF and research evaluation — GEDS v2 — 2026-05-27*
*All claims marked: [CONFIRMED], [PLAUSIBLE], or [UNCERTAIN — mark explicitly]*

---

## 1. What Parts of GEDS Are Already Common Research

### Supply Chain Network Propagation [CONFIRMED — established field]
- Acemoglu et al. 2012 (Econometrica): foundational theory; widely cited.
- Carvalho et al. 2021 (QJE): empirical validation via Tohoku.
- Barrot & Sauvagnat 2016 (QJE): firm-level shock propagation.
- Application of this theory is not novel by itself.

### Bullwhip Effect [CONFIRMED — textbook level]
Lee et al. 1997 is standard supply chain theory. Replicated across hundreds of industries. Application to simulation is not novel; parameterization with real event data is less common.

### Hysteresis in Macroeconomics [CONFIRMED — established]
Cerra & Saxena 2008 + Cerra Fatas Saxena 2020 establish hysteresis as consensus in empirical macroeconomics. Incorporating it into GEDS applies an established finding.

### Financial Contagion [CONFIRMED — established]
ECB WP1558/1666; IMF extreme value chapter — well-established frameworks. Application to GEDS finance nodes is application, not innovation.

### SEIR/SEIRS Applied to Supply Chains [PLAUSIBLE NOVELTY — limited prior work]
DRPRESS 2024 (Frontiers in Business Economics and Management) and Nature Scientific Reports 2021 apply SEIR dynamics to supply chain networks. This is recent and not yet mainstream. GEDS applying SEIRS to economic disruption propagation is at the frontier.

---

## 2. What Parts of GEDS Could Be Considered Novel

### 2.1 Multi-Mechanism Integration (SEIRS + Bullwhip + Hysteresis simultaneously) [PLAUSIBLE NOVELTY]
- Literature search found no published paper combining all three mechanisms in a single model.
- Caveat: Absence of search result is not proof of absence; comprehensive search in Econlit/REPEC/Google Scholar would confirm.
- Confidence: MEDIUM. Frame as: "To the best of the authors' knowledge, no prior work combines..."

### 2.2 Cross-Event Validation on 20+ Heterogeneous Events [PLAUSIBLE NOVELTY]
- Published papers typically validate on one event type. GEDS attempts 20+ events across 10 categories.
- Caveat: Validation quality depends on achieving R² > 0.
- Confidence: MEDIUM-HIGH if R² improves after OECD ICIO calibration.

### 2.3 Real-Time Chokepoint-to-GDP Propagation [PLAUSIBLE NOVELTY]
- Verschuur et al. 2025 (Nature Comms) quantifies systemic chokepoint risk but does not simulate downstream GDP sector-by-sector in a dynamic network.
- GEDS extending to dynamic network propagation is a potential extension of their work.
- Confidence: MEDIUM.

### 2.4 Empirically Calibrated SEIR R0 for Economic Networks [HIGH NOVELTY — if executed]
- No paper in DRPRESS 2024, Nature 2021, or AIMS 2025 provides empirically calibrated R0 for economic networks — confirmed gap.
- Requires firm-level supply chain data.
- Confidence: HIGH novelty value; HIGH execution difficulty.

---

## 3. Potential Research Contributions

### C.1 Validated Multi-Mechanism Economic Disruption Simulator
GEDS is the first platform to jointly model SEIRS propagation dynamics, Bullwhip inventory amplification, and hysteresis persistence in a unified global economic network, validated against 20+ historical disruption events.
- Defensibility: HIGH if R² > 0.5 on held-out events and OECD ICIO calibration is complete.
- Venue: Journal of International Economics; Review of Economics and Statistics; Economic Modelling; ISEF.

### C.2 Evidence-Driven Chokepoint Disruption Impact Database
Research-grade dataset of 42+ disruption events with IMF/World Bank/OECD-sourced quantitative impacts.
- Defensibility: HIGH — sourced and cited throughout.
- Venue: Scientific Data (Nature); International Journal of Disaster Risk Reduction.

### C.3 SEIR Threshold Activation in Supply Chain Networks
First empirical estimation of R0 for economic shock propagation in a production network.
- Defensibility: MEDIUM — requires data access beyond current GEDS scope.
- Venue: Management Science; QJE; Econometrica.

---

## 4. Potential Hypotheses

| Hypothesis | Evidence Basis | Testable | Confidence |
|---|---|---|---|
| H1: Supply chain shocks propagate with 3-4x amplification beyond direct damage | Carvalho et al. 2021 | YES — measure indirect vs direct in GEDS events | HIGH |
| H2: Events exceeding SEIRS R0>1 cause disproportionately larger losses than linear extrapolation | DRPRESS 2024; MIT 2025 | YES — compare GEDS outputs above/below threshold | MEDIUM |
| H3: High chokepoint concentration events show larger third-country spillover | Verschuur et al. 2025 | YES — GEDS cross-country vs chokepoint exposure | HIGH |
| H4: Hysteresis reduces recovery for financial crises more than supply chain disruptions | Cerra Saxena 2008; IMF WP/2021/170 | YES — compare GEDS recovery trajectories by event type | HIGH |
| H5: GEDS achieves R²>0.5 after OECD ICIO calibration | Theoretical (IO precision) | YES — before/after experiment | MEDIUM |
| H6: Bullwhip amplification measurable as order:demand variance ratio >1 | Lee et al. 1997 | YES — compute for COVID PPE and semiconductor shortage | HIGH |

---

## 5. Potential Publication Directions

### ISEF (Computer Science and Systems Software)
- Claim: Novel application of network epidemic dynamics + supply chain theory + hysteresis in unified global economic shock simulator.
- Strongest defense: Cross-event validation dataset; evidence-based calibration; transparent R² limitations with identified solution path.
- Risk: R² = -0.566 will be challenged; must frame as active research with documented fix.

### Economic Modelling (Elsevier)
- Fit: Applied simulation; cross-country validation; policy-relevant outputs.
- Target: "GEDS: A Multi-Mechanism Global Economic Disruption Simulator Validated on 20 Historical Events."

### International Journal of Disaster Risk Reduction (Elsevier)
- Fit: Cross-hazard risk; economic impact; supply chain resilience; chokepoint modeling.

### Scientific Data (Nature Portfolio)
- Fit: Data descriptor for GEDS disruption event database.
- Target: "A Research-Grade Dataset of Global Economic Disruption Events 2000-2026 for Model Validation."

---

## 6. Explicit Uncertainty Register

These claims are NOT supported by current evidence. Do NOT include without explicit uncertainty labeling:

| Claim | Status |
|---|---|
| SEIRS re-susceptibility rate (xi) | NULL — no empirical calibration found |
| Country-sector presence (heuristic weights) | ASSUMPTION — not from OECD ICIO/WIOD |
| Healthcare-economy feedback parameters | UNVALIDATED — Nature 2021 not calibrated to GEDS sectors |
| Financial contagion tail parameters | ASSUMPTION — ECB WP1666 not yet ingested |
| Multi-chokepoint simultaneous closure probability | UNKNOWN — no published joint probability distribution |
| North Korea GDP statistics | UNRELIABLE — state data; nighttime light proxy used by Fan & Rodrigues-Brown 2023 |
| Arab Spring GDP attribution | UNCERTAIN — concurrent factors; World Bank range 1-5% of GDP |
| Dot-com / 9-11 combined GDP attribution | UNCERTAIN — multiple concurrent shocks; no clean causal identification |
