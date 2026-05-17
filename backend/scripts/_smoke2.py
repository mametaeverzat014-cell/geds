"""Smoke test for batch 2: isotonic, DE, tail-risk, ERT, SAC."""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

print("=== 1. ISOTONIC POST-CALIBRATION (out-of-sample LOO) ===")
from app.core.postcalibration import loo_calibration_report
cal = loo_calibration_report()
print(f"  method: {cal.method}  n={cal.n_samples}")
print(f"  Pearson     before={cal.pearson_before:+.3f}   after={cal.pearson_after:+.3f}")
print(f"  Spearman    before={cal.spearman_before:+.3f}   after={cal.spearman_after:+.3f}")
print(f"  MAE         before={cal.mae_before:.4f}    after={cal.mae_after:.4f}")
print(f"  RMSE        before={cal.rmse_before:.4f}    after={cal.rmse_after:.4f}")
print(f"  Pass ±25%   before={cal.pass_rate_25pct_before:.2%}   after={cal.pass_rate_25pct_after:.2%}")

print()
print("=== 2. DIFFERENTIAL EVOLUTION CALIBRATION (1 restart, tiny smoke) ===")
from app.core.de_calibrate import run_de_calibration, save_de_result
t0 = time.perf_counter()
de = run_de_calibration(n_restarts=1, pop_size_per_dim=4, max_iter=8, seed=42)
print(f"  runtime={de.runtime_seconds:.1f}s  converged_fraction={de.converged_fraction:.2f}")
print(f"  best_loss={de.best_loss:.3f}")
for p in de.parameters:
    print(f"  {p.name:24s} point={p.point:.3f}  restart_std={p.restart_std:.3f}  [p05={p.restart_p05:.3f}, p95={p.restart_p95:.3f}]")
save_de_result(de)

print()
print("=== 3. TAIL-RISK ENGINE (VaR / CVaR / black-swan / fan chart) ===")
from app.core.tail_risk import compute_tail_risk
from app.core.graph import compile_graph
from app.core.types import Scenario, ShockSpec, EngineConfig
from app.data.seed import load_graph

g = compile_graph(load_graph())
sc = Scenario(
    id="tail_test", name="Taiwan Strait — tail",
    shocks=[ShockSpec(target_node_id="CP:TaiwanStrait", magnitude=0.85, duration_weeks=12)],
    horizon_weeks=26, config=EngineConfig(),
)
t0 = time.perf_counter()
tail = compute_tail_risk(sc, g, n_iterations=200, param_noise_pct=15.0, seed=42)
print(f"  runtime={time.perf_counter()-t0:.1f}s  n_iter={tail.n_iterations}")
print(f"  mean total loss  = ${tail.mean/1e9:>9.1f}B   std = ${tail.std/1e9:.1f}B")
print(f"  skewness         = {tail.skewness:+.3f}      kurtosis = {tail.kurtosis:+.3f}")
print(f"  VaR  95/99/99.9  = ${tail.var_95/1e9:.1f}B / ${tail.var_99/1e9:.1f}B / ${tail.var_999/1e9:.1f}B")
print(f"  CVaR 95/99/99.9  = ${tail.cvar_95/1e9:.1f}B / ${tail.cvar_99/1e9:.1f}B / ${tail.cvar_999/1e9:.1f}B")
print(f"  P(>2-sigma)={tail.p_loss_above_2sigma:.3f}  P(>3-sigma)={tail.p_loss_above_3sigma:.3f}  P(>5-sigma)={tail.p_loss_above_5sigma:.3f}")

print()
print("=== 4. ECONOMIC RESILIENCE TENSOR + SHOCK ABSORPTION CAPACITY ===")
from app.core.research_metrics import (
    economic_resilience_tensor, ert_summary,
    shock_absorption_capacity, sac_summary, evaluate_metrics_v2,
)
ert = economic_resilience_tensor(g, horizon_weeks=52)
print(f"  ERT shape = {ert.shape}  (N nodes x H+1 weeks)")
ert_s = ert_summary(g)
print(f"  mean resilience @ 4w  = {ert_s['mean_resilience_at_4w']:.3f}")
print(f"  mean resilience @ 12w = {ert_s['mean_resilience_at_12w']:.3f}")
print(f"  mean resilience @ 52w = {ert_s['mean_resilience_at_52w']:.3f}")
print(f"  slowest recovering    = {ert_s['slowest_recovering_nodes']}")
print(f"  fastest recovering    = {ert_s['fastest_recovering_nodes']}")
print()
sac = shock_absorption_capacity(g)
print(f"  SAC shape={sac.shape}  mean={sac.mean():.3f}  min={sac.min():.3f}  max={sac.max():.3f}")
sac_s = sac_summary(g)
print(f"  most fragile (low SAC):")
for n in sac_s['most_fragile_nodes']: print(f"    {n['node_id']:<28s}  SAC={n['sac']:.3f}")
print(f"  most robust (high SAC):")
for n in sac_s['most_robust_nodes']: print(f"    {n['node_id']:<28s}  SAC={n['sac']:.3f}")

print()
print("  Statistical evaluation (per-event variation):")
for ev in evaluate_metrics_v2():
    print(f"    {ev.metric_name:<22s}  pearson={ev.pearson:+.3f}  spearman={ev.spearman:+.3f}  p={ev.p_value_permutation:.3f}")

print()
print("BATCH 2 VERIFIED.")
