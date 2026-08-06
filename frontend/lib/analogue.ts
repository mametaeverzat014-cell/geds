/**
 * Finds the closest REAL historical disruption to the scenario being simulated.
 *
 * The point is to anchor a simulated forecast in something that actually
 * happened. The model's own magnitude output is the axis where it does not beat
 * a naive baseline, so a number it produces should not be the last word on
 * "how bad will this be". A matched historical event answers the same question
 * with a measured, primary-sourced figure instead: when a comparable shock hit
 * a comparable node, output fell by X and recovery took Y weeks.
 *
 * That is a statement of record, not a model claim. It is shown next to the
 * simulation precisely so a reader can see where the model's assertion ends and
 * the evidence begins.
 *
 * Matching is deliberately conservative. The node is the dominant term: a
 * shock to Taiwanese semiconductors is only really comparable to other shocks
 * to Taiwanese semiconductors, and failing that to other semiconductor shocks.
 * Magnitude and duration refine within that, they do not override it. When
 * nothing shares even an industry we return null rather than reaching for a
 * superficially similar event — a bad analogue is worse than none.
 */

import type { HistoricalEvent } from "./api";

export interface Analogue {
  event: HistoricalEvent;
  /** 0..1, higher is closer; see `scoreOf` for the components */
  score: number;
  /** why it matched, for display */
  matchKind: "same_node" | "same_industry";
  magnitudeDelta: number;
  durationDelta: number;
}

interface ShockLike {
  target_node_id: string;
  magnitude: number;
  duration_weeks: number;
}

const industryOf = (nodeId: string): string => nodeId.split(":")[1] ?? "";
const countryOf = (nodeId: string): string => nodeId.split(":")[0] ?? "";

/**
 * Only events that can be compared at all: wired into the graph, with a
 * recorded shock spec, and carrying at least one measured outcome. An event
 * with no observed recovery and no observed output loss has nothing to add.
 */
export function isComparable(e: HistoricalEvent): boolean {
  return (
    e.in_geds_graph &&
    !!e.target_node_geds &&
    e.shock_magnitude_geds !== null &&
    e.duration_weeks_geds !== null &&
    (e.recovery_weeks !== null || e.delta_output_pct !== null)
  );
}

export function findAnalogue(
  events: HistoricalEvent[] | null,
  shocks: ShockLike[],
): Analogue | null {
  if (!events?.length || !shocks.length) return null;

  // score against the largest shock — the one driving the cascade
  const primary = [...shocks].sort((a, b) => b.magnitude - a.magnitude)[0];
  const node = primary.target_node_id;
  const industry = industryOf(node);
  const country = countryOf(node);

  let best: Analogue | null = null;

  for (const e of events) {
    if (!isComparable(e)) continue;
    const eNode = e.target_node_geds as string;
    const sameNode = eNode === node;
    const sameIndustry = industryOf(eNode) === industry && industry !== "";
    if (!sameNode && !sameIndustry) continue;

    const mag = e.shock_magnitude_geds as number;
    const dur = e.duration_weeks_geds as number;
    const magnitudeDelta = Math.abs(mag - primary.magnitude);
    const durationDelta = Math.abs(dur - primary.duration_weeks);

    // structural term dominates; magnitude and duration only refine
    const structural = sameNode ? 1.0 : 0.55;
    const sameCountryBonus = !sameNode && countryOf(eNode) === country ? 0.1 : 0;
    // both similarities decay to 0 at a full-scale mismatch
    const magSim = Math.max(0, 1 - magnitudeDelta / 1.0);
    const durSim = Math.max(0, 1 - durationDelta / 26);

    const score =
      0.6 * structural + 0.1 * sameCountryBonus + 0.2 * magSim + 0.1 * durSim;

    if (!best || score > best.score) {
      best = {
        event: e,
        score,
        matchKind: sameNode ? "same_node" : "same_industry",
        magnitudeDelta,
        durationDelta,
      };
    }
  }

  return best;
}
