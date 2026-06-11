# GEDS Benchmark Leaderboard

- Generated: 2026-06-11T03:03:12.383481+00:00
- Events: 21  |  NDCG cutoff: k=5
- Pinned config: seed=0, stochastic_sigma=0.0

Error metrics: lower MAE/RMSE is better. Ranking metrics (Pearson/Spearman/Kendall/NDCG): higher is better. Skill = Murphy skill vs naive persistence (>0 beats the mean).

| Model | N | MAE | RMSE | R² | Pearson | Spearman | Kendall | NDCG@5 | Skill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SEIRS-Bullwhip-Hysteresis (GEDS) | 21 | 0.0192 | 0.0362 | -0.8328 | 0.1663 | 0.4212 | 0.2954 | 0.5824 | -0.8328 |
| Leontief (input-output equilibrium) | 21 | 0.0154 | 0.0301 | -0.2642 | 0.0064 | 0.2741 | 0.1501 | 0.2708 | -0.2642 |
| Linear Diffusion (network) | 21 | 0.0111 | 0.0140 | 0.7246 | 0.9053 | 0.8105 | 0.6635 | 0.9704 | 0.7246 |
| Naive Persistence (predict mean) | 21 | 0.0168 | 0.0268 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | 0.0000 |

## Winners

- Lowest MAE: **Linear Diffusion (network)**
- Lowest RMSE: **Linear Diffusion (network)**
- Highest R²: **Linear Diffusion (network)**
- Highest Pearson: **Linear Diffusion (network)**
- Highest Spearman: **Linear Diffusion (network)**
