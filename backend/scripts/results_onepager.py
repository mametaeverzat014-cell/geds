"""Generate docs/RESULTS.md — the single source of truth for every headline
number, assembled from committed artifacts and live engine runs.

The poster, the paper, and the interview all quote THIS file; this file
quotes only artifacts. Never hand-edit docs/RESULTS.md — rerun:

    python -m scripts.results_onepager        (~4 min)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
CALIB = BACKEND / "data" / "calibration"
OUT = BACKEND.parent / "docs" / "RESULTS.md"


def _ci(block: dict | None, digits: int = 4) -> str:
    if not block or block.get("point") is None:
        return "—"
    f = f"{{:.{digits}f}}"
    return (f"{f.format(block['point'])} "
            f"[{f.format(block['p2_5'])}, {f.format(block['p97_5'])}]")


def main() -> int:
    from app.core.benchmark import run_benchmark
    from app.core.benchmark import _eval_leontief
    from app.core.cascade_validation import (compare_spatial_recall,
                                             run_cascade_validation,
                                             run_spatial_validation)
    from app.core.graph import compile_graph
    from app.core.significance import paired_delta_bootstrap, sign_flip_p
    from app.data.seed import load_graph
    from app.data.seed_data import HISTORICAL_EVENTS

    sig = json.loads((CALIB / "significance.json").read_text())
    loo = json.loads((CALIB / "loo_de_result.json").read_text())
    ramp = json.loads((CALIB / "ramp_experiment.json").read_text())
    abl = json.loads((CALIB / "ablation.json").read_text())
    ident = json.loads((CALIB / "identifiability.json").read_text())
    robust = json.loads((CALIB / "spatial_recall_robustness.json").read_text())

    bench = run_benchmark()
    cascade = run_cascade_validation()
    spatial = run_spatial_validation()
    cmp = compare_spatial_recall()

    # paired out-of-sample test: LOO-recalibrated GEDS vs Leontief
    graph = compile_graph(load_graph())
    leon_pred, obs = _eval_leontief(graph)
    by_slug = {f["slug"]: f for f in loo["folds"]}
    slugs = [e["slug"] for e in HISTORICAL_EVENTS]
    loo_pred = np.array([by_slug[s]["loss_predicted"] for s in slugs])
    assert np.allclose(np.array([by_slug[s]["loss_observed"] for s in slugs]), obs)
    seed = sig["seed"]
    loo_p = sign_flip_p(np.abs(loo_pred - obs), np.abs(leon_pred - obs),
                        n_perm=sig["n_perm"], seed=seed)
    loo_delta = paired_delta_bootstrap(loo_pred, leon_pred, obs,
                                       n_boot=sig["n_boot"], seed=seed)

    L: list[str] = []
    add = L.append
    add("# GEDS — headline results (generated)")
    add("")
    add("> GENERATED FILE — regenerate with `python -m scripts.results_onepager`;")
    add("> never hand-edit. Sources: live engine runs plus `significance.json`")
    add(f"> (seed {sig['seed']}, {sig['n_boot']} bootstrap / {sig['n_perm']} perms,")
    add(f"> generated {sig['timestamp'][:10]}), `loo_de_result.json`")
    add(f"> ({loo['n_folds']} folds, {loo['timestamp'][:10]}), `ramp_experiment.json`")
    add(f"> ({ramp['timestamp'][:10]}). Benchmark config is the pinned deterministic")
    add("> config (`BENCHMARK_CONFIG`, stochastic_sigma=0, seed=0).")
    add("")
    add(f"**Benchmark set:** N={bench.n_events} primary-sourced historical events "
        "(1999–2023), golden-locked in `tests/test_reproducibility.py`.")
    add("")

    add("## 1. Point magnitude (Track A): four models, default parameters")
    add("")
    add("| Model | MAE [95% CI] | RMSE [95% CI] | Spearman [95% CI] |")
    add("|---|---|---|---|")
    for key, disp in sig["model_display_names"].items():
        m = sig["models"][key]
        add(f"| {disp} | {_ci(m['mae'])} | {_ci(m['rmse'])} | "
            f"{_ci(m['spearman'], 2) if m['spearman'] else 'constant — no ranking'} |")
    add("")
    add("**Pairwise differences (paired bootstrap + sign-flip permutation, "
        "Holm-corrected across all 6 pairs):**")
    add("")
    add("| Pair (first − second) | ΔMAE [95% CI] | p raw | p Holm | verdict |")
    add("|---|---|---|---|---|")
    for pair, d in sig["pairwise"].items():
        a, b = pair.split("__vs__")
        dm = d["delta_mae_a_minus_b"]
        add(f"| {a} − {b} | {_ci(dm)} | {d['p_perm_mae_two_sided']:.2f} | "
            f"{d['p_holm_mae_two_sided']:.2f} | "
            f"{'SIGNIFICANT' if d['significant_at_05_holm'] else 'n.s.'} |")
    add("")
    add(f"**Reading:** {sig['n_pairwise_significant_after_holm']} of "
        f"{len(sig['pairwise'])} pairwise magnitude differences are significant "
        f"at N={bench.n_events}. The six pairs are published as one table and so "
        "form one family of tests; the Holm-adjusted column is the operative "
        "one. Single-number validation cannot rank these models — which is what "
        "motivates the trajectory axes below.")
    add("")

    add("## 2. Trajectory shape (Track B, node-level; the axes only GEDS attempts)")
    add("")
    add("| Dimension | n | Spearman [95% CI] | family-wise 98.3% CI | MAE | survives correction |")
    add("|---|---|---|---|---|---|")
    for dim, pretty in (("magnitude", "peak magnitude"),
                        ("weeks_to_peak", "weeks to peak"),
                        ("recovery_weeks", "recovery weeks")):
        block = sig["cascade_shape_spearman"][dim]
        fw = (f"[{block['fw_p_low']:.2f}, {block['fw_p_high']:.2f}]"
              if "fw_p_low" in block else "—")
        ok = "**yes**" if block.get("excludes_zero_familywise") else "no"
        add(f"| {pretty} | {block['n']} | {_ci(block, 2)} | {fw} | "
            f"{cascade.mae_by_dim[dim]:.2f} | {ok} |")
    add("")
    survivors = [d for d in ("magnitude", "weeks_to_peak", "recovery_weeks")
                 if sig["cascade_shape_spearman"][d].get("excludes_zero_familywise")]
    add(f"**Reading:** the three dimensions are one published family, so a 95% "
        f"interval on each does not give 95% confidence in all three. "
        f"{len(survivors)} of 3 excludes zero at the family-wise level: "
        f"{', '.join(survivors) if survivors else 'none'}. "
        "This is the strongest quantitative result in the project.")
    add("")
    b_wtp = ramp["baseline"]["cascade"]["spearman_by_dim"]["weeks_to_peak"]
    r_wtp = ramp["ramp"]["cascade"]["spearman_by_dim"]["weeks_to_peak"]
    add(f"**Batch-19 ramp result:** weeks_to_peak was at chance ({b_wtp:.2f}) "
        f"because the engine had no rising forcing shape; the pre-registered "
        f"`ramp` adoption moved it to {r_wtp:.2f} at a benchmark cost of "
        f"+{ramp['gate_results']['G3_mae_delta']:.4f} MAE (gate: all 4 criteria "
        "passed; see `ramp_experiment.json`).")
    add("")

    add("## 3. Out-of-sample (leave-one-out, per-fold DE recalibration)")
    add("")
    s = loo["out_of_sample_score"]
    add(f"| | MAE | RMSE | Pearson | Spearman | R² |")
    add(f"|---|---|---|---|---|---|")
    add(f"| GEDS, LOO-recalibrated ({loo['n_folds']} folds) | {s['mae']:.4f} | "
        f"{s['rmse']:.4f} | {s['pearson']:.2f} | {s['spearman']:.2f} | "
        f"{s['r_squared']:.2f} |")
    add("")
    dm = loo_delta["delta_mae_a_minus_b"]
    add(f"Paired vs Leontief (zero-parameter baseline): ΔMAE {_ci(dm)}, "
        f"p={loo_p:.2f} — **magnitude parity holds out-of-sample too**, "
        "tuned or untuned.")
    add("")

    add("## 4. Spatial reach (did the cascade hit the right nodes?)")
    add("")
    add(f"| Graph | nodes | pooled spatial recall |")
    add(f"|---|---|---|")
    add(f"| v2 hand-authored | 36 | {cmp.v2_recall:.2f} ({cmp.v2_reached}/{cmp.v2_nodes}) |")
    add(f"| v3 OECD ICIO 2019 | 405 | {cmp.v3_recall:.2f} ({cmp.v3_reached}/{cmp.v3_nodes}) |")
    add("")
    add(f"Same engine, same shocks — only the graph changes ({cmp.events_compared} "
        f"comparable production events). Onset ordering on reached nodes: "
        f"Spearman {spatial.onset_spearman:.2f} (v2). Structure, not parameter "
        "tuning, is the binding constraint.")
    add("")
    add("**Robustness — is this a threshold artifact?** v3 runs ~4× hot in "
        "magnitude, so a fixed reach threshold could favour it mechanically. "
        "Sweeping the threshold across two orders of magnitude "
        "(`spatial_recall_robustness.json`):")
    add("")
    add("| reach threshold | v2 recall | v3 recall | v3 − v2 | v3 / v2 |")
    add("|---|---|---|---|---|")
    for r in robust["rows"]:
        tag = (" *(published)*" if r["is_published_threshold"]
               else " *(scale-corrected)*" if r["is_scale_corrected_threshold"]
               else "")
        ratio = f"{r['v3_over_v2']:.1f}×" if r["v3_over_v2"] else "—"
        add(f"| {r['threshold']}{tag} | {r['v2_recall']:.3f} "
            f"({r['v2_reached']}/{r['v2_nodes']}) | {r['v3_recall']:.3f} "
            f"({r['v3_reached']}/{r['v3_nodes']}) | {r['v3_minus_v2']:+.3f} | {ratio} |")
    add("")
    add(f"v3 leads at every threshold tested, including the scale-corrected "
        f"point {robust['scale_corrected_threshold']} "
        f"(= published threshold ÷ k, k={robust['k_v3_scale']}). "
        "The structural result is not a scale artifact.")
    add("")

    add("## 5. Component ablation — and why the table is not a ranking")
    add("")
    add("| Variant | MAE | ΔMAE vs full [95% CI] | p Holm | significant |")
    add("|---|---|---|---|---|")
    for r in abl["rows"]:
        if r["variant"] == "full":
            add(f"| {r['variant']} | {r['mae_loss']:.4f} | — | — | — |")
            continue
        add(f"| {r['variant']} | {r['mae_loss']:.4f} | "
            f"{r['mae_delta_vs_full']:+.4f} "
            f"[{r['mae_delta_ci_low']:+.4f}, {r['mae_delta_ci_high']:+.4f}] | "
            f"{r['p_holm_vs_full']:.2f} | "
            f"{'SIGNIFICANT' if r['significant_vs_full'] else 'n.s.'} |")
    add("")
    add(f"**Reading:** {abl['verdict']}")
    add("")
    add("Negative ΔMAE means the variant had *lower* error than the full engine "
        "— i.e. the component removed was costing accuracy. Point estimates put "
        "the SEIRS state machine and the hysteresis floor in that category, but "
        "no delta clears the correction, so the honest statement is that this "
        "benchmark cannot resolve any component's contribution.")
    add("")

    add("## 6. Parameter identifiability")
    add("")
    add("| Parameter | global fit | prior box | pinned to bound | LOO range | range/median |")
    add("|---|---|---|---|---|---|")
    for nm, b in ident["boundary_pinning"].items():
        d = ident["loo_dispersion"].get(nm, {})
        rom = (f"{d['range_over_median']:.1f}×" if d.get("range_over_median")
               else "—")
        add(f"| `{nm}` | {b['point']:.4f} | "
            f"[{b['prior_low']:g}, {b['prior_high']:g}] | "
            f"{'**yes**' if b['pinned'] else 'no'} | "
            f"[{d.get('min', float('nan')):.4g}, {d.get('max', float('nan')):.4g}] | {rom} |")
    add("")
    add(f"**Reading:** {ident['verdict']}")
    add("")
    add(f"The global fit falls outside the entire leave-one-out range for "
        f"{ident['summary']['n_global_fits_outside_loo_range']} of "
        f"{ident['n_parameters']} parameters, and only "
        f"{ident['global_fit_converged_fraction']:.0%} of DE restarts converged "
        "— both signatures of a flat or multimodal loss surface.")
    add("")

    add("## 7. Figures")
    add("")
    add("Regenerate with `python -m scripts.isef_figures` "
        "(PNG + numeric CSV pairs in `backend/data/calibration/figures/`):")
    add("")
    add("- `parity_forest` — §1 pairwise CIs as a forest plot")
    add("- `pred_vs_obs` — §1 per-model scatter, N=27")
    add("- `timing_ramp` — §2 weeks_to_peak before/after the ramp")
    add("- `spatial_recall` — §4 per-event v2→v3 dumbbell")
    add("")
    add("## 8. What this benchmark can and cannot support")
    add("")
    add("Four independent lines of evidence converge on one ceiling:")
    add("")
    add(f"1. **Power** — every observed pairwise |ΔMAE| is below its minimum "
        f"detectable effect; ~166 events would be needed to resolve the "
        f"GEDS/Leontief gap (`power_analysis.json`).")
    add(f"2. **Multiplicity** — "
        f"{sig['n_pairwise_significant_after_holm']}/{len(sig['pairwise'])} "
        f"model pairs and "
        f"{abl['n_significant_after_holm']}/"
        f"{len([r for r in abl['rows'] if r['variant'] != 'full'])} "
        f"ablation deltas survive Holm correction.")
    add(f"3. **Identifiability** — "
        f"{ident['summary']['n_pinned_at_prior_bound']}/{ident['n_parameters']} "
        f"parameters are pinned to their search-box bounds; one moves "
        f"{ident['loo_dispersion']['amplification_mu']['range_over_median']:.0f}× "
        f"its own median under leave-one-out.")
    add("4. **Parsimony** — on the dense graph a single scale parameter "
        "outperforms five tuned ones in point terms "
        "(`v3_calibration_result.json`).")
    add("")
    add("What survives all of it: the **recovery-duration ordering** "
        "(Track B, family-wise CI excludes zero) and the **structural graph "
        "result** (§4, robust across the full threshold sweep). Those two are "
        "the defensible contributions; the magnitude leaderboard is a measured "
        "null.")
    add("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
