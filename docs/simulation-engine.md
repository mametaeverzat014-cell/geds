# Simulation Engine

The shock-propagation engine is the heart of GEDS. It runs in two modes:

- **Synchronous** — small scenario, single shock, ≤2 years horizon, <1s. Used for interactive scenario building.
- **Asynchronous** — multi-shock, long horizon, ensemble runs. Queued via Celery, streamed live to the frontend via WebSocket.

Both modes share one engine. The difference is execution context, not algorithm.

---

## 1. Domain model

```python
# backend/app/simulation/types.py  (illustrative)

@dataclass(frozen=True)
class Shock:
    target_kind: Literal["node", "edge", "chokepoint", "commodity"]
    target: ShockTarget
    kind: Literal["multiplicative", "additive", "capacity_cap"]
    magnitude: float        # in [0, 1]
    start_week: int
    duration_weeks: int
    decay_curve: Literal["step", "linear", "exp"] = "step"

@dataclass(frozen=True)
class Scenario:
    id: UUID
    horizon_weeks: int      # max 520 (10 years)
    shocks: tuple[Shock, ...]
    config: SimulationConfig

@dataclass
class State:
    """Mutable simulation state. One instance per run."""
    week: int
    shock_state: np.ndarray              # shape (n_nodes, n_commodities)
    inflation_dev: np.ndarray            # shape (n_countries,)
    gdp_dev: np.ndarray                  # shape (n_countries,)
    shortage_prob: np.ndarray            # shape (n_countries, n_commodities)
    rerouted_share: np.ndarray           # shape (n_edges,)
    chokepoint_capacity: np.ndarray      # remaining capacity per chokepoint
```

State is a few NumPy arrays. For 250 countries × 5000 HS6 commodities that's 1.25M floats per matrix — ~10MB per slice, fits in cache. We don't need a graph object for the hot loop; we pre-compute the sparse dependency matrix at engine boot.

---

## 2. Graph preprocessing (once per engine start)

```
1. Pull graph snapshot from Neo4j (or warm Postgres mirror).
2. Build sparse CSR dependency matrix D[i, j, k] = inbound share of k at i from j.
   In practice we collapse (i, k) into a single dimension N = n_countries × n_commodities,
   yielding a sparse N×N matrix M where M[(i,k), (j,k)] = d_ij^k.
   Cross-commodity coupling via input-output coefficients adds off-diagonal blocks
   M[(i,k'), (i,k)] = λ · a_{k,k'}^i.
3. Compute per-node resilience vector R from current dependency data.
4. Compute per-edge propagation decay ρ_ij from lead times and tariffs.
5. Compute amplification thresholds θ from stockpile and capacity data.
6. Build chokepoint → flow incidence matrix C for the capacity-cap logic.
7. Pin all these in shared memory (one set per worker process; immutable for the run).
```

A graph snapshot is identified by a `graph_version` string and persisted to disk. Engine startup is dominated by step 1 (Neo4j → CSR); we cache the CSR on disk and reload in <2s for warm starts.

---

## 3. The main loop

```python
def simulate(scenario: Scenario, ctx: EngineContext) -> SimulationRun:
    state = State.zeros(ctx.n_nodes, ctx.n_commodities)
    frames = []

    for t in range(scenario.horizon_weeks):
        state.week = t

        # 1. Apply any shocks that activate this week.
        apply_shocks(state, scenario.shocks, t, ctx)

        # 2. Propagate one step over the graph (NumPy/SciPy sparse matmul).
        state.shock_state = propagate(state.shock_state, ctx)

        # 3. Nonlinear amplification near thresholds.
        state.shock_state *= amplification(state.shock_state, ctx)

        # 4. Adaptive rerouting for disrupted edges.
        state.rerouted_share, reroute_cost = reroute(state, ctx)

        # 5. Update macro state (inflation, GDP, shortage, unemployment).
        update_macro(state, reroute_cost, ctx)

        # 6. Persist frame: stream to Redis (live) and append to bulk write buffer.
        frames.append(snapshot(state))
        ctx.live_publisher.publish(state)

        # 7. Stop early if converged and no shocks pending.
        if converged(state, ctx) and no_future_shocks(scenario, t):
            break

    flush_frames_to_db(frames, ctx)
    return SimulationRun(state=state, frames=frames, run_id=ctx.run_id)
```

