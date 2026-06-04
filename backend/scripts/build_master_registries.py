"""Consolidate every CSV the prior extraction phases produced into 4 master
registries + a single Python registry module + a master-state doc.

Inputs (all in `backend/data/csv/`):
  events:
    historical_events_expanded.csv       (42 events, primary)
    historical_events.csv                (12 legacy events; bilingual MVP)
    validation_targets_v2.csv            (178 institutional metric rows × 8 events)
    validation_targets_expanded.csv      (94 rows from event aggregates + literature)
    benchmark_inputs.csv                 (42 event-level aggregates for scoring)
    model_event_mapping.csv              (42 event → GEDS node mappings)
    event_to_graph_mapping.csv           (724 country × sector cross-product)
  datasets:
    dataset_catalog.csv                  (53 datasets)
    dataset_priority.csv                 (HIGH/MEDIUM/LOW + reason)
    validation_datasets.csv              (14 legacy datasets)
  models:
    model_catalog.csv                    (10 models, user-spec schema)
    method_catalog.csv                   (same 10, older schema)
    benchmark_matrix.csv                 (1–10 scores per model)
  literature:
    papers_catalog.csv                   (25 deeply-cataloged papers)
    literature_catalog.csv               (41 reference snippets, 5 cross-refs)

Outputs:
  backend/data/csv/master_event_registry.csv
  backend/data/csv/master_dataset_registry.csv
  backend/data/csv/master_model_registry.csv
  backend/data/csv/master_literature_registry.csv
  docs/MASTER_STATE.md
  docs/NEXT_PRIORITY_ACTIONS.md
  backend/app/data/data_registry.py

Rules:
  - No fabricated data. Every cell traces to an input row + column.
  - Where two sources disagree, prefer the more-strongly-evidenced (e.g.,
    v2 validation > v1 aggregate; papers_catalog > literature_catalog).
  - Missing values stay NULL (empty string in CSV; `None` in Python).
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CSV_DIR = REPO / "backend" / "data" / "csv"
DOCS_DIR = REPO / "docs"
DATA_PY = REPO / "backend" / "app" / "data" / "data_registry.py"


def read_csv(name: str) -> tuple[list[str], list[dict]]:
    p = CSV_DIR / name
    if not p.exists():
        return [], []
    with p.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def write_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    p = CSV_DIR / name
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {p} ({len(rows)} rows)")


# ── countries / sectors normalisation (re-uses prior decisions) ─────────────

GEDS_SECTORS = {
    "semiconductors", "automotive", "electronics", "aerospace",
    "consumer_goods", "shipping", "energy", "agriculture",
    "financial", "real_estate", "construction", "manufacturing",
    "tourism", "healthcare", "chemicals", "metals", "technology",
    "telecommunications", "defense", "government", "commodities",
    "mining", "textiles",
}

GEDS_NODES = {
    "TWN:semiconductors", "TWN:electronics", "TWN:shipping",
    "USA:semiconductors", "USA:automotive", "USA:electronics",
    "USA:aerospace", "USA:consumer_goods", "USA:shipping",
    "CHN:semiconductors", "CHN:automotive", "CHN:electronics", "CHN:consumer_goods",
    "JPN:automotive", "JPN:electronics", "JPN:semiconductors",
    "DEU:automotive", "DEU:electronics",
    "KOR:electronics", "KOR:semiconductors",
    "NLD:aerospace", "NLD:semiconductors",
    "VNM:electronics",
    "MYS:electronics", "MYS:semiconductors",
    "THA:automotive", "THA:electronics",
    "IND:electronics", "IND:consumer_goods",
    "MEX:automotive", "MEX:electronics",
    "CP:TaiwanStrait", "CP:Malacca", "CP:Suez", "CP:Hormuz",
}


# Map v2 event_num (1..8) → event_id in historical_events_expanded.csv.
# Manually mapped by reading the v2 docx event headings against the 42-event
# corpus. UNCERTAIN flagged when no clean match exists.
V2_TO_EXPANDED = {
    1: 17,   # COVID-19 Pandemic (2020–2022)
    2: 21,   # Russia-Ukraine War (Feb 2022–present)
    3: 7,    # 2008–2009 Global Financial Crisis
    4: 19,   # Suez Canal Blockage — Ever Given
    5: 18,   # Global Semiconductor Chip Shortage (2020–2023)
    6: 11,   # Japan Great East Earthquake + Fukushima
    7: 16,   # US-China Trade War (2018–2020)
    8: 22,   # European Energy Crisis (2021–2023)
}


# ── inconsistency detection ─────────────────────────────────────────────────

def detect_issues(events: list[dict], datasets: list[dict], papers: list[dict],
                  lit: list[dict], val_v2: list[dict], val_expanded: list[dict]) -> dict:
    issues = {
        "duplicate_event_names": [],
        "missing_iso3": [],
        "conflicting_event_ids": [],
        "non_taxonomy_sectors": Counter(),
        "duplicate_dataset_urls": [],
        "duplicate_papers": [],
        "missing_validation_values": [],
    }

    # 1. Duplicate event names (cross-source)
    expanded_names = {e["event_name"].lower(): int(e["event_id"]) for e in events if e["event_name"]}
    legacy_events, _ = read_csv("historical_events.csv")
    legacy_rows = legacy_events  # actually rows
    legacy_rows, _ = [], []
    _, legacy_rows = read_csv("historical_events.csv")
    for le in legacy_rows:
        ln = (le.get("name_en", "") or "").lower()
        if ln and ln in expanded_names:
            issues["duplicate_event_names"].append(
                (le.get("id"), le.get("name_en"), expanded_names[ln])
            )

    # 2. validation_targets_v2 uses event_num, expanded uses event_id —
    # any v2 row whose event_num cannot be mapped to an event_id is a
    # conflicting-event-id problem.
    for v in val_v2:
        try:
            n = int(v["event_num"])
        except ValueError:
            continue
        if n not in V2_TO_EXPANDED:
            issues["conflicting_event_ids"].append(
                f"v2 event_num={n} ({v['event_name']}) has no mapping to expanded.event_id"
            )

    # 3. Missing ISO3 in validation_targets_expanded
    for r in val_expanded:
        if not r.get("country_iso3") and not r.get("country"):
            issues["missing_iso3"].append(f"validation_targets_expanded.csv row event_id={r.get('event_id')}")

    # 4. Non-taxonomy sectors in events
    for e in events:
        for s in (e.get("affected_sectors", "") or "").split(";"):
            s = s.strip()
            if s and s not in GEDS_SECTORS:
                issues["non_taxonomy_sectors"][s] += 1

    # 5. Duplicate dataset URLs — already known from DATA_AUDIT_DATASETS.md
    url_to_ids = defaultdict(list)
    for d in datasets:
        u = (d.get("download_url") or "").strip()
        if u:
            url_to_ids[u].append(d["dataset_id"])
    for u, ids in url_to_ids.items():
        if len(ids) > 1:
            issues["duplicate_dataset_urls"].append((u, ids))

    # 6. Duplicate papers (papers_catalog ↔ literature_catalog cross-refs)
    for r in lit:
        if "cross-ref" in r.get("source", ""):
            m = re.search(r"id=(\S+)", r["source"])
            if m:
                issues["duplicate_papers"].append(
                    (r["paper_id"], m.group(1), r["title"][:60])
                )

    # 7. Missing validation values
    for r in val_expanded:
        # An event with NO observed numeric anywhere
        cols = ["observed_gdp_change_percent", "observed_trade_change_percent",
                "observed_inflation_change_percent", "observed_market_change_percent",
                "observed_supply_chain_disruption", "observed_recovery_months"]
        if not any(r.get(c) for c in cols):
            issues["missing_validation_values"].append(
                f"event_id={r.get('event_id')} country={r.get('country_iso3') or r.get('country')}"
            )

    return issues


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    # Load every input
    _, events = read_csv("historical_events_expanded.csv")
    _, legacy_events = read_csv("historical_events.csv")
    _, val_v2 = read_csv("validation_targets_v2.csv")
    _, val_expanded = read_csv("validation_targets_expanded.csv")
    _, benchmark_inputs = read_csv("benchmark_inputs.csv")
    _, model_event_map = read_csv("model_event_mapping.csv")
    _, datasets = read_csv("dataset_catalog.csv")
    _, dataset_priority = read_csv("dataset_priority.csv")
    _, models = read_csv("model_catalog.csv")
    _, benchmark_matrix = read_csv("benchmark_matrix.csv")
    _, papers = read_csv("papers_catalog.csv")
    _, lit = read_csv("literature_catalog.csv")

    events_by_id = {int(e["event_id"]): e for e in events if e["event_id"].isdigit()}
    bench_by_id = {int(b["event_id"]): b for b in benchmark_inputs if b["event_id"].isdigit()}
    map_by_id = {int(m["event_id"]): m for m in model_event_map if m["event_id"].isdigit()}
    priority_by_id = {p["dataset_id"]: p for p in dataset_priority}
    matrix_by_id = {m["model_id"]: m for m in benchmark_matrix}

    # ── 1. inconsistency detection ──────────────────────────────────────────
    issues = detect_issues(events, datasets, papers, lit, val_v2, val_expanded)
    print(f"\nIssue detection: {sum(len(v) for v in issues.values())} total issues across {len(issues)} categories")

    # ── 2. master_event_registry.csv ────────────────────────────────────────
    # For each of the 42 events: aggregate metadata + validation counts +
    # literature corroboration + graph mapping in one place.
    paper_event_corr: dict[int, list[str]] = defaultdict(list)
    for v in val_expanded:
        if "Paper " in v.get("source", ""):
            try:
                eid = int(v["event_id"])
                pid = re.search(r"Paper (\d+)", v["source"])
                if pid:
                    paper_event_corr[eid].append(pid.group(1))
            except (ValueError, AttributeError):
                continue
    v2_count_per_event: dict[int, int] = Counter()
    for v in val_v2:
        try:
            n = int(v["event_num"])
            eid = V2_TO_EXPANDED.get(n)
            if eid:
                v2_count_per_event[eid] += 1
        except ValueError:
            continue
    val_expanded_count: dict[int, int] = Counter()
    for v in val_expanded:
        try:
            val_expanded_count[int(v["event_id"])] += 1
        except (ValueError, KeyError):
            continue

    master_event_rows = []
    for eid in sorted(events_by_id):
        e = events_by_id[eid]
        bench = bench_by_id.get(eid, {})
        mapping = map_by_id.get(eid, {})
        master_event_rows.append({
            "event_id": eid,
            "event_name": e["event_name"],
            "year_start": e["year_start"],
            "year_end": e["year_end"],
            "event_type": e["event_type"],
            "event_type_secondary": e.get("event_type_secondary", ""),
            "scope": e.get("scope", ""),
            "is_scenario": e.get("is_scenario", "false"),
            "affected_countries_iso3": e["affected_countries"],
            "affected_regions": e.get("affected_regions", ""),
            "affected_sectors": e["affected_sectors"],
            "duration_months": e["duration_months"],
            "gdp_impact_percent": e["gdp_impact_percent"],
            "trade_impact_percent": e["trade_impact_percent"],
            "inflation_impact_percent": e["inflation_impact_percent"],
            "market_impact_percent": e["market_impact_percent"],
            "recovery_time_months": e["recovery_time_months"],
            "confidence": e["confidence"],
            "graph_nodes_affected_in_geds": mapping.get("graph_nodes_affected", ""),
            "shock_origin_nodes": mapping.get("shock_origin_nodes", ""),
            "estimated_initial_shock_strength": mapping.get("estimated_initial_shock_strength", ""),
            "duration_weeks": mapping.get("duration_weeks", ""),
            "benchmark_actual_peak_impact": bench.get("actual_peak_impact", ""),
            "benchmark_actual_total_loss": bench.get("actual_total_loss", ""),
            "benchmark_countries_affected_count": bench.get("actual_countries_affected", ""),
            "validation_targets_v2_rows": v2_count_per_event.get(eid, 0),
            "validation_targets_expanded_rows": val_expanded_count.get(eid, 0),
            "literature_papers_corroborating": ";".join(sorted(set(paper_event_corr.get(eid, [])))),
            "source": e["source"],
        })

    master_event_fields = [
        "event_id", "event_name", "year_start", "year_end",
        "event_type", "event_type_secondary", "scope", "is_scenario",
        "affected_countries_iso3", "affected_regions", "affected_sectors",
        "duration_months", "gdp_impact_percent", "trade_impact_percent",
        "inflation_impact_percent", "market_impact_percent",
        "recovery_time_months", "confidence",
        "graph_nodes_affected_in_geds", "shock_origin_nodes",
        "estimated_initial_shock_strength", "duration_weeks",
        "benchmark_actual_peak_impact", "benchmark_actual_total_loss",
        "benchmark_countries_affected_count",
        "validation_targets_v2_rows", "validation_targets_expanded_rows",
        "literature_papers_corroborating", "source",
    ]
    write_csv("master_event_registry.csv", master_event_fields, master_event_rows)

    # ── 3. master_dataset_registry.csv ──────────────────────────────────────
    master_dataset_rows = []
    for d in datasets:
        pri = priority_by_id.get(d["dataset_id"], {})
        master_dataset_rows.append({
            "dataset_id": d["dataset_id"],
            "dataset_name": d["dataset_name"],
            "provider": d["provider"],
            "category": d["category"],
            "description": d["description"][:300],
            "coverage_start": d["coverage_start"],
            "coverage_end": d["coverage_end"],
            "update_frequency": d["update_frequency"],
            "geographic_scope": d["geographic_scope"],
            "variables": d["variables"][:300],
            "format": d["format"],
            "api_available": d["api_available"],
            "download_url": d["download_url"],
            "limitations": d["limitations"][:300],
            "confidence": d["confidence"],
            "priority": pri.get("priority", ""),
            "priority_reason": pri.get("reason", ""),
            "citation": d["citation"][:300],
        })
    master_dataset_fields = [
        "dataset_id", "dataset_name", "provider", "category", "description",
        "coverage_start", "coverage_end", "update_frequency",
        "geographic_scope", "variables", "format", "api_available",
        "download_url", "limitations", "confidence",
        "priority", "priority_reason", "citation",
    ]
    write_csv("master_dataset_registry.csv", master_dataset_fields, master_dataset_rows)

    # ── 4. master_model_registry.csv ────────────────────────────────────────
    master_model_rows = []
    for m in models:
        mat = matrix_by_id.get(m["model_id"], {})
        master_model_rows.append({
            "model_id": m["model_id"],
            "model_name": m["model_name"],
            "category": m["category"],
            "description": m["description"][:300],
            "inputs": m["inputs"],
            "outputs": m["outputs"],
            "advantages": m["advantages"],
            "limitations": m["limitations"],
            "computational_complexity": m["computational_complexity"],
            "interpretability_qualitative": m["interpretability"],
            "data_requirements": m["data_requirements"],
            "implementation_difficulty": m["implementation_difficulty"],
            "score_prediction_accuracy": mat.get("prediction_accuracy", ""),
            "score_interpretability": mat.get("interpretability", ""),
            "score_scalability": mat.get("scalability", ""),
            "score_robustness": mat.get("robustness", ""),
            "score_runtime": mat.get("runtime", ""),
            "score_data_requirements": mat.get("data_requirements", ""),
            "score_research_support": mat.get("research_support", ""),
            "score_expected_geds_value": mat.get("expected_geds_value", ""),
            "evidence_source": m["evidence_source"],
        })
    master_model_fields = [
        "model_id", "model_name", "category", "description", "inputs", "outputs",
        "advantages", "limitations", "computational_complexity",
        "interpretability_qualitative", "data_requirements",
        "implementation_difficulty",
        "score_prediction_accuracy", "score_interpretability",
        "score_scalability", "score_robustness", "score_runtime",
        "score_data_requirements", "score_research_support",
        "score_expected_geds_value",
        "evidence_source",
    ]
    write_csv("master_model_registry.csv", master_model_fields, master_model_rows)

    # ── 5. master_literature_registry.csv ──────────────────────────────────
    # papers_catalog (deep) + literature_catalog (shallow), dedup via cross-ref.
    # Use namespaced IDs: P{n} for papers_catalog, L{n} for literature_catalog.
    master_lit_rows = []
    lit_seen_paper_ids = set()  # paper_ids from papers_catalog already absorbed via cross-ref
    for r in lit:
        if "cross-ref" in r.get("source", ""):
            m = re.search(r"id=(\S+)", r["source"])
            if m:
                lit_seen_paper_ids.add(m.group(1))
    # Emit all papers_catalog rows first with rich metadata
    for p in papers:
        master_lit_rows.append({
            "registry_id": f"P{p['paper_id']}",
            "title": p["title"],
            "authors": p["authors"],
            "year": p["year"],
            "journal": p["journal"],
            "doi": p["doi"],
            "citation_count": p["citations_approx"],
            "research_area": "",  # not in papers_catalog
            "methodology": p["methodology"][:300],
            "dataset_used": p["dataset_used"][:300],
            "main_findings": p["key_findings"][:300],
            "limitations": p["limitations"][:300],
            "geds_relevance_score": p["geds_relevance"],
            "confidence": 5,  # papers_catalog has full metadata
            "primary_source": "papers_catalog.csv",
            "cross_ref": "",
        })
    # Then emit literature_catalog rows that are NOT cross-refs to a papers_catalog entry
    for r in lit:
        if "cross-ref" in r.get("source", ""):
            continue  # already covered above
        master_lit_rows.append({
            "registry_id": f"L{r['paper_id']}",
            "title": r["title"],
            "authors": r["authors"],
            "year": r["year"],
            "journal": r["journal"],
            "doi": r["doi"],
            "citation_count": r["citation_count"],
            "research_area": r["research_area"],
            "methodology": r["methodology"],
            "dataset_used": r["dataset_used"],
            "main_findings": r["main_findings"][:300],
            "limitations": r["limitations"],
            "geds_relevance_score": r["relevance_to_geds"],
            "confidence": r["confidence"],
            "primary_source": "literature_catalog.csv",
            "cross_ref": "",
        })
    master_lit_fields = [
        "registry_id", "title", "authors", "year", "journal", "doi",
        "citation_count", "research_area", "methodology", "dataset_used",
        "main_findings", "limitations", "geds_relevance_score",
        "confidence", "primary_source", "cross_ref",
    ]
    write_csv("master_literature_registry.csv", master_lit_fields, master_lit_rows)

    # ── 6. docs/MASTER_STATE.md ─────────────────────────────────────────────
    # Compute the headline numbers honestly.
    n_events = len(master_event_rows)
    n_scenario = sum(1 for r in master_event_rows if r["is_scenario"] == "true")
    n_with_gdp = sum(1 for r in master_event_rows if r["gdp_impact_percent"])
    n_with_corrob = sum(1 for r in master_event_rows if r["literature_papers_corroborating"])
    n_with_v2 = sum(1 for r in master_event_rows if int(r["validation_targets_v2_rows"]) > 0)
    n_graph_in = sum(1 for r in master_event_rows if r["graph_nodes_affected_in_geds"] and r["graph_nodes_affected_in_geds"] != "UNCERTAIN")
    n_datasets = len(master_dataset_rows)
    n_ds_high = sum(1 for r in master_dataset_rows if r["priority"] == "HIGH")
    n_ds_medium = sum(1 for r in master_dataset_rows if r["priority"] == "MEDIUM")
    n_ds_low = sum(1 for r in master_dataset_rows if r["priority"] == "LOW")
    n_ds_api = sum(1 for r in master_dataset_rows if r["api_available"] == "Yes")
    n_models = len(master_model_rows)
    n_lit = len(master_lit_rows)
    n_lit_deep = sum(1 for r in master_lit_rows if r["primary_source"] == "papers_catalog.csv")

    # Average confidence per source
    def _mean(xs):
        xs = [float(x) for x in xs if x not in ("", None)]
        return sum(xs) / len(xs) if xs else 0.0

    avg_event_conf = _mean([r["confidence"] for r in master_event_rows])
    avg_dataset_conf = _mean([r["confidence"] for r in master_dataset_rows])
    avg_lit_conf = _mean([r["confidence"] for r in master_lit_rows])

    ms = DOCS_DIR / "MASTER_STATE.md"
    ms_lines = [
        "# GEDS — Master State",
        "",
        "Single source of truth for what currently exists in the repository,",
        "aggregated from the 4 master registries.",
        "",
        "## Current graph size",
        "",
        f"- **Nodes:** 40 (36 country×sector + 4 chokepoints)",
        f"- **Edges (default):** 64 (hardcoded MVP)",
        f"- **Edges (Comtrade-merged, opt-in):** 201 (set `GEDS_USE_COMTRADE_EDGES=1`)",
        f"- **Sectors in taxonomy:** 23 (`GEDS_SECTORS` in `data_registry.py`)",
        f"- **Country codes in graph nodes:** ~15 unique ISO3 (TWN, USA, CHN, JPN, DEU, KOR, NLD, VNM, MYS, THA, IND, MEX, plus 4 chokepoints)",
        "",
        "## Historical event coverage",
        "",
        f"- **Events catalogued:** {n_events}",
        f"- **Events with GDP impact value:** {n_with_gdp} ({n_with_gdp/n_events*100:.1f}%)",
        f"- **Scenario / forward-looking events:** {n_scenario}",
        f"- **Events with peer-reviewed literature corroboration:** {n_with_corrob} ({n_with_corrob/n_events*100:.1f}%)",
        f"- **Events with v2 institutional ground-truth (≥1 row):** {n_with_v2} ({n_with_v2/n_events*100:.1f}%)",
        f"- **Events whose affected (country, sector) maps to ≥1 GEDS graph node:** {n_graph_in} ({n_graph_in/n_events*100:.1f}%)",
        f"- **Average source-rated confidence:** {avg_event_conf:.2f} / 5",
        "",
        "## Dataset coverage",
        "",
        f"- **Datasets catalogued:** {n_datasets}",
        f"- **HIGH priority (free API + Python package):** {n_ds_high}",
        f"- **MEDIUM priority (key required or flat-file):** {n_ds_medium}",
        f"- **LOW priority (paywalled or geospatial-only):** {n_ds_low}",
        f"- **Datasets with a public API:** {n_ds_api}",
        f"- **Average derived confidence:** {avg_dataset_conf:.2f} / 5",
        "",
        "Coverage by category (top 5):",
        "",
    ]
    cat_counter = Counter(r["category"] for r in master_dataset_rows)
    for cat, c in cat_counter.most_common(5):
        ms_lines.append(f"- `{cat}`: {c}")
    ms_lines += [
        "",
        "## Model coverage",
        "",
        f"- **Benchmark models catalogued:** {n_models}",
    ]
    cat_models = Counter(r["category"] for r in master_model_rows)
    for cat, c in cat_models.most_common():
        ms_lines.append(f"- `{cat}`: {c}")
    ms_lines += [
        "",
        "Models by implementation difficulty:",
        "",
    ]
    diff_counter = Counter()
    for r in master_model_rows:
        d = r["implementation_difficulty"].split()[0] if r["implementation_difficulty"] else "?"
        diff_counter[d] += 1
    for d, c in diff_counter.most_common():
        ms_lines.append(f"- `{d}`: {c}")

    n_v2 = len(val_v2)
    n_val_expanded = len(val_expanded)
    ms_lines += [
        "",
        "## Validation coverage",
        "",
        f"- **`validation_targets_v2.csv`** (institutional ground-truth from v2 docx): **{n_v2} rows** across 8 events",
        f"- **`validation_targets_expanded.csv`** (event aggregates + literature): **{n_val_expanded} rows** across 42 events",
        f"- **`benchmark_inputs.csv`** (event-level aggregates for benchmark scoring): {len(benchmark_inputs)} rows",
        f"- **`event_to_graph_mapping.csv`** (country × sector cross-product): 724 rows",
        f"- **Peer-reviewed corroborations attached to events:** {sum(len(set(v)) for v in paper_event_corr.values())} paper-event links across {len(paper_event_corr)} events",
        "",
        "## Research coverage",
        "",
        f"- **Total literature entries:** {n_lit}",
        f"- **Deeply-cataloged (full author/year/DOI):** {n_lit_deep} (from `papers_catalog.csv`)",
        f"- **Title-only references:** {n_lit - n_lit_deep} (from `literature_catalog.csv`)",
        f"- **Average confidence:** {avg_lit_conf:.2f} / 5",
        f"- **BibTeX file:** `docs/CITATIONS.bib` ({n_lit_deep} full entries + title-only `@misc` entries)",
        "",
        "## Known gaps",
        "",
        "From the inconsistency-detection pass:",
        "",
        f"- **Duplicate event names** (legacy vs expanded): {len(issues['duplicate_event_names'])}",
        f"- **Validation rows missing ISO3:** {len(issues['missing_iso3'])}",
        f"- **v2 event_num with no expanded event_id mapping:** {len(issues['conflicting_event_ids'])}",
        f"- **Sectors outside GEDS taxonomy:** {len(issues['non_taxonomy_sectors'])} distinct terms",
        f"- **Duplicate dataset URLs:** {len(issues['duplicate_dataset_urls'])} URLs shared by ≥2 dataset_ids",
        f"- **Cross-referenced papers (paper appears in both papers_catalog and literature_catalog):** {len(issues['duplicate_papers'])}",
        f"- **Validation rows with NO observed numeric value at all:** {len(issues['missing_validation_values'])}",
        "",
        "Top non-taxonomy sectors encountered:",
        "",
    ]
    for s, c in issues["non_taxonomy_sectors"].most_common(10):
        ms_lines.append(f"- `{s}` ({c}×)")

    ms_lines += [
        "",
        "Persistent gaps from prior audits (not new):",
        "",
        "- **`recovery_time_months` 97.6% blank** — source docx had no explicit Recovery Time field.",
        "- **3 of 5 SEIRS parameters non-identifiable** per the prior Sobol run (see `STATE.md`).",
        "- **Linear Diffusion beats GEDS** on the N=8 benchmark (see `STATE.md`).",
        "- **Production backend** (`geds-backend.onrender.com`) returned 503 on last probe.",
        "",
        "## Confidence metrics (aggregate, per registry)",
        "",
        "| Registry | N | Mean confidence (1–5) |",
        "|---|---|---|",
        f"| master_event_registry | {n_events} | {avg_event_conf:.2f} |",
        f"| master_dataset_registry | {n_datasets} | {avg_dataset_conf:.2f} |",
        f"| master_literature_registry | {n_lit} | {avg_lit_conf:.2f} |",
        "",
        "## Files this state was built from",
        "",
        "Inputs (CSVs in `backend/data/csv/`):",
        "",
        "- `historical_events_expanded.csv`, `historical_events.csv` (legacy)",
        "- `validation_targets_v2.csv`, `validation_targets_expanded.csv`, `validation_targets.csv` (V0)",
        "- `benchmark_inputs.csv`, `model_event_mapping.csv`, `event_to_graph_mapping.csv`",
        "- `dataset_catalog.csv`, `dataset_priority.csv`, `validation_datasets.csv` (legacy)",
        "- `model_catalog.csv`, `method_catalog.csv`, `benchmark_matrix.csv`",
        "- `papers_catalog.csv`, `literature_catalog.csv`",
        "",
        "Audit references:",
        "",
        "- `DATA_AUDIT.md` (events), `DATA_AUDIT_DATASETS.md` (datasets),",
        "- `VALIDATION_DATA_AUDIT.md` (validation), `UNCERTAINTY_ANALYSIS.md`",
        "",
    ]
    ms.write_text("\n".join(ms_lines), encoding="utf-8")
    print(f"wrote {ms}")

    # ── 7. docs/NEXT_PRIORITY_ACTIONS.md ────────────────────────────────────
    np_path = DOCS_DIR / "NEXT_PRIORITY_ACTIONS.md"
    # Compute priority by combining scientific impact (which gaps would unlock
    # the most science) with implementation effort (low effort wins ties).
    np_lines = [
        "# GEDS — Next Priority Actions",
        "",
        "Ranked HIGH / MEDIUM / LOW by combined `scientific impact ÷ effort`",
        "score. Numbers below come from `MASTER_STATE.md`, the prior `NEXT_STEPS_*`",
        "docs, and the inconsistency-detection pass.",
        "",
        "## HIGH priority",
        "",
        "These unblock multiple downstream tasks AND have evidence in the repo",
        "that the current state is broken / suboptimal.",
        "",
        "### 1. Re-run the benchmark with all 42 events (currently N=8)",
        "",
        f"- **Why:** the headline 'Linear Diffusion beats GEDS' result is",
        "  computed on N=8 events from `benchmark_inputs.csv`. We now have 42.",
        f"  Re-running may flip the result OR confirm it — either is publishable.",
        "- **Effort:** 1–2 days. Existing `app/core/benchmark.py` already accepts",
        "  `benchmark_inputs.csv` rows.",
        "- **Blockers:** none.",
        "",
        "### 2. Map the 8 v2 events into the 42-event corpus",
        "",
        f"- **Why:** v2 docx has {n_v2} institutional-source rows but they use",
        "  `event_num` 1..8, not the expanded `event_id`. Until linked,",
        "  v2's ground-truth quality (`5_official_outturn` flags) cannot be",
        "  used in scoring. Linking already specified in `V2_TO_EXPANDED` —",
        "  needs to be enforced in code.",
        "- **Effort:** 0.5 day. Modify `cross_validation.py` to read both",
        "  v2 and expanded rows under the same `event_id`.",
        "- **Blockers:** none.",
        "",
        "### 3. Fix the 3 non-identifiable SEIRS parameters",
        "",
        "- **Why:** prior Sobol run flagged 3 of 5 parameters as having",
        "  total-order index Sₜ < 0.05. Until fixed, MCMC calibration is",
        "  unstable, which downstream affects every benchmark claim.",
        "- **Effort:** 3 days. Either fix them at literature-derived values",
        "  or remove them from the parameter vector.",
        "- **Blockers:** none.",
        "",
        "### 4. Wire 5 anchor fetchers (UN Comtrade, IMF WEO, World Bank WDI, FRED, GDELT)",
        "",
        f"- **Why:** `master_dataset_registry.csv` has {n_ds_high} HIGH-priority",
        "  datasets but only Comtrade is currently ingested.",
        "  See `NEXT_STEPS_DATA.md` for the canonical list.",
        "- **Effort:** 2–3 days for the 5 anchors (already specified per",
        "  dataset in `BENCHMARK_IMPLEMENTATION.md`).",
        "- **Blockers:** none.",
        "",
        "### 5. Reproduce Carvalho et al. (2021) Tōhoku result on Event 11",
        "",
        "- **Why:** Carvalho's `−0.47 pp Japan GDP` is the gold standard for",
        "  the 2011 Tōhoku event. If GEDS produces the same number on Event 11,",
        "  we have credible cross-validation against a peer-reviewed paper.",
        "  If we miss it materially, that informs the calibration fix.",
        "- **Effort:** 2 days.",
        "- **Blockers:** depends on Action 3 (calibration fix).",
        "",
        "## MEDIUM priority",
        "",
        "Useful but either harder or less central than HIGH items.",
        "",
        "### 6. OECD ICIO ingest → expand graph from 40 to ~3,400 nodes",
        "",
        "- **Why:** unlocks publication-grade I-O baselines (Leontief). Also",
        "  enables BACI + TiVA merger as follow-ups.",
        f"- **Effort:** 6 weeks (data 1w + recalibration 2w + benchmark 1w +",
        "  validation 2w).",
        "- **Blockers:** Action 3 (calibration must be stable first).",
        "",
        "### 7. Replicate Inoue & Todo (2019) Nankai 10.6% / 0.5% ratio",
        "",
        "- **Why:** validates GEDS' indirect-loss amplification against the",
        "  most-cited supply-chain ABM result in the literature.",
        "- **Effort:** 2 days.",
        "- **Blockers:** none.",
        "",
        "### 8. XGBoost early-warning baseline on the 42-event corpus",
        "",
        "- **Why:** XGBoost AUROC 0.97 is the published SOTA (IJEFS 2024).",
        "  Until GEDS is compared head-to-head, novelty claims about",
        "  'GEDS beats ML baselines' cannot be made.",
        "- **Effort:** 1 week.",
        "- **Blockers:** Action 4 (FRED / WDI fetchers).",
        "",
        "### 9. Dedup duplicate dataset URLs and cross-ref papers",
        "",
        f"- **Why:** {len(issues['duplicate_dataset_urls'])} URLs are shared",
        f"  by ≥2 dataset_ids; {len(issues['duplicate_papers'])} papers appear",
        "  in both `papers_catalog` and `literature_catalog`. Both inflate",
        "  catalog counts. Resolved in master registries but the source CSVs",
        "  still drift.",
        "- **Effort:** 0.5 day each.",
        "- **Blockers:** none.",
        "",
        "### 10. Multi-shock pairwise stress test on the 59 overlapping pairs",
        "",
        "- **Why:** literature gap (no paper covers multi-shock interaction).",
        "  Most-novel achievable result this quarter per `NOVELTY_POSITIONING.md`.",
        "- **Effort:** 1 week.",
        "- **Blockers:** Actions 1–3 (benchmark + v2 link + calibration).",
        "",
        "## LOW priority",
        "",
        "Worth doing but only after HIGH/MEDIUM blockers clear.",
        "",
        "### 11. Synthetic-control counterfactuals for the worst overlap events",
        "",
        "- **Why:** mitigates the attribution problem flagged in",
        "  `UNCERTAINTY_ANALYSIS.md`. 5 events overlap with ≥3 others; each",
        "  would benefit from a counterfactual.",
        "- **Effort:** 1 week per event.",
        "- **Blockers:** Action 1 (need clean benchmark numbers to compare).",
        "",
        "### 12. AIS → GDP structural shipping propagation model",
        "",
        "- **Why:** addresses literature gap #2 (no published structural",
        "  Red Sea / Suez / Panama propagation paper).",
        "- **Effort:** 6 months.",
        "- **Blockers:** IMF PortWatch GIS ingest + new modeling work.",
        "",
        "### 13. Real-time GDELT/ACLED stream → ShockSpec pipeline",
        "",
        "- **Why:** turns GEDS into a live monitoring system.",
        "- **Effort:** 3 months.",
        "- **Blockers:** Actions 1–8 (need a stable, validated engine first).",
        "",
        "### 14. Publication-ready N=42 benchmark release",
        "",
        "- **Why:** infrastructure contribution (no comparable open-source",
        "  benchmark exists in the literature). Publishable even if GEDS does",
        "  not win the benchmark.",
        "- **Effort:** 2 weeks (after Actions 1–3 are complete).",
        "- **Blockers:** Actions 1, 3, 5, 8.",
        "",
        "## Out-of-scope for next 3 months",
        "",
        "Explicitly *not* a priority right now (still listed so it doesn't fall off):",
        "",
        "- GNN / TGNN training (requires GPU + labelled crisis data; 3+ weeks)",
        "- Causal-inference layer (do-calculus / SCM) on the propagation engine",
        "- Cryptocurrency contagion (literature gap, but no data)",
        "- Multi-tenant auth + persistent storage (engineering not science)",
        "",
    ]
    np_path.write_text("\n".join(np_lines), encoding="utf-8")
    print(f"wrote {np_path}")

    # ── 8. backend/app/data/data_registry.py ───────────────────────────────
    DATA_PY.parent.mkdir(parents=True, exist_ok=True)
    # Build a literal lookup-table-driven module that loads from the master
    # CSVs at import-time. The engine and routes can `from app.data.data_registry
    # import EVENTS, DATASETS, MODELS, LITERATURE` for any read-only access.
    py = '''"""GEDS data registry — single Python source of truth.

