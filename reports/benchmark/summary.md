# GEDS Benchmark Leaderboard

- Generated: 2026-06-11T17:49:50.966583+00:00
- Events: 26  |  NDCG cutoff: k=5
- Pinned config: seed=0, stochastic_sigma=0.0

Error metrics: lower MAE/RMSE is better. Ranking metrics (Pearson/Spearman/Kendall/NDCG): higher is better. Skill = Murphy skill vs naive persistence (>0 beats the mean).

| Model | N | MAE | RMSE | R² | Pearson | Spearman | Kendall | NDCG@5 | Skill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SEIRS-Bullwhip-Hysteresis (GEDS) | 26 | 0.0220 | 0.0446 | -2.2294 | 0.0712 | 0.4161 | 0.3007 | 0.4249 | -2.2294 |
| Leontief (input-output equilibrium) | 26 | 0.0144 | 0.0279 | -0.2597 | -0.0236 | 0.2600 | 0.1454 | 0.2237 | -0.2597 |
| Linear Diffusion (network) | 26 | 0.0147 | 0.0288 | -0.3420 | 0.5647 | 0.7071 | 0.5689 | 0.6826 | -0.3420 |
| Naive Persistence (predict mean) | 26 | 0.0148 | 0.0248 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | 0.0000 |

## Winners

- Lowest MAE: **Leontief (input-output equilibrium)**
- Lowest RMSE: **Naive Persistence (predict mean)**
- Highest R²: **Naive Persistence (predict mean)**
- Highest Pearson: **Linear Diffusion (network)**
- Highest Spearman: **Linear Diffusion (network)**
