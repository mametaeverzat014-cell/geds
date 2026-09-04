#!/usr/bin/env python3
"""Which node property, if any, explains WHEN a shock arrives?

WHY THIS EXISTS
---------------
Two places in the UI quoted four onset-lag correlations — dependency share
-0.45, vulnerability -0.53, centrality -0.46, inventory depth -0.44 — and drew a
mechanism from them ("timing falls out of the whole propagation step"). Those
numbers lived in a source comment. There was no artifact, no n, no interval and
no script that regenerated them, so nothing on the site could be checked against
anything, and the claim built on top of them could not be attacked.

That is the same failure mode that has already cost this project two published
results. So the quantity is measured here, with the funnel written down, and the
UI reads the artifact.

WHAT IS MEASURED
----------------
For the flagship scenario on the v2 graph:

    onset_week(node) = first week the node's output_loss reaches REACHED (0.01)

Nodes never reached inside the horizon are EXCLUDED, not imputed — substituting
the horizon would let the window length carry ordering information, which is the
exact confound that inflated the recovery result to 0.88 before it was fixed at
source (see scripts/fixed_horizon_recovery.py). Shock origins are excluded too:
they are forced at week 0 by construction and would anchor every correlation.

Candidate drivers, read off the same compiled graph the engine ran:

    dependency_share   row sum of D_eff — total effective dependence on suppliers
    vulnerability      node attribute
    centrality         node attribute
    inventory_depth    SEIS buffer depth in weeks

Spearman rho with a percentile bootstrap CI over nodes, plus a PAIRED bootstrap
of every pairwise difference with Holm correction. The pairing matters: both
coefficients in a comparison come from the same nodes, and eyeballing whether two
intervals overlap is not a test of difference.

WHAT IS NOT ESTABLISHED
-----------------------
The candidates are correlated with each other; that matrix is reported. No
partial or multivariate analysis is run, so this cannot say which property, if
any, does the work. A negative result here means "no candidate is separable from
the others at this n" and nothing more.

USAGE
    python -m scripts.onset_drivers
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.core.graph import compile_graph  # noqa: E402
from app.core.metrics import spearman_rho  # noqa: E402
from app.core.propagation import PropagationEngine  # noqa: E402
from app.core.scenarios import by_id, list_scenarios  # noqa: E402
from app.data.seed import load_graph  # noqa: E402

REACHED = 0.01  # the published reach threshold, the same constant the UI uses
N_BOOT = 4000
SEED = 20260814

OUT = HERE.parent / "data" / "calibration" / "onset_drivers.json"


def onset_weeks(frames, node_ids: set[str]) -> dict[str, int]:
    """First week each node crosses REACHED. An absent key means never reached."""
    first: dict[str, int] = {}
    for f in frames:
        for n in f.nodes:
            if n.output_loss >= REACHED and n.id not in first:
                first[n.id] = f.week
    return {k: v for k, v in first.items() if k in node_ids}


def bootstrap_rho(x: np.ndarray, y: np.ndarray, n_boot: int, seed: int) -> dict:
    """Percentile CI on Spearman rho, resampling NODES (the sampling unit)."""
    rng = np.random.default_rng(seed)
    n = len(x)
    point = spearman_rho(list(x), list(y))
    if n < 4:
        return {"rho": round(float(point), 4), "n": n, "ci95_lo": None, "ci95_hi": None}
    draws = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        xs, ys = x[idx], y[idx]
        # A resample can be constant in either variable; rho is undefined there.
        if len(np.unique(xs)) < 2 or len(np.unique(ys)) < 2:
            continue
        draws.append(spearman_rho(list(xs), list(ys)))
    if len(draws) < n_boot // 10:
        return {"rho": round(float(point), 4), "n": n, "ci95_lo": None, "ci95_hi": None,
                "note": "too many degenerate resamples for an interval"}
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {
        "rho": round(float(point), 4),
        "n": int(n),
        "ci95_lo": round(float(lo), 4),
        "ci95_hi": round(float(hi), 4),
        "n_boot_used": len(draws),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="taiwan-semi-75")
    args = ap.parse_args()

    known = {s.id for s in list_scenarios()}
    if args.scenario not in known:
        print(f"unknown scenario {args.scenario}; have {sorted(known)}", file=sys.stderr)
        return 1
    scenario = by_id(args.scenario)

    graph = compile_graph(load_graph())
    result = PropagationEngine(graph).run(scenario)

    node_ids = list(graph.node_ids)
    index = dict(graph.index)
    origins = {sh.target_node_id for sh in scenario.shocks}
    onsets = onset_weeks(result.frames, set(node_ids))

    # D_eff rows are targets, so a row sum is that node's total effective
    # dependence on its suppliers — the quantity the UI calls "dependency share",
    # and the one the engine actually multiplies against.
    drivers = {
        "dependency_share": np.asarray(graph.D_eff.sum(axis=1)).ravel().astype(float),
        "vulnerability": np.asarray(graph.vulnerability, dtype=float),
        "centrality": np.asarray(graph.centrality, dtype=float),
        "inventory_depth": np.asarray(graph.inventory_weeks, dtype=float),
    }
    names = list(drivers)

    kept = [
        nid for nid in node_ids
        if nid in onsets and nid not in origins and onsets[nid] > 0
    ]
    funnel = {
        "nodes_in_graph": len(node_ids),
        "shock_origins_excluded": len(origins & set(node_ids)),
        "never_reached_excluded": len(node_ids) - len(onsets),
        "onset_week_zero_excluded": sum(
            1 for nid in node_ids
            if nid in onsets and nid not in origins and onsets[nid] == 0
        ),
        "nodes_scored": len(kept),
    }

    y = np.array([onsets[nid] for nid in kept], dtype=float)
    xs_all = {n: np.array([drivers[n][index[nid]] for nid in kept]) for n in names}

    rows = {}
    for name in names:
        rows[name] = bootstrap_rho(xs_all[name], y, N_BOOT, SEED)
        rows[name]["constant_across_scored_nodes"] = bool(len(np.unique(xs_all[name])) < 2)

    collinearity = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            collinearity[f"{a}__{b}"] = round(
                float(spearman_rho(list(xs_all[a]), list(xs_all[b]))), 4
            )

    # ── are any two candidates actually distinguishable? ─────────────────────
    # PAIRED: each replicate draws one set of node indices and computes every rho
    # on it, the same shared-index scheme the ablation and Spearman families use.
    # Holm across the six pairs, because six comparisons on one small sample is
    # exactly where an uncorrected "significant" difference appears out of noise.
    rng = np.random.default_rng(SEED + 1)
    boot_rows: list[dict[str, float]] = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(kept), len(kept))
        ys = y[idx]
        if len(np.unique(ys)) < 2:
            continue
        rep, ok = {}, True
        for name in names:
            v = xs_all[name][idx]
            if len(np.unique(v)) < 2:
                ok = False
                break
            rep[name] = spearman_rho(list(v), list(ys))
        if ok:
            boot_rows.append(rep)

    pair_tests: dict[str, dict] = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            diffs = np.array([r[a] - r[b] for r in boot_rows])
            if len(diffs) < N_BOOT // 10:
                continue
            lo, hi = np.percentile(diffs, [2.5, 97.5])
            frac = float(np.mean(diffs <= 0))
            # Two-sided bootstrap p, floored at 1/B so it is never reported as 0.
            p = max(min(1.0, 2 * min(frac, 1 - frac)), 1.0 / len(diffs))
            pair_tests[f"{a}__{b}"] = {
                "delta_rho": round(float(rows[a]["rho"] - rows[b]["rho"]), 4),
                "ci95_lo": round(float(lo), 4),
                "ci95_hi": round(float(hi), 4),
                "p_boot": round(p, 4),
            }

    ordered = sorted(pair_tests.items(), key=lambda kv: kv[1]["p_boot"])
    m, running = len(ordered), 0.0
    for rank, (key, v) in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * v["p_boot"]))  # monotone
        pair_tests[key]["p_holm"] = round(running, 4)
        pair_tests[key]["significant"] = bool(running < 0.05)

    n_sig = sum(1 for v in pair_tests.values() if v.get("significant"))

    payload = {
        "scenario": args.scenario,
        "graph_version": "v2",
        "reach_threshold": REACHED,
        "horizon_weeks": scenario.horizon_weeks,
        "quantity": "Spearman rho of onset week against each candidate driver",
        "sampling_unit": "node",
        "n_boot": N_BOOT,
        "seed": SEED,
        "funnel": funnel,
        "onset_week_range": [int(y.min()), int(y.max())] if len(y) else None,
        "correlations": rows,
        "collinearity_spearman": collinearity,
        "pairwise_paired_bootstrap": pair_tests,
        "n_pairs_significant_after_holm": n_sig,
        "verdict": (
            "No pair of candidates is distinguishable after Holm correction: at "
            f"n={len(kept)} this run cannot separate them."
            if n_sig == 0 else
            f"{n_sig} of {len(pair_tests)} pairs differ after Holm correction — "
            "the candidates are NOT interchangeable here."
        ),
        "not_established": (
            "The candidates are correlated with each other (see "
            "collinearity_spearman); no partial or multivariate analysis was run, "
            "so this does not identify which property, if any, drives onset "
            "timing. One scenario on one graph is measured here."
        ),
        "reproduce_command": "python -m scripts.onset_drivers",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(f"scored {funnel['nodes_scored']} of {funnel['nodes_in_graph']} nodes")
    for name, v in rows.items():
        ci = (f"[{v['ci95_lo']:+.3f}, {v['ci95_hi']:+.3f}]"
              if v.get("ci95_lo") is not None else "[no interval]")
        print(f"  {name:18s} rho={v['rho']:+.3f}  n={v['n']:3d}  95% CI {ci}")
    print(f"\npairs significant after Holm: {n_sig} of {len(pair_tests)}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
