# Mathematical Framework

The formalism behind GEDS. Five primitives, then macro transmission, then network metrics, then calibration. Every equation in this doc maps to a function in `backend/app/simulation/` or `ml/models/`.

Notation:

- **i, j ∈ V** — country-sector nodes (a country × sector pair, e.g., `(DEU, automotive)`)
- **k ∈ K** — commodities (HS-coded)
- **t** — discrete time step, units = 1 week
- **w_ij^k(t)** — weight of the directed edge `i → j` for commodity `k` at time `t`, normalized so Σ_j w_ij^k(t) = 1 (i's outbound trade share of commodity k)
- **f_ij^k(t)** — absolute flow on that edge in monetary units
- **s_i(t)** — shock state vector on node `i` at time `t` (one component per commodity)
- **R_i** — resilience modifier of node `i` (scalar in (0, 1])
- **ρ** — propagation decay coefficient (scalar in (0, 1))
- **A_i(t)** — amplification kicker on node `i` at time `t`

---

## 1. The graph

GEDS treats the global economy as a weighted, directed, *commodity-labeled* multigraph:

```
G = (V, E, W, K)
```

Each edge `(i, j, k) ∈ E` carries:

- `f_ij^k` — flow (USD/year, downscaled to USD/week for sim)
- `w_ij^k = f_ij^k / Σ_m f_im^k` — outbound share
- `dist_ij` — shipping distance (km), proxy for time and cost
- `route_ij ⊂ Chokepoints` — the set of chokepoints the route uses
- `tariff_ij^k`, `lead_time_ij^k` — frictions

The graph is bipartite-ish in practice: country-sector nodes link via commodities, sectors couple within a country via input-output coefficients (see §5), and country-country links carry trade. This is one homogeneous formulation rather than three separate graphs.

---

## 2. Weighted graph traversal & propagation

### 2.1 Single-step propagation

A shock `s_j^k(t)` on commodity `k` at node `j` propagates to a downstream importer `i` proportional to dependency:

```
Δs_i^k(t+1)  =  ρ · Σ_j  d_ij^k · s_j^k(t)  -  R_i · s_i^k(t)
```

where the **dependency weight** is the share of `i`'s consumption of `k` that comes from `j`:

```
d_ij^k  =  f_ji^k / Σ_m f_mi^k   ← note: inbound share
```

So a country that imports 80% of its semiconductors from Taiwan has `d` = 0.8 on that edge, and a shock at Taiwan transmits ~80% (× decay × resilience) into its semiconductor shock state next week.

The new state is bounded:

```
s_i^k(t+1)  =  clip(  s_i^k(t) + Δs_i^k(t+1),  0,  1  )
```

(`s = 0` is normal, `s = 1` is total disruption; we work in normalized units.)

### 2.2 Multi-step propagation

Cascading effects come for free from iterating the equation. After T steps, the shock at node `i` is the sum over all paths from origin `o` of length ≤ T:

```
s_i^k(T)  ≈  Σ_paths o→…→i  (Π edges  ρ · d^k)  · s_o^k(0)
```

This is what makes contagion *non-local*: nodes that don't trade directly with the origin still get hit through intermediaries.

### 2.3 Cross-commodity coupling

A shortage in commodity `k` at node `i` raises shock on commodity `k'` to the extent the sectors that produce `k'` *use* `k` as input. With input-output coefficient `a_{k k'}^i` (the share of `k` in `k'`'s production cost in country `i`):

```
Δs_i^{k'}(t+1)  +=  λ · Σ_k  a_{k k'}^i · s_i^k(t)
```

`λ` is a cross-commodity transmission constant calibrated against historical input-output shocks (e.g., chip shortage → automotive output).

---

## 3. Propagation decay

`ρ ∈ (0, 1)` is not a single constant. It depends on edge characteristics:

```
ρ_ij = ρ_0 · exp(-α · lead_time_ij)  ·  (1 - τ_ij)
```

- `ρ_0 ≈ 0.85` — base decay per hop, calibrated on COVID supply shock transmission
- `α` — sensitivity to lead time (longer ⇒ more damping, more inventory buffer)
- `τ_ij` — tariff/friction adjustment (higher friction *increases* damping)

Decay reflects two real-world mechanisms:

1. **Inventory buffer** — downstream nodes hold safety stock; not every shock transmits instantly.
2. **Substitution slack** — even disrupted markets find marginal substitutes.

---

## 4. Resilience modifier

`R_i ∈ (0, 1]` is per-country, per-sector. Composed of four factors:

```
R_i  =  σ( β_0 + β_1 · log GDPpc_i + β_2 · diversification_i + β_3 · stockpile_ratio_i^k - β_4 · concentration_i^k )
```

- **GDPpc** — capacity to absorb shocks (Lucas critique notwithstanding; calibrate, don't theorize)
- **diversification** — number of effective trade partners, measured as `1 / HHI` over import shares of commodity `k`
- **stockpile_ratio** — strategic reserves / annual consumption (oil, food, semiconductors)
- **concentration** — HHI of import partners; high concentration *reduces* resilience

`σ` is the logistic function bounding `R` to `(0, 1)`. Coefficients fit by maximum-likelihood against historical shock-response data (§9).

---

## 5. Adaptive rerouting

When edge `(i, j)` is disrupted (shock on a chokepoint, sanctions, accident), the flow `f_ij^k` must redistribute over alternative paths. Two implementations, swappable:

### 5.1 Analytic — Yen's k-shortest paths

For each disrupted commodity `k` and origin-destination pair `(o, d)`, find the k shortest paths under cost:

```
c(p)  =  Σ edges  ( dist_e + ζ · tariff_e + η · congestion_e )
```

Yen's algorithm gives the top-k paths. Flow is reallocated by softmax over costs:

```
share(p)  =  exp( -c(p) / T )  /  Σ_p'  exp( -c(p') / T )
```

The rerouting *cost* shows up as an inflation pressure on the destination:

```
Δπ_d^k  =  γ_r · ( c(p_new) - c(p_old) ) / c(p_old)
```

where `π` is the price-level deviation for commodity `k` at destination `d`, and `γ_r` is the rerouting-to-inflation pass-through coefficient.

### 5.2 Learned — RL policy

A PPO agent trained against the simulator chooses the rerouting strategy. State = graph embedding + current shock vector + capacity remaining at each chokepoint. Action = a distribution over alternative paths. Reward = -inflation impact - unmet demand. See [`ai-ml-models.md`](./ai-ml-models.md) §4 for the full RL setup.

The learned policy outperforms the analytic one when there are non-obvious second-order effects (a path that seems short locally but congests a chokepoint with downstream consequences).

---

## 6. Nonlinear amplification

Real crises exhibit cliff-edge behavior: nothing happens, nothing happens, then everything happens. We model this with a logistic kicker that activates when shock magnitude crosses a node-specific threshold `θ_i^k`:

```
A_i^k(t)  =  1  +  μ · σ( (s_i^k(t) - θ_i^k) / ε )
```

where `σ` is the logistic function, `μ` is the maximum amplification (typically 2–4×), and `ε` controls the sharpness of the transition.

The amplification multiplies the propagation outflow:

```
effective outflow from i  =  A_i^k(t)  ·  s_i^k(t)
```

Threshold `θ` is typically calibrated to:

- **Stockpile depletion** — when inventories run out, panic-substitution begins
- **Capacity ceiling** — when alternative suppliers hit their own capacity
- **Political tipping** — sanctions, export bans (modeled as discrete events but smoothed by `σ`)

This single mechanism reproduces three observed phenomena: (a) the speed of price spikes once stockpiles deplete, (b) the asymmetry between mild and severe shocks, (c) the difficulty of predicting *when* a crisis goes critical even when you know it will.

---

## 7. Macro transmission

The graph-level shock state translates into macro outcomes via the equations below. All are calibrated, not derived from first principles. They are good enough to be useful and humble enough to be honest.

### 7.1 Inflation

Per country, per consumption basket. CPI deviation in week `t+1`:

```
π_i(t+1)  =  α · π_i(t)  +  Σ_k  ω_i^k · ( γ_1 · s_i^k(t) + γ_2 · Δp_k^world(t) )  +  ε
```

- `α ≈ 0.7` — persistence (inflation is sticky)
- `ω_i^k` — basket weight of commodity `k` in country `i`'s CPI
- `Δp_k^world` — world-price deviation of commodity `k`, derived from supply-demand imbalance
- `γ_1, γ_2` — pass-through coefficients

### 7.2 GDP impact

Output loss per country-sector:

```
ΔGDP_i,sector(t+1)  =  -  Σ_k  ψ_{sector,k} · s_i^k(t)  ·  GDP_i,sector
```

where `ψ_{sector,k}` is the elasticity of that sector's output to commodity `k`'s availability (high for `automotive × semiconductors`, low for `services × wheat`).

Aggregated to country: `ΔGDP_i = Σ_sector ΔGDP_i,sector`.

### 7.3 Sector vulnerability

A static score, recomputed when graph data updates:

```
V_i,sector  =  Σ_k  ψ_{sector,k}  ·  HHI(import_partners_i^k)  ·  ( 1 - R_i )
```

High when the sector depends on a commodity that comes from few sources and the country has low resilience.

### 7.4 Shortage probability

Per country, per commodity, from logistic regression on shock state + inventory + alternative-supplier capacity:

```
P( shortage_i^k | t )  =  σ( η_0 + η_1 · s_i^k(t) + η_2 · stockpile_ratio_i^k + η_3 · alt_capacity_i^k )
```

Fit on labeled shortage events from historical data.

### 7.5 Unemployment risk

```
ΔU_i(t+H)  =  -  φ  ·  ΔGDP_i(t)  /  GDP_i  ·  labor_intensity_i
```

with `φ` calibrated by Okun's law-style relationship for each country (developed economies have lower `φ` than emerging ones).

### 7.6 Recovery trajectory

After a shock subsides, recovery follows a damped path:

```
s_i^k(t+1)  =  (1 - r_i^k) · s_i^k(t)
```

with `r_i^k` the per-node-per-commodity recovery rate, function of resilience and the speed of substitute mobilization. Fit on observed post-shock recovery in historical events.

---

## 8. Network metrics

These don't update at simulation time; they're static features computed when the graph updates.

- **Betweenness centrality** — identifies chokepoint criticality. `BC(c) = Σ_{o,d} σ_{od}(c) / σ_{od}`. High BC chokepoints (Suez, Hormuz, Malacca) are the system's load-bearing edges.
- **PageRank-flavored trade importance** — converged-state importance under the trade weight matrix; identifies trade hubs.
- **k-core decomposition** — locates the densely interconnected core vs. the periphery.
- **Structural holes** — Burt's measure; identifies countries / commodities whose disruption opens unbridgeable gaps.
- **Global fragility index** — a scalar summary defined as the expected GDP loss under a uniform random small shock across the graph. Computed by Monte Carlo:

```
FI(G)  =  E_shock~Uniform[  Σ_i  |ΔGDP_i|  ]
```

A high FI means the system is brittle (small shocks cause big damage); a low FI means it's resilient. Track FI over time to see whether globalization is making the system more or less fragile.

---

## 9. Stochastic component

Every transmission step has a noise term `ε ~ N(0, σ_step)` to reflect the irreducible uncertainty in commodity-market and policy responses. For uncertainty bands on forecasts we run an ensemble of `N` paths (typically `N = 200`) and report quantiles. Variance reduction via antithetic sampling.

For the most likely path (deterministic mode), we set `ε = 0`.

---

## 10. Calibration

Parameters split into three classes:

| Class | Where calibrated | Example |
|---|---|---|
| **Physically grounded** | Data observation, no fitting | `d_ij^k` (dependency weights), `w_ij^k` (flow shares), `route_ij` (chokepoints used) |
| **Calibrated** | Maximum likelihood on historical events | `ρ_0`, `α`, `γ_1`, `γ_2`, `φ`, `θ_i^k`, `μ` |
| **Learned** | Trained ML model | GNN propagation kernel, RL rerouting policy, ensemble forecast heads |

Calibration objective: minimize forecast error on held-out historical crises (COVID 2020 commodity shock, Suez 2021, Ukraine 2022, 2014 oil shock, 2020 semiconductor shortage). Train on N-1 of them, hold out one as the test set; rotate. Metric: weighted MAPE on inflation, GDP delta, and shortage occurrence per country-sector-week.

Calibration is a continuous process. Each new dataset version triggers re-fitting; coefficients are versioned alongside the dataset for reproducibility.

---

## 11. Sanity / well-posedness

Three things we explicitly verify:

1. **Conservation under no-shock.** Running the simulator with `s(0) = 0` keeps `s(t) = 0` for all `t`. Trivial, but catches numerical bugs.
2. **Bounded response.** A bounded shock yields bounded response: `‖s(t)‖_∞ ≤ M` for all `t`, where `M` depends on `ρ`, `R`, and `μ` but not on `t`. This requires the spectral radius of the linearized propagation operator (without amplification) to be < 1. We check this on every graph update; if violated, recalibrate `ρ`.
3. **Convergence of recovery.** With no further shocks, `s(t) → 0` exponentially. Equivalent to `r_i^k > 0` for all `i, k`.

These three properties make the simulator a *contraction mapping* away from the amplification regime — guarantees we can promise our predictions terminate. Once amplification activates, all bets are off, which is exactly the point: that's the crisis.

---

## 12. Limitations (honest)

- **No endogenous policy response.** Real central banks respond. Real governments impose price caps and export bans. We don't model these endogenously; they enter as user-specified scenarios.
- **Calibration is on a small N.** Major crises in the training set: ~5–8. Statistical power is limited. Confidence intervals on coefficient estimates are wide; we report them in the model card.
- **Time aggregation hides intra-week dynamics.** A week is the smallest unit. Same-week panic buying is not modeled.
- **Firm-level heterogeneity is collapsed.** Country-sector aggregates hide firm-level resilience differences. The firm-level layer (planned, year 2+) addresses this.

We are explicit about these. The platform is a *decision support tool*, not an oracle.