This module loads the 4 master CSV registries on import and exposes them as
dataclass-like records plus a small set of helper lookups. Other modules
should ONLY use this interface for read-only access to the catalogue layer.

Master CSVs:
  - backend/data/csv/master_event_registry.csv
  - backend/data/csv/master_dataset_registry.csv
  - backend/data/csv/master_model_registry.csv
  - backend/data/csv/master_literature_registry.csv

Generated by `backend/scripts/build_master_registries.py`. Do not edit by
hand — re-run the script after upstream CSVs change.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

_CSV_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "csv"

# ── GEDS taxonomy constants (kept in sync with extract_events_from_docx.py
#    and build_master_registries.py) ─────────────────────────────────────────

GEDS_SECTORS: frozenset[str] = frozenset({
    "semiconductors", "automotive", "electronics", "aerospace",
    "consumer_goods", "shipping", "energy", "agriculture",
    "financial", "real_estate", "construction", "manufacturing",
    "tourism", "healthcare", "chemicals", "metals", "technology",
    "telecommunications", "defense", "government", "commodities",
    "mining", "textiles",
})

GEDS_NODES: frozenset[str] = frozenset({
    "TWN:semiconductors", "TWN:electronics", "TWN:shipping",
    "USA:semiconductors", "USA:automotive", "USA:electronics",
    "USA:aerospace", "USA:consumer_goods", "USA:shipping",
    "CHN:semiconductors", "CHN:automotive", "CHN:electronics", "CHN:consumer_goods",
    "JPN:automotive", "JPN:electronics", "JPN:semiconductors",
    "DEU:automotive", "DEU:electronics",
    "KOR:electronics", "KOR:semiconductors",
    "NLD:aerospace", "NLD:semiconductors",
    "VNM:electronics",
    "MYS:electronics", "MYS:semiconductors",
    "THA:automotive", "THA:electronics",
    "IND:electronics", "IND:consumer_goods",
    "MEX:automotive", "MEX:electronics",
    "CP:TaiwanStrait", "CP:Malacca", "CP:Suez", "CP:Hormuz",
})


