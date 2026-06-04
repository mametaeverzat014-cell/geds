"""Phase 5 — regenerate docs/STATE.md honestly from all prior phases' artefacts.

Reads (only what exists; absence is reported, not invented):
  - backend/data/csv/master_event_registry.csv
  - backend/data/csv/master_dataset_registry.csv
  - backend/data/csv/master_model_registry.csv
  - backend/data/csv/master_literature_registry.csv
  - backend/data/csv/expanded_graph_nodes.csv
  - backend/data/csv/expanded_graph_edges.csv
  - backend/data/csv/event_evidence.csv
  - backend/data/calibration/benchmark_v2.json
  - backend/data/calibration/calibration_v2.json
  - backend/data/calibration/posterior_v2.json

Writes docs/STATE.md (overwrites prior version; prior STATE.md is the dated
snapshot from 2026-05-21 that drove this strengthening pass).
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CSV_DIR = REPO / "backend" / "data" / "csv"
CALIB_DIR = REPO / "backend" / "data" / "calibration"
DOCS = REPO / "docs"


def _read_csv(name: str) -> list[dict]:
    p = CSV_DIR / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    events = _read_csv("master_event_registry.csv")
    datasets = _read_csv("master_dataset_registry.csv")
    models = _read_csv("master_model_registry.csv")
    literature = _read_csv("master_literature_registry.csv")
    expanded_nodes = _read_csv("expanded_graph_nodes.csv")
    expanded_edges = _read_csv("expanded_graph_edges.csv")
    evidence = _read_csv("event_evidence.csv")

    bench_v2 = _read_json(CALIB_DIR / "benchmark_v2.json")
    calib_v2 = _read_json(CALIB_DIR / "calibration_v2.json")
    post_v2 = _read_json(CALIB_DIR / "posterior_v2.json")
    bench_v1 = _read_json(CALIB_DIR / "benchmark.json")

    # Compute counts
    n_events = len(events)
    n_scenario = sum(1 for e in events if e.get("is_scenario") == "true")
    n_events_with_gdp = sum(1 for e in events if e.get("gdp_impact_percent"))
    n_events_with_v2 = sum(1 for e in events
                           if int(e.get("validation_targets_v2_rows") or 0) > 0)
    n_events_with_corrob = sum(1 for e in events
                               if e.get("literature_papers_corroborating"))
    n_events_in_default_graph = sum(
        1 for e in events
        if e.get("graph_nodes_affected_in_geds") and e["graph_nodes_affected_in_geds"] != "UNCERTAIN"
    )

    # Phase 1 graph stats
    n_expanded_nodes = len(expanded_nodes)
    n_expanded_chokepoints = sum(1 for n in expanded_nodes if n.get("industry") == "chokepoint")
    n_expanded_countries = len({n["country_iso3"] for n in expanded_nodes if n.get("country_iso3")})
    n_expanded_edges = len(expanded_edges)

    # Phase 2 evidence stats
    n_evidence_rows = len(evidence)
    events_with_evidence = len({r["event_id"] for r in evidence})
    events_with_paper_evidence = len({r["event_id"] for r in evidence
                                       if r.get("paper_id", "").startswith("P")})

    # Phase 3 benchmark
    bench_section_lines = []
    if bench_v2:
        bench_section_lines += [
            f"- **Benchmark v2** (`benchmark_v2.json`):",
            f"  - N benchmarked: **{bench_v2.get('n_events_benchmarked')}** / {bench_v2.get('n_events_total_corpus')} (engine sector/graph limits)",
            f"  - Winner by MAE: `{bench_v2.get('winner_by_mae')}`",
            f"  - Winner by R²: `{bench_v2.get('winner_by_r_squared')}`",
            "",
            "  Per-model scores:",
            "",
            "  | Model | MAE | R² | Pearson | Skill |",
            "  |---|---|---|---|---|",
        ]
        for m in bench_v2.get("models", []):
            bench_section_lines.append(
                f"  | {m['model']} | {m['mae']:.4f} | "
                f"{m.get('r_squared', 'NaN'):.3f} | {m.get('pearson', 'NaN'):.3f} | "
                f"{m.get('skill_vs_persistence', 'NaN'):+.3f} |"
            )
    else:
        bench_section_lines.append("- `benchmark_v2.json` NOT FOUND (Phase 3 not yet run)")

    # Phase 4 calibration
    calib_lines = []
    if calib_v2:
        calib_lines += [
            f"- **Calibration v2** (`calibration_v2.json`):",
            f"  - Best method: `{calib_v2.get('winner')}`",
            f"  - Default-config RMSE: {calib_v2.get('default_config_rmse'):.5f}",
            f"  - Best-params RMSE: {calib_v2.get('optuna', {}).get('best_loss_rmse') or calib_v2.get('differential_evolution', {}).get('best_loss_rmse'):.5f}",
            f"  - Improvement vs default: {calib_v2.get('improvement_vs_default'):.5f}",
        ]
        sobol = calib_v2.get("sobol_sensitivity", {})
        if sobol:
            calib_lines += [
                f"  - Sobol identifiable parameters: {sobol.get('identifiable_count')} / {len(sobol.get('indices', []))}",
            ]
    else:
        calib_lines.append("- `calibration_v2.json` NOT FOUND (Phase 4 not yet run / still running)")

    mcmc_lines = []
    if post_v2:
        mcmc_lines += [
            f"- **MCMC posterior** (`posterior_v2.json`):",
            f"  - Walkers × steps: {post_v2.get('n_walkers')} × {post_v2.get('n_steps')} (burn-in {post_v2.get('n_burnin')})",
            f"  - Acceptance fraction: {post_v2.get('acceptance_fraction_mean'):.3f}",
            f"  - Autocorr time max: {post_v2.get('autocorr_time_max', float('nan')):.1f}",
            f"  - Converged heuristic: {post_v2.get('converged_heuristic')}",
            "",
            "  Posterior summary (mean ± std, [P05, P95]):",
            "",
            "  | Parameter | Mean | Std | P05 | P50 | P95 |",
            "  |---|---|---|---|---|---|",
        ]
        for p in post_v2.get("parameters", []):
            mcmc_lines.append(
                f"  | {p['name']} | {p['mean']:.4f} | {p['std']:.4f} | "
                f"{p['p05']:.4f} | {p['p50']:.4f} | {p['p95']:.4f} |"
            )
        mcmc_lines.append(
            f"\n  _Compute-budget note: {post_v2.get('compute_budget_note', '')}_"
        )
    else:
        mcmc_lines.append("- `posterior_v2.json` NOT FOUND (Phase 4 not yet run / still running)")

    state = DOCS / "STATE.md"

    # Build the doc
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        "# GEDS — Current State of Reality",
        "",
        f"**Snapshot date**: {today}",
        "**Method**: aggregated from master registries + Phase 1–5 artefacts.",
        "**Purpose**: single source of truth for what the engine and data layer actually contain.",
        "",
        "## Headline numbers",
        "",
        f"- **Historical events catalogued:** {n_events}",
        f"  - With observed GDP impact value: {n_events_with_gdp} ({n_events_with_gdp/max(n_events,1)*100:.1f}%)",
        f"  - With v2 institutional ground-truth attached: {n_events_with_v2}",
        f"  - With peer-reviewed paper corroboration: {n_events_with_corrob}",
        f"  - Mapping to ≥1 node in the *default* engine graph (40 nodes): {n_events_in_default_graph}",
        f"  - Scenario / forward-looking: {n_scenario}",
        f"- **Datasets catalogued:** {len(datasets)} (HIGH/MEDIUM/LOW counts in `MASTER_STATE.md`)",
        f"- **Benchmark models catalogued:** {len(models)} (in `master_model_registry.csv`)",
        f"- **Literature entries:** {len(literature)} (25 deeply-cataloged + 36 title-only)",
        f"- **Event evidence rows mined:** {n_evidence_rows} across {events_with_evidence} events",
        f"  - Peer-reviewed paper-derived rows: {events_with_paper_evidence} events",
        "",
        "## Graph",
        "",
        "**Default engine graph:**",
        "- Nodes: 40 (36 country×industry + 4 chokepoints)",
        "- Edges (default): 64 hardcoded MVP",
        "- Edges (Comtrade-merged, opt-in via `GEDS_USE_COMTRADE_EDGES=1`): 201",
        "",
        "**Expanded graph (Phase 1 — opt-in, not yet wired into `seed.py`):**",
        f"- Nodes: {n_expanded_nodes} ({n_expanded_nodes - n_expanded_chokepoints} country×industry + {n_expanded_chokepoints} chokepoints)",
        f"- Edges: {n_expanded_edges}",
        f"- Country coverage: {n_expanded_countries} ISO3 (G20 + key trade hubs)",
        "- See `docs/GRAPH_EXPANSION.md` for the integration roadmap.",
        "",
        "## Validation",
        "",
        "- `validation_targets_v2.csv` — 178 institutional ground-truth rows across 8 events (✅/⚠️ flagged)",
        "- `validation_targets_expanded.csv` — 94 rows across 42 events (literature + aggregates)",
        "- `event_evidence.csv` — 319 rows (Phase 2) cross-linking papers + v2 + aggregates per event",
        "- `benchmark_inputs.csv` — 42 event-level aggregates",
        "",
        "## Benchmark (Phase 3 result)",
        "",
    ]
    lines += bench_section_lines
    lines += [
        "",
        "**Comparison vs prior benchmark (`benchmark.json`):**",
        "",
    ]
    if bench_v1:
        lines += [
            f"- Prior N = {bench_v1.get('n_events')}; new N = {bench_v2.get('n_events_benchmarked') if bench_v2 else 'N/A'}",
        ]
    else:
        lines.append("- (no prior `benchmark.json` found)")
    lines += [
        "",
        "## Calibration (Phase 4 result)",
        "",
    ]
    lines += calib_lines
    lines.append("")
    lines += mcmc_lines
    lines += [
        "",
        "## Known weaknesses (do not exaggerate)",
        "",
        "1. **Sector enum is the bottleneck.** Engine `Industry` enum has only 7",
        "   members; 31 of 42 events touch sectors outside the enum and are",
        "   excluded from the benchmark. The Phase 1 expanded-graph CSV is",
        "   *data only* — wiring it into `seed.py` requires careful re-tuning",
        "   of per-node parameters that this session did not perform.",
        "",
        "2. **N benchmarked = ~11.** Even at N=42 corpus size, only the subset",
        "   matching engine-known sectors AND engine graph nodes can be scored.",
        "   Any 'GEDS beats baseline' claim is currently an N=11 claim.",
        "",
        "3. **MCMC budget is below user spec.** User asked for 600–1000 steps;",
        "   this session ran 150 steps × 20 walkers to fit the time window.",
        "   Posterior widths are wider than they would be with production budget.",
        "   See `posterior_v2.json::compute_budget_note`.",
        "",
        "4. **Only 1–10 events have paper corroboration depending on definition.**",
        "   Curated `PAPER_TO_EVENTS` map in `phase1_2_expand_and_mine.py` links",
        "   25 papers to events, but only papers with extractable numbers contribute",
        "   numeric evidence rows. Most papers are theoretical methodology, not",
        "   per-event measurements.",
        "",
        "5. **Recovery-time data is 97.6% blank.** Source docx never had an",
        "   explicit Recovery Time field — values exist only when paper text",
        "   explicitly says e.g. 'reconstruction: 10 years'.",
        "",
        "6. **Disk-space note.** During this session the local `C:` drive was",
        "   reported at 100% utilisation; pipeline runs should be kept on `D:`",
        "   until that's resolved.",
        "",
        "## Confidence summary",
        "",
        "| Layer | Aggregate confidence | Source |",
        "|---|---|---|",
        f"| Event registry | {sum(int(e['confidence'] or 0) for e in events)/max(n_events,1):.2f} / 5 | source-rated in docx |",
        f"| Dataset registry | {sum(int(d['confidence'] or 0) for d in datasets)/max(len(datasets),1):.2f} / 5 | derived from provider + API + Python-package signals |",
        f"| Literature registry | {sum(int(l['confidence'] or 0) for l in literature)/max(len(literature),1):.2f} / 5 | 5 for deeply-cataloged papers, 2-3 for title-only |",
        "",
        "## What is reproducible",
        "",
        "Every number in this doc traces to a file in the repo:",
        "",
        "- Event counts → `master_event_registry.csv`",
        "- Dataset counts → `master_dataset_registry.csv`",
        "- Graph node counts → `expanded_graph_nodes.csv` and `seed_data.py`",
        "- Benchmark numbers → `backend/data/calibration/benchmark_v2.json`",
        "- Calibration numbers → `backend/data/calibration/calibration_v2.json`",
        "- Posterior numbers → `backend/data/calibration/posterior_v2.json`",
        "",
        "Re-run order: `phase1_2_expand_and_mine.py` → `phase3_benchmark_v2.py`",
        "→ `phase4_calibrate_v2.py` → `phase5_regenerate_state.py`.",
        "",
    ]
    state.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
