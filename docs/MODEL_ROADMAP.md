# GEDS Model Roadmap

Derived from `model_catalog.csv` (10 models) and
`benchmark_matrix.csv`. Effort estimates are calendar days for one
engineer in the existing GEDS Python codebase.

## Immediate (1–3 days)

Goal: lock down the 'must-beat' baselines. The current benchmark
(`backend/data/benchmark.json`) shows Linear Diffusion winning on N=8.
We need the baselines in production before we can credibly claim
anything about the more complex models.

- **1. Leontief Input-Output (I-O)** — pymrio (Python), iotables (R), BEA I-O Tool; ~2 days; risk: Low — globally validated; only risk is misalignment between input shock units an
- **2. Linear Network Diffusion** — scipy.sparse, networkx, numpy; ~1 days; risk: Low — currently the best-performing baseline on the GEDS N=8 benchmark
- **9. Random Forest (RF)** — scikit-learn, ranger (R, faster); ~3 days; risk: Low — robust to outliers; competitive baseline

## Short-term (1–2 weeks)

Goal: add the medium-effort models that complete the baseline triad.

- **5. Dynamic Bayesian Network (DBN)** — pgmpy, pomegranate (Python); bnlearn (R); ~14 days; risk: Medium — structure validity hard to verify; acyclicity may be violated by interb
- **6. Network Contagion Model (SIR-type / Gai-Kapadia)** — EpiModel (R), networkx (Python), custom impl recommended; ~5 days; risk: Low — well-understood; main risk is misspecified mixing assumption
- **8. XGBoost (Gradient-Boosted Trees)** — xgboost, shap, optuna; ~5 days; risk: Low — well-trodden path; risk is overfitting on N<50 events
- **10. Monte Carlo Simulation (MCS)** — scipy.stats, numpy, SALib (Sobol); ~4 days; risk: Medium — convergence slow for rare tail events; depends on input distribution qu

**Dependencies:** existing fetcher infrastructure must be wired
(see `dataset_priority.csv` HIGH items: FRED, IMF WEO, BIS).
**Expected scientific impact:** completes the baseline comparison set;
allows fair claims of 'GEDS beats / loses to baseline X'.

## Medium-term (2–4 weeks)

Goal: the higher-effort statistically-rich models.

- **3. Agent-Based Model (ABM)** — mesa (Python), Agents.jl (Julia), acclimate (C++); ~30 days; risk: HIGH — parameter sensitivity high; results differ across replications; difficult
- **4. Graph Neural Network (GNN / TGNN)** — PyTorch Geometric, DGL, torch-temporal; ~21 days; risk: Medium — requires GPU + labelled crisis data; risk of overfitting on small N
- **7. Temporal Graph Model (TGN / TGAT)** — PyTorch + torch-temporal; TGB benchmark code (TGB 2.0); ~28 days; risk: HIGH — TGAT specifically has known OOM failures on large graphs per docx

**Dependencies:** access to firm-level data (ABM) OR GPU access
(GNN/TGN). Both are non-trivial blockers.
**Expected scientific impact:** establishes whether non-linear /
deep-learning models add value over the linear baselines. If they
don't, that itself is a publishable finding.

## Long-term (months)

Goal: original work beyond the published baselines.

- **Hybrid SEIRS-Bullwhip-Hysteresis** (the GEDS engine) — already
  exists but needs the calibration fix flagged in
  `NEXT_STEPS_VALIDATION.md`. Effort: ~1 month.
- **Multi-shock interaction matrix** — no published method covers
  this; build the first benchmark for pairwise shock interaction
  on the 42-event corpus. Effort: ~2 months.
- **AIS-to-GDP structural shipping propagation** — fills the
  literature gap flagged in `LITERATURE_GAP_ANALYSIS.md`. Requires
  IMF PortWatch GIS ingest. Effort: ~6 months.
- **LLM → ShockSpec real-time pipeline** — GDELT/ACLED events parsed
  by Grok/Claude into engine input. Effort: ~3 months.

**Expected scientific impact:** these are the candidate novelty
claims from `NOVELTY_POSITIONING.md`. Publication-grade results
require completing them after the medium-term baselines.
