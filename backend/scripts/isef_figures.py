"""Poster/paper figure generator — every figure ships with its numeric CSV.

Four figures, each regenerated from committed artifacts or live engine runs
(never hand-drawn, per the repo rule that any graphic must come with a
checkable numeric table):

  1. parity_forest    — paired ΔMAE 95% CIs + permutation p for all 6 model
                        pairs (the "nothing wins on magnitude" result)
  2. pred_vs_obs      — per-model predicted-vs-observed scatter, N=27
  3. timing_ramp      — weeks_to_peak before/after the Batch-19 ramp adoption
  4. spatial_recall   — v2 (36-node) vs v3 (405-node ICIO) cascade reach

Colors are the first three slots of the validated categorical palette from
the dataviz reference (all-pairs colorblind-safe at <=3 series):
blue #2a78d6, orange #eb6834, aqua #1baf7a. Text/ink stays neutral.

Run:  python -m scripts.isef_figures      (~3 min; writes PNG+CSV pairs)
Output: data/calibration/figures/
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
CALIB = BACKEND / "data" / "calibration"
OUT = CALIB / "figures"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#333333", "#666666", "#e0e0e0"

plt.rcParams.update({
    "figure.dpi": 200, "savefig.dpi": 200, "font.size": 9,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
})


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def fig_parity_forest(sig: dict) -> None:
    pairs = list(sig["pairwise"].items())
    labels, pts, los, his, ps = [], [], [], [], []
    for name, d in pairs:
        a, b = name.split("__vs__")
        dm = d["delta_mae_a_minus_b"]
        labels.append(f"{a} − {b}")
        pts.append(dm["point"]); los.append(dm["p2_5"]); his.append(dm["p97_5"])
        ps.append(d["p_perm_mae_two_sided"])

    y = np.arange(len(labels))[::-1]
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.axvline(0, color=INK, lw=1.2, zorder=1)
    ax.hlines(y, los, his, color=BLUE, lw=2, zorder=2)
    ax.scatter(pts, y, s=42, color=BLUE, zorder=3)
    for yi, hi, p in zip(y, his, ps):
        ax.annotate(f"p={p:.2f}", (hi, yi), xytext=(6, -3),
                    textcoords="offset points", fontsize=8, color=MUTED)
    ax.set_yticks(y, labels, fontsize=8)
    ax.set_xlabel("Δ MAE (first − second), 95% paired-bootstrap CI")
    ax.set_title("Point-magnitude parity at N=27:\nno model pair separates",
                 loc="left", fontsize=10, fontweight="bold")
    ax.margins(x=0.15)
    fig.tight_layout()
    fig.savefig(OUT / "parity_forest.png", bbox_inches="tight")
    plt.close(fig)
    _write_csv(OUT / "parity_forest.csv",
               ["pair", "delta_mae", "ci_lo", "ci_hi", "p_perm_two_sided"],
               [[l, p, lo, hi, pp] for l, p, lo, hi, pp
                in zip(labels, pts, los, his, ps)])


def fig_pred_vs_obs(sig: dict) -> None:
    from app.core.benchmark import (BENCHMARK_CONFIG, _eval_diffusion,
                                    _eval_leontief, _eval_persistence,
                                    _eval_seirs)
    from app.core.graph import compile_graph
    from app.data.seed import load_graph
    from app.data.seed_data import HISTORICAL_EVENTS

    graph = compile_graph(load_graph())
    evals = {
        "GEDS": _eval_seirs(graph, BENCHMARK_CONFIG),
        "Leontief": _eval_leontief(graph),
        "LinearDiffusion": _eval_diffusion(graph),
        "NaivePersistence": _eval_persistence(graph),
    }
    slugs = [e["slug"] for e in HISTORICAL_EVENTS]
    obs = evals["GEDS"][1]
    lim = float(max(obs.max(), max(p.max() for p, _ in evals.values()))) * 1.1

    fig, axes = plt.subplots(2, 2, figsize=(6.4, 6.0), sharex=True, sharey=True)
    for ax, (name, (pred, o)) in zip(axes.ravel(), evals.items()):
        ax.plot([0, lim], [0, lim], color=MUTED, lw=1, ls="--", zorder=1)
        ax.scatter(o, pred, s=26, color=BLUE, alpha=0.85, zorder=2)
        m = sig["models"][name]
        sp = m["spearman"]
        sub = (f"MAE {m['mae']['point']:.4f} · ρ {sp['point']:.2f}"
               if sp else f"MAE {m['mae']['point']:.4f} · constant")
        ax.set_title(f"{name}\n{sub}", loc="left", fontsize=9)
        ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    for ax in axes[-1]:
        ax.set_xlabel("observed industry loss")
    for ax in axes[:, 0]:
        ax.set_ylabel("predicted")
    fig.suptitle("Predicted vs observed, N=27 events (identity = perfect)",
                 x=0.02, ha="left", fontsize=10, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT / "pred_vs_obs.png")
    plt.close(fig)
    rows = [[s, round(float(obs[i]), 4)]
            + [round(float(evals[k][0][i]), 4) for k in evals]
            for i, s in enumerate(slugs)]
    _write_csv(OUT / "pred_vs_obs.csv",
               ["slug", "observed"] + [f"pred_{k}" for k in evals], rows)


def fig_timing_ramp(ramp: dict) -> None:
    base_pe = ramp["baseline"]["cascade"]["per_event"]
    ramp_pe = ramp["ramp"]["cascade"]["per_event"]
    treated = set(ramp["treatment"])
    rows = []
    for slug, dims in base_pe.items():
        if "weeks_to_peak" not in dims:
            continue
        o = dims["weeks_to_peak"]["obs"]
        pb = dims["weeks_to_peak"]["pred"]
        pr = ramp_pe[slug]["weeks_to_peak"]["pred"]
        rows.append([slug, o, pb, pr, slug in treated])

    obs = [r[1] for r in rows]
    lim = max(max(obs), max(r[2] for r in rows), max(r[3] for r in rows)) * 1.1
    short = {"us-west-coast-ports-2021": "WC ports",
             "panama-canal-drought-2023": "Panama",
             "gfc-auto-collapse-2008-2009": "GFC",
             "eu-energy-crisis-2021": "EU energy"}
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.plot([0, lim], [0, lim], color=MUTED, lw=1, ls="--", zorder=1)
    for slug, o, pb, pr, is_treated in rows:
        if is_treated:
            ax.annotate("", xy=(o, pr), xytext=(o, pb),
                        arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.9))
            ax.annotate(short[slug], (o, pr), xytext=(7, 2),
                        textcoords="offset points", fontsize=7.5, color=MUTED)
    ax.scatter(obs, [r[2] for r in rows], s=34, facecolors="white",
               edgecolors=ORANGE, lw=1.6, zorder=3, label="before (Batch 18)")
    ax.scatter(obs, [r[3] for r in rows], s=34, color=BLUE, zorder=4,
               label="after ramp (Batch 19)")
    b = ramp["baseline"]["cascade"]["spearman_by_dim"]["weeks_to_peak"]
    a = ramp["ramp"]["cascade"]["spearman_by_dim"]["weeks_to_peak"]
    ax.set_xlabel("observed weeks to peak")
    ax.set_ylabel("predicted weeks to peak")
    ax.set_title(f"Onset timing: Spearman {b:.2f} → {a:.2f} after the ramp "
                 "forcing shape (n=15)", loc="left", fontsize=10,
                 fontweight="bold")
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "timing_ramp.png")
    plt.close(fig)
    _write_csv(OUT / "timing_ramp.csv",
               ["slug", "observed", "pred_before", "pred_after", "ramp_treated"],
               rows)


def fig_spatial_recall() -> None:
    from app.core.cascade_validation import compare_spatial_recall

    cmp = compare_spatial_recall()
    rows = []
    for e in cmp.per_event:
        v2r, v2n = (int(x) for x in e["v2"].split("/"))
        v3r, v3n = (int(x) for x in e["v3"].split("/"))
        rows.append([e["slug"], v2r, v2n, v3r, v3n])

    labels = [r[0] for r in rows]
    v2f = [r[1] / r[2] if r[2] else 0.0 for r in rows]
    v3f = [r[3] / r[4] if r[4] else 0.0 for r in rows]
    y = np.arange(len(rows))[::-1]

    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    ax.hlines(y, v2f, v3f, color=GRID, lw=2, zorder=1)
    ax.scatter(v2f, y, s=38, facecolors="white", edgecolors=ORANGE, lw=1.6,
               zorder=2, label=f"v2 hand-authored ({cmp.v2_recall:.2f} pooled)")
    ax.scatter(v3f, y, s=38, color=BLUE, zorder=3,
               label=f"v3 OECD ICIO ({cmp.v3_recall:.2f} pooled)")
    ax.set_yticks(y, labels, fontsize=7.5)
    ax.set_xlabel("share of historically-hit nodes the cascade reaches")
    ax.set_xlim(-0.03, 1.05)
    ax.set_title("Spatial recall: the ICIO-grounded graph\nreaches far more of the observed cascade",
                 loc="left", fontsize=10, fontweight="bold")
    ax.legend(frameon=False, loc="upper center", ncols=2, fontsize=8,
              bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    fig.savefig(OUT / "spatial_recall.png", bbox_inches="tight")
    plt.close(fig)
    _write_csv(OUT / "spatial_recall.csv",
               ["slug", "v2_reached", "v2_nodes", "v3_reached", "v3_nodes"],
               rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sig = json.loads((CALIB / "significance.json").read_text())
    ramp = json.loads((CALIB / "ramp_experiment.json").read_text())
    fig_parity_forest(sig)
    print("parity_forest done")
    fig_pred_vs_obs(sig)
    print("pred_vs_obs done")
    fig_timing_ramp(ramp)
    print("timing_ramp done")
    fig_spatial_recall()
    print("spatial_recall done")
    print(f"wrote 4 PNG+CSV pairs to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
