# AI / ML Architecture

Five model families, each with a clear job. None is asked to be a universal forecaster. Composition is the point.

| Model | Job | Format | Inference SLO |
|---|---|---|---|
| **Graph Neural Network** | Country-sector embeddings, vulnerability scoring, propagation kernel (future) | PyTorch + PyTorch Geometric | p50 < 50ms |
| **XGBoost (multiple)** | Per-target tabular forecast (inflation, unemployment, GDP delta, shortage probability) conditioned on simulation features + graph embeddings | XGBoost | p50 < 10ms per call |
| **Temporal Fusion Transformer** | Multi-horizon, multivariate forecasts of commodity prices and country macro indicators | PyTorch Lightning | p50 < 200ms |
| **PPO RL policy** | Adaptive rerouting under uncertainty | Stable Baselines3 / cleanrl | p50 < 100ms |
| **Anomaly detection** | Real-time alerts on price/flow regime shifts | Isolation Forest + LSTM autoencoder | p50 < 20ms |

All five sit behind one `ModelEnsemble` facade in `ml/inference/ensemble.py`. The simulation engine and analytics service talk to the facade, never to a specific model. This is what lets us swap models without coordinating with consumers.

---

## 1. Graph Neural Network

### 1.1 Why GNN

Country-sector resilience is a function of *position in the network*, not of country-level features alone. A country with high GDP but a single concentrated supplier is fragile; a country with lower GDP and 8 diversified suppliers is not. GNNs encode position directly.

### 1.2 Architecture

Hybrid GraphSAGE + GAT, two layers, residual:

```
Input:   node features (country/commodity/sector) + edge features (flow, tariff, distance)
Layer 1: GraphSAGE(128) — neighbor aggregation, learnable mean over import partners
Layer 2: GAT(128, heads=4) — attention reweighs neighbors by learned importance
Head A:  vulnerability_score = MLP(emb) → [0, 1] scalar per country-sector
Head B:  shock_response_kernel = MLP(emb, neighbor_emb) → propagation weights (used in
         "GNN propagation" mode of the engine; future)
```

Node features include: log-GDP, GDP per capita, log-population, sector GVA share, total trade as % of GDP, stockpile ratios for top-N commodities. Edge features include: log(flow value), tariff, log(distance), chokepoints traversed (one-hot over top-7).

Pre-training trick: initialize with Neo4j FastRP embeddings (128-d) — gives the GNN a structural prior so it doesn't need to relearn the trade-bloc community structure from scratch.

### 1.3 Training

- **Self-supervised pre-training** on link prediction: mask 10% of EXPORTS edges; ask the model to predict whether a missing edge exists and its value bucket. 100 epochs, AdamW, lr 1e-3 with cosine schedule.
- **Supervised fine-tuning** for vulnerability head: targets are historical shortage occurrences (binary) per country-commodity-quarter from the historical events dataset, plus simulator-generated labels for synthetic shocks. Weighted BCE (positives are rare).
- **Negative sampling** for the kernel head: pair shock_t with shock_{t+1} from simulator runs; the kernel learns the per-edge propagation factor.

Train on a single A100 in ~6 hours for the MVP graph. Larger graphs go multi-GPU via PyTorch Geometric's `NeighborLoader`.

### 1.4 Calibration & explainability

- Vulnerability scores are calibrated on a held-out set via Platt scaling; ECE reported in the model card.
- Per-prediction attribution via GNNExplainer: returns subgraph and edge mask. Surfaced in the API as `attributions.{nodes, edges, weights}`.

---

## 2. XGBoost forecasters

### 2.1 Why XGBoost (still, in 2026)

For tabular forecasting with mixed dense/sparse features and limited training data, gradient-boosted trees still beat neural baselines per-effort. They're fast (<10ms per call), produce calibrated probability output, and SHAP gives us a clean attribution story.

We use **one XGBoost model per target × horizon bucket**, so we don't ask one tree ensemble to do everything:

