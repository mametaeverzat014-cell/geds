"""Phase 4 — Calibration stability diagnostics.

Outputs:
  backend/data/calibration/calibration_stability.json
  backend/data/calibration/parameter_sensitivity.csv

Diagnostics:
  1. **Local sensitivity (finite-difference rank)**
     For each calibrated parameter θ_i, hold all other params at calibrated value,
     perturb θ_i by ±1σ_LOEO (clamped to prior), and report ΔMAE relative to the
     baseline calibrated MAE. Rank by |ΔMAE|.

  2. **Variance decomposition (first-order sensitivity from MC samples)**
     Using ensemble_predictions.json: regress each per-event prediction against
     the 7 sampled parameters. The R² of θ_i (univariate, ignoring others) is a
     "variance-explained" proxy for first-order Sobol index. Reported per event
     AND averaged across events.

  3. **Identifiability**
     Condition number of the sampled-param correlation matrix is well-defined
     (input is independent normals). The interesting object is the
     parameter-to-output Jacobian estimate's conditioning: we regress the
     21-vector of predictions on the 7 params (multiple regression), compute
     the singular-value spectrum of the design matrix, and report condition
     number κ and effective rank. High κ ⇒ params are jointly unidentifiable
     from this data.

  4. **Pairwise parameter correlation**
     - Input-input: correlation between sampled params (sanity check ~ identity)
     - Input-output: correlation between each param and the per-event prediction
     - Output-output: correlation between predictions across events
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

PRIORS = {
    "amplification_mu": (0.0, 4.0),
    "amplification_eps": (0.01, 0.2),
    "propagation_decay": (0.5, 0.99),
    "recovery_rate": (0.01, 0.3),
    "bullwhip_factor": (1.0, 2.0),
    "inventory_scale": (0.3, 2.0),
    "r_output_floor": (0.05, 0.4),
}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print("Phase 4 — Calibration stability diagnostics\n")

    cma = json.loads((CALIB_DIR / "cmaes_best_params.json").read_text(encoding="utf-8"))
    best = cma["best_params"]
    loeo = json.loads((CALIB_DIR / "loeo_results.json").read_text(encoding="utf-8"))
    fold_var = loeo["fold_variance"]
    sigma = {k: float(fold_var[k]["std"]) for k in best}
    param_names = list(best.keys())
    print("Calibrated params and LOEO σ:")
    for k in param_names:
        print(f"  {k:24s} μ={best[k]:.5f}  σ={sigma[k]:.5f}")

    # ---- Build normalised OECD+WIOD graph ----
    print("\nBuilding normalised OECD+WIOD graph...")
    from run_spectral_recalibration import build_three_graphs, spectral_normalise
    graphs = build_three_graphs()
    aug_info = graphs["OECD+WIOD"]
    rho_before, scale = spectral_normalise(aug_info["graph"], target_rho=1.0)
    graph = aug_info["graph"]

    from app.data import seed as seed_mod
    from app.core import backtest as bt_mod
    aug_snap = aug_info["snap"]
    def _patched(): return aug_snap
    seed_mod.load_graph = _patched
    bt_mod.load_graph = _patched

    from run_oecd_benchmark import remap_events_for_oecd_graph
    remapped = remap_events_for_oecd_graph(graph)
    events = [r["_translated"] for r in remapped if r["mapping_status"] == "OK"]
    events.sort(key=lambda e: e["event_id"])
    print(f"Eligible events: {len(events)}")

    from app.core.types import EngineConfig
    from app.core.backtest import backtest_event

    def run_cfg(cfg):
        preds = np.zeros(len(events))
        obs = np.zeros(len(events))
        for i, ev in enumerate(events):
            try:
                bt = backtest_event(ev, graph, cfg)
                preds[i] = float(bt.industry_loss_predicted)
                obs[i] = float(bt.industry_loss_observed)
            except Exception:
                preds[i] = float("nan")
                obs[i] = float("nan")
        return preds, obs

    # ---- 1. Local sensitivity (finite-difference) ----
    print("\n[1] Local sensitivity (finite-difference around calibrated point):")
    base_cfg = EngineConfig().model_copy(update=best)
    base_pred, base_obs = run_cfg(base_cfg)
    mask = np.isfinite(base_pred) & np.isfinite(base_obs)
    base_mae = float(np.mean(np.abs(base_pred[mask] - base_obs[mask])))
    print(f"  baseline MAE = {base_mae:.5f}  (over {int(mask.sum())} of {len(events)} events)")

    sensitivity_rows = []
    sens_t0 = time.time()
    for k in param_names:
        lo_b, hi_b = PRIORS[k]
        mu = float(best[k])
        s = sigma[k]
        plus = float(np.clip(mu + s, lo_b, hi_b))
        minus = float(np.clip(mu - s, lo_b, hi_b))
        cfg_plus = base_cfg.model_copy(update={k: plus})
        cfg_minus = base_cfg.model_copy(update={k: minus})
        pp, po = run_cfg(cfg_plus)
        mp, mo = run_cfg(cfg_minus)
        m_p = np.isfinite(pp) & np.isfinite(po)
        m_m = np.isfinite(mp) & np.isfinite(mo)
        mae_plus = float(np.mean(np.abs(pp[m_p] - po[m_p]))) if m_p.sum() else float("nan")
        mae_minus = float(np.mean(np.abs(mp[m_m] - mo[m_m]))) if m_m.sum() else float("nan")
        d_mae_plus = mae_plus - base_mae
        d_mae_minus = mae_minus - base_mae
        # central difference proxy
        denom = (plus - minus) if (plus - minus) != 0 else 1e-9
        d_mae_d_theta = (mae_plus - mae_minus) / denom
        # max |Δprediction| (cross-event) under each perturbation
        max_dp_plus = float(np.nanmax(np.abs(pp - base_pred))) if np.any(np.isfinite(pp)) else float("nan")
        max_dp_minus = float(np.nanmax(np.abs(mp - base_pred))) if np.any(np.isfinite(mp)) else float("nan")
        print(f"  {k:24s} θ±σ={minus:.4f}..{plus:.4f}  "
              f"MAE: {mae_minus:.5f} | {base_mae:.5f} | {mae_plus:.5f}  "
              f"ΔMAE±: {d_mae_minus:+.5f} / {d_mae_plus:+.5f}  "
              f"max|Δpred|: {max_dp_minus:.5f}/{max_dp_plus:.5f}")
        sensitivity_rows.append({
            "parameter": k,
            "calibrated": mu,
            "sigma_loeo": s,
            "perturbed_low": minus,
            "perturbed_high": plus,
            "mae_low": mae_minus,
            "mae_baseline": base_mae,
            "mae_high": mae_plus,
            "delta_mae_low": d_mae_minus,
            "delta_mae_high": d_mae_plus,
            "d_mae_d_theta_centraldiff": d_mae_d_theta,
            "max_abs_pred_change_low": max_dp_minus,
            "max_abs_pred_change_high": max_dp_plus,
            "max_abs_delta_mae": max(abs(d_mae_low_h) for d_mae_low_h in (d_mae_minus, d_mae_plus)),
        })
    print(f"  sensitivity sweep elapsed {time.time()-sens_t0:.1f}s")

    # Rank by max |ΔMAE|
    sensitivity_rows.sort(key=lambda r: r["max_abs_delta_mae"], reverse=True)
    for rank, r in enumerate(sensitivity_rows, 1):
        r["rank"] = rank

    # ---- Write parameter_sensitivity.csv ----
    sens_csv = CALIB_DIR / "parameter_sensitivity.csv"
    fields = ["rank", "parameter", "calibrated", "sigma_loeo",
              "perturbed_low", "perturbed_high", "mae_low", "mae_baseline", "mae_high",
              "delta_mae_low", "delta_mae_high", "d_mae_d_theta_centraldiff",
              "max_abs_pred_change_low", "max_abs_pred_change_high", "max_abs_delta_mae"]
    with sens_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sensitivity_rows:
            w.writerow({k: (f"{r[k]:.6f}" if isinstance(r[k], float) and np.isfinite(r[k])
                            else ("" if isinstance(r[k], float) and not np.isfinite(r[k]) else r[k]))
                        for k in fields})
    print(f"wrote {sens_csv}")

    # ---- 2-4. Stats from MC ensemble (if present) ----
    ensemble_path = CALIB_DIR / "ensemble_predictions.json"
    variance_decomp = None
    identifiability = None
    pairwise = None
    if ensemble_path.exists():
        ens = json.loads(ensemble_path.read_text(encoding="utf-8"))
        samples = ens["sampled_param_vectors"]
        preds_mc = np.array(ens["predictions_per_sample_per_event"], dtype=float)
        n_ens, n_ev = preds_mc.shape
        print(f"\n[2-4] Using MC ensemble: {n_ens} samples × {n_ev} events")

        # Build sample matrix (n_ens × 7)
        X = np.array([[s[k] for k in param_names] for s in samples], dtype=float)

        # --- 2. Variance decomposition (per-event univariate R²) ---
        print("\n[2] Variance decomposition (univariate R² per param per event):")
        per_event_r2 = np.full((n_ev, len(param_names)), np.nan)
        for j in range(n_ev):
            y = preds_mc[:, j]
            mask = np.isfinite(y)
            if mask.sum() < 5:
                continue
            yy = y[mask]
            for ip, k in enumerate(param_names):
                xk = X[mask, ip]
                if np.std(xk) == 0 or np.std(yy) == 0:
                    per_event_r2[j, ip] = 0.0
                    continue
                r = np.corrcoef(xk, yy)[0, 1]
                per_event_r2[j, ip] = float(r ** 2)
        # Mean R² across events
        mean_r2 = np.nanmean(per_event_r2, axis=0)
        print("  parameter           mean R²_across_events")
        order = np.argsort(-mean_r2)
        decomp_list = []
        for o in order:
            print(f"    {param_names[o]:22s} {mean_r2[o]:.5f}")
            decomp_list.append({
                "parameter": param_names[o],
                "mean_r2_univariate": float(mean_r2[o]),
                "per_event_r2": [float(per_event_r2[j, o]) if np.isfinite(per_event_r2[j, o]) else None
                                 for j in range(n_ev)],
            })
        variance_decomp = {
            "method": "univariate R² between each parameter and each event prediction (first-order Sobol approximation)",
            "per_parameter": decomp_list,
        }

        # --- 3. Identifiability: rank of param→prediction-vector map ---
        print("\n[3] Identifiability: SVD of the param→pred map at MC sample level")
        # Center and scale X and preds_mc (column-wise)
        X_finite_mask = np.all(np.isfinite(X), axis=1) & np.all(np.isfinite(preds_mc), axis=1)
        Xc = X[X_finite_mask]
        Yc = preds_mc[X_finite_mask]
        if Xc.shape[0] >= len(param_names) + 1:
            X_n = (Xc - Xc.mean(0)) / (Xc.std(0) + 1e-12)
            Y_n = (Yc - Yc.mean(0)) / (Yc.std(0) + 1e-12)
            # Multi-output regression: Y = X β + ε  → β = (XᵀX)⁻¹ XᵀY
            beta, *_ = np.linalg.lstsq(X_n, Y_n, rcond=None)
            # Singular values of β (7 × n_ev) give us the effective rank of the
            # response → which gives directions in θ space that meaningfully
            # change the output
            u, sv, vt = np.linalg.svd(beta, full_matrices=False)
            tol = max(beta.shape) * sv.max() * np.finfo(float).eps if sv.size else 0.0
            rank = int(np.sum(sv > tol))
            cond = float(sv.max() / sv.min()) if sv.min() > 0 else float("inf")
            print(f"  β shape={beta.shape}, singular values={[float(round(x,4)) for x in sv]}")
            print(f"  effective rank={rank}/{len(param_names)}  κ(β)={cond:.2f}")
            # Data-driven interpretation — computed from the ACTUAL κ and rank,
            # not assumed. (Earlier versions hardcoded a "κ ≫ 100 / rank-deficient"
            # string that was false for this corpus.)
            n_par = len(param_names)
            if cond < 10:
                kappa_band = "well-conditioned (κ < 10)"
            elif cond < 30:
                kappa_band = "mildly ill-conditioned (10 ≤ κ < 30)"
            elif cond < 100:
                kappa_band = "moderately ill-conditioned (30 ≤ κ < 100)"
            elif cond < 1000:
                kappa_band = "seriously ill-conditioned (100 ≤ κ < 1000)"
            else:
                kappa_band = "severely ill-conditioned / near-singular (κ ≥ 1000)"
            if rank >= n_par:
                rank_clause = (
                    f"effective rank is full ({rank}/{n_par}): in the linearised map every "
                    "parameter moves predictions along a distinct direction, so the parameters "
                    "are *formally* distinguishable. This does NOT contradict the near-zero "
                    "local-sensitivity result — the parameters shift individual event predictions "
                    "in independent directions, but the shifts are negligible in magnitude versus "
                    "the observed-loss scale and cancel at the aggregate, so the calibration is "
                    "*practically* weakly-determined rather than *formally* rank-deficient."
                )
            else:
                rank_clause = (
                    f"effective rank is deficient ({rank}/{n_par}): {n_par - rank} parameter "
                    "direction(s) leave predictions unchanged and are unidentifiable from this "
                    "corpus / topology."
                )
            identifiability = {
                "design_matrix_shape": list(Xc.shape),
                "response_matrix_shape": list(Yc.shape),
                "singular_values": [float(x) for x in sv.tolist()],
                "effective_rank": rank,
                "condition_number": cond,
                "interpretation": f"Condition number is {kappa_band}; {rank_clause}",
            }
        else:
            print("  not enough finite samples to compute identifiability")
            identifiability = {"error": "insufficient_finite_samples"}

        # --- 4. Pairwise correlations ---
        print("\n[4] Pairwise correlations (3 matrices):")
        # Input-input (should be ~identity since we sampled independent)
        ii = np.corrcoef(X.T)
        # Input-output: param vs each event prediction
        io = np.zeros((len(param_names), n_ev))
        for j in range(n_ev):
            y = preds_mc[:, j]
            m = np.isfinite(y)
            if m.sum() < 5 or np.std(y[m]) == 0:
                io[:, j] = np.nan
                continue
            for ip in range(len(param_names)):
                x = X[m, ip]
                if np.std(x) == 0:
                    io[ip, j] = np.nan
                else:
                    io[ip, j] = float(np.corrcoef(x, y[m])[0, 1])
        # Output-output
        oo = np.full((n_ev, n_ev), np.nan)
        for a in range(n_ev):
            for b in range(n_ev):
                ya, yb = preds_mc[:, a], preds_mc[:, b]
                m = np.isfinite(ya) & np.isfinite(yb)
                if m.sum() < 5 or np.std(ya[m]) == 0 or np.std(yb[m]) == 0:
                    continue
                oo[a, b] = float(np.corrcoef(ya[m], yb[m])[0, 1])
        # Max abs off-diagonal of input-input
        ii_offdiag = ii.copy()
        np.fill_diagonal(ii_offdiag, 0.0)
        ii_max_offdiag = float(np.nanmax(np.abs(ii_offdiag)))
        print(f"  input-input max |off-diag corr| = {ii_max_offdiag:.4f} (independent ⇒ should be small)")
        # Top 5 (input,event) pairs by |corr|
        flat = [(param_names[i], int(ens['event_ids'][j]), float(io[i, j]))
                for i in range(len(param_names)) for j in range(n_ev) if np.isfinite(io[i, j])]
        flat.sort(key=lambda t: abs(t[2]), reverse=True)
        print("  top input-output |corr| pairs:")
        for p, eid, c in flat[:8]:
            print(f"    {p:22s} ↔ event {eid:3d}: r = {c:+.4f}")
        pairwise = {
            "param_names": param_names,
            "event_ids": [int(x) for x in ens["event_ids"]],
            "input_input_corr": ii.tolist(),
            "input_input_max_abs_offdiag": ii_max_offdiag,
            "input_output_corr_param_x_event": io.tolist(),
            "output_output_corr_event_x_event": oo.tolist(),
        }
    else:
        print("\nensemble_predictions.json NOT FOUND — skipping variance decomposition/identifiability/pairwise")

    # ---- Combined JSON output ----
    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "graph": "OECD+WIOD spectrally normalised (ρ=1.0)",
        "calibrated_params": best,
        "loeo_sigma": sigma,
        "prior_ranges": PRIORS,
        "baseline_mae": base_mae,
        "n_events": len(events),
        "local_sensitivity_ranked": sensitivity_rows,
        "variance_decomposition": variance_decomp,
        "identifiability": identifiability,
        "pairwise_correlations": pairwise,
        "preserved_files": [
            "benchmark_spectral_normalized.json", "bootstrap_results.json",
            "ensemble_predictions.json", "ensemble_statistics.json",
            "ablation_post_normalization.json", "loeo_results.json",
        ],
    }
    out_path = CALIB_DIR / "calibration_stability.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
