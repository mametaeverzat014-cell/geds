"""Smoke test for batch 3: ablation, sensitivity (Sobol), benchmark."""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

# 1. Ablation -----------------------------------------------------------
print("=== 1. ABLATION STUDY ===")
from app.core.ablation import run_ablation_study, save_ablation
t0 = time.perf_counter()
abl = run_ablation_study()
print(f"  runtime={time.perf_counter()-t0:.1f}s  n_events={abl.n_events}")
print(f"  {'variant':<24s}  {'MAE':>7s}  {'RMSE':>7s}  {'Pearson':>8s}  {'pass50':>7s}  {'dMAE':>7s}  {'dPearson':>9s}")
print(f"  {'-'*24}  {'-'*7}  {'-'*7}  {'-'*8}  {'-'*7}  {'-'*7}  {'-'*9}")
for r in abl.rows:
    print(f"  {r.variant:<24s}  {r.mae_loss:7.4f}  {r.rmse_loss:7.4f}  {r.pearson_loss:+8.4f}  {r.pass_rate_50pct:7.2%}  {r.mae_delta_vs_full:+7.4f}  {r.pearson_delta_vs_full:+9.4f}")
print(f"  >>> BEST  (lowest MAE): {abl.best_variant}")
print(f"  >>> WORST (highest MAE): {abl.worst_variant}")
save_ablation(abl)

# 2. Sobol sensitivity --------------------------------------------------
print()
print("=== 2. SOBOL GLOBAL SENSITIVITY (n_base=128, tiny smoke) ===")
from app.core.sensitivity import run_sobol, save_sobol
t0 = time.perf_counter()
sob = run_sobol(n_base_samples=128, seed=42)
print(f"  runtime={sob.runtime_seconds:.1f}s  evals={sob.n_engine_evals}")
print(f"  output mean={sob.output_mean:.4f}  std={sob.output_std:.4f}  sum_S1={sob.sum_S1:.3f}")
print(f"  {'parameter':<22s}  {'S1':>7s}  {'ST':>7s}  {'rank':>4s}  interpretation")
for p in sorted(sob.parameters, key=lambda x: x.rank_by_total_effect):
    print(f"  {p.name:<22s}  {p.first_order_S1:7.3f}  {p.total_effect_ST:7.3f}  {p.rank_by_total_effect:4d}  {p.interpretation}")
save_sobol(sob)

# 3. Benchmark ----------------------------------------------------------
print()
print("=== 3. MODEL BENCHMARK LEADERBOARD ===")
from app.core.benchmark import run_benchmark, save_benchmark
bench = run_benchmark()
print(f"  n_events={bench.n_events}")
print(f"  {'model':<40s}  {'MAE':>7s}  {'RMSE':>7s}  {'R2':>7s}  {'Pearson':>8s}  {'Skill':>7s}  {'Bias':>7s}")
print(f"  {'-'*40}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*8}  {'-'*7}  {'-'*7}")
for m in bench.models:
    print(f"  {m.model[:40]:<40s}  {m.mae:7.4f}  {m.rmse:7.4f}  {m.r_squared:+7.3f}  {m.pearson:+8.4f}  {m.skill_score_vs_persistence:+7.3f}  {m.bias:+7.4f}")
print(f"  >>> Winner by MAE:     {bench.winner_by_mae}")
print(f"  >>> Winner by RMSE:    {bench.winner_by_rmse}")
print(f"  >>> Winner by R^2:     {bench.winner_by_r_squared}")
print(f"  >>> Winner by Pearson: {bench.winner_by_pearson}")
save_benchmark(bench)

print()
print("BATCH 3 VERIFIED.")