- `xgb_inflation_4w`, `xgb_inflation_12w`, `xgb_inflation_52w`
- `xgb_gdp_4w`, `xgb_gdp_12w`, `xgb_gdp_52w`
- `xgb_unemployment_12w`, `xgb_unemployment_52w`
- `xgb_shortage_prob_4w` (binary classification)

### 2.2 Features

For target country `i`, target horizon `h`, features include:

- **Simulation features** — the current shock_state vector (top-k components by magnitude), rerouted_share, chokepoint_capacity_remaining.
- **Graph features** — GNN embedding for country `i`, plus aggregated embeddings of i's top-5 partners weighted by import share.
- **Macro features** — inflation_yoy, GDP per capita, government debt / GDP, central-bank policy rate (where available).
- **Time-series features** — last-4-quarter trend on inflation and GDP, 12-month rolling vol of commodity prices in i's import basket.
- **Calendar** — week of year (cyclic), distance from last major regime shift event.

Feature engineering pipeline lives in `ml/features/`. All feature builders are pure functions of the dataset version + scenario state — fully reproducible.

### 2.3 Training

Walk-forward cross-validation: train on data through year T, validate on year T+1, slide forward. No future leakage. We grid-search depth (4–8), eta (0.03–0.1), subsample (0.7–0.9), colsample_bytree (0.5–0.9), min_child_weight (1–10). Best model per target × horizon bucket is registered.

### 2.4 Calibration

Probabilistic outputs (`xgb_shortage_prob_*`) are isotonic-calibrated on a held-out set. Regression outputs use quantile regression objectives so we get p10/p50/p90 directly. ECE and CRPS reported per model.

---

## 3. Temporal Fusion Transformer

For multi-horizon, multivariate forecasting of commodity prices and country-level macro indicators. TFT handles:

- **Static covariates** (country, sector identity)
- **Known future covariates** (calendar, scheduled events, scenario shock schedule)
- **Past observed covariates** (historical prices, flows, shocks)
- **Variable selection** at each timestep

### 3.1 Architecture

Standard TFT (Lim et al. 2021): variable-selection networks, gated residual networks, LSTM encoder + decoder, multi-head attention over the past. 128 hidden, 4 attention heads, 0.1 dropout, sequence_length=104 (2 years), horizon=52 (1 year forward).

### 3.2 Training

PyTorch Lightning. Quantile loss at {0.1, 0.5, 0.9}. Train on the full historical time series for all tracked commodities (~30) and all major-economy CPI series. Early stopping on validation CRPS.

### 3.3 Use

The simulation engine calls TFT for the *world-price* trajectory of each commodity (input to inflation update). It can also be called directly via the API for ad-hoc forecasts independent of any scenario.

---

## 4. Reinforcement Learning for adaptive rerouting

### 4.1 Why RL

The analytic Yen's-k-shortest baseline is a one-shot optimization at each timestep. It doesn't anticipate downstream congestion that *its own* rerouting decisions create. RL learns to.

### 4.2 Environment

```python
# ml/training/rl_env.py
class ReroutingEnv(gym.Env):
    observation_space = Box(...)   # graph embedding + state + capacity remaining
    action_space      = Box(...)   # softmax over top-k path candidates per disrupted route

    def step(self, action):
        # 1. Apply rerouting decision.
        # 2. Step the underlying simulator one tick.
        # 3. Compute reward.
        reward = (
            - alpha * mean_inflation_dev           # avoid inflation
            - beta  * unmet_demand                 # don't strand goods
            - gamma * chokepoint_congestion_delta  # don't crowd downstream
        )
        return obs, reward, done, info
```

The simulator runs as the environment. Training is on-policy (PPO), with the simulator parallelized across N=64 envs.

### 4.3 Architecture

PPO with a graph-aware actor-critic: the actor is a small MLP on top of the GNN embedding of the disrupted region; the critic shares the encoder. 256 hidden, 0.99 discount, GAE lambda 0.95. ~10M environment steps for convergence on the MVP graph.

### 4.4 Sim-to-real concern

The RL policy is trained against *our own simulator*, which is a model of reality. The policy is therefore as good as our simulator, no better. We mitigate with:

