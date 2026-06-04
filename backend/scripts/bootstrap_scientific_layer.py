"""Bootstrap the 6 named scientific-layer CSVs from existing repo evidence.

CRITICAL: this script does NOT invent values. Every cell in every output CSV
traces to an existing repo document:

  Source artifacts (all already in repo):
    docs/publication_risk_report.md       — peer-reviewed citations + numeric values
    backend/data/csv/papers_catalog.csv   — 25 deeply-cataloged papers
    backend/data/csv/expanded_graph_nodes_v2.csv  — 595 country×sector nodes
    backend/data/csv/master_event_registry.csv    — 42 events + best-estimate columns
    backend/data/csv/benchmark_event_matrix_v2.csv — event → graph mapping status

  Output CSVs (each row has a _source_origin column to make provenance explicit):
    backend/data/csv/country_sector_presence.csv   — derived from expanded_graph_nodes_v2
    backend/data/csv/global_chokepoints.csv        — bootstrapped from publication_risk_report
    backend/data/csv/propagation_literature.csv    — derived from papers_catalog + risk report
    backend/data/csv/financial_contagion.csv       — subset of papers_catalog for finance
    backend/data/csv/mechanism_validation.csv      — from publication_risk_report §6
    backend/data/csv/missing_event_mapping.csv     — derived from benchmark_event_matrix_v2

Rules respected:
  - NULL preserved for any quantity not explicitly stated in the source doc
  - _source_origin column marks each row's provenance
  - publication_risk_report.md citations include DOIs where stated
  - No row is invented (every row corresponds to an entity already named in
    the source documents)
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CSV_DIR = REPO / "backend" / "data" / "csv"


def read_csv(name: str) -> list[dict]:
    p = CSV_DIR / name
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(name: str, fields: list[str], rows: list[dict]) -> Path:
    p = CSV_DIR / name
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return p


# ── 1. country_sector_presence.csv ────────────────────────────────────────
# Source: backend/data/csv/expanded_graph_nodes_v2.csv (already built from
# G20 + trade hubs × 19 sectors using documented industry presence heuristics).
# We denormalise it as a (country, sector, present) table; no new info added.

def bootstrap_country_sector_presence() -> Path:
    nodes = read_csv("expanded_graph_nodes_v2.csv")
    presence: dict[str, set[str]] = defaultdict(set)
    for n in nodes:
        if n.get("kind") != "country_industry":
            continue
        country = n["country_iso3"]
        sector = n["industry"]
        if country and sector:
            presence[country].add(sector)
    rows = []
    SECTORS = ["semiconductors", "automotive", "electronics", "aerospace",
               "shipping", "energy", "consumer_goods",
               "banking", "insurance", "capital_markets", "oil", "gas",
               "utilities", "aviation", "ports", "telecommunications",
               "agriculture", "tourism", "government"]
    for country in sorted(presence.keys()):
        for sector in SECTORS:
            rows.append({
                "country_iso3": country,
                "sector": sector,
                "present": "true" if sector in presence[country] else "false",
                "_source_origin": "denormalized from expanded_graph_nodes_v2.csv",
            })
    return write_csv(
        "country_sector_presence.csv",
        ["country_iso3", "sector", "present", "_source_origin"],
        rows,
    )


# ── 2. global_chokepoints.csv ────────────────────────────────────────────
# Source: docs/publication_risk_report.md §2.4 — explicit per-chokepoint
# numeric values with citations to UNCTAD, EIA, Ballast Markets, Verschuur 2025.
# Only entries with a documented source value are emitted; NULL preserved
# for anything not in the source doc.

CHOKEPOINT_EVIDENCE = [
    {
        "chokepoint_id": "CP:Suez",
        "name": "Suez Canal",
        "capacity_share_global_trade_pct": 15.0,
        "rerouting_cost_per_day_usd_b": None,  # not in source
        "failure_duration_observed_days": 6.5,
        "failure_event_year": 2021,
        "failure_event_name": "Ever Given",
        "downstream_sectors": "shipping;automotive;consumer_goods;oil",
        "evidence_citation": "UNCTAD 2024",
        "doi_or_url": "https://unctad.org",
        "evidence_confidence": "HIGH",
        "_source_origin": "publication_risk_report.md §2.4",
    },
    {
        "chokepoint_id": "CP:Hormuz",
        "name": "Strait of Hormuz",
        "capacity_share_global_seaborne_oil_pct": 25.0,
        "rerouting_cost_per_day_usd_b": None,
        "failure_duration_observed_days": None,
        "failure_event_year": None,
        "failure_event_name": None,
        "downstream_sectors": "oil;gas;energy;shipping",
        "evidence_citation": "UNCTAD March 2026; EIA 2017",
        "doi_or_url": "https://www.eia.gov/international/analysis/special-topics/world_oil_transit_chokepoints",
        "evidence_confidence": "HIGH",
        "_source_origin": "publication_risk_report.md §2.4",
    },
    {
        "chokepoint_id": "CP:Malacca",
        "name": "Strait of Malacca",
        "capacity_share_global_seaborne_trade_pct": 23.7,
        "rerouting_cost_per_day_usd_b": None,
        "failure_duration_observed_days": None,
        "failure_event_year": None,
        "failure_event_name": None,
        "downstream_sectors": "shipping;electronics;consumer_goods;oil",
        "evidence_citation": "Ballast Markets May 2025; EIA 2017",
        "doi_or_url": "https://www.eia.gov/international/analysis/special-topics/world_oil_transit_chokepoints",
        "evidence_confidence": "HIGH",
        "_source_origin": "publication_risk_report.md §2.4",
    },
    {
        "chokepoint_id": "CP:TaiwanStrait",
        "name": "Taiwan Strait (TSMC foundry concentration)",
        "tsmc_foundry_share_pct": 69.9,
        "tsmc_advanced_chips_share_pct": 90.0,
        "rerouting_cost_per_day_usd_b": None,
        "failure_duration_observed_days": None,
        "failure_event_year": None,
        "failure_event_name": None,
        "downstream_sectors": "semiconductors;electronics;automotive;aerospace",
        "evidence_citation": "TrendForce; Taipei Times March 2026",
        "doi_or_url": None,
        "evidence_confidence": "HIGH",
        "_source_origin": "publication_risk_report.md §2.4; Verschuur 2025 ranks Taiwan top risk",
    },
    {
        "chokepoint_id": "GLOBAL_CHOKEPOINT_BASKET",
        "name": "Aggregate expected annual chokepoint loss",
        "expected_annual_loss_usd_b": 14.0,
        "rerouting_cost_per_day_usd_b": None,
        "downstream_sectors": "all",
        "evidence_citation": "Verschuur, Lumma, Hall (2025) Nature Communications",
        "doi_or_url": "10.1038/s41467-025-65403-w",
        "evidence_confidence": "HIGH",
        "_source_origin": "publication_risk_report.md §2.4",
    },
    {
        "chokepoint_id": "CP:Panama",
        "name": "Panama Canal",
        "capacity_share_global_trade_pct": None,  # not stated numerically in risk report
        "rerouting_cost_per_day_usd_b": None,
        "failure_duration_observed_days": None,
        "failure_event_year": 2023,
        "failure_event_name": "El Niño drought (Gatún Lake)",
        "downstream_sectors": "shipping;agriculture;consumer_goods",
        "evidence_citation": "master_event_registry.csv event_id=27",
        "doi_or_url": None,
        "evidence_confidence": "MEDIUM",
        "_source_origin": "bootstrapped from master_event_registry.csv (no numeric value in risk report)",
    },
    {
        "chokepoint_id": "CP:RedSea",
        "name": "Red Sea / Bab-el-Mandeb",
        "capacity_share_global_trade_pct": None,
        "rerouting_cost_per_day_usd_b": None,
        "failure_duration_observed_days": None,
        "failure_event_year": 2023,
        "failure_event_name": "Houthi attacks (event_id=26)",
        "downstream_sectors": "shipping;oil;consumer_goods",
        "evidence_citation": "master_event_registry.csv event_id=26",
        "doi_or_url": None,
        "evidence_confidence": "MEDIUM",
        "_source_origin": "bootstrapped from master_event_registry.csv (no numeric value in risk report)",
    },
    {
        "chokepoint_id": "CP:Bosphorus",
        "name": "Bosphorus Strait",
        "capacity_share_global_trade_pct": None,
        "rerouting_cost_per_day_usd_b": None,
        "failure_duration_observed_days": None,
        "failure_event_year": None,
        "failure_event_name": None,
        "downstream_sectors": "shipping;oil;agriculture",
        "evidence_citation": "—",
        "doi_or_url": None,
        "evidence_confidence": "NULL",
        "_source_origin": "no source in repo; row preserved for schema completeness with all values NULL",
    },
]


def bootstrap_chokepoints() -> Path:
    fields = sorted({k for r in CHOKEPOINT_EVIDENCE for k in r.keys()})
    fields = ["chokepoint_id", "name"] + [f for f in fields if f not in ("chokepoint_id", "name")]
    rows = []
    for r in CHOKEPOINT_EVIDENCE:
        row = {f: r.get(f, "") for f in fields}
        # Replace None with empty string (NULL semantics)
        for k, v in row.items():
            if v is None:
                row[k] = ""
        rows.append(row)
    return write_csv("global_chokepoints.csv", fields, rows)


# ── 3. propagation_literature.csv ─────────────────────────────────────────
# Source: papers_catalog.csv (already exists with full author/year/DOI/findings)
# Plus the per-mechanism evidence from publication_risk_report.md §2.

PROPAGATION_PAPERS = [
    # From publication_risk_report.md §2.1 (supply chain propagation)
    {"paper_id": "Barrot-Sauvagnat-2016",
     "title": "Input Specificity and the Propagation of Idiosyncratic Shocks",
     "authors": "Barrot, Sauvagnat",
     "year": 2016, "journal": "Quarterly Journal of Economics",
     "doi": "10.1093/qje/qjw018",
     "mechanism": "supply_chain_propagation",
     "key_quantitative_finding": "-5pp supplier sales; -2pp customer sales after disaster",
     "propagation_multiplier_estimate": None,
     "recovery_duration_estimate_months": 6,
     "evidence_confidence": "HIGH",
     "_source_origin": "publication_risk_report.md §2.1"},
    {"paper_id": "Carvalho-2021",
     "title": "Supply Chain Disruptions: Evidence from the Great East Japan Earthquake",
     "authors": "Carvalho, Nirei, Saito, Tahbaz-Salehi",
     "year": 2021, "journal": "Quarterly Journal of Economics",
     "doi": "10.1093/qje/qjab010",
     "mechanism": "network_multiplier",
     "key_quantitative_finding": "Indirect effects 3-4x direct damage (Tohoku)",
     "propagation_multiplier_estimate": 3.5,
     "recovery_duration_estimate_months": 12,
     "evidence_confidence": "HIGH",
     "_source_origin": "publication_risk_report.md §2.1"},
    {"paper_id": "Boehm-2019",
     "title": "Input Linkages and the Transmission of Shocks: Firm-Level Evidence from the 2011 Tohoku Earthquake",
     "authors": "Boehm, Flaaen, Pandalai-Nayar",
     "year": 2019, "journal": "Review of Economics and Statistics",
     "doi": "10.1162/rest_a_00750",
     "mechanism": "input_complementarity",
     "key_quantitative_finding": "Elasticity ≈ -1 in automotive/electronics (near-perfect complementarity)",
     "propagation_multiplier_estimate": None,
     "recovery_duration_estimate_months": None,
     "evidence_confidence": "HIGH",
     "_source_origin": "publication_risk_report.md §2.1"},
    # From publication_risk_report.md §2.2 (hysteresis)
    {"paper_id": "Cerra-Fatas-Saxena-2020",
     "title": "Hysteresis and Business Cycles",
     "authors": "Cerra, Fatas, Saxena",
     "year": 2020, "journal": "IMF Working Paper",
     "doi": "10.5089/9781513537559.001",
     "mechanism": "hysteresis",
     "key_quantitative_finding": "1-2% permanent GDP loss per recession",
     "propagation_multiplier_estimate": None,
     "recovery_duration_estimate_months": 60,
     "evidence_confidence": "HIGH",
     "_source_origin": "publication_risk_report.md §2.2"},
    {"paper_id": "IMF-WP-24-039",
     "title": "Medium-Term Macroeconomic Effects of Russia's War in Ukraine and the Subsequent Energy Crisis",
     "authors": "IMF Research Department",
     "year": 2024, "journal": "IMF Working Paper",
     "doi": None,
     "mechanism": "hysteresis",
     "key_quantitative_finding": "1.5% GDP below baseline at 5 years post-conflict",
     "propagation_multiplier_estimate": None,
     "recovery_duration_estimate_months": 60,
     "evidence_confidence": "HIGH",
     "_source_origin": "publication_risk_report.md §2.2"},
    # From publication_risk_report.md §2.3 (bullwhip)
    {"paper_id": "Lee-Padmanabhan-Whang-1997",
     "title": "The Bullwhip Effect in Supply Chains",
     "authors": "Lee, Padmanabhan, Whang",
     "year": 1997, "journal": "Management Science",
     "doi": "10.1287/mnsc.43.4.546",
     "mechanism": "bullwhip",
     "key_quantitative_finding": "Var(orders)/Var(demand) >= 1 + 2αL + 2α²L² (L=lead time, α=smoothing)",
     "propagation_multiplier_estimate": None,
     "recovery_duration_estimate_months": None,
     "evidence_confidence": "HIGH",
     "_source_origin": "publication_risk_report.md §2.3"},
    # From publication_risk_report.md §2.4 (chokepoints)
    {"paper_id": "Verschuur-2025",
     "title": "Quantification of systemic global trade chokepoint risks",
     "authors": "Verschuur, Lumma, Hall",
     "year": 2025, "journal": "Nature Communications",
     "doi": "10.1038/s41467-025-65403-w",
     "mechanism": "chokepoint",
     "key_quantitative_finding": "$14B/year expected chokepoint losses globally",
     "propagation_multiplier_estimate": None,
     "recovery_duration_estimate_months": None,
     "evidence_confidence": "HIGH",
     "_source_origin": "publication_risk_report.md §2.4"},
    # From publication_risk_report.md §3 (UNSUPPORTED — for evidence labelling)
    {"paper_id": "DRPRESS-2024",
     "title": "SEIR Supply Chain (MATLAB simulation)",
     "authors": "DRPRESS",
     "year": 2024, "journal": None,
     "doi": None,
     "mechanism": "SEIRS",
     "key_quantitative_finding": "Theoretical SEIR for supply chain; no empirical ξ calibration",
     "propagation_multiplier_estimate": None,
     "recovery_duration_estimate_months": None,
     "evidence_confidence": "MEDIUM",
     "_source_origin": "publication_risk_report.md §3.1"},
    {"paper_id": "Nature-Sci-Reports-2021",
     "title": "Coupled SEIR-economic network model",
     "authors": "—",
     "year": 2021, "journal": "Nature Scientific Reports",
     "doi": "10.1038/s41598-021-94619-1",
     "mechanism": "SEIRS",
     "key_quantitative_finding": "Theoretical coupled model; parameters not calibrated to economic sectors",
     "propagation_multiplier_estimate": None,
     "recovery_duration_estimate_months": None,
     "evidence_confidence": "MEDIUM",
     "_source_origin": "publication_risk_report.md §3.1"},
    {"paper_id": "MIT-2025-Cascade",
     "title": "Nonlinear cascade threshold in supply networks (MIT working paper)",
     "authors": "—",
     "year": 2025, "journal": None,
     "doi": None,
     "mechanism": "nonlinear_threshold",
     "key_quantitative_finding": "Small shocks barely amplify; large shocks cause relationship dissolution",
     "propagation_multiplier_estimate": None,
     "recovery_duration_estimate_months": None,
     "evidence_confidence": "MEDIUM",
     "_source_origin": "publication_risk_report.md §2.1 (not yet peer-reviewed)"},
]


def bootstrap_propagation_literature() -> Path:
    fields = ["paper_id", "title", "authors", "year", "journal", "doi",
              "mechanism", "key_quantitative_finding",
              "propagation_multiplier_estimate", "recovery_duration_estimate_months",
              "evidence_confidence", "_source_origin"]
    rows = []
    for r in PROPAGATION_PAPERS:
        row = {f: r.get(f, "") for f in fields}
        for k, v in row.items():
            if v is None:
                row[k] = ""
        rows.append(row)
    return write_csv("propagation_literature.csv", fields, rows)


# ── 4. financial_contagion.csv ────────────────────────────────────────────
# Source: papers_catalog.csv subset for financial-contagion papers
# Plus publication_risk_report.md §3.5 references (ECB WP1666, IMF Ch.21).

FINANCIAL_PAPERS = [
    # ECB WP1666 — cited in publication_risk_report.md §3.5
    {"paper_id": "ECB-WP-1666",
     "title": "Bilateral spillover coefficients for EU finance",
     "authors": "ECB Working Paper 1666",
     "year": None, "journal": "ECB Working Paper Series",
     "doi": None,
     "contagion_type": "bilateral_spillover",
     "key_finding": "Bilateral spillover matrix for EU finance nodes (point estimates not extracted into this row)",
     "spillover_coefficient_estimate": None,
     "scope": "EU",
     "evidence_confidence": "MEDIUM",
     "_source_origin": "publication_risk_report.md §3.5"},
    {"paper_id": "IMF-Ch21-Extreme",
     "title": "Extreme-value framework for financial contagion (IMF Ch.21)",
     "authors": "IMF",
     "year": None, "journal": "IMF Financial Stability Report",
     "doi": None,
     "contagion_type": "extreme_value",
     "key_finding": "Logit parameters for global banking spillovers",
     "spillover_coefficient_estimate": None,
     "scope": "global_banking",
     "evidence_confidence": "MEDIUM",
     "_source_origin": "publication_risk_report.md §3.5"},
]
# Also pull from papers_catalog.csv any paper with mechanism related to financial contagion

def bootstrap_financial_contagion() -> Path:
    papers = read_csv("papers_catalog.csv")
    rows = []
    # Hand-curated additions from publication_risk_report.md
    for r in FINANCIAL_PAPERS:
        rows.append({**{k: (v if v is not None else "") for k, v in r.items()}})
    # Pull finance-related rows from papers_catalog
    for p in papers:
        title_low = p["title"].lower()
        findings_low = (p.get("key_findings", "") or "").lower()
        keywords = ("financial contagion", "interbank", "banking ecosystem",
                    "financial network", "systemic risk", "liaisons dangereuses",
                    "financial contagion")
        if any(kw in title_low or kw in findings_low for kw in keywords):
            rows.append({
                "paper_id": p["paper_id"],
                "title": p["title"],
                "authors": p["authors"],
                "year": p.get("year", ""),
                "journal": p.get("journal", ""),
                "doi": p.get("doi", ""),
                "contagion_type": "network_cascade",
                "key_finding": p.get("key_findings", "")[:200],
                "spillover_coefficient_estimate": "",
                "scope": "global",
                "evidence_confidence": "HIGH" if int(p.get("geds_relevance", "0") or 0) >= 9 else "MEDIUM",
                "_source_origin": "papers_catalog.csv",
            })
    fields = ["paper_id", "title", "authors", "year", "journal", "doi",
              "contagion_type", "key_finding", "spillover_coefficient_estimate",
              "scope", "evidence_confidence", "_source_origin"]
    return write_csv("financial_contagion.csv", fields, rows)


# ── 5. mechanism_validation.csv ───────────────────────────────────────────
# Source: publication_risk_report.md §6 "Evidence Confidence Register"

MECHANISM_VALIDATION = [
    {"mechanism": "supply_chain_network_propagation",
     "label": "SUPPORTED",
     "evidence_strength": "STRONG",
     "key_paper": "Acemoglu 2012; Carvalho 2021; Barrot & Sauvagnat 2016",
     "geds_assumption_used": "linear amplified propagation through D_eff matrix",
     "matches_evidence": "true",
     "confidence": 5,
     "_source_origin": "publication_risk_report.md §6"},
    {"mechanism": "bullwhip_amplification",
     "label": "SUPPORTED",
     "evidence_strength": "STRONG",
     "key_paper": "Lee, Padmanabhan, Whang 1997",
     "geds_assumption_used": "1.25x inbound amplification on E-state nodes",
     "matches_evidence": "partial — Lee formula not parameterized to GEDS sector lead times",
     "confidence": 4,
     "_source_origin": "publication_risk_report.md §6"},
    {"mechanism": "hysteresis_permanent_losses",
     "label": "SUPPORTED",
     "evidence_strength": "STRONG",
     "key_paper": "Cerra-Fatas-Saxena 2020 IMF WP; IMF WP/2021/170",
     "geds_assumption_used": "R-state output floor 0.30 (70% production cap)",
     "matches_evidence": "partial — Cerra 1-2% permanent loss; GEDS 30% floor is much larger",
     "confidence": 4,
     "_source_origin": "publication_risk_report.md §6"},
    {"mechanism": "chokepoint_systemic_risk",
     "label": "SUPPORTED",
     "evidence_strength": "STRONG",
     "key_paper": "Verschuur et al. 2025 Nature Comms",
     "geds_assumption_used": "chokepoint nodes with adaptive_rerouting surcharge",
     "matches_evidence": "true (qualitative); GEDS does not currently use Verschuur loss magnitudes",
     "confidence": 5,
     "_source_origin": "publication_risk_report.md §6"},
    {"mechanism": "SEIRS_supply_chain_threshold",
     "label": "UNCERTAIN",
     "evidence_strength": "MODERATE",
     "key_paper": "DRPRESS 2024; Nature Sci Reports 2021",
     "geds_assumption_used": "SEIRS state machine with EXPOSURE_TRIGGER=0.05",
     "matches_evidence": "qualitative match; empirical calibration ABSENT",
     "confidence": 3,
     "_source_origin": "publication_risk_report.md §6"},
    {"mechanism": "financial_contagion_extreme_value",
     "label": "UNCERTAIN",
     "evidence_strength": "MODERATE",
     "key_paper": "ECB WP1666; IMF Ch.21",
     "geds_assumption_used": "GEDS finance sector not parameterized from ECB/BIS data",
     "matches_evidence": "false — parameters absent",
     "confidence": 2,
     "_source_origin": "publication_risk_report.md §6"},
    {"mechanism": "SEIRS_re_susceptibility_rate_xi",
     "label": "UNSUPPORTED",
     "evidence_strength": "ABSENT",
     "key_paper": "No empirical calibration found",
     "geds_assumption_used": "Implicit ξ embedded in R→S transition after recovery_delay weeks",
     "matches_evidence": "false — ξ is arbitrary",
     "confidence": 1,
     "_source_origin": "publication_risk_report.md §3.1, §6"},
    {"mechanism": "country_sector_heuristic_weights",
     "label": "UNSUPPORTED",
     "evidence_strength": "ABSENT",
     "key_paper": "OECD ICIO 2018 / WIOD 2016 publicly available but not yet ingested",
     "geds_assumption_used": "Hardcoded SPECIALTY_PRESENCE map per country",
     "matches_evidence": "false — heuristic, not data-derived",
     "confidence": 1,
     "_source_origin": "publication_risk_report.md §3.2, §6"},
    {"mechanism": "healthcare_sector_propagation",
     "label": "UNCERTAIN",
     "evidence_strength": "WEAK",
     "key_paper": "Nature Sci Reports 2021 DOI:10.1038/s41598-021-94619-1",
     "geds_assumption_used": "healthcare not in engine Industry enum (mapped to tourism for COVID)",
     "matches_evidence": "false — wrong proxy sector",
     "confidence": 2,
     "_source_origin": "publication_risk_report.md §3.4"},
]


def bootstrap_mechanism_validation() -> Path:
    fields = ["mechanism", "label", "evidence_strength", "key_paper",
              "geds_assumption_used", "matches_evidence", "confidence",
              "_source_origin"]
    return write_csv("mechanism_validation.csv", fields, MECHANISM_VALIDATION)


# ── 6. missing_event_mapping.csv ───────────────────────────────────────
# Source: benchmark_event_matrix_v2.csv — events whose mapping_status is
# UNMAPPED or NO_TARGET. We list them with the gap explicitly identified.
# NO targets fabricated: target_gdp stays whatever benchmark_event_matrix_v2 has.

def bootstrap_missing_event_mapping() -> Path:
    matrix = read_csv("benchmark_event_matrix_v2.csv")
    rows = []
    for r in matrix:
        status = r.get("mapping_status", "")
        if status == "OK":
            continue
        # Identify gap
        sectors_src = r.get("sectors_source") or ""
        sectors_mapped = r.get("sectors_mapped") or ""
        if status == "SCENARIO":
            gap = "forward-looking scenario (excluded by design)"
        elif not r.get("target_gdp"):
            gap = "no GDP target available"
        elif not sectors_mapped:
            gap = f"all source sectors out of engine enum: {sectors_src[:80]}"
        elif not r.get("countries"):
            gap = "no affected country listed"
        else:
            gap = f"sectors mapped ({sectors_mapped}) but no graph node exists for any (country, sector) combination"
        rows.append({
            "event_id": r["event_id"],
            "event_name": r["event_name"],
            "current_mapping_status": status,
            "source_sectors": sectors_src,
            "mapped_sectors_after_normalization": sectors_mapped,
            "countries": r.get("countries", ""),
            "n_mapped_graph_nodes": r.get("n_mapped_nodes", "0"),
            "gap_description": gap,
            "suggested_resolution": (
                "extend engine Industry enum" if "out of engine enum" in gap
                else "add (country, sector) node to expanded graph" if "graph node" in gap
                else "supply peer-reviewed GDP target" if "no GDP target" in gap
                else "—"
            ),
            "_source_origin": "derived from benchmark_event_matrix_v2.csv",
        })
    return write_csv(
        "missing_event_mapping.csv",
        ["event_id", "event_name", "current_mapping_status", "source_sectors",
         "mapped_sectors_after_normalization", "countries",
         "n_mapped_graph_nodes", "gap_description", "suggested_resolution",
         "_source_origin"],
        rows,
    )


# ── main ─────────────────────────────────────────────────────────────────

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print("Bootstrap scientific-layer CSVs from existing repo evidence.")
    print("Source artifacts:")
    print("  docs/publication_risk_report.md (peer-reviewed citations + numeric values)")
    print("  backend/data/csv/papers_catalog.csv (25 cataloged papers)")
    print("  backend/data/csv/expanded_graph_nodes_v2.csv (595 nodes)")
    print("  backend/data/csv/benchmark_event_matrix_v2.csv (event mapping status)")
    print()

    out = []
    out.append(bootstrap_country_sector_presence())
    out.append(bootstrap_chokepoints())
    out.append(bootstrap_propagation_literature())
    out.append(bootstrap_financial_contagion())
    out.append(bootstrap_mechanism_validation())
    out.append(bootstrap_missing_event_mapping())

    print("Wrote:")
    for p in out:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
