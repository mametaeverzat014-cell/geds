"""Phase 1 — Bootstrap confidence intervals for the 4-model benchmark on the
spectrally-normalised OECD+WIOD graph.

Uses the per-event predictions stored in `benchmark_spectral_normalized.json`
(produced by the spectral recalibration pipeline). Resamples events with
replacement N_BOOT times and recomputes MAE/RMSE/R²/Pearson on each resample,
producing 95% CIs and percentile bands.

This script does NOT re-run the engine — it bootstraps over the recorded
per-event predictions. That keeps the analysis cheap and reproducible.

Output: backend/data/calibration/bootstrap_results.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
CALIB_DIR = REPO / "backend" / "data" / "calibration"

N_BOOT = 5000           # > 1000 required
SEED = 20260529         # deterministic
ALPHAS = [2.5, 50.0, 97.5]


def _safe_pearson(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _r2(pred: np.ndarray, obs: np.ndarray) -> float:
    if obs.size < 2:
        return float("nan")
    ss_res = float(np.sum((obs - pred) ** 2))
    ss_tot = float(np.sum((obs - obs.mean()) ** 2))
    if ss_tot == 0:
        return float("nan")
    return 1.0 - ss_res / ss_tot


def _metrics(pred: np.ndarray, obs: np.ndarray) -> dict:
    return {
        "mae": float(np.mean(np.abs(pred - obs))),
        "rmse": float(np.sqrt(np.mean((pred - obs) ** 2))),
        "r_squared": _r2(pred, obs),
        "pearson": _safe_pearson(pred, obs),
    }


def _bootstrap(pred: np.ndarray, obs: np.ndarray, n_boot: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n = pred.size
    mae = np.empty(n_boot)
    rmse = np.empty(n_boot)
    r2 = np.empty(n_boot)
    pearson = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        p = pred[idx]
        o = obs[idx]
        mae[b] = float(np.mean(np.abs(p - o)))
        rmse[b] = float(np.sqrt(np.mean((p - o) ** 2)))
        r2[b] = _r2(p, o)
        pearson[b] = _safe_pearson(p, o)
    out = {
        "mae": {
            "point": float(np.mean(np.abs(pred - obs))),
            "boot_mean": float(np.nanmean(mae)),
            "boot_std": float(np.nanstd(mae)),
            "p2_5": float(np.nanpercentile(mae, 2.5)),
            "p50": float(np.nanpercentile(mae, 50.0)),
            "p97_5": float(np.nanpercentile(mae, 97.5)),
        },
        "rmse": {
            "point": float(np.sqrt(np.mean((pred - obs) ** 2))),
            "boot_mean": float(np.nanmean(rmse)),
            "boot_std": float(np.nanstd(rmse)),
            "p2_5": float(np.nanpercentile(rmse, 2.5)),
            "p50": float(np.nanpercentile(rmse, 50.0)),
            "p97_5": float(np.nanpercentile(rmse, 97.5)),
        },
        "r_squared": {
            "point": _r2(pred, obs),
            "boot_mean": float(np.nanmean(r2)),
            "boot_std": float(np.nanstd(r2)),
            "p2_5": float(np.nanpercentile(r2, 2.5)),
            "p50": float(np.nanpercentile(r2, 50.0)),
            "p97_5": float(np.nanpercentile(r2, 97.5)),
        },
        "pearson": {
            "point": _safe_pearson(pred, obs),
            "boot_mean": float(np.nanmean(pearson)),
            "boot_std": float(np.nanstd(pearson)),
            "p2_5": float(np.nanpercentile(pearson, 2.5)),
            "p50": float(np.nanpercentile(pearson, 50.0)),
            "p97_5": float(np.nanpercentile(pearson, 97.5)),
        },
    }
    return out


def _delta_bootstrap(pred_a: np.ndarray, pred_b: np.ndarray, obs: np.ndarray,
                     n_boot: int, seed: int) -> dict:
    """Paired-bootstrap of (MAE_b - MAE_a) so the same resample indices are used."""
    rng = np.random.default_rng(seed)
    n = obs.size
    delta_mae = np.empty(n_boot)
    delta_pearson = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        oa = pred_a[idx]
        ob = pred_b[idx]
        oo = obs[idx]
        delta_mae[b] = float(np.mean(np.abs(ob - oo)) - np.mean(np.abs(oa - oo)))
        delta_pearson[b] = _safe_pearson(ob, oo) - _safe_pearson(oa, oo)
    return {
        "delta_mae_b_minus_a": {
            "point": float(np.mean(np.abs(pred_b - obs)) - np.mean(np.abs(pred_a - obs))),
            "boot_mean": float(np.nanmean(delta_mae)),
            "boot_std": float(np.nanstd(delta_mae)),
            "p2_5": float(np.nanpercentile(delta_mae, 2.5)),
            "p50": float(np.nanpercentile(delta_mae, 50.0)),
            "p97_5": float(np.nanpercentile(delta_mae, 97.5)),
            "frac_b_better": float((delta_mae < 0).mean()),
        },
        "delta_pearson_b_minus_a": {
            "point": _safe_pearson(pred_b, obs) - _safe_pearson(pred_a, obs),
            "boot_mean": float(np.nanmean(delta_pearson)),
            "boot_std": float(np.nanstd(delta_pearson)),
            "p2_5": float(np.nanpercentile(delta_pearson, 2.5)),
            "p50": float(np.nanpercentile(delta_pearson, 50.0)),
            "p97_5": float(np.nanpercentile(delta_pearson, 97.5)),
        },
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    bench_path = CALIB_DIR / "benchmark_spectral_normalized.json"
    if not bench_path.exists():
        print(f"ERROR: missing {bench_path}", file=sys.stderr)
        return 1
    bench = json.loads(bench_path.read_text(encoding="utf-8"))
    per_event = bench["models"]["per_event"]
    n = len(per_event)
    obs = np.array([e["target"] for e in per_event], dtype=float)
    geds = np.array([e["seirs"] for e in per_event], dtype=float)
    leon = np.array([e["leontief"] for e in per_event], dtype=float)
    lind = np.array([e["linear"] for e in per_event], dtype=float)
    naive = np.full(n, obs.mean(), dtype=float)
    zero = np.zeros(n, dtype=float)
    print(f"Loaded benchmark with N={n} events.")

    print(f"\nBootstrapping {N_BOOT} resamples (seed={SEED})...")
    models = {
        "GEDS-SEIRS": geds,
        "Leontief": leon,
        "Linear-Diffusion": lind,
        "Naive-Mean": naive,
        "Zero-Predictor": zero,
    }
    per_model = {}
    for name, pred in models.items():
        per_model[name] = _bootstrap(pred, obs, N_BOOT, SEED)
        m = per_model[name]
        print(f"  {name:20s} MAE={m['mae']['point']:.5f} "
              f"[{m['mae']['p2_5']:.5f}, {m['mae']['p97_5']:.5f}]   "
              f"Pearson={m['pearson']['point']:+.4f} "
              f"[{m['pearson']['p2_5']:+.4f}, {m['pearson']['p97_5']:+.4f}]")

    print(f"\nPaired-bootstrap pairwise deltas (b - a). frac_b_better is the fraction"
          f" of resamples where b has lower MAE than a.")
    pairs = [
        ("GEDS-SEIRS", "Leontief"),
        ("GEDS-SEIRS", "Linear-Diffusion"),
        ("GEDS-SEIRS", "Naive-Mean"),
        ("GEDS-SEIRS", "Zero-Predictor"),
        ("Leontief", "Linear-Diffusion"),
        ("Leontief", "Naive-Mean"),
        ("Linear-Diffusion", "Naive-Mean"),
    ]
    pairwise = {}
    for a, b in pairs:
        d = _delta_bootstrap(models[a], models[b], obs, N_BOOT, SEED)
        pairwise[f"{a}__vs__{b}"] = d
        dm = d["delta_mae_b_minus_a"]
        print(f"  {a:15s} vs {b:15s}: ΔMAE(b-a)={dm['point']:+.5f}, "
              f"95%=[{dm['p2_5']:+.5f}, {dm['p97_5']:+.5f}], "
              f"frac_b_better={dm['frac_b_better']:.3f}")

    per_event_table = []
    for i, e in enumerate(per_event):
        per_event_table.append({
            "event_id": e["event_id"],
            "name": e["name"],
            "observed": e["target"],
            "geds_pred": e["seirs"],
            "geds_err_abs": abs(e["target"] - e["seirs"]),
            "leontief_pred": e["leontief"],
            "leontief_err_abs": abs(e["target"] - e["leontief"]),
            "linear_pred": e["linear"],
            "linear_err_abs": abs(e["target"] - e["linear"]),
            "naive_pred": float(naive[i]),
            "naive_err_abs": abs(e["target"] - float(naive[i])),
        })

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": "non-parametric event-level bootstrap",
        "n_resamples": N_BOOT,
        "seed": SEED,
        "ci_levels": ALPHAS,
        "n_events": n,
        "source_benchmark": "benchmark_spectral_normalized.json",
        "graph": bench.get("graph"),
        "per_model_ci": per_model,
        "pairwise_paired_bootstrap": pairwise,
        "per_event_predictions": per_event_table,
        "interpretation": {
            "frac_b_better_meaning": "fraction of resamples in which model 'b' has strictly lower MAE than model 'a'",
            "ci_overlap_check": "if 0 falls inside the 95% CI of delta_mae_b_minus_a then the difference is not significant at α=0.05",
        },
        "preserved_files": [
            "benchmark_spectral_normalized.json", "benchmark_oecd.json",
            "benchmark_wiod.json", "benchmark_v3.json", "ablation_post_normalization.json",
        ],
    }
    out_path = CALIB_DIR / "bootstrap_results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
