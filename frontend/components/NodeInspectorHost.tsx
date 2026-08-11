"use client";

import NodeInspector from "@/components/NodeInspector";
import { useSimStore } from "@/lib/store";

/**
 * Connects the store's `inspectedNodeId` to the presentational NodeInspector.
 *
 * Kept separate so the inspector itself stays a pure prop-driven component that
 * can be dropped into a story, a test, or a second surface without dragging the
 * store along. The map sets the id; this decides when the panel exists.
 */
export default function NodeInspectorHost() {
  const nodeId = useSimStore((s) => s.inspectedNodeId);
  const inspectNode = useSimStore((s) => s.inspectNode);

  return <NodeInspector nodeId={nodeId} onClose={() => inspectNode(null)} />;
}