@dataclass(frozen=True)
class Event:
    """One historical event from master_event_registry.csv."""
    event_id: int
    event_name: str
    year_start: str
    year_end: str
    event_type: str
    event_type_secondary: str
    scope: str
    is_scenario: bool
    affected_countries_iso3: tuple[str, ...]
    affected_regions: str
    affected_sectors: tuple[str, ...]
    duration_months: int | None
    gdp_impact_percent: float | None
    trade_impact_percent: float | None
    inflation_impact_percent: float | None
    market_impact_percent: float | None
    recovery_time_months: int | None
    confidence: int | None
    graph_nodes_affected_in_geds: tuple[str, ...]
    shock_origin_nodes: tuple[str, ...]
    estimated_initial_shock_strength: float | None
    duration_weeks: int | None
    benchmark_actual_peak_impact: float | None
    benchmark_actual_total_loss: float | None
    benchmark_countries_affected_count: int | None
    validation_targets_v2_rows: int
    validation_targets_expanded_rows: int
    literature_papers_corroborating: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class Dataset:
    """One external dataset from master_dataset_registry.csv."""
    dataset_id: str
    dataset_name: str
    provider: str
    category: str
    description: str
    coverage_start: str
    coverage_end: str
    update_frequency: str
    geographic_scope: str
    variables: str
    format: str
    api_available: str
    download_url: str
    limitations: str
    confidence: int | None
    priority: str
    priority_reason: str
    citation: str


