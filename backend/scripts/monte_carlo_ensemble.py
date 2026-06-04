"""Phase 2 — Monte Carlo ensemble forecasting on the spectrally-normalised
OECD+WIOD graph.

Approach:
  - Calibrated mean = `cmaes_best_params.json::best_params`
  - Per-parameter σ = LOEO fold std (from `loeo_results.json::fold_variance`).
    LOEO fold variance is the most defensible empirical estimate of
    calibration uncertainty: each fold refit on a leave-one-event-out
    training set, so the cross-fold spread is the parameter spread
    consistent with the same likelihood at the data.
  - Sample N_ENSEMBLE parameter vectors from independent truncated Gaussians
    (clamped to prior ranges to avoid invalid params).
  - For each sampled vector, run GEDS on all 21 engine-eligible events.
  - Compute mean, std, and percentile bands per event.

Outputs:
  backend/data/calibration/ensemble_predictions.json
  backend/data/calibration/ensemble_statistics.json
"""

from __future__ import annotations

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

N_ENSEMBLE = 500
SEED = 20260529
PERCENTILES = [2.5, 5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0, 97.5]

# Prior ranges (must match calibration script; used for clamping samples)
PRIORS = {
    "amplification_mu": (0.0, 4.0),
    "amplification_eps": (0.01, 0.2),
    "propagation_decay": (0.5, 0.99),
    "recovery_rate": (0.01, 0.3),
    "bullwhip_factor": (1.0, 2.0),
    "inventory_scale": (0.3, 2.0),
    "r_output_floor": (0.05, 0.4),
}


def _load_inputs():
    cma = json.loads((CALIB_DIR / "cmaes_best_params.json").read_text(encoding="utf-8"))
    loeo = json.loads((CALIB_DIR / "loeo_results.json").read_text(encoding="utf-8"))
    return cma["best_params"], loeo["fold_variance"]


