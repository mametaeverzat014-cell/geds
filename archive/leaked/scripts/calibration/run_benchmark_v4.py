"""GEDS BENCHMARK V4 — Phase 3 re-evaluation.

Controlled expansion test. The Mission-1 spectrally-normalised OECD+WIOD graph
(rho=1.0) and the *frozen* calibrated GEDS config + Linear-Diffusion params are
reused verbatim, so the ONLY thing that changes between the current corpus and
the V4 corpus is the EVENT SET. That isolates the effect of adding events.

Event sets:
  current    N=21  -> the engine-eligible subset of the existing 42-event matrix
  v4_primary N=22  -> current + Mexican Peso Crisis 1994 (the one clean, single-
                      country, comparable national-output-drop net-new event)
  v4_max     N=28  -> v4_primary + Turkey Izmit 1999 + Asian Financial Crisis
                      split into 5 per-country output drops (the maximally
                      generous, figure-type-stretching expansion)

New-event targets are TRANSCRIBED verbatim from the cited sources (no
fabrication); shock magnitude is the same deterministic transform of the target
used by remap_events_for_oecd_graph (magnitude = clip(|target%|/50, 0.1, 0.9));
seed node = an existing country:sector graph node. Events whose seed node is not
present in the graph are skipped (NOT fabricated).

Outputs (backend/data/calibration/):
  benchmark_v4.json  bootstrap_v4.json  uncertainty_v4.json  loeo_v4.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "backend" / "scripts"))
sys.path.insert(0, str(REPO / "backend" / "scripts" / "calibration"))

CALIB_DIR = REPO / "backend" / "data" / "calibration"

import run_spectral_recalibration as rsr  # noqa: E402
from run_oecd_benchmark import remap_events_for_oecd_graph  # noqa: E402

N_BOOT = 5000
SEED = 20260603


# ── new-event definitions (Phase-1 MAPPED / PARTIAL adjudication) ─────────────
# target = observed output-loss fraction transcribed from source (verbatim).
NEW_EVENTS_SPEC = [
    # eid, name, iso3, sector, target_fraction, duration_months, tier, provenance
    (101, "1994 Mexican Peso Crisis (Tequila Crisis)", "MEX", "banking",
     0.048, 12, "primary",
     "World Bank projected 1995 GDP decline -4.8% (doc 381141468300609145). Single-country national output drop."),
    (102, "1999 Turkey Izmit (Kocaeli) Earthquake", "TUR", "consumer_goods",
     0.05, 6, "max",
     "OECD: official first estimates indicated a 5% drop in 1999 GDP (PARTIAL: preliminary; OECD's preferred measure is a 0.5-1pp growth delta)."),
    (103, "1997 Asian Financial Crisis (Korea)", "KOR", "banking",
     0.07, 18, "max",
     "World Bank GEP 1998-99: 1998 real output decline 7% (Republic of Korea)."),
    (104, "1997 Asian Financial Crisis (Thailand)", "THA", "banking",
     0.07, 18, "max",
     "World Bank GEP 1998-99: 1998 real output decline 7% (Thailand)."),
    (105, "1997 Asian Financial Crisis (Malaysia)", "MYS", "banking",
     0.05, 18, "max",
     "World Bank GEP 1998-99: 1998 real output decline 5% (Malaysia)."),
    (106, "1997 Asian Financial Crisis (Indonesia)", "IDN", "banking",
     0.15, 18, "max",
     "World Bank GEP 1998-99: 1998 real output decline 15% (Indonesia)."),
    (107, "1997 Asian Financial Crisis (Philippines)", "PHL", "banking",
     0.005, 18, "max",
     "World Bank GEP 1998-99: 1998 real output decline 0.5% (Philippines)."),
]


def build_translated_event(spec, node_ids):
    eid, name, iso3, sector, target, dur_m, tier, prov = spec
    node = f"{iso3}:{sector}"
    if node not in node_ids:
        return None, f"SKIP {name}: seed node {node} not in graph (cannot seed without fabrication)"
    magnitude = max(0.1, min(0.9, abs(target * 100) / 50.0))
    duration_weeks = max(1, min(26, int(round(dur_m * 4.345 / 4))))
    horizon = max(52, duration_weeks * 2)
    ev = {
        "slug": f"v4-{eid}", "name": name, "event_id": eid, "_tier": tier,
        "_provenance": prov,
        "shocks": [{"target_node_id": node, "magnitude": magnitude,
                    "start_week": 0, "duration_weeks": duration_weeks,
                    "decay_curve": "exp"}],
        "horizon_weeks": horizon,
        "observed": {"auto_production_loss_pct": abs(target),
                     "us_inflation_contribution": 0.0,
                     "expected_recovery_weeks": float(duration_weeks * 2),
                     "most_impacted_industry": sector},
        "sources": [prov[:120]], "notes": tier,
    }
    return ev, f"ADD  {name}: seed {node}, target {target}, magnitude {magnitude:.3f}"


# ── bootstrap (non-parametric, paired) ────────────────────────────────────────
def _r2(pred, obs):
    if obs.size < 2:
        return float("nan")
    ss_res = float(np.sum((obs - pred) ** 2)); ss_tot = float(np.sum((obs - obs.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def _pearson(a, b):
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _ci(pred, obs, n_boot, seed):
    rng = np.random.default_rng(seed); n = pred.size
    mae = np.empty(n_boot); pear = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        mae[b] = float(np.mean(np.abs(pred[idx] - obs[idx])))
        pear[b] = _pearson(pred[idx], obs[idx])
    return {
        "mae": {"point": float(np.mean(np.abs(pred - obs))),
                "p2_5": float(np.nanpercentile(mae, 2.5)),
                "p50": float(np.nanpercentile(mae, 50)),
                "p97_5": float(np.nanpercentile(mae, 97.5))},
        "pearson": {"point": _pearson(pred, obs),
                    "p2_5": float(np.nanpercentile(pear, 2.5)),
                    "p97_5": float(np.nanpercentile(pear, 97.5))},
        "rmse": float(np.sqrt(np.mean((pred - obs) ** 2))),
        "r_squared": _r2(pred, obs), "bias": float((pred - obs).mean()),
    }


def _delta_ci(pred_a, pred_b, obs, n_boot, seed):
    """Paired bootstrap of MAE_b - MAE_a (a=GEDS, b=baseline)."""
    rng = np.random.default_rng(seed); n = obs.size
    d = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        d[b] = float(np.mean(np.abs(pred_b[idx] - obs[idx])) - np.mean(np.abs(pred_a[idx] - obs[idx])))
    lo, hi = float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
    point = float(np.mean(np.abs(pred_b - obs)) - np.mean(np.abs(pred_a - obs)))
    return {"delta_mae_baseline_minus_geds": {"point": point, "p2_5": lo, "p97_5": hi,
            "frac_geds_better": float((d > 0).mean()),
            "zero_in_ci": bool(lo <= 0.0 <= hi),
            "significant_at_0.05": bool(not (lo <= 0.0 <= hi))}}


def arrays(per_event):
    obs = np.array([e["target"] for e in per_event])
    return {
        "obs": obs,
        "GEDS-SEIRS": np.array([e["seirs"] for e in per_event]),
        "Leontief": np.array([e["leontief"] for e in per_event]),
        "Linear-Diffusion": np.array([e["linear"] for e in per_event]),
        "Naive": np.full(obs.size, obs.mean()),
    }


def bootstrap_set(per_event, label):
    a = arrays(per_event); obs = a["obs"]
    per_model = {m: _ci(a[m], obs, N_BOOT, SEED) for m in ("GEDS-SEIRS", "Leontief", "Linear-Diffusion", "Naive")}
    pairwise = {}
    for base in ("Leontief", "Linear-Diffusion", "Naive"):
        pairwise[f"GEDS-SEIRS__vs__{base}"] = _delta_ci(a["GEDS-SEIRS"], a[base], obs, N_BOOT, SEED)
    return {"set": label, "n_events": int(obs.size), "n_resamples": N_BOOT,
            "seed": SEED, "per_model_ci": per_model, "pairwise_paired_bootstrap": pairwise}


def empirical_coverage(per_event):
    """Fraction of observed values inside GEDS pred +- 1.96*resid_std (crude 95% PI)."""
    a = arrays(per_event); obs = a["obs"]; pred = a["GEDS-SEIRS"]
    resid = obs - pred; sd = float(resid.std(ddof=1)) if obs.size > 1 else float("nan")
    lo = pred - 1.96 * sd; hi = pred + 1.96 * sd
    n_in = int(np.sum((obs >= lo) & (obs <= hi)))
    return {"method": "GEDS pred +- 1.96*residual_std (Gaussian 95% PI proxy)",
            "resid_std": sd, "n_in_band": n_in, "n_events": int(obs.size),
            "fraction": n_in / obs.size if obs.size else float("nan")}


def custom_loeo(graph, full_events, base_cfg, fold_event_ids, budget, seed):
    """LOEO over selected held-out events; train on (full_set - heldout)."""
    folds, failed = [], []
    t0 = time.time()
    id_to_ev = {e["event_id"]: e for e in full_events}
    for k, eid in enumerate(fold_event_ids):
        test_event = id_to_ev[eid]
        train = [e for e in full_events if e["event_id"] != eid]
        ft0 = time.time()
        print(f"  LOEO fold {k+1}/{len(fold_event_ids)} heldout eid={eid} ({test_event['name'][:40]})", flush=True)
        try:
            res = rsr.run_cma_es_with_trace(
                graph, train, base_cfg, maxiter=budget["maxiter"], popsize=budget["popsize"],
                seed=seed + k, trace_csv=None,
                checkpoint_path=rsr.SPEC_DIR / f"loeo_v4_fold_{k}_state.pkl", tag=f"loeo_v4_{k}")
            theta = np.array([res["best_params"][n] for n in rsr.PARAM_NAMES])
            cfg = rsr.theta_to_cfg(theta, base_cfg)
            pt, ot = rsr.eval_events(graph, [test_event], cfg)
            ptr, otr = rsr.eval_events(graph, train, cfg)
            folds.append({"fold": k, "status": "ok", "heldout_event_id": eid,
                          "heldout_event_name": test_event["name"],
                          "train_n": len(train), "train_mae": round(float(np.abs(ptr - otr).mean()), 5),
                          "test_pred": float(pt[0]), "test_obs": float(ot[0]),
                          "test_err_abs": round(float(abs(pt[0] - ot[0])), 5),
                          "best_params": res["best_params"], "best_loss_on_train": res["best_loss"],
                          "n_evals": res["n_evals"], "elapsed_seconds": round(time.time() - ft0, 1)})
            print(f"    train_mae={folds[-1]['train_mae']:.5f} test_err={folds[-1]['test_err_abs']:.5f}", flush=True)
        except Exception as exc:
            import traceback
            failed.append({"fold": k, "heldout_event_id": eid, "error": str(exc),
                           "traceback": traceback.format_exc()})
            print(f"    FAILED: {exc}", flush=True)
    test_errs = np.array([f["test_err_abs"] for f in folds]) if folds else np.array([])
    train_maes = np.array([f["train_mae"] for f in folds]) if folds else np.array([])
    vm = {}
    if folds:
        vm = {"loeo_mae": float(test_errs.mean()), "loeo_mae_std": float(test_errs.std()),
              "loeo_rmse": float(np.sqrt((test_errs ** 2).mean()))}
    return {"timestamp": datetime.now(timezone.utc).isoformat(),
            "method": "leave-one-event-out, train on full V4 set minus heldout (capped folds)",
            "n_folds_attempted": len(fold_event_ids), "n_folds_succeeded": len(folds),
            "n_folds_failed": len(failed), "elapsed_seconds": round(time.time() - t0, 1),
            "train_mae_mean": float(train_maes.mean()) if len(train_maes) else None,
            "val_metrics": vm,
            "overfitting_gap": (vm["loeo_mae"] - float(train_maes.mean())) if folds else None,
            "fold_variance": {n: {"mean": float(np.mean([f["best_params"][n] for f in folds])),
                                  "std": float(np.std([f["best_params"][n] for f in folds]))}
                              for n in rsr.PARAM_NAMES} if folds else {},
            "successful_folds": folds, "failed_folds": failed}


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser()
    ap.add_argument("--loeo", action="store_true", help="run capped LOEO (slow)")
    ap.add_argument("--loeo-maxiter", type=int, default=4)
    ap.add_argument("--loeo-popsize", type=int, default=5)
    args = ap.parse_args()

    # frozen Mission-1 calibration
    spec = json.loads((CALIB_DIR / "benchmark_spectral_normalized.json").read_text(encoding="utf-8"))
    from app.core.types import EngineConfig
    geds_cfg = EngineConfig(**{k: v for k, v in spec["geds_config"].items() if k in EngineConfig.model_fields})
    ld_best = spec["linear_diffusion_best"]
    print(f"frozen geds_config loaded; ld_best={ld_best}")

    # graph
    print("\nBuilding + spectrally normalising OECD+WIOD graph...")
    graphs = rsr.build_three_graphs()
    aug_snap = graphs["OECD+WIOD"]["snap"]
    graph = graphs["OECD+WIOD"]["graph"]
    rho_before, scale = rsr.spectral_normalise(graph, target_rho=1.0)
    from app.data import seed as seed_mod
    from app.core import backtest as bt_mod
    seed_mod.load_graph = lambda: aug_snap
    bt_mod.load_graph = lambda: aug_snap
    print(f"  graph n={graph.n}, rho {rho_before:.4f} -> 1.0")

    node_ids = {n.id for n in graph.snapshot.nodes}

    # current 21
    remapped = remap_events_for_oecd_graph(graph)
    current = sorted([r["_translated"] for r in remapped if r["mapping_status"] == "OK"],
                     key=lambda e: e["event_id"])
    print(f"\ncurrent engine-eligible: N={len(current)} (ids {[e['event_id'] for e in current]})")

    # new events
    new_primary, new_max = [], []
    for s in NEW_EVENTS_SPEC:
        ev, msg = build_translated_event(s, node_ids)
        print("  " + msg)
        if ev is None:
            continue
        if ev["_tier"] == "primary":
            new_primary.append(ev)
        new_max.append(ev)

    sets = {
        "current": current,
        "v4_primary": current + new_primary,
        "v4_max": current + new_max,
    }
    print(f"\nset sizes: current={len(sets['current'])}, "
          f"v4_primary={len(sets['v4_primary'])}, v4_max={len(sets['v4_max'])}")

    # benchmark each set (frozen config)
    bench = {}
    for label, evs in sets.items():
        fb = rsr.fair_benchmark(graph, evs, geds_cfg, ld_best)
        bench[label] = fb
        g = fb["GEDS-SEIRS"]; le = fb["Leontief"]; li = fb["Linear-Diffusion"]
        print(f"\n[{label} N={len(evs)}]")
        print(f"  GEDS     MAE={g['mae']} R2={g['r_squared']} Pearson={g['pearson']} CI95={g['mae_ci95']}")
        print(f"  Leontief MAE={le['mae']} R2={le['r_squared']} Pearson={le['pearson']}")
        print(f"  Linear   MAE={li['mae']} R2={li['r_squared']} Pearson={li['pearson']}")

    # bootstrap each set
    boot = {label: bootstrap_set(bench[label]["per_event"], label) for label in sets}

    # coverage
    cover = {label: empirical_coverage(bench[label]["per_event"]) for label in sets}

    # ── write benchmark_v4.json ───────────────────────────────────────────────
    benchmark_v4 = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "graph": "OECD+WIOD spectrally normalised (rho=1.0)",
        "graph_nodes": graph.n,
        "method": "frozen Mission-1 GEDS config + Linear-Diffusion params; only the EVENT SET varies across corpora (controlled expansion test).",
        "frozen_geds_config": spec["geds_config"],
        "linear_diffusion_best": ld_best,
        "corpora": {label: {"n_events": len(sets[label]), "models": bench[label]} for label in sets},
        "new_events": [{"event_id": s[0], "name": s[1], "iso3": s[2], "sector": s[3],
                        "target": s[4], "tier": s[6], "provenance": s[7]} for s in NEW_EVENTS_SPEC],
    }
    (CALIB_DIR / "benchmark_v4.json").write_text(json.dumps(benchmark_v4, indent=2), encoding="utf-8")
    print("\nwrote benchmark_v4.json")

    # ── write bootstrap_v4.json ───────────────────────────────────────────────
    bootstrap_v4 = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": "non-parametric event-level bootstrap; paired bootstrap for GEDS-vs-baseline ΔMAE.",
        "n_resamples": N_BOOT, "seed": SEED,
        "corpora": boot,
        "interpretation": {
            "zero_in_ci": "if 0 lies inside the 95% CI of (MAE_baseline - MAE_GEDS) the MAE difference is NOT significant at alpha=0.05",
            "frac_geds_better": "fraction of resamples in which GEDS has strictly lower MAE than the baseline",
        },
    }
    (CALIB_DIR / "bootstrap_v4.json").write_text(json.dumps(bootstrap_v4, indent=2), encoding="utf-8")
    print("wrote bootstrap_v4.json")

    # ── write uncertainty_v4.json (assembled) ─────────────────────────────────
    cs = json.loads((CALIB_DIR / "calibration_stability.json").read_text(encoding="utf-8"))
    es = json.loads((CALIB_DIR / "ensemble_statistics.json").read_text(encoding="utf-8"))
    uncertainty_v4 = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Assembled uncertainty layer for V4. Bootstrap CIs and coverage recomputed on the V4 corpora; "
                "identifiability (SVD) and Monte-Carlo ensemble coverage carried forward from the Mission-1 "
                "uncertainty stack (these are properties of the model + parameter space + frozen calibration, "
                "essentially invariant to a +1 to +7 event change).",
        "per_corpus": {
            label: {
                "n_events": len(sets[label]),
                "geds_mae_ci95": [boot[label]["per_model_ci"]["GEDS-SEIRS"]["mae"]["p2_5"],
                                  boot[label]["per_model_ci"]["GEDS-SEIRS"]["mae"]["p97_5"]],
                "geds_pearson_ci95": [boot[label]["per_model_ci"]["GEDS-SEIRS"]["pearson"]["p2_5"],
                                      boot[label]["per_model_ci"]["GEDS-SEIRS"]["pearson"]["p97_5"]],
                "superiority_vs_baselines": {
                    base: boot[label]["pairwise_paired_bootstrap"][f"GEDS-SEIRS__vs__{base}"]["delta_mae_baseline_minus_geds"]
                    for base in ("Leontief", "Linear-Diffusion", "Naive")},
                "empirical_coverage_95pi": cover[label],
            } for label in sets},
        "identifiability_carried_forward": {
            "condition_number": cs["identifiability"]["condition_number"],
            "effective_rank": cs["identifiability"]["effective_rank"],
            "n_params": len(rsr.PARAM_NAMES),
            "interpretation": cs["identifiability"]["interpretation"],
        },
        "monte_carlo_ensemble_coverage_carried_forward": {
            "n_ensemble": es["n_ensemble"], "n_events_at_build": es["n_events"],
            "coverage_observed_in_p2_5_p97_5": es["coverage_observed_in_p2_5_p97_5"],
            "parameter_uncertainty_source": es["parameter_uncertainty_source"],
        },
        "loeo_sigma_carried_forward": cs["loeo_sigma"],
    }

    # ── LOEO (optional, slow) ─────────────────────────────────────────────────
    if args.loeo:
        print("\n=== LOEO-CV on v4_primary (capped folds incl. the new Mexico event) ===", flush=True)
        prim = sets["v4_primary"]
        existing_ids = [e["event_id"] for e in current]
        # held-out folds: the new event (101) + 5 representative existing events
        fold_ids = [101] + existing_ids[:5]
        from app.core.types import EngineConfig as _EC
        base_cfg = _EC()
        loeo_v4 = custom_loeo(graph, prim, base_cfg, fold_ids,
                              budget={"maxiter": args.loeo_maxiter, "popsize": args.loeo_popsize},
                              seed=SEED)
        (CALIB_DIR / "loeo_v4.json").write_text(json.dumps(loeo_v4, indent=2), encoding="utf-8")
        print(f"wrote loeo_v4.json ({loeo_v4['n_folds_succeeded']}/{loeo_v4['n_folds_attempted']} folds)")
        uncertainty_v4["loeo_v4_summary"] = {
            "n_folds": loeo_v4["n_folds_succeeded"], "val_metrics": loeo_v4["val_metrics"],
            "overfitting_gap": loeo_v4["overfitting_gap"], "fold_variance": loeo_v4["fold_variance"]}
    else:
        print("\n(LOEO skipped; pass --loeo to run)")

    (CALIB_DIR / "uncertainty_v4.json").write_text(json.dumps(uncertainty_v4, indent=2), encoding="utf-8")
    print("wrote uncertainty_v4.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
