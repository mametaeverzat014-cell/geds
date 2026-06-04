"""Phase 3 — Event-level uncertainty decomposition.

For each engine-eligible event, decompose the prediction uncertainty into:
  1. Parameter uncertainty   = std of MC ensemble (from ensemble_predictions.json).
  2. Topology sensitivity    = range of prediction across {heuristic, OECD-only,
                              OECD+WIOD} graphs (all spectrally normalised),
                              with the SAME calibrated params.
  3. Calibration variance    = spread of predictions for that event across the
                              5 LOEO folds' refitted parameter sets (loeo_results.json).
  4. Graph-density sensitivity = how the prediction scales with graph density
                              (n_nodes × density across the 3 graphs).

NEVER fabricates predictions — events that don't map to a particular graph are
marked NULL.

Output: backend/data/calibration/event_uncertainty_breakdown.csv
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "backend" / "scripts"))
sys.path.insert(0, str(REPO / "backend" / "scripts" / "calibration"))

CALIB_DIR = REPO / "backend" / "data" / "calibration"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print("Phase 3 — Event-level uncertainty decomposition\n")

    # ---- Load inputs ----
    cma = json.loads((CALIB_DIR / "cmaes_best_params.json").read_text(encoding="utf-8"))
    best_params = cma["best_params"]
    loeo = json.loads((CALIB_DIR / "loeo_results.json").read_text(encoding="utf-8"))
    loeo_fold_params = [f["best_params"] for f in loeo["successful_folds"]]
    print(f"Loaded calibrated params + {len(loeo_fold_params)} LOEO fold param sets.")

    # ---- Optional MC stats (Phase 2). If absent we skip parameter-uncertainty column. ----
    ensemble_path = CALIB_DIR / "ensemble_statistics.json"
    if ensemble_path.exists():
        ensemble = json.loads(ensemble_path.read_text(encoding="utf-8"))
        ens_by_event = {int(e["event_id"]): e for e in ensemble["per_event_statistics"]}
        print(f"Loaded ensemble_statistics for {len(ens_by_event)} events.")
    else:
        ens_by_event = {}
        print("ensemble_statistics.json NOT YET PRESENT — parameter-uncertainty columns "
              "will be NULL. Re-run after Phase 2.")

    # ---- Build all three graphs and apply spectral normalisation to each ----
    print("\nBuilding 3 graphs (all normalised to ρ=1.0)...")
    from run_spectral_recalibration import build_three_graphs, spectral_normalise

    graphs = build_three_graphs()
    graph_infos = {}
    for key in ("heuristic", "OECD-only", "OECD+WIOD"):
        info = graphs[key]
        rho_before, scale = spectral_normalise(info["graph"], target_rho=1.0)
        graph_infos[key] = {
            "snap": info["snap"],
            "graph": info["graph"],
            "rho_before": rho_before,
            "scale": scale,
            "n_nodes": info["graph"].n_nodes if hasattr(info["graph"], "n_nodes")
                       else int(info["snap"].n_nodes if hasattr(info["snap"], "n_nodes") else 0),
        }
        print(f"  {key:12s} normalised: ρ {rho_before:.4f} → 1.0  scale={scale:.4f}")

    # ---- Helpers to swap graphs at runtime ----
    from app.data import seed as seed_mod
    from app.core import backtest as bt_mod
    from run_oecd_benchmark import remap_events_for_oecd_graph

    def use_graph(graph_key: str):
        snap = graph_infos[graph_key]["snap"]
        def _patched():
            return snap
        seed_mod.load_graph = _patched
        bt_mod.load_graph = _patched

    # Get events with graph-specific mapping per graph
    print("\nRemapping events for each graph...")
    events_by_graph: dict[str, list] = {}
    for key in ("OECD-only", "OECD+WIOD"):
        info = graph_infos[key]
        remapped = remap_events_for_oecd_graph(info["graph"])
        events = [r["_translated"] for r in remapped if r["mapping_status"] == "OK"]
        events.sort(key=lambda e: e["event_id"])
        events_by_graph[key] = events
        print(f"  {key}: {len(events)} eligible events")
    # Heuristic graph: events use their original (raw) seed nodes; we re-translate
    # against the heuristic graph for fair comparison.
    h_info = graph_infos["heuristic"]
    remapped_h = remap_events_for_oecd_graph(h_info["graph"])  # works generically on any CompiledGraph
    events_h = [r["_translated"] for r in remapped_h if r["mapping_status"] == "OK"]
    events_h.sort(key=lambda e: e["event_id"])
    events_by_graph["heuristic"] = events_h
    print(f"  heuristic: {len(events_h)} eligible events")

    # ---- Run calibrated config on each graph ----
    from app.core.types import EngineConfig
    from app.core.backtest import backtest_event

    base_cfg = EngineConfig().model_copy(update=best_params)
    print("\nRunning calibrated config on each graph...")
    pred_by_graph: dict[str, dict[int, float]] = {}
    obs_by_event: dict[int, float] = {}
    for gk in ("heuristic", "OECD-only", "OECD+WIOD"):
        use_graph(gk)
        evs = events_by_graph[gk]
        g = graph_infos[gk]["graph"]
        d: dict[int, float] = {}
        t0 = time.time()
        for ev in evs:
            try:
                bt = backtest_event(ev, g, base_cfg)
                d[int(ev["event_id"])] = float(bt.industry_loss_predicted)
                obs_by_event[int(ev["event_id"])] = float(bt.industry_loss_observed)
            except Exception:
                d[int(ev["event_id"])] = float("nan")
        print(f"  {gk:12s}: {len(d)} preds in {time.time()-t0:.1f}s")
        pred_by_graph[gk] = d

    # ---- Run LOEO fold params on OECD+WIOD graph (calibration variance) ----
    use_graph("OECD+WIOD")
    evs_main = events_by_graph["OECD+WIOD"]
    g_main = graph_infos["OECD+WIOD"]["graph"]
    print(f"\nRunning {len(loeo_fold_params)} LOEO fold param sets on OECD+WIOD...")
    loeo_pred_per_event: dict[int, list[float]] = {int(e["event_id"]): [] for e in evs_main}
    for fi, fold_params in enumerate(loeo_fold_params):
        cfg = EngineConfig().model_copy(update=fold_params)
        for ev in evs_main:
            try:
                bt = backtest_event(ev, g_main, cfg)
                loeo_pred_per_event[int(ev["event_id"])].append(
                    float(bt.industry_loss_predicted))
            except Exception:
                loeo_pred_per_event[int(ev["event_id"])].append(float("nan"))
        print(f"  fold {fi+1}/{len(loeo_fold_params)} done", flush=True)

    # ---- Assemble per-event row ----
    print("\nAssembling per-event uncertainty breakdown...")
    obs_lookup = obs_by_event
    rows = []
    for ev in evs_main:
        eid = int(ev["event_id"])
        name = ev.get("name", "")
        observed = obs_lookup[eid]
        p_heur = pred_by_graph["heuristic"].get(eid, float("nan"))
        p_oecd = pred_by_graph["OECD-only"].get(eid, float("nan"))
        p_aug = pred_by_graph["OECD+WIOD"].get(eid, float("nan"))

        # Topology sensitivity: max - min across the 3 graphs (NaN if any missing)
        graph_preds = [v for v in (p_heur, p_oecd, p_aug) if np.isfinite(v)]
        topo_range = float(max(graph_preds) - min(graph_preds)) if len(graph_preds) >= 2 else float("nan")
        topo_std = float(np.std(graph_preds, ddof=0)) if len(graph_preds) >= 2 else float("nan")

        # Calibration variance: std of LOEO fold predictions on OECD+WIOD
        fold_preds = np.array(loeo_pred_per_event[eid], dtype=float)
        fold_preds_finite = fold_preds[np.isfinite(fold_preds)]
        calib_std = float(fold_preds_finite.std(ddof=0)) if fold_preds_finite.size >= 2 else float("nan")
        calib_mean = float(fold_preds_finite.mean()) if fold_preds_finite.size >= 1 else float("nan")
        calib_min = float(fold_preds_finite.min()) if fold_preds_finite.size >= 1 else float("nan")
        calib_max = float(fold_preds_finite.max()) if fold_preds_finite.size >= 1 else float("nan")

        # Parameter uncertainty: from ensemble stats (Phase 2 output) if present
        ens = ens_by_event.get(eid, {}).get("stats", {})
        param_std = ens.get("std", None) if ens else None
        param_p2_5 = ens.get("p2_5", None) if ens else None
        param_p97_5 = ens.get("p97_5", None) if ens else None
        param_mean = ens.get("mean", None) if ens else None

        # Graph-density sensitivity:  relative change between the 2 densest graphs
        # vs the sparsest. If sparsest pred ≈ 0, fall back to absolute range.
        if np.isfinite(p_aug) and np.isfinite(p_heur):
            denom = max(abs(p_heur), 1e-9)
            density_sens = float((p_aug - p_heur) / denom) if denom > 0 else float("nan")
        else:
            density_sens = float("nan")

        rows.append({
            "event_id": eid,
            "name": name,
            "observed": observed,
            "pred_heuristic": p_heur,
            "pred_oecd_only": p_oecd,
            "pred_oecd_wiod": p_aug,
            "topology_range_max_minus_min": topo_range,
            "topology_std_across_graphs": topo_std,
            "calibration_loeo_mean": calib_mean,
            "calibration_loeo_std": calib_std,
            "calibration_loeo_min": calib_min,
            "calibration_loeo_max": calib_max,
            "parameter_ensemble_mean": param_mean,
            "parameter_ensemble_std": param_std,
            "parameter_ensemble_p2_5": param_p2_5,
            "parameter_ensemble_p97_5": param_p97_5,
            "graph_density_relative_change_h_to_aug": density_sens,
            "err_abs_calibrated": abs(observed - p_aug) if np.isfinite(p_aug) else float("nan"),
        })

    # ---- Write CSV ----
    fields = list(rows[0].keys())
    out_csv = CALIB_DIR / "event_uncertainty_breakdown.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            row = {}
            for k in fields:
                v = r[k]
                if isinstance(v, float) and not np.isfinite(v):
                    row[k] = ""
                elif v is None:
                    row[k] = ""
                elif isinstance(v, float):
                    row[k] = f"{v:.6f}"
                else:
                    row[k] = v
            w.writerow(row)
    print(f"\nwrote {out_csv}")

    # Also write a small JSON sidecar so the provenance is preserved
    sidecar = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "graphs_used": {k: {"n_nodes": v["n_nodes"], "rho_before": v["rho_before"],
                           "scale": v["scale"]} for k, v in graph_infos.items()},
        "calibrated_params": best_params,
        "loeo_n_fold_params": len(loeo_fold_params),
        "ensemble_available": bool(ens_by_event),
        "n_events_main": len(rows),
        "preserved_files": [
            "benchmark_spectral_normalized.json", "bootstrap_results.json",
            "ensemble_predictions.json", "ensemble_statistics.json",
            "ablation_post_normalization.json",
        ],
    }
    (CALIB_DIR / "event_uncertainty_breakdown_sidecar.json").write_text(
        json.dumps(sidecar, indent=2), encoding="utf-8")
    print(f"wrote sidecar {CALIB_DIR / 'event_uncertainty_breakdown_sidecar.json'}")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
