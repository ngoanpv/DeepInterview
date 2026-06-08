"use client";

import {
  ReactFlow,
  Background,
  Handle,
  Position,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Eyebrow } from "@/components/ui/eyebrow";
import {
  SAMPLE_MASTERY_GRAPH,
  type MasteryGraph,
  type MasteryState,
} from "@/lib/sample-mastery";
import { MASTERY_LABEL, MASTERY_COLORS } from "@/components/prep/status-chip";

/** Data carried by each custom mastery node. */
type MasteryNodeData = {
  label: string;
  state: MasteryState;
};
type MasteryFlowNode = Node<MasteryNodeData, "mastery">;

/**
 * Read-only mastery node, styled with the shared `MASTERY_COLORS` palette so it
 * matches the study-plan chips exactly. Handles are present (so prerequisite
 * edges connect) but rendered nearly invisible to keep the editorial calm.
 */
function MasteryNodeComponent({ data }: NodeProps<MasteryFlowNode>) {
  const c = MASTERY_COLORS[data.state];
  return (
    <div
      className="rounded-[10px] border px-3.5 py-2.5 text-center"
      style={{
        backgroundColor: c.bg,
        borderColor: c.border,
        minWidth: 150,
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ opacity: 0, width: 1, height: 1, border: "none" }}
        isConnectable={false}
      />
      <p className="text-[13px] font-medium" style={{ color: "#17171a" }}>
        {data.label}
      </p>
      <p
        className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.1em]"
        style={{ color: c.fg }}
      >
        {MASTERY_LABEL[data.state]}
      </p>
      <Handle
        type="source"
        position={Position.Right}
        style={{ opacity: 0, width: 1, height: 1, border: "none" }}
        isConnectable={false}
      />
    </div>
  );
}

// Module-level constant — defining nodeTypes inline would remount on every
// render and trip a React Flow warning.
const NODE_TYPES: NodeTypes = { mastery: MasteryNodeComponent };

function toFlow(graph: MasteryGraph): {
  nodes: MasteryFlowNode[];
  edges: Edge[];
} {
  const nodes: MasteryFlowNode[] = graph.nodes.map((n) => ({
    id: n.id,
    type: "mastery",
    position: { x: n.x, y: n.y },
    data: { label: n.label, state: n.state },
    draggable: false,
    selectable: false,
    connectable: false,
  }));

  const edges: Edge[] = graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: "smoothstep",
    style: { stroke: "#d9d4c8", strokeWidth: 1.5 },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: "#c9c3b5",
      width: 16,
      height: 16,
    },
  }));

  return { nodes, edges };
}

/**
 * Read-only prerequisite map over the candidate's competency entities, colored
 * by mastery `state`. Calm, non-interactive (pan/zoom/selection off), fits the
 * editorial look. Fixed-height container — a zero-height parent renders nothing.
 */
export function MasteryGraphView({
  graph = SAMPLE_MASTERY_GRAPH,
}: {
  graph?: MasteryGraph;
}) {
  const { nodes, edges } = toFlow(graph);

  return (
    <section aria-labelledby="mastery-heading">
      <header className="mb-4">
        <Eyebrow>Knowledge map</Eyebrow>
        <h2 id="mastery-heading" className="mt-2 font-serif text-2xl text-ink">
          Mastery graph
        </h2>
        <p className="mt-1 text-[14px] leading-relaxed text-muted">
          Competencies and their prerequisites, colored by where you stand.
        </p>
      </header>

      <div
        className="h-[420px] w-full overflow-hidden rounded-card border border-line bg-panel"
        role="img"
        aria-label="Prerequisite graph of competencies colored by mastery state"
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          preventScrolling={false}
          minZoom={0.4}
          maxZoom={1.2}
        >
          <Background color="#e7e3da" gap={22} size={1.2} />
        </ReactFlow>
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap gap-3">
        {(Object.keys(MASTERY_LABEL) as MasteryState[]).map((s) => {
          const c = MASTERY_COLORS[s];
          return (
            <span
              key={s}
              className="inline-flex items-center gap-1.5 text-[12px] text-muted"
            >
              <span
                className="h-2.5 w-2.5 rounded-full border"
                style={{ backgroundColor: c.bg, borderColor: c.fg }}
                aria-hidden
              />
              {MASTERY_LABEL[s]}
            </span>
          );
        })}
      </div>
    </section>
  );
}
