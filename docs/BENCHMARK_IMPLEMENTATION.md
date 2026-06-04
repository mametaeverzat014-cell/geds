# GEDS Benchmark — Implementation Plan

Sources: `model_catalog.csv` (10 models) +
`benchmark_matrix.csv` (1–10 scoring) + the GEDS benchmark-comparison
docx implementation references.

Each model below has:
- **Libraries** — concrete packages from the docx + repo state
- **Datasets** — only from `dataset_catalog.csv` priorities
- **Training** — what calibration / fit step looks like
- **Runtime** — order-of-magnitude estimate
- **Effort** — calendar days for 1 engineer, with risk caveats

## 1. Leontief Input-Output (I-O)

- **Category:** `economic_models`
- **Libraries:** pymrio (Python), iotables (R), BEA I-O Tool
- **Datasets:** OECD ICIO (76 countries × 45 sectors), BEA US I-O Tables, WIOD
- **Training:** No training — closed-form inversion of (I − A)
- **Runtime:** <1s for 200 nodes; ~10s for full ICIO
- **Implementation effort:** 2 days
- **Risk:** Low — globally validated; only risk is misalignment between input shock units and I-O units

## 2. Linear Network Diffusion

- **Category:** `linear_models`
- **Libraries:** scipy.sparse, networkx, numpy
- **Datasets:** UN Comtrade adjacency (already ingested), OECD ICIO, BIS interbank, BACI bilateral
- **Training:** No training — eigendecomposition + matrix exponential
- **Runtime:** Real-time for n=200 countries; sub-second per step
- **Implementation effort:** 1 days
- **Risk:** Low — currently the best-performing baseline on the GEDS N=8 benchmark

## 3. Agent-Based Model (ABM)

- **Category:** `agent_based_models`
- **Libraries:** mesa (Python), Agents.jl (Julia), acclimate (C++)
- **Datasets:** RIETI Japan interfirm (~1M firms; restricted), FactSet/Orbis (paid), OECD ICIO (free)
- **Training:** Calibration via genetic algorithm or pattern-matching, not gradient descent
- **Runtime:** Hours for 100K agents × 52 weeks; days for 1M+ agents
- **Implementation effort:** 30 days
- **Risk:** HIGH — parameter sensitivity high; results differ across replications; difficult to validate against macro data per docx

## 4. Graph Neural Network (GNN / TGNN)

- **Category:** `graph_neural_networks`
- **Libraries:** PyTorch Geometric, DGL, torch-temporal
- **Datasets:** EconoGNN replication data (UN Comtrade 1996–2019 × 183 countries × PWT features)
- **Training:** GPU; ~hours per epoch on 183-country graph
- **Runtime:** Inference < 1s per snapshot; training is the bottleneck
- **Implementation effort:** 21 days
- **Risk:** Medium — requires GPU + labelled crisis data; risk of overfitting on small N

## 5. Dynamic Bayesian Network (DBN)

- **Category:** `network_models`
- **Libraries:** pgmpy, pomegranate (Python); bnlearn (R)
- **Datasets:** Balance-sheet data (BoE / ECB / Bundesbank) — partly restricted
- **Training:** Structure learning is NP-hard in general; manual DAG specification recommended
- **Runtime:** Exact inference exponential in clique size; approximate methods needed
- **Implementation effort:** 14 days
- **Risk:** Medium — structure validity hard to verify; acyclicity may be violated by interbank loops

## 6. Network Contagion Model (SIR-type / Gai-Kapadia)

- **Category:** `network_models`
- **Libraries:** EpiModel (R), networkx (Python), custom impl recommended
- **Datasets:** Network topology (already in graph.snapshot); thresholds (literature-derived)
- **Training:** No training — closed-form threshold; calibration of β and γ from data
- **Runtime:** Fast — O(n) per simulation step
- **Implementation effort:** 5 days
- **Risk:** Low — well-understood; main risk is misspecified mixing assumption

## 7. Temporal Graph Model (TGN / TGAT)

- **Category:** `graph_neural_networks`
- **Libraries:** PyTorch + torch-temporal; TGB benchmark code (TGB 2.0)
- **Datasets:** TGB 2.0 datasets; UN Comtrade time-series edges (custom prep)
- **Training:** GPU; OOM risk on large graphs per docx
- **Runtime:** Training: hours-days. Inference: <1s.
- **Implementation effort:** 28 days
- **Risk:** HIGH — TGAT specifically has known OOM failures on large graphs per docx

## 8. XGBoost (Gradient-Boosted Trees)

- **Category:** `machine_learning`
- **Libraries:** xgboost, shap, optuna
- **Datasets:** FRED + IMF WEO + BIS (all HIGH priority in dataset_priority.csv)
- **Training:** Minutes-hours on a single CPU; SHAP for feature importance
- **Runtime:** Inference sub-millisecond per observation
- **Implementation effort:** 5 days
- **Risk:** Low — well-trodden path; risk is overfitting on N<50 events

## 9. Random Forest (RF)

- **Category:** `machine_learning`
- **Libraries:** scikit-learn, ranger (R, faster)
- **Datasets:** Same as XGBoost
- **Training:** Minutes on CPU; no hyperparameter tuning as critical as XGBoost
- **Runtime:** Fast
- **Implementation effort:** 3 days
- **Risk:** Low — robust to outliers; competitive baseline

## 10. Monte Carlo Simulation (MCS)

- **Category:** `hybrid_models`
- **Libraries:** scipy.stats, numpy, SALib (Sobol)
- **Datasets:** Any underlying model's input distributions
- **Training:** N runs × base model — N=1000 is typical for 95% CIs
- **Runtime:** Slow for tail events; convergence by law of large numbers
- **Implementation effort:** 4 days
- **Risk:** Medium — convergence slow for rare tail events; depends on input distribution quality