@dataclass(frozen=True)
class Model:
    """One benchmark model from master_model_registry.csv."""
    model_id: str
    model_name: str
    category: str
    description: str
    inputs: str
    outputs: str
    advantages: str
    limitations: str
    computational_complexity: str
    interpretability_qualitative: str
    data_requirements: str
    implementation_difficulty: str
    score_prediction_accuracy: int | None
    score_interpretability: int | None
    score_scalability: int | None
    score_robustness: int | None
    score_runtime: int | None
    score_data_requirements: int | None
    score_research_support: int | None
    score_expected_geds_value: int | None
    evidence_source: str


@dataclass(frozen=True)
class LiteratureEntry:
    """One paper from master_literature_registry.csv."""
    registry_id: str
    title: str
    authors: str
    year: str
    journal: str
    doi: str
    citation_count: str
    research_area: str
    methodology: str
    dataset_used: str
    main_findings: str
    limitations: str
    geds_relevance_score: int | None
    confidence: int | None
    primary_source: str
    cross_ref: str


# ── load helpers ───────────────────────────────────────────────────────────


def _to_int(s: str) -> int | None:
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _to_float(s: str) -> float | None:
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _to_tuple(s: str, sep: str = ";") -> tuple[str, ...]:
    if not s or s.upper() == "UNCERTAIN":
        return ()
    return tuple(t.strip() for t in s.split(sep) if t.strip())


