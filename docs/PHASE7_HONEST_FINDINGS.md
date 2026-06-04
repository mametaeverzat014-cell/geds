# Phase 7 — Honest Findings (peer-reviewed evidence ingestion)

This pass ingested **7 events** with **13 evidence rows** from **13 distinct papers**.

## 1. Events with the strongest evidence

Ranked by mean confidence (then by # papers):

| Event | Mean confidence | # papers |
|---|---|---|
| 11. Tōhoku Earthquake, Tsunami & Fukushima Nuclear Cri | 5.00 | 2 |
| 19. Ever Given Suez Canal Blockage | 5.00 | 1 |
| 17. COVID-19 Global Pandemic | 4.50 | 2 |
| 18. Global Semiconductor Chip Shortage | 4.00 | 1 |
| 7. Global Financial Crisis | 3.67 | 3 |
| 21. Russia Invasion of Ukraine & Global Sanctions | 3.50 | 2 |
| 22. European Natural Gas & Energy Crisis | 3.50 | 2 |

## 2. Events with weak evidence (within this pass)

- **Event 19 (Ever Given Suez):** ONLY anchored on Hummels & Schaur (AER 2013),
  which is a general delay-cost paper. The 0.6–2.3% per-day-of-delay range applies
  to *cargo value*, not global trade volume. No Suez-specific peer-reviewed
  macro estimate was supplied.
- **Event 18 (Semi shortage):** Anchored only on IMF WP/22/61 *Shipping Costs
  and Inflation*, which is NOT chip-specific. The 0.7pp inflation figure is
  for a 100% rise in *shipping* costs; the chip channel is not isolated.

## 3. Unsupported assumptions currently in GEDS

Assumptions that this ingestion pass does NOT validate:

- **Sector enum is correct.** Engine `Industry` enum has 7 members; many
  evidence sectors (financial, agriculture, utilities, energy-intensive
  manufacturing, chemicals) fall outside. Mapping to graph nodes is partial.
- **Shock magnitudes derived from |GDP impact|/50.** The Phase 3 benchmark
  script uses this heuristic to convert observed GDP loss into engine input
  magnitudes. This is NOT supported by any peer-reviewed paper in this pass.
- **Linear weighting of papers by confidence score.** `weighted_mean = Σ(value×conf)
  / Σ(conf)`. This treats confidence as a numeric weight which is convenient
  but unprincipled — a proper Bayesian aggregation would model paper-level
  variance, not just point confidence.
- **'Best estimate' from highest-confidence rows only.** Phase 3 picks max-
  confidence rows and ignores lower-confidence ones. This biases benchmark
  targets toward the most-cited paper, which may not be the most accurate.

## 4. Where benchmark values changed vs prior

**7** events in `master_event_registry.csv` now have non-NULL
`best_estimate_*` columns populated. Comparison vs original docx aggregate:

| Event | Original `gdp_impact_percent` (docx) | New `best_estimate_gdp` (papers) | Δ |
|---|---|---|---|
| 7. Global Financial Crisis | -1.300 | -0.300 | +1.000 |
| 11. Tōhoku Earthquake, Tsunami & Fukushima N | -0.900 | -0.410 | +0.490 |
| 17. COVID-19 Global Pandemic | -3.000 | -3.000 | +0.000 |
| 21. Russia Invasion of Ukraine & Global Sanc | +14.000 | -1.500 | -15.500 |
| 22. European Natural Gas & Energy Crisis | +3.000 | -0.700 | -3.700 |

## 5. Does this increase scientific validity?

**Yes, partially.** Concrete gains:

- 3 of 7 events now have a paper with confidence ≥5 (peer-reviewed journal).
- Uncertainty bands are preserved (`uncertainty_lower`/`upper`) for 6 of 7 events.
- DOIs cited for 3 papers (Inoue-Todo, Carvalho QJE, Hummels-Schaur, IMF WP/22/61).
- Benchmark targets in `benchmark_targets_expanded.csv` now have explicit
  paper provenance per metric.

**Honest caveats:**

- This pass covers **7 of 42 events** in the master registry. The other 35
  events have no new peer-reviewed support.
- The Suez and Semi events have only indirect/methodological anchors; their
  confidence scores would not survive scrutiny in a publication context.
- Phase 3 benchmark target values are *aggregated* peer-reviewed estimates,
  not single canonical values. Different papers gave different numbers (e.g.
  GFC GDP -0.1 to -0.5 from IMF WEO); the script preserves the range but
  publication-grade reporting should cite the range, not the midpoint.
- Inflation evidence is essentially absent for 4 of 7 events (COVID, GFC,
  Tōhoku, Suez). The ECB/SUERF pass-through coefficients are the only
  inflation-level numbers we have.

## 6. What is NOT in this pass that should be next

Tier-1 missing evidence (would most improve registry):

- **Suez-specific macro paper** — Allianz Research estimate cited in user table
  as 0.2-0.4 pp annual trade growth per week of blockage. Not in 'required list'.
  A peer-reviewed Suez paper would replace the AER framework hack.
- **Chip-shortage isolated GDP estimate** — current IMF WP is shipping-broad.
  Federal Reserve FEDS Notes have chip-specific work but not in this pass.
- **COVID equity-market quantification** — table flags this as 'outside listed
  sources'. NBER COVID-19 research project has direct estimates.
- **Russia-Ukraine country-level point estimates** — IMF WP/24/039 gives ranges,
  not single-country point estimates. Bruegel + Atlantic Council have these.