def _sample_param_vectors(mu_dict: dict, sigma_dict: dict, n: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    keys = list(mu_dict.keys())
    samples = []
    for i in range(n):
        sample = {}
        for k in keys:
            mu = float(mu_dict[k])
            sigma = float(sigma_dict[k]["std"])
            lo, hi = PRIORS[k]
            # Truncated Gaussian: reject-and-resample, capped at 50 tries → clamp.
            for _ in range(50):
                v = rng.normal(mu, sigma)
                if lo <= v <= hi:
                    sample[k] = v
                    break
            else:
                sample[k] = float(np.clip(rng.normal(mu, sigma), lo, hi))
        samples.append(sample)
    return samples


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print(f"Phase 2 — Monte Carlo ensemble (N={N_ENSEMBLE}, seed={SEED})\n")

    best_params, fold_var = _load_inputs()
    print("Calibrated mean params (from cmaes_best_params.json):")
    for k, v in best_params.items():
        s = fold_var[k]["std"]
        lo, hi = PRIORS[k]
        print(f"  {k:24s}: μ={v:.5f}  σ_LOEO={s:.5f}  prior=[{lo}, {hi}]")

    # Build normalised graph
    print("\nBuilding normalised OECD+WIOD graph...")
    from run_spectral_recalibration import build_three_graphs, spectral_normalise
    graphs = build_three_graphs()
    aug_info = graphs["OECD+WIOD"]
    rho_before, scale = spectral_normalise(aug_info["graph"], target_rho=1.0)
    print(f"  applied spectral normalisation: ρ {rho_before:.4f} → 1.0 (scale={scale:.4f})")

    from app.data import seed as seed_mod
    from app.core import backtest as bt_mod
    aug_snap = aug_info["snap"]
    def _patched():
        return aug_snap
    seed_mod.load_graph = _patched
    bt_mod.load_graph = _patched

    from run_oecd_benchmark import remap_events_for_oecd_graph
    remapped = remap_events_for_oecd_graph(aug_info["graph"])
    events = [r["_translated"] for r in remapped if r["mapping_status"] == "OK"]
    events.sort(key=lambda e: e["event_id"])
    print(f"\nEligible events: {len(events)}")

    # Sample parameter vectors
    print(f"\nSampling {N_ENSEMBLE} parameter vectors (LOEO σ; clamped to priors)...")
    samples = _sample_param_vectors(best_params, fold_var, N_ENSEMBLE, SEED)

    # Run engine for each sample × each event
    from app.core.types import EngineConfig
    from app.core.backtest import backtest_event

    base_cfg = EngineConfig()
    n_events = len(events)
    predictions = np.zeros((N_ENSEMBLE, n_events), dtype=float)
    # First-call probe: pull observed via backtest_event so we get the same value
    # the engine sees (NOT a separate seed-event field).
    graph = aug_info["graph"]
    observed = np.zeros(n_events, dtype=float)
    try:
        bt0 = backtest_event(events[0], graph, base_cfg.model_copy(update=best_params))
        for j, ev in enumerate(events):
            bj = backtest_event(ev, graph, base_cfg.model_copy(update=best_params))
            observed[j] = float(bj.industry_loss_observed)
    except Exception as ex:
        print(f"ERROR probing observed values: {ex!r}", file=sys.stderr)
        return 2

    print(f"\nRunning {N_ENSEMBLE} × {n_events} = {N_ENSEMBLE*n_events} backtest_event calls...")
    t0 = time.time()
    last_report = t0
    n_fail = 0
    for i, sample in enumerate(samples):
        cfg = base_cfg.model_copy(update=sample)
        for j, ev in enumerate(events):
            try:
                bt = backtest_event(ev, graph, cfg)
                predictions[i, j] = float(bt.industry_loss_predicted)
            except Exception:
                # NEVER fabricate. Record NaN; downstream stats skip via nan-aware reducers.
                predictions[i, j] = float("nan")
                n_fail += 1
        if time.time() - last_report > 30.0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (N_ENSEMBLE - i - 1) / rate if rate > 0 else float("inf")
            print(f"  [{i+1:3d}/{N_ENSEMBLE}] elapsed={elapsed:.0f}s rate={rate:.2f}/s eta={eta:.0f}s",
                  flush=True)
            last_report = time.time()
    total_elapsed = time.time() - t0
    print(f"\nTotal elapsed: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)  "
          f"failed_calls={n_fail}/{N_ENSEMBLE*n_events}")

    # Validity check
    n_finite_per_event = np.sum(np.isfinite(predictions), axis=0)
    print(f"\nFinite-sample counts per event: min={n_finite_per_event.min()}, "
          f"max={n_finite_per_event.max()}, median={int(np.median(n_finite_per_event))}")

    # Statistics per event
    event_stats = []
    for j, ev in enumerate(events):
        col = predictions[:, j]
        finite = col[np.isfinite(col)]
        if finite.size == 0:
            stats = {"n_finite": 0, "mean": None, "std": None, "min": None, "max": None}
        else:
            stats = {
                "n_finite": int(finite.size),
                "mean": float(finite.mean()),
                "std": float(finite.std()),
                "min": float(finite.min()),
                "max": float(finite.max()),
                "p2_5": float(np.percentile(finite, 2.5)),
                "p5": float(np.percentile(finite, 5.0)),
                "p10": float(np.percentile(finite, 10.0)),
                "p25": float(np.percentile(finite, 25.0)),
                "p50": float(np.percentile(finite, 50.0)),
                "p75": float(np.percentile(finite, 75.0)),
                "p90": float(np.percentile(finite, 90.0)),
                "p95": float(np.percentile(finite, 95.0)),
                "p97_5": float(np.percentile(finite, 97.5)),
            }
        event_stats.append({
            "event_id": ev["event_id"],
            "name": ev.get("name", ""),
            "observed": float(ev.get("observed_drop_in_output", 0.0)),
            "stats": stats,
            "observed_in_p2_5_p97_5_band": (
                (stats.get("p2_5") is not None and stats.get("p97_5") is not None
                 and float(stats["p2_5"]) <= ev.get("observed_drop_in_output", 0.0) <= float(stats["p97_5"]))
            ),
        })

    # Aggregate ensemble metrics: compute MAE/Pearson distribution across samples
    sample_metrics = {"mae": [], "rmse": [], "r_squared": [], "pearson": []}
    for i in range(N_ENSEMBLE):
        col = predictions[i, :]
        mask = np.isfinite(col)
        if mask.sum() < 2:
            continue
        p = col[mask]
        o = observed[mask]
        sample_metrics["mae"].append(float(np.mean(np.abs(p - o))))
        sample_metrics["rmse"].append(float(np.sqrt(np.mean((p - o) ** 2))))
        if np.std(o) > 0 and np.std(p) > 0:
            sample_metrics["pearson"].append(float(np.corrcoef(p, o)[0, 1]))
        ss_res = float(np.sum((o - p) ** 2))
        ss_tot = float(np.sum((o - o.mean()) ** 2))
        sample_metrics["r_squared"].append(1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"))

    def _stat_summary(arr_list):
        arr = np.array(arr_list, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return {"n": 0}
        return {
            "n": int(arr.size),
            "mean": float(arr.mean()),
            "std": float(arr.std()),
            "p2_5": float(np.percentile(arr, 2.5)),
            "p50": float(np.percentile(arr, 50.0)),
            "p97_5": float(np.percentile(arr, 97.5)),
        }
    ensemble_metric_distribution = {k: _stat_summary(v) for k, v in sample_metrics.items()}

    # Coverage diagnostic
    in_band = sum(1 for e in event_stats if e["observed_in_p2_5_p97_5_band"])
    coverage = in_band / max(1, len(event_stats))
    print(f"\nCoverage of observed by 95% ensemble band: {in_band}/{len(event_stats)} = {coverage:.2%}")

    # ===== Output 1: ensemble_predictions.json =====
    pred_out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "graph": "OECD+WIOD spectrally normalised (ρ=1.0)",
        "rho_before_normalisation": rho_before,
        "spectral_scale_applied": scale,
        "n_ensemble": N_ENSEMBLE,
        "seed": SEED,
        "parameter_uncertainty_source": "LOEO fold std (loeo_results.json::fold_variance)",
        "calibrated_mean_params": best_params,
        "loeo_sigma": {k: float(fold_var[k]["std"]) for k in best_params},
        "prior_ranges": PRIORS,
        "n_events": n_events,
        "elapsed_seconds": total_elapsed,
        "sampled_param_vectors": samples,
        "predictions_per_sample_per_event": predictions.tolist(),
        "observed_per_event": observed.tolist(),
        "event_ids": [int(e["event_id"]) for e in events],
        "event_names": [str(e.get("name", "")) for e in events],
    }
    out_pred = CALIB_DIR / "ensemble_predictions.json"
    out_pred.write_text(json.dumps(pred_out, indent=2), encoding="utf-8")
    print(f"\nwrote {out_pred}")

    # ===== Output 2: ensemble_statistics.json =====
    stats_out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "graph": "OECD+WIOD spectrally normalised (ρ=1.0)",
        "n_ensemble": N_ENSEMBLE,
        "n_events": n_events,
        "seed": SEED,
        "parameter_uncertainty_source": "LOEO fold std (loeo_results.json::fold_variance)",
        "percentiles_reported": PERCENTILES,
        "calibrated_mean_params": best_params,
        "loeo_sigma": {k: float(fold_var[k]["std"]) for k in best_params},
        "per_event_statistics": event_stats,
        "ensemble_metric_distribution": ensemble_metric_distribution,
        "coverage_observed_in_p2_5_p97_5": {
            "n_in_band": in_band,
            "n_events": len(event_stats),
            "fraction": coverage,
        },
        "preserved_files": [
            "benchmark_spectral_normalized.json", "bootstrap_results.json",
            "ablation_post_normalization.json",
        ],
    }
    out_stats = CALIB_DIR / "ensemble_statistics.json"
    out_stats.write_text(json.dumps(stats_out, indent=2), encoding="utf-8")
    print(f"wrote {out_stats}")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