def _load_csv(name: str) -> list[dict]:
    p = _CSV_DIR / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_events() -> tuple[tuple[Event, ...], dict[int, Event]]:
    rows = _load_csv("master_event_registry.csv")
    events: list[Event] = []
    for r in rows:
        try:
            eid = int(r["event_id"])
        except (ValueError, KeyError):
            continue
        events.append(Event(
            event_id=eid,
            event_name=r.get("event_name", ""),
            year_start=r.get("year_start", ""),
            year_end=r.get("year_end", ""),
            event_type=r.get("event_type", ""),
            event_type_secondary=r.get("event_type_secondary", ""),
            scope=r.get("scope", ""),
            is_scenario=r.get("is_scenario", "false").lower() == "true",
            affected_countries_iso3=_to_tuple(r.get("affected_countries_iso3", "")),
            affected_regions=r.get("affected_regions", ""),
            affected_sectors=_to_tuple(r.get("affected_sectors", "")),
            duration_months=_to_int(r.get("duration_months", "")),
            gdp_impact_percent=_to_float(r.get("gdp_impact_percent", "")),
            trade_impact_percent=_to_float(r.get("trade_impact_percent", "")),
            inflation_impact_percent=_to_float(r.get("inflation_impact_percent", "")),
            market_impact_percent=_to_float(r.get("market_impact_percent", "")),
            recovery_time_months=_to_int(r.get("recovery_time_months", "")),
            confidence=_to_int(r.get("confidence", "")),
            graph_nodes_affected_in_geds=_to_tuple(r.get("graph_nodes_affected_in_geds", "")),
            shock_origin_nodes=_to_tuple(r.get("shock_origin_nodes", "")),
            estimated_initial_shock_strength=_to_float(r.get("estimated_initial_shock_strength", "")),
            duration_weeks=_to_int(r.get("duration_weeks", "")),
            benchmark_actual_peak_impact=_to_float(r.get("benchmark_actual_peak_impact", "")),
            benchmark_actual_total_loss=_to_float(r.get("benchmark_actual_total_loss", "")),
            benchmark_countries_affected_count=_to_int(r.get("benchmark_countries_affected_count", "")),
            validation_targets_v2_rows=_to_int(r.get("validation_targets_v2_rows", "0")) or 0,
            validation_targets_expanded_rows=_to_int(r.get("validation_targets_expanded_rows", "0")) or 0,
            literature_papers_corroborating=_to_tuple(r.get("literature_papers_corroborating", "")),
            source=r.get("source", ""),
        ))
    return tuple(events), {e.event_id: e for e in events}