Each step is pure NumPy/SciPy sparse operations on dense vectors and sparse matrices. The hot inner loop, on a typical machine, runs ≥10k weeks/sec for the MVP graph size. Ensemble runs parallelize over the `n_paths` axis with batched NumPy: 200 paths × 104 weeks in ~2s.

### 3.1 `apply_shocks`

Materializes shocks into the state arrays. Three flavors:

- **Multiplicative** — `state.shock_state[target] += magnitude · decay_curve(t - start)` where decay_curve maps the elapsed week within the shock window to a [0,1] factor.
- **Additive** — `state.shock_state[target] = clip(state.shock_state[target] + magnitude, 0, 1)`.
- **Capacity cap** — only meaningful for chokepoints; reduces `chokepoint_capacity[id]` to `(1 - magnitude) · original_capacity` for `duration_weeks`.

### 3.2 `propagate`

The core step. Given the sparse matrix `M` (precomputed in §2) and current shock vector `s`:

```
Δs = ρ ⊙ (M @ s) − R ⊙ s
s' = clip(s + Δs, 0, 1)
```

`⊙` is elementwise multiplication. `M @ s` is a single sparse matrix-vector multiply — the dominant cost. The `ρ ⊙` and `R ⊙` are cheap elementwise operations.

This linear operator without amplification is a contraction iff the spectral radius of `(diag(ρ) · M − diag(R))` is less than 1. We verify this at calibration time (see math doc §11). If violated, calibration recalibrates `ρ` downward.

### 3.3 `amplification`

```python
def amplification(s, ctx):
    delta = (s - ctx.thresholds) / ctx.eps
    return 1.0 + ctx.mu * sigmoid(delta)
```

Element-wise. `mu`, `eps`, `thresholds` are precomputed in ctx. This is what gives the engine its cliff-edge behavior — past `theta`, response multiplies superlinearly.

### 3.4 `reroute`

Two implementations, swappable via `ctx.rerouter`:

**Analytic (`KShortestPathsRerouter`):** for each (commodity, disrupted_route) pair, find Yen's top-k alternative paths. Softmax-allocate flow. Compute rerouting cost as the weighted-average path-cost increase.

**Learned (`RLRerouter`):** load a trained PPO policy. Pass `(graph_embedding, current_state, capacity_remaining)` as observation; receive a softmax over the action set (top-k paths). RL outperforms analytic when there are non-obvious second-order effects (a locally cheap path that congests downstream).

Both return `(rerouted_share, reroute_cost_per_node_commodity)`.

For performance, Yen's k-shortest is computed lazily — we only invoke it when an edge actually has shock_state > 0.05 (well below the noise floor) and we cache results by `(source, target, hs, disrupted_set)`.

### 3.5 `update_macro`

Implements equations from math doc §7. One sparse matmul per macro variable. Inflation update needs the previous inflation, so it's stateful (we keep last week in state); GDP update is memoryless modulo the persistence in inflation.

### 3.6 `converged` and stop conditions

```python
def converged(state, ctx, eps=1e-4, k=4):
    """L2-norm of last-k frames < eps."""
    return (state.recent_deltas[-k:] < eps).all()
```

We short-circuit only when (a) all shock windows have ended, and (b) state delta has been below epsilon for k consecutive weeks.

---

## 4. Adaptive rerouting in detail

When chokepoint `c` is disrupted, every flow that used to route through `c` must find an alternative. Three policies are supported:

| Policy | When to use | Where it lives |
|---|---|---|
| `proportional_redistribute` | Default. Reallocate flow to other paths in proportion to their pre-disruption volumes. | `simulation/rerouting/proportional.py` |
| `k_shortest_paths` | More physically accurate. Yen's k-shortest under cost = distance + tariff + congestion. | `simulation/rerouting/yen.py` |
| `rl_policy` | When chokepoint disruption causes cascade congestion. | `simulation/rerouting/rl.py` |

The proportional baseline is the warmup default. K-shortest activates for multi-chokepoint scenarios. RL activates by config or when k-shortest's predicted congestion exceeds a threshold (the analytic policy itself flags when it needs the learned one).

Capacity is enforced. When a path would exceed downstream chokepoint capacity, flow spills to the next path in the softmax. This produces realistic queueing behavior at Hormuz and Malacca during compound shocks.

---

## 5. Nonlinear amplification — calibration

Each amplification term has three calibrated parameters (`μ`, `ε`, `θ`):

