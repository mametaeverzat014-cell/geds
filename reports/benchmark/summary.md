# GEDS Benchmark Leaderboard

- Generated: 2026-06-09T20:15:10.794676+00:00
- Events: 21  |  NDCG cutoff: k=5
- Pinned config: seed=0, stochastic_sigma=0.0

Error metrics: lower MAE/RMSE is better. Ranking metrics (Pearson/Spearman/Kendall/NDCG): higher is better. Skill = Murphy skill vs naive persistence (>0 beats the mean).

| Model | N | MAE | RMSE | R² | Pearson | Spearman | Kendall | NDCG@5 | Skill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SEIRS-Bullwhip-Hysteresis (GEDS) | 21 | 0.0216 | 0.0379 | -1.0085 | 0.1396 | 0.3611 | 0.2634 | 0.4408 | -1.0085 |
| Leontief (input-output equilibrium) | 21 | 0.0180 | 0.0321 | -0.4436 | -0.0718 | 0.2151 | 0.1268 | 0.2286 | -0.4436 |
| Linear Diffusion (network) | 21 | 0.0130 | 0.0169 | 0.5999 | 0.8222 | 0.5978 | 0.4586 | 0.9363 | 0.5999 |
| Naive Persistence (predict mean) | 21 | 0.0168 | 0.0268 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | 0.0000 |

## Winners

- Lowest MAE: **Linear Diffusion (network)**
- Lowest RMSE: **Linear Diffusion (network)**
- Highest R²: **Linear Diffusion (network)**
- Highest Pearson: **Linear Diffusion (network)**
- Highest Spearman: **Linear Diffusion (network)**
