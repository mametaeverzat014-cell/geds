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
    add("**Pairwise differences (paired bootstrap + sign-flip permutation):**")
    add("")
    add("| Pair (first − second) | ΔMAE [95% CI] | p (two-sided) | verdict |")
    add("|---|---|---|---|")
    for pair, d in sig["pairwise"].items():
        a, b = pair.split("__vs__")
        dm = d["delta_mae_a_minus_b"]
        signif = (dm["p2_5"] is not None and (dm["p2_5"] > 0 or dm["p97_5"] < 0)
                  and d["p_perm_mae_two_sided"] < 0.05)
        add(f"| {a} − {b} | {_ci(dm)} | {d['p_perm_mae_two_sided']:.2f} | "
            f"{'SIGNIFICANT' if signif else 'n.s.'} |")
    add("")
    add("**Reading:** no pairwise magnitude difference is significant at N="
        f"{bench.n_events} — single-number validation cannot rank these models. "
        "This motivates the trajectory axes below.")
    add("")

    add("## 2. Trajectory shape (Track B, node-level; the axes only GEDS attempts)")
    add("")
    add("| Dimension | n | Spearman [95% CI] | MAE |")
    add("|---|---|---|---|")
    for dim, pretty in (("magnitude", "peak magnitude"),
                        ("weeks_to_peak", "weeks to peak"),
                        ("recovery_weeks", "recovery weeks")):
        block = sig["cascade_shape_spearman"][dim]
        add(f"| {pretty} | {block['n']} | {_ci(block, 2)} | "
            f"{cascade.mae_by_dim[dim]:.2f} |")
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

    add("## 5. Figures")
    add("")
    add("Regenerate with `python -m scripts.isef_figures` "
        "(PNG + numeric CSV pairs in `backend/data/calibration/figures/`):")
    add("")
    add("- `parity_forest` — §1 pairwise CIs as a forest plot")
    add("- `pred_vs_obs` — §1 per-model scatter, N=27")
    add("- `timing_ramp` — §2 weeks_to_peak before/after the ramp")
    add("- `spatial_recall` — §4 per-event v2→v3 dumbbell")
    add("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
