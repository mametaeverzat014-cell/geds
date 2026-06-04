# GEDS Benchmark Leaderboard

- Generated: 2026-06-04T09:57:08.991592+00:00
- Events: 8  |  NDCG cutoff: k=5
- Pinned config: seed=0, stochastic_sigma=0.0

Error metrics: lower MAE/RMSE is better. Ranking metrics (Pearson/Spearman/Kendall/NDCG): higher is better. Skill = Murphy skill vs naive persistence (>0 beats the mean).

| Model | N | MAE | RMSE | R² | Pearson | Spearman | Kendall | NDCG@5 | Skill |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SEIRS-Bullwhip-Hysteresis (GEDS) | 8 | 0.0248 | 0.0361 | 0.0451 | 0.7196 | 0.8264 | 0.6183 | 0.9422 | 0.0451 |
| Leontief (input-output equilibrium) | 8 | 0.0301 | 0.0478 | -0.6696 | 0.0753 | 0.6347 | 0.4001 | 0.7005 | -0.6696 |
| Linear Diffusion (network) | 8 | 0.0152 | 0.0179 | 0.7647 | 0.8790 | 0.8503 | 0.6910 | 0.9905 | 0.7647 |
| Naive Persistence (predict mean) | 8 | 0.0305 | 0.0370 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | — | 0.0000 |

## Winners

- Lowest MAE: **Linear Diffusion (network)**
- Lowest RMSE: **Linear Diffusion (network)**
- Highest R²: **Linear Diffusion (network)**
- Highest Pearson: **Linear Diffusion (network)**
- Highest Spearman: **Linear Diffusion (network)**
