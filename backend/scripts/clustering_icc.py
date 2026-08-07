"""How much statistical power would node-level scoring actually buy?

The benchmark scores one scalar per event, which is why N=27 and why the power
analysis needs ~166 events to resolve the observed model gaps. An obvious
response is to score at the NODE level instead: `cascade_spatial.csv` records
which downstream nodes each event reached and when, giving far more rows than
there are events.

The tempting version of that move is wrong. Node observations inside one event
are not independent — they share the same shock, the same graph neighbourhood
and the same measurement conventions — so treating 66 rows as N=66 would inflate
significance exactly the way this project exists to avoid. The honest question
is how much INDEPENDENT information those rows carry, which is what the
intraclass correlation measures:

    ICC   = var_between_events / (var_between_events + var_within_events)
    DEFF  = 1 + (m_bar - 1) * ICC          (design effect for clustered data)
    N_eff = n_observations / DEFF

ICC near 0 means residuals are essentially independent within an event and
node-level scoring nearly multiplies the sample. ICC near 1 means every node in
an event tells you the same thing and node-level scoring buys almost nothing —
in which case the only route to power really is more events, and this script
says so.

Estimator: one-way random-effects ANOVA on the per-observation residual
(predicted onset week minus observed onset week), clustered by event. Uses the
unbiased ANOVA estimator with the harmonic-style m_0 correction for unequal
cluster sizes, and clamps a negative variance estimate to 0 (ANOVA ICC can go
negative when between-cluster variance is smaller than sampling noise, which is
itself informative and reported rather than hidden).

Run:  python -m scripts.clustering_icc
Output: data/calibration/clustering_icc.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.core.backtest import _scenario_from_event
from app.core.graph import compile_graph
from app.core.propagation import PropagationEngine
from app.core.types import EngineConfig
from app.data.csv_loader import (
    load_cascade_spatial_csv,
    load_standardized_targets_csv,
)
from app.data.seed import load_graph
from app.data.seed_data import HISTORICAL_EVENTS

CAL = Path(__file__).resolve().parents[1] / "data" / "calibration"


def out_path(graph_version: str) -> Path:
    """v2 and v3 are different measurements and must not overwrite each other."""
    suffix = "" if graph_version == "v2" else f"_{graph_version}"
    return CAL / f"clustering_icc{suffix}.json"

REACH_THRESHOLD = 0.01   # same definition of "node was hit" as the spatial report


def collect_residuals(graph_version: str = "v2") -> tuple[list[str], list[float], list[dict], dict]:
    """Per (event, node) onset residual, plus the funnel that produced them.

    The funnel matters more than the residuals here. On the hand-authored v2
    graph most observed nodes are simply never reached by the cascade (spatial
    recall 0.29), and a node with no predicted onset contributes no residual —
    so the node-level sample collapses to roughly one observation per event and
    the ICC becomes inestimable. Running the same measurement on v3, where
    recall is 0.79, is the test of whether that collapse is a property of the
    data or of the graph.
    """
    cfg = EngineConfig(stochastic_sigma=0.0, seed=0)
    events = {e["slug"]: e for e in HISTORICAL_EVENTS}
    perp_to_engine = {t.perplexity_slug: t.engine_slug
                      for t in load_standardized_targets_csv()}

    if graph_version == "v3":
        from app.data.expanded_graph import build_expanded_snapshot, to_v3_node
        graph = compile_graph(build_expanded_snapshot())
        remap = to_v3_node
    else:
        graph = compile_graph(load_graph())
        remap = lambda nid: nid  # noqa: E731

    rows = load_cascade_spatial_csv()
    funnel = {"rows_total": len(rows)}

    # group observed onsets: engine_slug -> node_id -> earliest observed week
    observed: dict[str, dict[str, int]] = {}
    with_onset = 0
    for r in rows:
        if r.onset_week is None:
            continue
        with_onset += 1
        eng = perp_to_engine.get(r.slug, r.slug)
        if eng not in events:
            continue
        nid = remap(r.node_id())
        if nid is None:
            continue
        bucket = observed.setdefault(eng, {})
        bucket[nid] = min(bucket.get(nid, r.onset_week), r.onset_week)

    funnel["rows_with_onset"] = with_onset
    funnel["pairs_in_wired_events"] = sum(len(v) for v in observed.values())

    cluster: list[str] = []
    resid: list[float] = []
    detail: list[dict] = []
    representable = 0

    for slug, nodes in sorted(observed.items()):
        ev = events.get(slug)
        if ev is None:
            continue
        # on v3 the shocked node must be remapped too, else the run is empty
        shocks = []
        mappable = True
        for sh in ev["shocks"]:
            t = remap(sh["target_node_id"])
            if t is None or t not in graph.index:
                mappable = False
                break
            shocks.append({**sh, "target_node_id": t})
        if not mappable:
            continue
        sim = PropagationEngine(graph, cfg).run(
            _scenario_from_event({**ev, "shocks": shocks}, cfg))

        for nid, obs_week in sorted(nodes.items()):
            idx = graph.index.get(nid)
            if idx is None:
                continue  # node not representable in this graph
            representable += 1
            traj = np.array([f.nodes[idx].output_loss for f in sim.frames])
            hit = np.where(traj >= REACH_THRESHOLD)[0]
            if not hit.size:
                continue  # never reached: no predicted onset to compare
            pred_week = float(hit[0])
            cluster.append(slug)
            resid.append(pred_week - float(obs_week))
            detail.append({"event": slug, "node": nid,
                           "predicted_onset_week": pred_week,
                           "observed_onset_week": int(obs_week),
                           "residual_weeks": pred_week - float(obs_week)})

    funnel["pairs_representable_in_graph"] = representable
    funnel["pairs_reached_by_cascade"] = len(resid)
    return cluster, resid, detail, funnel


def anova_icc(cluster: list[str], value: list[float]) -> dict:
    """One-way random-effects ICC with unequal cluster sizes."""
    groups: dict[str, list[float]] = {}
    for c, v in zip(cluster, value):
        groups.setdefault(c, []).append(v)
    # a cluster of one contributes nothing to within-variance; keep it for the
    # between term but the estimator needs k >= 2 clusters and n > k
    k = len(groups)
    n = sum(len(v) for v in groups.values())
    if k < 2 or n <= k:
        return {"estimable": False,
                "reason": f"need >=2 clusters and n>k; got k={k}, n={n}"}

    grand = float(np.mean(value))
    ms_between = sum(len(v) * (np.mean(v) - grand) ** 2 for v in groups.values()) / (k - 1)
    ss_within = sum(float(np.sum((np.asarray(v) - np.mean(v)) ** 2)) for v in groups.values())
    ms_within = ss_within / (n - k)

    # m_0: correction for unequal cluster sizes (Snedecor & Cochran)
    sizes = np.array([len(v) for v in groups.values()], dtype=float)
    m0 = (n - float((sizes ** 2).sum()) / n) / (k - 1)

    var_between_raw = (ms_between - ms_within) / m0 if m0 > 0 else 0.0
    var_between = max(0.0, var_between_raw)
    total = var_between + ms_within
    icc = var_between / total if total > 0 else 0.0

    m_bar = n / k
    deff = 1.0 + (m_bar - 1.0) * icc
    # An ICC needs clusters with more than one member to be estimated at all.
    # With m_bar near 1 there is almost no within-cluster variation, MS_within
    # is built from a handful of clusters, and the estimate is degenerate —
    # ICC collapses to 0 and DEFF to 1 by construction, NOT as a finding.
    multi = int(sum(1 for v in groups.values() if len(v) > 1))
    degenerate = m_bar < 1.5 or multi < 3
    return {
        "estimable": True,
        "n_clusters_with_multiple_observations": multi,
        "degenerate_design": degenerate,
        "degenerate_reason": (
            f"mean cluster size {m_bar:.2f} and only {multi} cluster(s) have "
            "more than one observation — there is not enough within-event "
            "variation to estimate an ICC; the value below is an artifact of "
            "the design, not a measurement"
            if degenerate else None
        ),
        "n_observations": int(n),
        "n_clusters": int(k),
        "mean_cluster_size": round(m_bar, 3),
        "m0_unequal_size_correction": round(float(m0), 3),
        "ms_between": round(float(ms_between), 4),
        "ms_within": round(float(ms_within), 4),
        "var_between_raw": round(float(var_between_raw), 4),
        "var_between_clamped_at_zero": bool(var_between_raw < 0),
        "icc": round(float(icc), 4),
        "design_effect": round(float(deff), 4),
        "effective_n": round(float(n / deff), 2),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="ICC of node-level onset residuals")
    ap.add_argument("--graph", choices=("v2", "v3"), default="v2")
    args = ap.parse_args(argv)

    cluster, resid, detail, funnel = collect_residuals(args.graph)
    stats = anova_icc(cluster, resid)

    payload = {
        "schema": "geds.clustering_icc.v2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "graph_version": args.graph,
        "quantity": "onset-week residual (predicted minus observed), per event x node",
        "reach_threshold": REACH_THRESHOLD,
        "source": "data/csv/cascade_spatial.csv",
        "estimator": "one-way random-effects ANOVA, unequal cluster sizes (m0 correction)",
        "sample_funnel": funnel,
        "statistics": stats,
        "observations": detail,
    }

    if stats.get("estimable") and stats.get("degenerate_design"):
        payload["interpretation"] = {
            "reading": stats["degenerate_reason"],
            "verdict": (
                "INESTIMABLE on this graph. The node-level sample collapses "
                "before the statistics start: of "
                f"{funnel['pairs_representable_in_graph']} observed node-pairs the "
                f"graph can represent, the cascade reaches only "
                f"{funnel['pairs_reached_by_cascade']}. A node the cascade never "
                "reaches has no predicted onset and contributes no residual, so "
                "there is roughly one usable observation per event and nothing to "
                "cluster. This is the spatial-recall limitation showing up again, "
                "not a property of node-level scoring."
            ),
            "next_test": (
                "Re-run on the v3 graph, where pooled spatial recall is 0.79 "
                "instead of 0.29. If the sample survives there, the ICC becomes "
                "estimable and the question can be answered; if it does not, the "
                "node-level route is closed for this benchmark."
            ),
        }
    elif stats.get("estimable"):
        icc, neff, n = stats["icc"], stats["effective_n"], stats["n_observations"]
        payload["interpretation"] = {
            "reading": (
                f"{n} node-level observations across {stats['n_clusters']} events "
                f"carry the independent information of about {neff:.0f} "
                f"independent observations (ICC {icc:.3f}, design effect "
                f"{stats['design_effect']:.2f})."
            ),
            "verdict": (
                "node-level scoring buys substantial power: residuals are close "
                "to independent within an event, so the effective sample is much "
                "larger than the event count"
                if icc < 0.15 else
                "node-level scoring buys moderate power; within-event correlation "
                "absorbs a meaningful share of the extra rows"
                if icc < 0.4 else
                "node-level scoring buys little: nodes inside one event largely "
                "repeat the same information, so more EVENTS, not more nodes, is "
                "the only route to power"
            ),
            "caveat": (
                "This is the ICC of onset-week residuals, the dimension with the "
                "most node-level data. It does not license treating node rows as "
                "independent on the magnitude axis, where n is far smaller and "
                "the clustering may differ."
            ),
        }
    out = out_path(args.graph)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"graph: {args.graph}   funnel: " + " -> ".join(f"{k}={v}" for k, v in funnel.items()))
    print(f"observations: {stats.get('n_observations')}   "
          f"events (clusters): {stats.get('n_clusters')}   "
          f"mean cluster size: {stats.get('mean_cluster_size')}")
    if not stats.get("estimable"):
        print("NOT ESTIMABLE:", stats.get("reason"))
        print(f"wrote {out}")
        return 0
    print()
    print(f"  ICC            = {stats['icc']:.4f}"
          + ("   (between-event variance clamped at 0)"
             if stats["var_between_clamped_at_zero"] else ""))
    print(f"  design effect  = {stats['design_effect']:.3f}")
    print(f"  effective N    = {stats['effective_n']:.1f}"
          f"   (vs {stats['n_clusters']} at event level, "
          f"{stats['n_observations']} if wrongly treated as independent)")
    print()
    print("verdict:", payload["interpretation"]["verdict"])
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
