"""Extract the GEDS Literature Review docx into validation assets.

Source: D:/GEDS Literature Review  Peer-Reviewed Papers on Economic Shock
        Propagation, Network Analysis, and Crisis Modeling.docx
        dumped to backend/data/raw/literature_review_dump.json.

Honest note on scope: the source docx is a 25-paper academic literature
review, NOT a per-country crisis-observation database. It supplies:
  - paper-level quantitative findings (e.g. "Earthquake caused -0.47 pp
    Japan GDP" from Carvalho et al. 2021)
  - methodological references for GEDS validation choices
  - peer-reviewed corroboration tags for the 42 events extracted earlier

Outputs (all relative to repo root):
  backend/data/csv/papers_catalog.csv              — 25-paper transcription
  backend/data/csv/validation_targets_expanded.csv — events × countries with
                                                      per-row paper attribution
                                                      and paper-mined numbers
  backend/data/csv/model_event_mapping.csv         — event → graph nodes
  backend/data/csv/benchmark_inputs.csv            — event-level aggregates
                                                      for benchmark scoring
  docs/VALIDATION_PLAN.md                          — metrics + procedures
  docs/UNCERTAINTY_ANALYSIS.md                     — confidence/attribution
  docs/VALIDATION_DATA_AUDIT.md                    — quality issues
  docs/NEXT_STEPS_VALIDATION.md                    — implementation tasks

Rules:
  - No invented numbers. Each cell traces to either historical_events_expanded
    or to a literature_review paper row.
  - When the literature corroborates an event-level number with its own
    measurement, both numbers appear and the divergence is logged in the
    audit.
  - Missing → empty cell (NULL semantics).
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
LIT_DUMP = REPO / "backend" / "data" / "raw" / "literature_review_dump.json"
EVENTS_CSV = REPO / "backend" / "data" / "csv" / "historical_events_expanded.csv"
VAL_CSV_EXISTING = REPO / "backend" / "data" / "csv" / "validation_targets.csv"
CSV_DIR = REPO / "backend" / "data" / "csv"
DOCS_DIR = REPO / "docs"
CSV_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)


# ── helpers ──────────────────────────────────────────────────────────────────

_FOOTNOTE_RE = re.compile(r"\[\^?\d+\]|\[\d+\]\[\d+\]|\[\d+\]")


def strip_footnotes(s: str) -> str:
    return _FOOTNOTE_RE.sub("", s or "").strip()


# Event-keyword catalogue → maps a token found in paper text to the
# event_id from historical_events_expanded.csv. Built manually because the
# literature review uses event nicknames (Tōhoku, Lehman, COVID, Brexit)
# that don't match the structured event names verbatim. Multiple paper
# rows can map to the same event.
EVENT_KEYWORDS: dict[str, list[int]] = {
    # nickname / phrase → list of event_ids
    "great east japan earthquake": [11],
    "tōhoku": [11],
    "tohoku": [11],
    "fukushima": [11],
    "japan earthquake": [11],
    "covid-19": [17],
    "covid": [17],
    "pandemic": [17, 8, 3],  # SARS=3, H1N1=8, COVID=17
    "lehman": [7],
    "great recession": [7],
    "global financial crisis": [7],
    "european sovereign debt": [9],
    "brexit": [15],
    "trade war": [16, 28],  # 2018 US-China=16, 2025 tariffs=28
    "tariff": [16, 28],
    "ever given": [19],
    "suez": [19, 26],
    "ukraine": [21],
    "russia invasion": [21],
    "evergrande": [24],
    "sri lanka default": [25],
    "red sea": [26],
    "houthi": [26],
    "nankai": [11],  # Inoue & Todo scenario — treated as Japan-earthquake corroboration
}

_PCT_RE = re.compile(
    r"(?P<sign>[−\-+])?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>%|pp\b|percentage points)",
    re.IGNORECASE,
)


def mine_paper_numbers(key_findings: str) -> list[tuple[float, str, str]]:
    """Pull (value, unit, surrounding-fragment) for each numeric percent / pp."""
    if not key_findings:
        return []
    s = strip_footnotes(key_findings).replace("−", "-").replace("–", "-")
    out = []
    for m in _PCT_RE.finditer(s):
        try:
            v = float(m.group("num"))
        except ValueError:
            continue
        sign = -1.0 if m.group("sign") == "-" else 1.0
        # 30-char context window around match
        start = max(0, m.start() - 40)
        end = min(len(s), m.end() + 30)
        ctx = s[start:end].strip()
        out.append((sign * v, m.group("unit").lower(), ctx))
    return out


def map_paper_to_events(title: str, key_findings: str) -> list[int]:
    """Return list of historical_events_expanded.csv event_ids that this paper
    discusses, derived from EVENT_KEYWORDS hits in title + findings.
    """
    haystack = f"{title or ''} {key_findings or ''}".lower()
    hits: set[int] = set()
    for kw, eids in EVENT_KEYWORDS.items():
        if kw in haystack:
            hits.update(eids)
    return sorted(hits)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    if not LIT_DUMP.exists():
        print(f"ERROR: {LIT_DUMP} not found.", file=sys.stderr)
        return 1
    if not EVENTS_CSV.exists():
        print(f"ERROR: {EVENTS_CSV} not found. Run extract_events_from_docx.py first.", file=sys.stderr)
        return 1

    raw = json.loads(LIT_DUMP.read_text(encoding="utf-8"))
    paragraphs: list[str] = raw["paragraphs"]
    tables: list[list[list[str]]] = raw["tables"]

    # ── papers_catalog.csv ───────────────────────────────────────────────────
    papers: list[dict] = []
    master_tbl = tables[0]
    header = master_tbl[0]
    for row in master_tbl[1:]:
        if len(row) < 12:
            continue
        # Citations stripped of footnotes, e.g. "~4,200[1][2]" → "~4,200"
        cit_clean = strip_footnotes(row[5])
        # Relevance: numeric prefix of column 11
        rel_match = re.match(r"\s*(\d+)", row[11])
        relevance = int(rel_match.group(1)) if rel_match else None
        papers.append({
            "paper_id": row[0].strip(),
            "title": strip_footnotes(row[1]).strip(),
            "authors": strip_footnotes(row[2]).strip(),
            "year": row[3].strip(),
            "journal": strip_footnotes(row[4]).strip(),
            "citations_approx": cit_clean,
            "doi": row[6].strip(),
            "methodology": strip_footnotes(row[7]).strip(),
            "dataset_used": strip_footnotes(row[8]).strip(),
            "key_findings": strip_footnotes(row[9]).strip(),
            "limitations": strip_footnotes(row[10]).strip(),
            "geds_relevance": relevance if relevance is not None else "",
        })

    papers_path = CSV_DIR / "papers_catalog.csv"
    papers_fields = [
        "paper_id", "title", "authors", "year", "journal",
        "citations_approx", "doi", "methodology", "dataset_used",
        "key_findings", "limitations", "geds_relevance",
    ]
    with papers_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=papers_fields)
        w.writeheader()
        w.writerows(papers)
    print(f"wrote {papers_path} ({len(papers)} papers)")

    # ── Load existing validation_targets.csv + historical_events_expanded ────
    events: list[dict] = []
    with EVENTS_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            events.append(row)
    events_by_id = {int(e["event_id"]): e for e in events if e["event_id"].isdigit()}

    existing_val: list[dict] = []
    if VAL_CSV_EXISTING.exists():
        with VAL_CSV_EXISTING.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                existing_val.append(row)

    # ── Mine paper-level numbers tied to specific events ────────────────────
    # For each paper, if it references a known event, emit a validation-target
    # row with the paper as source. Country/sector left blank when the paper
    # gives a national-level number without disaggregation.
    paper_derived_rows: list[dict] = []
    paper_event_corroboration: dict[int, list[str]] = defaultdict(list)
    for p in papers:
        eids = map_paper_to_events(p["title"], p["key_findings"])
        if not eids:
            continue
        numbers = mine_paper_numbers(p["key_findings"])
        for eid in eids:
            paper_event_corroboration[eid].append(p["paper_id"])
            # Emit one row per numeric finding, attached to the event.
            for val, unit, ctx in numbers:
                # Heuristic: classify as GDP if the context mentions GDP,
                # otherwise leave generic in the supply_chain field.
                ctx_low = ctx.lower()
                row = {
                    "event_id": eid,
                    "event_name": events_by_id.get(eid, {}).get("event_name", ""),
                    "country": "",
                    "country_iso3": "",
                    "sector": "",
                    "year": events_by_id.get(eid, {}).get("year_start", ""),
                    "observed_gdp_change_percent": "",
                    "observed_trade_change_percent": "",
                    "observed_inflation_change_percent": "",
                    "observed_market_change_percent": "",
                    "observed_supply_chain_disruption": "",
                    "observed_recovery_months": "",
                    "confidence": min(5, max(1, p["geds_relevance"] // 2 if isinstance(p["geds_relevance"], int) else 3)),
                    "source": f"Paper {p['paper_id']}: {p['authors']} ({p['year']}). \"{p['title']}\". DOI: {p['doi']}",
                }
                if "gdp" in ctx_low:
                    row["observed_gdp_change_percent"] = f"{val:.3f}"
                    # Try to extract country from context
                    for cn, iso in [("japan", "JPN"), ("us ", "USA"), ("china", "CHN"),
                                    ("germany", "DEU"), ("greece", "GRC")]:
                        if cn in ctx_low:
                            row["country"] = cn.strip().title()
                            row["country_iso3"] = iso
                            break
                elif "cascading" in ctx_low or "loss" in ctx_low or "indirect" in ctx_low:
                    row["observed_supply_chain_disruption"] = f"{val:.3f}{unit}"
                elif "volatility" in ctx_low or "trade" in ctx_low:
                    row["observed_trade_change_percent"] = f"{val:.3f}"
                else:
                    # Default bucket
                    row["observed_supply_chain_disruption"] = f"{val:.3f}{unit} — {ctx[:80]}"
                paper_derived_rows.append(row)

    # ── validation_targets_expanded.csv ─────────────────────────────────────
    # Carry existing validation_targets columns + add paper-derived rows.
    val_path = CSV_DIR / "validation_targets_expanded.csv"
    val_fields = [
        "event_id", "event_name", "country", "country_iso3", "sector", "year",
        "observed_gdp_change_percent", "observed_trade_change_percent",
        "observed_inflation_change_percent", "observed_market_change_percent",
        "observed_supply_chain_disruption", "observed_recovery_months",
        "confidence", "source",
    ]
    expanded_rows: list[dict] = []
    # 1. Existing per-event/country rows, schema-translated.
    for r in existing_val:
        eid = r.get("event_id", "")
        try:
            eid_int = int(eid)
        except ValueError:
            continue
        event_row = events_by_id.get(eid_int, {})
        # Pre-existing rows have one observed value (either gdp or trade); fill
        # remaining fields from the event aggregate.
        expanded_rows.append({
            "event_id": eid_int,
            "event_name": event_row.get("event_name", ""),
            "country": r.get("country", ""),
            "country_iso3": r.get("country", ""),
            "sector": r.get("sector", ""),
            "year": event_row.get("year_start", ""),
            "observed_gdp_change_percent": r.get("observed_gdp_change", ""),
            "observed_trade_change_percent": r.get("observed_trade_change", ""),
            "observed_inflation_change_percent": r.get("observed_inflation_change", ""),
            "observed_market_change_percent": event_row.get("market_impact_percent", ""),
            "observed_supply_chain_disruption": "",
            "observed_recovery_months": r.get("observed_recovery_time", ""),
            "confidence": event_row.get("confidence", ""),
            "source": r.get("source", ""),
        })
    # 2. Paper-derived rows appended.
    expanded_rows.extend(paper_derived_rows)

    with val_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=val_fields)
        w.writeheader()
        w.writerows(expanded_rows)
    print(f"wrote {val_path} ({len(expanded_rows)} rows; "
          f"{len(paper_derived_rows)} from literature)")

    # ── model_event_mapping.csv ─────────────────────────────────────────────
    map_path = CSV_DIR / "model_event_mapping.csv"
    map_fields = [
        "event_id", "graph_nodes_affected", "shock_origin_nodes",
        "primary_sectors", "secondary_sectors",
        "estimated_initial_shock_strength", "duration_weeks",
    ]
    # GEDS engine node set (kept in sync with extract_events_from_docx.py).
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
    # Manual shock-origin heuristic per event: where did the shock START?
    # Filled from the event Trigger column when possible, else UNCERTAIN.
    # Only the most obvious cases are encoded; everything else is UNCERTAIN
    # so we don't invent.
    ORIGIN_HINTS: dict[int, list[str]] = {
        3: ["CHN:consumer_goods"],            # SARS — Guangdong
        4: ["IRQ:energy"],                    # Iraq War — oil disruption
        5: ["IDN:consumer_goods"],            # Indian Ocean Tsunami
        6: ["USA:energy", "USA:shipping"],   # Katrina (gulf coast)
        7: ["USA:financial"],                 # GFC — subprime
        11: ["JPN:automotive", "JPN:electronics", "JPN:semiconductors"],  # Tohoku
        17: ["CHN:consumer_goods"],           # COVID-19 — Wuhan
        18: ["TWN:semiconductors"],           # Semi shortage
        19: ["CP:Suez"],                      # Ever Given
        21: ["UKR:agriculture"],              # Russia-Ukraine (commodity-side)
        22: ["DEU:energy"],                   # EU gas
        24: ["CHN:real_estate"],              # Evergrande
        26: ["CP:Suez"],                      # Red Sea
        27: ["PAN:shipping"],                 # Panama drought
        41: ["CP:TaiwanStrait", "TWN:semiconductors"],  # Taiwan scenario
    }

    map_rows = []
    for eid, e in sorted(events_by_id.items()):
        countries = (e["affected_countries"] or "").split(";") if e["affected_countries"] else []
        sectors = (e["affected_sectors"] or "").split(";") if e["affected_sectors"] else []
        graph_nodes = [f"{c}:{s}" for c in countries for s in sectors if c and s]
        in_graph = [n for n in graph_nodes if n in GEDS_NODES]
        origin = ORIGIN_HINTS.get(eid, ["UNCERTAIN"])
        # Initial shock strength: derive from gdp_impact magnitude (capped).
        gdp_raw = e["gdp_impact_percent"]
        try:
            gdp_v = abs(float(gdp_raw))
            # Map |GDP impact %| → shock strength in [0, 1]. 0% → 0.0; 10% → 1.0.
            shock_strength = f"{min(1.0, gdp_v / 10.0):.2f}"
        except (ValueError, TypeError):
            shock_strength = "UNCERTAIN"
        # Duration in weeks: from duration_months × 4.345
        try:
            dur_w = int(round(int(e["duration_months"]) * 4.345)) if e["duration_months"] else None
        except (ValueError, TypeError):
            dur_w = None
        # Primary sector = first listed; secondary = rest.
        primary = sectors[0] if sectors else ""
        secondary = ";".join(sectors[1:]) if len(sectors) > 1 else ""
        map_rows.append({
            "event_id": eid,
            "graph_nodes_affected": ";".join(in_graph) if in_graph else "UNCERTAIN",
            "shock_origin_nodes": ";".join(origin),
            "primary_sectors": primary or "UNCERTAIN",
            "secondary_sectors": secondary,
            "estimated_initial_shock_strength": shock_strength,
            "duration_weeks": dur_w if dur_w is not None else "UNCERTAIN",
        })
    with map_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=map_fields)
        w.writeheader()
        w.writerows(map_rows)
    print(f"wrote {map_path} ({len(map_rows)} rows)")

    # ── benchmark_inputs.csv ────────────────────────────────────────────────
    bench_path = CSV_DIR / "benchmark_inputs.csv"
    bench_fields = [
        "event_id", "actual_peak_impact", "actual_total_loss",
        "actual_recovery_time", "actual_countries_affected",
        "actual_trade_disruption", "actual_inflation_effect",
    ]
    bench_rows = []
    for eid, e in sorted(events_by_id.items()):
        countries = [c for c in (e["affected_countries"] or "").split(";") if c]
        # Peak impact: use |GDP impact| as proxy (no time-series in source).
        peak_raw = e["gdp_impact_percent"]
        try:
            peak = f"{abs(float(peak_raw)):.3f}" if peak_raw else ""
        except ValueError:
            peak = ""
        # Total loss: %-GDP × duration_months as proxy (only when both present).
        try:
            total_loss = (
                f"{abs(float(peak_raw)) * int(e['duration_months']) / 12:.3f}"
                if peak_raw and e["duration_months"]
                else ""
            )
        except (ValueError, TypeError):
            total_loss = ""
        bench_rows.append({
            "event_id": eid,
            "actual_peak_impact": peak,
            "actual_total_loss": total_loss,
            "actual_recovery_time": e["recovery_time_months"],
            "actual_countries_affected": len(countries),
            "actual_trade_disruption": e["trade_impact_percent"],
            "actual_inflation_effect": e["inflation_impact_percent"],
        })
    with bench_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=bench_fields)
        w.writeheader()
        w.writerows(bench_rows)
    print(f"wrote {bench_path} ({len(bench_rows)} rows)")

    # ── docs/VALIDATION_PLAN.md ─────────────────────────────────────────────
    vplan = DOCS_DIR / "VALIDATION_PLAN.md"
    vplan_lines = [
        "# GEDS Scientific Evaluation Plan",
        "",
        "Derived from:",
        f"- `backend/data/csv/papers_catalog.csv` ({len(papers)} peer-reviewed references)",
        f"- `backend/data/csv/validation_targets_expanded.csv` ({len(expanded_rows)} validation rows)",
        f"- `backend/data/csv/benchmark_inputs.csv` ({len(bench_rows)} event-level targets)",
        "",
        "## Performance metrics",
        "",
        "All metrics are reported with bootstrap-resampled 95% CIs (N=1000).",
        "",
        "### Regression metrics (per-event continuous outputs)",
        "",
        "| Metric | Formula | Use |",
        "|---|---|---|",
        "| **MAE** | mean(\\|y - ŷ\\|) | scale-aware error, robust to outliers |",
        "| **RMSE** | sqrt(mean((y - ŷ)²)) | penalises large errors |",
        "| **R²** | 1 − SSE/SST | variance explained vs predict-the-mean |",
        "| **Pearson r** | cov(y, ŷ) / (σy · σŷ) | linear correlation |",
        "| **MAPE** | mean(\\|y - ŷ\\|/\\|y\\|) | only when y ≠ 0 |",
        "| **Murphy skill** | 1 − MSE / MSE_clim | scaled vs climatology |",
        "",
        "Reference benchmark already lives in `backend/data/benchmark.json`",
        "(Linear Diffusion = in-sample winner with R² +0.7647 on N=8 events).",
        "",
        "### Classification metrics (per-event binary signals)",
        "",
        "Applied to: was a country/sector affected above a threshold? did peak",
        "exceed VaR_95? did recovery occur within forecast window?",
        "",
        "| Metric | Formula |",
        "|---|---|",
        "| **Precision** | TP / (TP + FP) |",
        "| **Recall** | TP / (TP + FN) |",
        "| **F1** | 2 · P · R / (P + R) |",
        "| **Calibration error (ECE)** | Σᵦ \\|acc(b) − conf(b)\\| · w(b) |",
        "",
        "ECE is reported per decile of forecasted probability. The model is",
        "well-calibrated when |gap| < 0.05 in every decile.",
        "",
        "## Validation procedure",
        "",
        "### Leave-one-out (LOO)",
        "",
        "For each of the N events in `historical_events_expanded.csv`:",
        "1. Re-calibrate model parameters on remaining N−1 events.",
        "2. Predict the held-out event.",
        "3. Score with all regression + classification metrics above.",
        "Aggregate metrics and CIs across the N folds.",
        "",
        "Existing GEDS infrastructure: `app/core/cross_validation.py` (already implemented).",
        "",
        "### Bootstrap (uncertainty bands on every metric)",
        "",
        "Resample N events with replacement, recompute metrics, repeat 1000×.",
        "Report 2.5 / 50 / 97.5 percentile bands.",
        "Existing: bootstrap utility in `app/core/cross_validation.py` (LOO + bootstrap CI both live there).",
        "",
        "### Sensitivity analysis (Sobol)",
        "",
        "Variance-decomposition of model outputs against parameter uncertainty.",
        "Already implemented: `app/core/sensitivity.py` (Sobol indices via SALib). Output: first-order + total-order",
        "indices per parameter (propagation_decay, amplification_mu, recovery_rate, ...).",
        "Re-run after each graph expansion (BACI / OECD ICIO integration).",
        "",
        "### Ablation",
        "",
        "Disable one model component at a time and re-run full LOO. Report",
        "ΔR² and ΔMAE per ablated component (SEIRS, bullwhip, hysteresis,",
        "amplification). Existing: `app/core/ablation.py`.",
        "",
        "### Baseline comparison",
        "",
        "Three baselines must be beaten or matched for GEDS to claim utility:",
        "1. **Naive Persistence** (predict mean of historical events)",
        "2. **Linear Diffusion** (network propagation without SEIRS/bullwhip)",
        "3. **Leontief Equilibrium** (I-O fixed-point)",
        "",
        "Current state (2026-05-21 benchmark): Linear Diffusion beats GEDS on",
        "N=8 events. This **must be addressed** before publication-grade claims.",
        "Action items in NEXT_STEPS_VALIDATION.md.",
        "",
        "## Per-event scoring loop",
        "",
        "Inputs are taken row-by-row from `benchmark_inputs.csv`:",
        "",
        "```",
        "for event in benchmark_inputs.csv:",
        "    scenario  = build_scenario_from(historical_events_expanded[event.id],",
        "                                    model_event_mapping[event.id])",
        "    forecast  = engine.run(scenario)",
        "    score(forecast, event)  # regression + classification metrics",
        "```",
        "",
        "Existing GEDS scoring entry-point: `app/core/benchmark.py::run_benchmark()`.",
        "",
        "## Literature corroboration layer",
        "",
        "For each event-level prediction, we cross-reference against the",
        "peer-reviewed paper that measured that event (when one exists).",
        "Corroboration count per event:",
        "",
        "| Event ID | Event Name | Corroborating papers |",
        "|---|---|---|",
    ]
    for eid in sorted(paper_event_corroboration):
        ev = events_by_id.get(eid)
        if not ev:
            continue
        vplan_lines.append(
            f"| {eid} | {ev['event_name'][:50]} | {', '.join(paper_event_corroboration[eid])} |",
        )
    vplan.write_text("\n".join(vplan_lines), encoding="utf-8")
    print(f"wrote {vplan}")

    # ── docs/UNCERTAINTY_ANALYSIS.md ────────────────────────────────────────
    unc = DOCS_DIR / "UNCERTAINTY_ANALYSIS.md"
    low_conf = [e for e in events if e["confidence"] and e["confidence"].isdigit() and int(e["confidence"]) <= 2]
    scenario_events = [e for e in events if e.get("is_scenario") == "true"]
    no_country = [e for e in events if not e["affected_countries"]]
    no_sector = [e for e in events if not e["affected_sectors"]]
    no_inflation = [e for e in events if not e["inflation_impact_percent"]]
    overlap_pairs: list[tuple[int, int]] = []
    eids_sorted = sorted(int(e["event_id"]) for e in events if e["event_id"].isdigit())
    for i, a in enumerate(eids_sorted):
        ea = events_by_id.get(a)
        if not ea or not ea["year_start"]:
            continue
        for b in eids_sorted[i + 1:]:
            eb = events_by_id.get(b)
            if not eb or not eb["year_start"]:
                continue
            try:
                ya1, ya2 = int(ea["year_start"]), int(ea["year_end"] or ea["year_start"])
                yb1, yb2 = int(eb["year_start"]), int(eb["year_end"] or eb["year_start"])
                if ya1 <= yb2 and yb1 <= ya2:
                    overlap_pairs.append((a, b))
            except ValueError:
                continue
    unc_lines = [
        "# GEDS Uncertainty Analysis",
        "",
        "Inputs:",
        f"- `historical_events_expanded.csv` ({len(events)} events)",
        f"- `papers_catalog.csv` ({len(papers)} papers)",
        "",
        "## Low-confidence events (source-rated confidence ≤ 2)",
        "",
        f"Count: **{len(low_conf)}**",
        "",
    ]
    for e in low_conf:
        unc_lines.append(
            f"- Event {e['event_id']} ({e['event_name']}): confidence={e['confidence']}, "
            f"trigger={e['trigger'][:100]}"
        )
    if not low_conf:
        unc_lines.append("- (none)")

    unc_lines += [
        "",
        "## Scenario / forward-looking events (treat as model input only)",
        "",
        f"Count: **{len(scenario_events)}** — these are projections, not history.",
        "Including them in LOO inflates 'accuracy' artificially because the",
        "model is being scored against its own hypothesis. Exclude from",
        "validation; include in stress-test playbook.",
        "",
    ]
    for e in scenario_events:
        unc_lines.append(
            f"- Event {e['event_id']} ({e['event_name']}): year={e['year_start']}–{e['year_end']}, "
            f"trigger={e['trigger'][:100]}"
        )

    unc_lines += [
        "",
        "## Missing measurements",
        "",
        f"- Events with no `affected_countries` (source said 'Global' or aggregate): **{len(no_country)}**",
        f"- Events with no `affected_sectors` (source said 'all sectors' or meta-term): **{len(no_sector)}**",
        f"- Events with no `inflation_impact_percent`: **{len(no_inflation)}** "
        f"({len(no_inflation)/len(events)*100:.1f}%)",
        "- Events with no `recovery_time_months`: source docx has no explicit",
        "  Recovery Time field — values only present when text explicitly says",
        "  'reconstruction: N years'.",
        "",
        "## Overlapping crises (attribution problem)",
        "",
        f"**{len(overlap_pairs)}** pairs of events whose year ranges intersect.",
        "When two events overlap, any economic indicator is the sum of both",
        "effects + secular trend. Without a counterfactual control, attribution",
        "to one cause is identifying-assumption-dependent.",
        "",
        "Mitigation strategies, in order of strength:",
        "1. **Synthetic control method** (Abadie et al. 2010) per event — build",
        "   a donor-weighted counterfactual from countries not exposed to the",
        "   overlapping shock. Adds ~2 weeks of work per event.",
        "2. **Difference-in-differences** when an obvious unexposed control",
        "   exists (e.g. Carvalho et al. 2021 for Tōhoku — Paper 2 in catalog).",
        "3. **Period-of-acute-shock isolation** — score only the first quarter",
        "   post-shock to minimise contamination.",
        "",
        "Sample overlapping pairs (first 10):",
        "",
    ]
    for a, b in overlap_pairs[:10]:
        ea = events_by_id.get(a, {})
        eb = events_by_id.get(b, {})
        unc_lines.append(
            f"- Event {a} ({ea.get('event_name', '?')[:30]}) "
            f"↔ Event {b} ({eb.get('event_name', '?')[:30]})"
        )

    unc_lines += [
        "",
        "## Attribution problems flagged in literature",
        "",
    ]
    for p in papers:
        lim = p["limitations"].lower()
        if any(kw in lim for kw in ("identification", "attribution", "endogeneity", "causal")):
            unc_lines.append(
                f"- Paper {p['paper_id']} ({p['authors']}, {p['year']}): "
                f"{p['limitations'][:200]}"
            )

    unc_lines += [
        "",
        "## Scenario-based values — handling rules",
        "",
        "Rows where `is_scenario == true` must be flagged in any benchmark",
        "output. The benchmark code in `app/core/benchmark.py` should:",
        "",
        "1. Exclude scenario rows from MAE / RMSE / R² / Pearson aggregates.",
        "2. Report scenario rows separately as 'stress-test predictions'",
        "   with no ground-truth comparison.",
        "3. Show wider uncertainty bands (±2σ instead of ±1σ).",
        "",
        "## Confidence intervals — recommended reporting standard",
        "",
        "Every published metric must include:",
        "",
        "- point estimate",
        "- 95% bootstrap CI (N=1000 resamples)",
        "- N of underlying events",
        "- exclusion criteria (scenario-rows excluded? low-conf excluded?)",
        "",
        "Existing implementation: `app/core/cross_validation.py` (bootstrap CI helpers).",
        "Not yet wired into the `/api/v1/research-metrics` endpoint — see",
        "NEXT_STEPS_VALIDATION.md.",
        "",
    ]
    unc.write_text("\n".join(unc_lines), encoding="utf-8")
    print(f"wrote {unc}")

    # ── docs/VALIDATION_DATA_AUDIT.md ───────────────────────────────────────
    aud = DOCS_DIR / "VALIDATION_DATA_AUDIT.md"
    # Duplicates: events with same name OR same (year, country-set)
    name_counts = Counter(e["event_name"] for e in events if e["event_name"])
    dup_names = [n for n, c in name_counts.items() if c > 1]
    # Conflicting values: where a paper-derived row and an event-aggregate row
    # disagree on GDP for the same (event_id, country).
    by_event_country: dict[tuple, list[dict]] = defaultdict(list)
    for r in expanded_rows:
        if r["country_iso3"] and r["observed_gdp_change_percent"]:
            by_event_country[(r["event_id"], r["country_iso3"])].append(r)
    conflicts = []
    for k, rows_ in by_event_country.items():
        vals = []
        for r in rows_:
            try:
                vals.append(float(r["observed_gdp_change_percent"]))
            except ValueError:
                continue
        if len(set(round(v, 1) for v in vals)) > 1:
            conflicts.append((k, vals, [r["source"][:80] for r in rows_]))
    # Impossible values: |gdp impact| > 100% (some are legit; others suspect)
    impossible = []
    for e in events:
        for fld in ("gdp_impact_percent", "trade_impact_percent",
                    "inflation_impact_percent", "market_impact_percent"):
            v_raw = e.get(fld, "")
            if not v_raw:
                continue
            try:
                v = float(v_raw)
            except ValueError:
                continue
            if abs(v) > 100 and fld != "market_impact_percent":
                impossible.append((e["event_id"], e["event_name"], fld, v))
    # Missing values per field
    miss = Counter()
    for e in events:
        for fld in ("year_start", "event_type", "affected_countries",
                    "affected_sectors", "duration_months",
                    "gdp_impact_percent", "trade_impact_percent",
                    "inflation_impact_percent", "market_impact_percent",
                    "recovery_time_months", "confidence"):
            if not e.get(fld):
                miss[fld] += 1
    aud_lines = [
        "# GEDS Validation Data Audit",
        "",
        "Inputs:",
        f"- `historical_events_expanded.csv` ({len(events)} events)",
        f"- `validation_targets_expanded.csv` ({len(expanded_rows)} rows)",
        f"- `papers_catalog.csv` ({len(papers)} papers)",
        "",
        "## Duplicate events",
        "",
        f"Events sharing a name: **{len(dup_names)}**",
    ]
    for n in dup_names:
        aud_lines.append(f"- `{n}`")
    if not dup_names:
        aud_lines.append("- (none)")

    aud_lines += [
        "",
        "## Conflicting values across sources",
        "",
        f"Same (event, country) reported with disagreeing GDP numbers across",
        f"event-aggregate and paper-derived sources: **{len(conflicts)}**",
        "",
    ]
    for (eid, iso), vals, srcs in conflicts:
        aud_lines.append(
            f"- Event {eid} {iso}: values {vals}; sources: {srcs}"
        )

    aud_lines += [
        "",
        "## Impossible / suspect values",
        "",
        f"Magnitude > 100% in fields other than market_impact_percent: **{len(impossible)}**",
        "",
        "Note: source text frequently expresses 'X% of GDP' for cumulative damage",
        "(e.g. Haiti earthquake = 120% of pre-shock GDP), which is mathematically",
        "valid but visually suspect. These rows are kept in the catalog but",
        "flagged here for human review.",
        "",
    ]
    for eid, name, fld, v in impossible:
        aud_lines.append(f"- Event {eid} ({name[:40]}): `{fld}` = {v}")

    aud_lines += [
        "",
        "## Missing values per field",
        "",
        "| Field | Missing | % |",
        "|---|---|---|",
    ]
    n = len(events)
    for fld, c in miss.most_common():
        aud_lines.append(f"| {fld} | {c} | {c/n*100:.1f}% |")

    aud_lines += [
        "",
        "## Source inconsistencies — observed across docx sources",
        "",
        "1. **Event 4 (Iraq War & oil spike)** GDP Impact text describes both",
        "   `~−0.5% per year` (the impact channel) and `~$275 billion cumulative`",
        "   (a stock measure). These are non-comparable; parser keeps the % value.",
        "2. **Event 7 (Global Financial Crisis)** quotes both `−1.3%` (global GDP)",
        "   and country-specific figures (`US −2.5%`, `DEU −5.6%`). All preserved",
        "   in `validation_targets_expanded.csv` as separate rows.",
        "3. **Event 27 (Panama Canal drought)** `73%` appears as 'US share of",
        "   canal traffic' but the parser reads it into `gdp_impact_percent`.",
        "   Audit-flag — should be reviewed manually.",
        "",
        "## Weak-evidence flags",
        "",
        "Papers with self-declared limitations include:",
        "",
    ]
    for p in papers:
        if p["limitations"]:
            score_in = int(p["geds_relevance"]) if str(p["geds_relevance"]).isdigit() else 0
            if score_in <= 8 and len(p["limitations"]) > 30:
                aud_lines.append(
                    f"- Paper {p['paper_id']} ({p['authors']}, {p['year']}, rel={score_in}): "
                    f"{p['limitations'][:200]}"
                )

    aud_lines += [
        "",
        "## Note on file naming",
        "",
        "The historical-events audit is at `docs/DATA_AUDIT.md`; the dataset-",
        "registry audit is at `docs/DATA_AUDIT_DATASETS.md`. This validation-",
        "specific audit is `docs/VALIDATION_DATA_AUDIT.md` to avoid clobbering.",
        "",
    ]
    aud.write_text("\n".join(aud_lines), encoding="utf-8")
    print(f"wrote {aud}")

    # ── docs/NEXT_STEPS_VALIDATION.md ───────────────────────────────────────
    nxt = DOCS_DIR / "NEXT_STEPS_VALIDATION.md"
    nxt_lines = [
        "# GEDS Validation — Implementation Roadmap",
        "",
        f"Derived from `validation_targets_expanded.csv` ({len(expanded_rows)} rows,",
        f"{len(paper_derived_rows)} from literature) and `benchmark_inputs.csv`",
        f"({len(bench_rows)} events).",
        "",
        "## Immediate (1–3 days)",
        "",
        "Goal: make the validation layer reproducible from CSV inputs alone.",
        "Current state: `app/core/cross_validation.py` + `app/core/benchmark.py` exist but",
        "consume hardcoded subsets of the events list. Wire them to the new CSVs.",
        "",
        "- [ ] **Update `benchmark.py` to consume `benchmark_inputs.csv`** instead",
        "  of its hardcoded N=8 list. _Effort: 0.5 day._",
        "- [ ] **Filter scenario events** (`is_scenario == true`) from MAE/R²",
        "  aggregates; report separately. _Effort: 0.5 day._",
        "- [ ] **Wire `validation_targets_expanded.csv` into `loo_cv.py`** so",
        "  paper-corroborated rows are scored against literature, not only",
        "  event-aggregates. _Effort: 1 day._",
        "- [ ] **Add `/api/v1/papers` endpoint** returning `papers_catalog.csv`",
        "  so the frontend can cite the validation literature. _Effort: 0.5 day._",
        "",
        "## Short-term (1–2 weeks)",
        "",
        "Goal: address the core scientific weakness — Linear Diffusion beats",
        "GEDS on the current N=8 benchmark. Two parallel tracks.",
        "",
        "### Track A — bigger N for honest validation",
        "",
        "- [ ] Re-run benchmark with all 42 events (minus the 1 scenario) = N=41.",
        "  The current sub-selection masks model behaviour on noisy events.",
        "  _Effort: 1 day._",
        "- [ ] Implement synthetic-control counterfactuals for the top-5",
        "  overlapping-crisis events (events 9, 10, 13, 14, 17, 18, 20, 21",
        "  all overlap with at least 3 others). _Effort: 1 week._",
        "- [ ] Bootstrap CIs for every metric in `/api/v1/research-metrics`.",
        "  _Effort: 1 day._",
        "",
        "### Track B — make the GEDS engine actually identifiable",
        "",
        "Sobol indices from the prior session showed 3 of 5 parameters are",
        "non-identifiable. Until that is fixed, calibration is unstable.",
        "",
        "- [ ] Re-run Sobol on the expanded edge set (with Comtrade merger).",
        "  _Effort: 0.5 day._",
        "- [ ] Drop or fix the non-identifiable parameters; re-run MCMC.",
        "  _Effort: 3 days._",
        "- [ ] Re-run full benchmark; report whether GEDS now beats Linear",
        "  Diffusion. _Effort: 0.5 day._",
        "",
        "## Medium-term (1 month)",
        "",
        "- [ ] **Paper-by-paper replication**: pick the 4 highest-relevance",
        "  papers with reproducible code (papers 14, 15, 25 have GitHub repos",
        "  per the docx) and reproduce their core figure inside GEDS as a",
        "  validation regression-test. If GEDS produces the same numbers on the",
        "  same data, we have credible cross-validation. _Effort: 1 week per paper._",
        "- [ ] **Expand the event corpus to 100+ events** via the EM-DAT and",
        "  ACLED feeds (already catalogued in `dataset_catalog.csv` dataset_ids",
        "  43, 44, 52). Many low-magnitude events would shore up the statistics.",
        "  _Effort: 1 week (ingest + label + recalibrate)._",
        "- [ ] **Calibration error (ECE) reporting** per decile of forecast.",
        "  The current benchmark only reports point R². _Effort: 2 days._",
        "",
        "## Long-term (multi-month)",
        "",
        "- [ ] **Out-of-sample temporal hold-out**: train on 2000–2020 events,",
        "  test on 2021–2026 (12 events). This is the cleanest test of",
        "  generalisation and the closest to real-world use. _Effort: 2–3 weeks._",
        "- [ ] **Multi-shock simulation literature gap** — the docx review",
        "  flags this as an open research area (no paper covers pandemic + war",
        "  + energy crisis simultaneously). Build a stress-test suite combining",
        "  events from `historical_events_expanded.csv` pairwise and measure",
        "  emergent dynamics. _Effort: 1–2 months._",
        "- [ ] **Cross-country panel validation**: replace the per-event scoring",
        "  with a country×year panel and run the full battery on 200 countries ×",
        "  26 years = 5,200 observations instead of 41 events. _Effort: 2 months._",
        "",
        "## Out-of-scope for v1",
        "",
        "Marked as 'long-term' but explicitly NOT a v1 commitment:",
        "",
        "- **Real-time backtest** against live GDELT/ACLED streams.",
        "- **Causal inference layer** with do-calculus / structural causal models.",
        "- **Cryptocurrency / digital-asset contagion** (literature gap per docx).",
        "- **GNN / transformer / XGBoost ML layer** (no training data; needs the",
        "  100+ event corpus first).",
        "",
    ]
    nxt.write_text("\n".join(nxt_lines), encoding="utf-8")
    print(f"wrote {nxt}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