- **Domain randomization** during training: vary ρ, R, amplification thresholds across the calibrated range to make the policy robust to model uncertainty.
- **Replay-based validation**: the RL policy is evaluated on historical events. If it makes replays worse than the analytic baseline, we don't promote it for that scenario class.

The honest framing: RL gives us a *better baseline* than Yen's, not a *correct* answer.

---

## 5. Anomaly detection

Real-time deviation alerts on prices, flows, AIS movements. Surface "something is happening" before it shows up in scheduled forecasts.

Two-tier ensemble:

- **Isolation Forest** — per-commodity, per-route. Fast, handles concept drift via periodic refit. Catches univariate outliers.
- **LSTM autoencoder** — multivariate; encodes a 4-week window of (price, volume, AIS density), reconstructs, alerts on reconstruction error > threshold (set via held-out quantile).

Outputs an `anomaly_score` per (commodity, region, week) with a deviation magnitude. Plumbed into the API as a live channel; the frontend shows a "what's anomalous now" tile on the Atlas screen.

---

## 6. Ensemble facade

```python
# ml/inference/ensemble.py
class ModelEnsemble:
    def __init__(self, gnn, xgb_pack, tft, rl_policy, anomaly):
        ...

    def predict_inflation(self, iso3: str, horizon_weeks: int, scenario_features: dict) -> Distribution:
        # Fuse XGBoost point estimate + intervals with TFT quantiles by horizon.
        ...

    def predict_shortage(self, iso3: str, hs: str, horizon_weeks: int, scenario_features: dict) -> Distribution:
        ...

    def explain(self, prediction_id: UUID) -> Explanation:
        # Returns SHAP values + GNN attributions joined.
        ...

    def vulnerability_scores(self, iso3: str | None = None) -> dict:
        # Pure GNN read.
        ...
```

The simulation engine and analytics service only know `ModelEnsemble`. Swapping a model (new XGBoost version, GNN family change) is a single config update — no consumer changes.

---

## 7. Training data

| Source | Use |
|---|---|
| Historical events (COVID, Suez, Ukraine, 1973/79 oil shocks, 2008 commodity, 2020–23 chip shortage, ~30 smaller) | Labels for vulnerability, shortage, recovery times |
| UN Comtrade time series | Trade flows, edge weights, structural change over time |
| World Bank Pink Sheet | Commodity prices |
| IMF IFS / OECD | Macro indicators |
| WTO / OECD I-O tables | Sector-sector and commodity-sector coefficients |
| AIS public feed | Live shipping flows, lag-1 indicator of disruption |
| Simulator-generated | Synthetic scenarios for GNN kernel and RL training |

Two-track training data:

- **Real history** — small N (5–8 major crises), high signal, used for fine-tuning and final validation.
- **Simulator-synthesized** — large N, low signal-per-sample but unlimited, used for pre-training and RL.

The split is what lets us train modern model sizes without overfitting to a handful of events.

---

## 8. Model registry & promotion

Every trained model is versioned: `name@semver+gitsha`. Stored in object storage with metadata in Postgres (`model_registry` table). Promotion to "active" requires:

1. CI runs the full replay test suite with the candidate model.
2. Replay metrics are within tolerance of, or better than, the current active model.
3. Bias / calibration checks pass (ECE under threshold).
4. Manual approval (until we have enough confidence to automate).

Rollback is one row: `UPDATE model_registry SET is_active = false WHERE id = ? RETURNING ...; UPDATE model_registry SET is_active = true WHERE id = ?;` — done atomically.

---

## 9. Honest limitations

- The training corpus of real major crises is small. Confidence intervals on coefficients are wide; we surface this in the UI rather than hiding it.
- The GNN, RL policy, and anomaly detectors are trained mostly on simulator data. Real-world performance is upper-bounded by simulator fidelity, which we measure via replay tests.
- TFT extrapolation past 26 weeks loses meaningfully — we cap default forecast horizons at 26 weeks for TFT outputs and switch to scenario-based simulation for longer horizons.
- We do not currently model adversarial dynamics (e.g., strategic actors gaming the rerouting). Future work.

These are documented in every model card and shown in the UI alongside the prediction. A prediction without its model card is not shipped.