- `θ_i^k` is set per-node-per-commodity from two sources: stockpile depletion threshold (`stockpile_ratio = 0.2 ⇒ θ = 0.6` shock fires panic substitution) and capacity-ceiling threshold (`alt_capacity_idx = 0.3 ⇒ θ = 0.7`).
- `μ` is fit globally to ~2.5 from peak-vs-baseline ratios in historical price spikes (1973 oil, 2008 oil/food, 2022 wheat).
- `ε` controls how sharp the transition is; set to 0.05 (about 5% of shock-state range gives a near-step). Higher `ε` gives smoother transitions and more numerical stability; lower `ε` gives sharper cliffs but can oscillate.

Per-commodity overrides for `μ` exist (semiconductors amplify harder than wheat because substitution is harder).

---

## 6. Determinism & reproducibility

- The engine is fully deterministic in `deterministic=True` mode: same scenario + same graph_version + same model versions → same frames.
- In ensemble mode (`n_paths > 1`), each path uses a path-indexed seed derived from `(run_id, path_index)`. Re-running an ensemble reproduces every path.
- Graph snapshot, scenario, and model version are stamped onto every `SimulationRun`. Replay = read those three and re-execute.

---

## 7. Live streaming

After each `update_macro`, the engine publishes a compact frame to Redis:

```
channel: sim:{run_id}
payload: msgpack-encoded { week, top_k_shocks, top_k_inflation, top_k_gdp, frame_hash }
```

`top_k` means we don't publish the full 250×5000 state — only the top-k entities by magnitude, with the full state available on demand via `GET /api/v1/simulations/{run_id}/frames?week={w}`. This keeps the WebSocket bandwidth bounded (~5KB/frame) and lets the frontend lazy-load detail when the user clicks.

Bulk frames are flushed in batches of 8 weeks to TimescaleDB to amortize write cost.

---

## 8. Async / Celery

```python
# backend/app/workers/simulation.py
@celery_app.task(bind=True, time_limit=900, soft_time_limit=600)
def run_simulation(self, scenario_id: str, requested_by: str | None = None):
    scenario = scenario_repo.load(scenario_id)
    run = simulation_run_repo.create(scenario_id=scenario_id, status='running', ...)
    try:
        result = simulate(scenario, EngineContext.for_run(run.id))
        simulation_run_repo.mark_succeeded(run.id, metrics_summary=result.summary)
    except SimulationError as e:
        simulation_run_repo.mark_failed(run.id, error=str(e))
        raise
```

Queue topology:

- `sim_interactive` — high-priority, short tasks (<5s soft limit). Workers tuned for latency.
- `sim_batch` — long ensembles, multi-shock, replays. Lower priority, longer time limit.
- `sim_replay` — historical replay validation. Off-peak.

Auto-scale on queue depth via KEDA / a custom HPA exporter.

---

## 9. Testing strategy

Three layers:

1. **Unit** — every primitive (propagate, amplification, reroute) has tests against tiny hand-built graphs where the closed-form answer is known.
2. **Property** — randomized graphs and shocks. Properties: state stays in [0, 1]; recovery converges; conservation when no shock; spectral radius < 1 on the linearized operator.
3. **Replay** — full historical events as integration tests. Each replay has tolerances on (peak inflation deviation, GDP impact magnitude, recovery time). CI fails if regressions exceed tolerance.

The replay tests are the *real* regression net. Math and code can both be wrong in ways that pass unit tests; replays catch divergence from reality.

---

## 10. Future: GNN-based propagation

The analytic `propagate` is `s' = clip(s + ρ ⊙ M s − R ⊙ s, 0, 1)`. A trained GNN with the same input shape can replace this kernel. Plan:

- Architecture: GraphSAGE-style with edge features (commodity, distance, tariff).
- Training: supervised on simulator-generated (state_t, state_{t+1}) pairs from random scenarios, fine-tuned on real historical week-to-week transitions.
- Calibration check: monotonic improvement in held-out replay tests is the only signal that lets us promote the GNN to default. If it makes replays worse, we don't promote.
- Rollout: behind a config flag (`engine.propagation = "analytic" | "gnn"`); A/B in shadow mode for 2 weeks before flipping default.

The point of the analytic engine is to be debuggable and fast. The point of the GNN swap is to capture nonlinearities the analytic engine misses. We keep the analytic version forever as a fallback and ground-truth comparison.