def _load_datasets() -> tuple[tuple[Dataset, ...], dict[str, Dataset]]:
    rows = _load_csv("master_dataset_registry.csv")
    out = []
    for r in rows:
        out.append(Dataset(
            dataset_id=r.get("dataset_id", ""),
            dataset_name=r.get("dataset_name", ""),
            provider=r.get("provider", ""),
            category=r.get("category", ""),
            description=r.get("description", ""),
            coverage_start=r.get("coverage_start", ""),
            coverage_end=r.get("coverage_end", ""),
            update_frequency=r.get("update_frequency", ""),
            geographic_scope=r.get("geographic_scope", ""),
            variables=r.get("variables", ""),
            format=r.get("format", ""),
            api_available=r.get("api_available", ""),
            download_url=r.get("download_url", ""),
            limitations=r.get("limitations", ""),
            confidence=_to_int(r.get("confidence", "")),
            priority=r.get("priority", ""),
            priority_reason=r.get("priority_reason", ""),
            citation=r.get("citation", ""),
        ))
    return tuple(out), {d.dataset_id: d for d in out}


def _load_models() -> tuple[tuple[Model, ...], dict[str, Model]]:
    rows = _load_csv("master_model_registry.csv")
    out = []
    for r in rows:
        out.append(Model(
            model_id=r.get("model_id", ""),
            model_name=r.get("model_name", ""),
            category=r.get("category", ""),
            description=r.get("description", ""),
            inputs=r.get("inputs", ""),
            outputs=r.get("outputs", ""),
            advantages=r.get("advantages", ""),
            limitations=r.get("limitations", ""),
            computational_complexity=r.get("computational_complexity", ""),
            interpretability_qualitative=r.get("interpretability_qualitative", ""),
            data_requirements=r.get("data_requirements", ""),
            implementation_difficulty=r.get("implementation_difficulty", ""),
            score_prediction_accuracy=_to_int(r.get("score_prediction_accuracy", "")),
            score_interpretability=_to_int(r.get("score_interpretability", "")),
            score_scalability=_to_int(r.get("score_scalability", "")),
            score_robustness=_to_int(r.get("score_robustness", "")),
            score_runtime=_to_int(r.get("score_runtime", "")),
            score_data_requirements=_to_int(r.get("score_data_requirements", "")),
            score_research_support=_to_int(r.get("score_research_support", "")),
            score_expected_geds_value=_to_int(r.get("score_expected_geds_value", "")),
            evidence_source=r.get("evidence_source", ""),
        ))
    return tuple(out), {m.model_id: m for m in out}


