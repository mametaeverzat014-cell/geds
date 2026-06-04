# GEDS Publication Readiness v2

Generated: `2026-05-27T07:49:46.501357+00:00`
Drives entirely from `mechanism_validation.csv` which was bootstrapped from
`docs/publication_risk_report.md` §6 (Evidence Confidence Register).

## Validated components (SUPPORTED)

These mechanisms have published peer-reviewed support AND a GEDS implementation:

| Mechanism | Evidence strength | Key paper | GEDS assumption | Matches evidence? | Confidence |
|---|---|---|---|---|---|
| supply_chain_network_propagation | STRONG | Acemoglu 2012; Carvalho 2021; Barrot & Sauvagnat 2016 | linear amplified propagation through D_eff matrix | true | 5 / 5 |
| bullwhip_amplification | STRONG | Lee, Padmanabhan, Whang 1997 | 1.25x inbound amplification on E-state nodes | partial — Lee formula not parameterized to GEDS sector lead times | 4 / 5 |
| hysteresis_permanent_losses | STRONG | Cerra-Fatas-Saxena 2020 IMF WP; IMF WP/2021/170 | R-state output floor 0.30 (70% production cap) | partial — Cerra 1-2% permanent loss; GEDS 30% floor is much larger | 4 / 5 |
| chokepoint_systemic_risk | STRONG | Verschuur et al. 2025 Nature Comms | chokepoint nodes with adaptive_rerouting surcharge | true (qualitative); GEDS does not currently use Verschuur loss magnitudes | 5 / 5 |

## Heuristic components (UNCERTAIN — needs evidence anchor)

| Mechanism | Evidence strength | Key paper | GEDS assumption | Status |
|---|---|---|---|---|
| SEIRS_supply_chain_threshold | MODERATE | DRPRESS 2024; Nature Sci Reports 2021 | SEIRS state machine with EXPOSURE_TRIGGER=0.05 | qualitative match; empirical calibration ABSENT |
| financial_contagion_extreme_value | MODERATE | ECB WP1666; IMF Ch.21 | GEDS finance sector not parameterized from ECB/BIS data | false — parameters absent |
| healthcare_sector_propagation | WEAK | Nature Sci Reports 2021 DOI:10.1038/s41598-021-94619-1 | healthcare not in engine Industry enum (mapped to tourism for COVID) | false — wrong proxy sector |

## Unsupported assumptions (UNSUPPORTED — must be addressed before publication)

| Mechanism | Evidence strength | Key paper | GEDS assumption | Risk |
|---|---|---|---|---|
| SEIRS_re_susceptibility_rate_xi | ABSENT | No empirical calibration found | Implicit ξ embedded in R→S transition after recovery_delay weeks | false — ξ is arbitrary |
| country_sector_heuristic_weights | ABSENT | OECD ICIO 2018 / WIOD 2016 publicly available but not yet ingested | Hardcoded SPECIALTY_PRESENCE map per country | false — heuristic, not data-derived |

## Remaining risks (from publication_risk_report.md §1)

These risks were flagged in the original audit and remain unaddressed in
the current integration pass (no engine values were changed):

1. **CRITICAL — Negative R² on structural models**: GEDS R² = −0.566 on N=23. Diagnosis (per audit §1): heuristic edge weights; OECD ICIO not yet ingested.
2. **HIGH — SEIRS re-susceptibility rate (ξ) is arbitrary**: no empirical calibration found in the literature. Either set ξ=0 (plain SEIR) or run sensitivity analysis with explicit uncertainty bands.
3. **HIGH — Country×sector presence is heuristic**: bootstrapped from GEDS's own SPECIALTY_PRESENCE map; OECD ICIO 2018 / WIOD 2016 ingestion is the only real fix.
4. **HIGH — Finance sector parameters not from ECB/BIS**: ECB WP1666 bilateral coefficients and IMF Ch.21 logit parameters are publicly available but not yet wired into the engine.

## Honest assessment of this integration pass

- **Scientific registry built** ✓ — all 5 dataclasses load and expose lookups.
- **Mechanism labels published** ✓ — SUPPORTED / UNCERTAIN / UNSUPPORTED per source.
- **Engine values NOT changed** ✓ — calibrated_v2 params remain authoritative.
- **Literature priors documented** ✓ in `calibration_v2/literature_priors.json`.
- **No new events gained** — `benchmark_event_matrix_v3.csv` is identical to v2 in OK-status counts (still 23). Gaining events requires OECD ICIO ingestion or further engine enum extensions, both of which are real-data work not done in this pass.
- **Bootstrapped CSVs are flagged** — every row in the 6 new CSVs carries a `_source_origin` column. Where the source did not provide a numeric value, the cell is NULL (empty). No values were invented.

**Counts:** SUPPORTED: 4, UNCERTAIN: 3, UNSUPPORTED: 2.

## Status verdict

GEDS is **publication-defensible for the SUPPORTED mechanisms** (supply-chain propagation, bullwhip amplification, hysteresis, chokepoint risk) provided that:

1. The UNSUPPORTED items above are explicitly disclosed in any paper / ISEF presentation, not hidden.
2. The negative R² is reported with its causal diagnosis (heuristic edge weights), not as a model-quality claim.
3. The 'SEIRS-Bullwhip-Hysteresis' brand is qualified — the prior forensics showed those layers are partially active on the expanded graph but the weight of model effect remains in network propagation + amplification.
