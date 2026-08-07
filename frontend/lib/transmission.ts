/**
 * Reconstructs WHY each node was hit — the transmission chain back to the shock.
 *
 * The simulation tells you that Germany's car industry loses output in week 6.
 * It does not, on its own, tell you through whom. This module recovers that by
 * combining two things the run already produced:
 *
 *   - the onset week of every node (first week its output loss crosses the
 *     reach threshold), which fixes the causal ORDER, and
 *   - the graph's dependency edges, which fix the possible causal PATHS.
 *
 * For each affected node we pick the supplier that best explains it: among all
 * suppliers it depends on, the one that was already disrupted when this node
 * turned, weighted by how much this node depends on it. Following those parent
 * links back produces a chain that ends at the shocked node.
 *
 * Edge direction matters and is easy to get backwards. In the engine,
 * `D_eff[i, j]` is the sensitivity of i to a shortage of j, built with
 * `i = index[edge.target]`, `j = index[edge.source]`. So **`source` is the
 * supplier and `target` is the customer** — disruption flows source → target.
 *
 * What this is and is not: it is an attribution over the model's own graph,
 * not a claim about the real world. It says "in this model, this is the path
 * that carried the shock", which is exactly the kind of ordering claim the
 * validation supports (recovery/onset ordering), rather than a magnitude claim,
 * which it does not.
 *
 * One thing this deliberately does NOT claim: that the dependency share explains
 * the lag. It is tempting to read "51% dependency, arrived in week 1" as cause
 * and effect, and it was written that way at first. Measured on a Taiwan
 * semiconductor shock across all 16 reached nodes, onset lag correlates with
 * dependency share at only rho -0.45 — statistically indistinguishable from its
 * correlation with vulnerability (-0.53), centrality (-0.46) and inventory depth
 * (-0.44). No single node property drives the timing; it falls out of the whole
 * propagation step. Note especially that inventory depth points the WRONG way
 * (deeper buffers correlate with EARLIER onset, because buffer depth is
 * confounded with how directly a sector connects to semiconductors) — so the
 * intuitive "automotive holds stock, electronics does not" story is false twice
 * over: electronics carries 7 weeks of inventory in this graph and automotive
 * only 5. The UI copy states the two facts side by side without joining them
 * causally.
 */

import type { Frame, GraphSnapshot } from "./types";

export interface TransmissionLink {
  /** the supplier that best explains this node's disruption */
  from: string;
  to: string;
  /** raw dependency weight of the edge that carried it */
  weight: number;
  /** this node's dependence on that supplier as a share of all its inputs, 0..1 */
  share: number;
  /** how hard the supplier was already hit when this node turned, 0..1 */
  supplierLossAtOnset: number;
  /** weeks between the supplier's onset and this node's */
  lagWeeks: number;
}

export interface Transmission {
  /** onset week per node id */
  onset: Map<string, number>;
  /** best-explaining supplier per node id (absent for the shocked nodes) */
  parent: Map<string, TransmissionLink>;
  /** full chain from a shocked origin down to `id`, origin first */
  chainFor: (id: string) => string[];
}

const MAX_CHAIN = 8; // guard against pathological graphs; real chains are 2–4 long

export function buildTransmission(
  graph: GraphSnapshot | null,
  frames: Frame[],
  originIds: string[],
  reachedThreshold: number,
): Transmission | null {
  if (!graph || !frames.length) return null;

  // ── onset week per node, and a (week → id → loss) lookup ──
  const onset = new Map<string, number>();
  const lossByWeek = new Map<number, Map<string, number>>();
  for (const f of frames) {
    const row = new Map<string, number>();
    for (const n of f.nodes) {
      row.set(n.id, n.output_loss);
      if (n.output_loss >= reachedThreshold && !onset.has(n.id)) {
        onset.set(n.id, f.week);
      }
    }
    lossByWeek.set(f.week, row);
  }

  // ── incoming edges per node (its suppliers) + total inbound dependency ──
  const suppliers = new Map<string, { from: string; weight: number }[]>();
  const inboundTotal = new Map<string, number>();
  for (const e of graph.edges) {
    const w = e.dependency_weight;
    if (!(w > 0)) continue;
    const list = suppliers.get(e.target);
    if (list) list.push({ from: e.source, weight: w });
    else suppliers.set(e.target, [{ from: e.source, weight: w }]);
    inboundTotal.set(e.target, (inboundTotal.get(e.target) ?? 0) + w);
  }

  const origins = new Set(originIds);

  // ── pick, for each affected node, the supplier that best explains it ──
  const parent = new Map<string, TransmissionLink>();
  for (const [id, week] of onset) {
    if (origins.has(id)) continue;
    const cands = suppliers.get(id);
    if (!cands?.length) continue;

    const row = lossByWeek.get(week);
    let best: TransmissionLink | null = null;
    let bestScore = 0;

    for (const c of cands) {
      const sOnset = onset.get(c.from);
      // the supplier must already have been disrupted when this node turned
      if (sOnset === undefined || sOnset > week) continue;
      // same-week ties are allowed only from an origin, so chains stay acyclic
      if (sOnset === week && !origins.has(c.from)) continue;

      const supplierLoss = row?.get(c.from) ?? 0;
      const score = c.weight * supplierLoss;
      if (score > bestScore) {
        bestScore = score;
        const total = inboundTotal.get(id) ?? c.weight;
        best = {
          from: c.from,
          to: id,
          weight: c.weight,
          share: total > 0 ? c.weight / total : 0,
          supplierLossAtOnset: supplierLoss,
          lagWeeks: week - sOnset,
        };
      }
    }
    if (best) parent.set(id, best);
  }

  const chainFor = (id: string): string[] => {
    const chain = [id];
    const seen = new Set([id]);
    let cur = id;
    while (chain.length < MAX_CHAIN) {
      const link = parent.get(cur);
      if (!link || seen.has(link.from)) break;
      chain.push(link.from);
      seen.add(link.from);
      cur = link.from;
      if (origins.has(cur)) break;
    }
    return chain.reverse();
  };

  return { onset, parent, chainFor };
}