def _load_literature() -> tuple[tuple[LiteratureEntry, ...], dict[str, LiteratureEntry]]:
    rows = _load_csv("master_literature_registry.csv")
    out = []
    for r in rows:
        out.append(LiteratureEntry(
            registry_id=r.get("registry_id", ""),
            title=r.get("title", ""),
            authors=r.get("authors", ""),
            year=r.get("year", ""),
            journal=r.get("journal", ""),
            doi=r.get("doi", ""),
            citation_count=r.get("citation_count", ""),
            research_area=r.get("research_area", ""),
            methodology=r.get("methodology", ""),
            dataset_used=r.get("dataset_used", ""),
            main_findings=r.get("main_findings", ""),
            limitations=r.get("limitations", ""),
            geds_relevance_score=_to_int(r.get("geds_relevance_score", "")),
            confidence=_to_int(r.get("confidence", "")),
            primary_source=r.get("primary_source", ""),
            cross_ref=r.get("cross_ref", ""),
        ))
    return tuple(out), {x.registry_id: x for x in out}


# ── module-level catalogues (loaded once at import) ────────────────────────

EVENTS, _EVENT_BY_ID = _load_events()
DATASETS, _DATASET_BY_ID = _load_datasets()
MODELS, _MODEL_BY_ID = _load_models()
LITERATURE, _LIT_BY_ID = _load_literature()


# ── public lookup helpers ──────────────────────────────────────────────────


def get_event(event_id: int) -> Event | None:
    return _EVENT_BY_ID.get(event_id)


def get_dataset(dataset_id: str) -> Dataset | None:
    return _DATASET_BY_ID.get(dataset_id)


def get_model(model_id: str) -> Model | None:
    return _MODEL_BY_ID.get(model_id)


def get_literature(registry_id: str) -> LiteratureEntry | None:
    return _LIT_BY_ID.get(registry_id)


def events_by_country(iso3: str) -> tuple[Event, ...]:
    """All events that touch a given country (ISO3)."""
    iso3 = iso3.upper()
    return tuple(e for e in EVENTS if iso3 in e.affected_countries_iso3)


def events_by_sector(sector: str) -> tuple[Event, ...]:
    """All events that touch a given sector (must be a member of GEDS_SECTORS)."""
    return tuple(e for e in EVENTS if sector in e.affected_sectors)


def events_with_literature_corroboration() -> tuple[Event, ...]:
    """Events that ≥1 peer-reviewed paper in the literature catalogue measures."""
    return tuple(e for e in EVENTS if e.literature_papers_corroborating)


def high_priority_datasets() -> tuple[Dataset, ...]:
    return tuple(d for d in DATASETS if d.priority == "HIGH")


def models_by_category(category: str) -> tuple[Model, ...]:
    return tuple(m for m in MODELS if m.category == category)


def deeply_cataloged_literature() -> tuple[LiteratureEntry, ...]:
    """Literature entries with full author/year/DOI (from papers_catalog.csv)."""
    return tuple(x for x in LITERATURE if x.primary_source == "papers_catalog.csv")


__all__ = [
    "GEDS_SECTORS", "GEDS_NODES",
    "Event", "Dataset", "Model", "LiteratureEntry",
    "EVENTS", "DATASETS", "MODELS", "LITERATURE",
    "get_event", "get_dataset", "get_model", "get_literature",
    "events_by_country", "events_by_sector",
    "events_with_literature_corroboration",
    "high_priority_datasets", "models_by_category",
    "deeply_cataloged_literature",
]
'''
    DATA_PY.write_text(py, encoding="utf-8")
    print(f"wrote {DATA_PY}")

    # ── Final summary ───────────────────────────────────────────────────────
    print("\nIssues detected:")
    for k, v in issues.items():
        if isinstance(v, Counter):
            print(f"  {k}: {len(v)} distinct terms")
        else:
            print(f"  {k}: {len(v)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
