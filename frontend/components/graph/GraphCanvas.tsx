"use client";

import { FormEvent, useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeProps,
  Handle,
  Position,
  NodeChange,
  applyNodeChanges,
} from "reactflow";
import "reactflow/dist/style.css";
import { formatFetchError, resolveApiBaseUrl } from "@/lib/apiBase";

/* ─── Types ───────────────────────────────────────────────────────────── */

type GraphPayload = {
  nodes: Array<{ id: string; label: string; type: string }>;
  edges: Array<{ id: string; source: string; target: string; type: string }>;
};

type GraphSearchPayload = {
  nodes: Array<{ id: string; label: string; type: string; properties?: Record<string, unknown> }>;
};

type NodeDetailPayload = {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
  degree: number;
  neighbors: Array<{ id: string; label: string; type: string; relation?: string | null }>;
};

/* ─── Design tokens per node type ─────────────────────────────────────── */

const TYPE_CONFIG: Record<string, {
  icon: string;
  color: string;
  glow: string;
  ring: string;
  bg: string;
  size: number;
}> = {
  book: {
    icon: "📚",
    color: "#34d9ca",
    glow: "rgba(52, 217, 202, 0.6)",
    ring: "rgba(52, 217, 202, 0.8)",
    bg: "var(--surface)",
    size: 14,
  },
  concept: {
    icon: "💡",
    color: "#fb923c",
    glow: "rgba(251, 146, 60, 0.6)",
    ring: "rgba(251, 146, 60, 0.8)",
    bg: "var(--surface)",
    size: 10,
  },
  author: {
    icon: "✍️",
    color: "#818cf8",
    glow: "rgba(129, 140, 248, 0.6)",
    ring: "rgba(129, 140, 248, 0.8)",
    bg: "var(--surface)",
    size: 10,
  },
  field: {
    icon: "🏷️",
    color: "#c084fc",
    glow: "rgba(192, 132, 252, 0.6)",
    ring: "rgba(192, 132, 252, 0.8)",
    bg: "var(--surface)",
    size: 12,
  },
};

const DEFAULT_CONFIG = {
  icon: "🔹",
  color: "#94a3b8",
  glow: "rgba(148, 163, 184, 0.4)",
  ring: "rgba(148, 163, 184, 0.6)",
  bg: "var(--surface)",
  size: 10,
};

function getConfig(type: string) {
  return TYPE_CONFIG[type] ?? DEFAULT_CONFIG;
}

/* ─── Edge styling per relationship ───────────────────────────────────── */

const EDGE_COLORS: Record<string, string> = {
  RELATED_TO: "#38bdf8",
  INFLUENCED_BY: "#fb7185",
  CONTRADICTS: "#f97316",
  EXPANDS: "#4ade80",
  BELONGS_TO: "#a78bfa",
  WRITTEN_BY: "#94a3b8",
  MENTIONS: "#fbbf24",
};

function edgeStyle(type: string, isSelected: boolean) {
  const color = EDGE_COLORS[type] ?? "var(--border-strong)";
  return {
    stroke: color,
    strokeWidth: isSelected ? 3 : 1.2,
    opacity: isSelected ? 1 : 0.4,
    transition: "stroke-width 0.2s, opacity 0.2s",
  };
}

/* ─── Globe Layout (Force-Directed Simulation Heuristic) ──────────────── */

function globeLayout(
  nodes: Array<{ id: string; label: string; type: string }>,
  edges: Array<{ source: string; target: string }>
): Record<string, { x: number; y: number }> {
  const positions: Record<string, { x: number; y: number }> = {};
  if (!nodes.length) return positions;

  // Basic circular dispersion based on degree
  const degrees: Record<string, number> = {};
  nodes.forEach(n => degrees[n.id] = 0);
  edges.forEach(e => {
    if (degrees[e.source] !== undefined) degrees[e.source]++;
    if (degrees[e.target] !== undefined) degrees[e.target]++;
  });

  const sorted = [...nodes].sort((a, b) => degrees[b.id] - degrees[a.id]);
  const centerId = sorted[0].id;
  
  // High degree nodes in center, others in rings
  positions[centerId] = { x: 0, y: 0 };
  
  const others = sorted.slice(1);
  const totalRings = Math.ceil(Math.sqrt(others.length / 4));
  let nodesPlaced = 0;

  for (let r = 1; r <= totalRings; r++) {
    const ringRadius = r * 140;
    const ringCapacity = r * 8;
    const ringNodes = others.slice(nodesPlaced, nodesPlaced + ringCapacity);
    
    ringNodes.forEach((node, i) => {
      const angle = (i / ringNodes.length) * 2 * Math.PI;
      // Add a bit of jitter for a more organic 'cloud' look
      const jitter = (Math.random() - 0.5) * 40;
      positions[node.id] = {
        x: Math.cos(angle) * ringRadius + jitter,
        y: Math.sin(angle) * ringRadius + jitter,
      };
    });
    nodesPlaced += ringNodes.length;
  }

  return positions;
}

/* ─── Custom Node Component (Glowing Dot) ───────────────────────────── */

function KnowledgeNode({ data }: NodeProps) {
  const cfg = getConfig(String(data.kind ?? ""));
  const selected = Boolean(data.selected);
  const highlighted = Boolean(data.highlighted);

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div
        style={{
          width: `${cfg.size * (selected ? 1.8 : highlighted ? 1.4 : 1)}px`,
          height: `${cfg.size * (selected ? 1.8 : highlighted ? 1.4 : 1)}px`,
          borderRadius: "50%",
          background: selected ? "#fff" : cfg.color,
          boxShadow: `0 0 ${selected ? 25 : highlighted ? 15 : 8}px ${cfg.glow}`,
          border: selected ? `3px solid ${cfg.color}` : "none",
          transition: "all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)",
          cursor: "pointer",
          position: "relative"
        }}
      >
        {(selected || highlighted) && (
          <div style={{
            position: "absolute",
            top: "120%",
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(15, 23, 42, 0.85)",
            backdropFilter: "blur(4px)",
            padding: "4px 10px",
            borderRadius: "6px",
            color: "#fff",
            fontSize: "11px",
            fontWeight: 600,
            whiteSpace: "nowrap",
            border: `1px solid ${cfg.color}40`,
            zIndex: 10
          }}>
            {String(data.label ?? "")}
          </div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </>
  );
}

const nodeTypes = { knowledge: KnowledgeNode };

/* ─── Helpers ─────────────────────────────────────────────────────────── */

function buildNodes(
  raw: GraphPayload["nodes"],
  rawEdges: GraphPayload["edges"],
  highlightIds: Set<string>,
  selectedId: string | null,
  existingPositions: Record<string, { x: number; y: number }>
): Node[] {
  const positions = globeLayout(raw, rawEdges);
  return raw
    .filter((n) => n?.id && n?.label)
    .map((n) => ({
      id: n.id,
      type: "knowledge",
      position: existingPositions[n.id] ?? positions[n.id] ?? { x: 0, y: 0 },
      data: {
        label: n.label,
        kind: n.type,
        highlighted: highlightIds.has(n.id),
        selected: n.id === selectedId,
      },
      draggable: true,
    }));
}

function buildEdges(raw: GraphPayload["edges"], selectedNodeId: string | null): Edge[] {
  return raw
    .filter((e) => e?.id)
    .map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: "", // Remove labels for the globe view to reduce clutter
      type: "straight", // Use straight lines for a cleaner constellation look
      style: edgeStyle(e.type, e.source === selectedNodeId || e.target === selectedNodeId),
    }));
}

/* ─── Main Component ──────────────────────────────────────────────────── */

export default function GraphCanvas() {
  const searchParams = useSearchParams();
  const insightId = searchParams.get("insight");
  const startNodeId = searchParams.get("node_id");
  const highlightParam = searchParams.get("highlight");
  const apiBase = resolveApiBaseUrl();

  const [query, setQuery] = useState("");
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightNodeIds, setHighlightNodeIds] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodeDetail, setNodeDetail] = useState<NodeDetailPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [rawNodes, setRawNodes] = useState<GraphPayload["nodes"]>([]);
  const [rawEdges, setRawEdges] = useState<GraphPayload["edges"]>([]);

  // Track dragged positions so they survive re-renders
  const [userPositions, setUserPositions] = useState<Record<string, { x: number; y: number }>>({});

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
    changes.forEach((c) => {
      if (c.type === "position" && c.position) {
        setUserPositions((prev) => ({ ...prev, [c.id]: c.position! }));
      }
    });
  }, []);

  const loadFullGraph = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${apiBase}/graph`);
      const payload = (await res.json()) as GraphPayload;
      if (!res.ok) throw new Error("Failed to load graph.");
      
      setRawNodes(payload.nodes);
      setRawEdges(payload.edges);
      
      const builtNodes = buildNodes(payload.nodes, payload.edges, highlightNodeIds, selectedNodeId, userPositions);
      const builtEdges = buildEdges(payload.edges, selectedNodeId);
      
      setNodes(builtNodes);
      setEdges(builtEdges);
    } catch (err) {
      setError(formatFetchError(err, apiBase, "Failed to load globe."));
    } finally {
      setLoading(false);
    }
  }, [apiBase, highlightNodeIds, selectedNodeId, userPositions]);

  useEffect(() => {
    void loadFullGraph();
  }, []); // Run once on mount

  const applyGraph = useCallback(
    (payload: GraphPayload, merge: boolean) => {
      const allRawNodes = merge
        ? [...rawNodes.filter((n) => !payload.nodes.find((p) => p.id === n.id)), ...payload.nodes]
        : payload.nodes;
      
      const allRawEdges = merge
        ? [...rawEdges.filter((e) => !payload.edges.find((p) => p.id === e.id)), ...payload.edges]
        : payload.edges;

      setRawNodes(allRawNodes);
      setRawEdges(allRawEdges);

      const builtNodes = buildNodes(allRawNodes, allRawEdges, highlightNodeIds, selectedNodeId, userPositions);
      const builtEdges = buildEdges(allRawEdges, selectedNodeId);

      setNodes(builtNodes);
      setEdges(builtEdges);
    },
    [rawNodes, rawEdges, highlightNodeIds, selectedNodeId, userPositions]
  );

  const loadNodeDetails = async (nodeId: string) => {
    try {
      setDetailLoading(true);
      const res = await fetch(`${apiBase}/graph/nodes/${encodeURIComponent(nodeId)}`);
      if (!res.ok) { setNodeDetail(null); return; }
      setNodeDetail((await res.json()) as NodeDetailPayload);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleDeleteNode = async (nodeId: string) => {
    if (!window.confirm("Are you sure you want to delete this node? This will remove all its relationships as well.")) {
      return;
    }
    try {
      setLoading(true);
      const res = await fetch(`${apiBase}/graph/nodes/${encodeURIComponent(nodeId)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete node.");
      
      // Update local state: remove node and associated edges
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
      setRawNodes((raw) => raw.filter((n) => n.id !== nodeId));
      setNodeDetail(null);
      setSelectedNodeId(null);
    } catch (err) {
      setError(formatFetchError(err, apiBase, "Failed to delete node."));
    } finally {
      setLoading(false);
    }
  };

  const loadFocus = useCallback(async (nodeId: string, depth = 1, merge = false) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${apiBase}/graph/focus?node_id=${encodeURIComponent(nodeId)}&depth=${depth}&limit=140`);
      const payload = (await res.json()) as GraphPayload;
      if (!res.ok) throw new Error("Failed to load graph.");
      applyGraph(payload, merge, nodeId);
      setSelectedNodeId(nodeId);
      void loadNodeDetails(nodeId);
    } catch (err) {
      setError(formatFetchError(err, apiBase, "Failed to load focused graph."));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, applyGraph]);

  const runSearch = async (e: FormEvent) => {
    e.preventDefault();
    setSearchLoading(true);
    setError(null);
    try {
      const typeQ = nodeTypeFilter !== "all" ? `&type=${encodeURIComponent(nodeTypeFilter)}` : "";
      const res = await fetch(`${apiBase}/graph/search?q=${encodeURIComponent(query)}${typeQ}&limit=25`);
      const payload = (await res.json()) as GraphSearchPayload;
      if (!res.ok) throw new Error("Search failed.");
      setSearchResults(payload.nodes || []);
    } catch (err) {
      setError(formatFetchError(err, apiBase, "Search failed."));
    } finally {
      setSearchLoading(false);
    }
  };

  useEffect(() => {
    if (!startNodeId) return;
    void loadFocus(startNodeId, 1, false);
  }, [apiBase, startNodeId]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!insightId || startNodeId) return;
    const run = async () => {
      const res = await fetch(`${apiBase}/discoveries/${encodeURIComponent(insightId)}`);
      if (!res.ok) return;
      const p = (await res.json()) as { node_ids?: string[] };
      const seed = p.node_ids?.[0];
      if (seed) void loadFocus(seed, 1, false);
    };
    void run();
  }, [apiBase, insightId, startNodeId]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Re-render nodes when highlight set changes
  useEffect(() => {
    setNodes((current) =>
      current.map((n) => ({
        ...n,
        data: {
          ...(n.data as Record<string, unknown>),
          highlighted: highlightNodeIds.has(n.id),
        },
      }))
    );
  }, [highlightNodeIds]);

  // Re-render nodes when selectedNodeId changes (update selected state)
  useEffect(() => {
    setNodes((current) =>
      current.map((n) => ({
        ...n,
        data: { ...(n.data as Record<string, unknown>), selected: n.id === selectedNodeId },
      }))
    );
    setEdges((current) =>
      current.map((e) => ({
        ...e,
        style: edgeStyle(
          String((e as unknown as Record<string, unknown>).relType ?? ""),
          e.source === selectedNodeId || e.target === selectedNodeId
        ),
      }))
    );
  }, [selectedNodeId]);

  const cfg = nodeDetail ? getConfig(nodeDetail.type) : DEFAULT_CONFIG;

  return (
    <div className="graph-explorer">
      {/* ── Toolbar ── */}
      <div className="graph-toolbar" style={{ display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
        <div style={{ display: "flex", gap: "8px" }}>
          <button 
            type="button" 
            className="btn btn-secondary btn-sm"
            onClick={() => void loadFullGraph()}
            disabled={loading}
          >
            🔄 Refresh Globe
          </button>
          {!!nodes.length && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setNodes([]);
                setEdges([]);
                setRawNodes([]);
                setRawEdges([]);
                setUserPositions({});
                setNodeDetail(null);
                setSelectedNodeId(null);
              }}
            >
              🗑️ Clear Canvas
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="error-panel">
          <h3>Error</h3>
          <p>{error}</p>
        </div>
      )}

      <div className="graph-layout">
        {/* ── Canvas ── */}
        <div className="graph-frame" style={{ position: "relative" }}>
          {loading && (
            <div className="graph-overlay">
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: "2.5rem", marginBottom: "12px", animation: "spin 1.2s linear infinite" }}>⚙️</div>
                <p style={{ color: "#94a3b8" }}>Building graph…</p>
              </div>
            </div>
          )}
          {!loading && !nodes.length && (
            <div className="graph-overlay">
              <div style={{ textAlign: "center" }}>
                <div style={{
                  fontSize: "4rem",
                  marginBottom: "16px",
                  filter: "drop-shadow(0 0 24px rgba(52,217,202,0.5))"
                }}>🌐</div>
                <p style={{ fontSize: "1.1rem", color: "#e2e8f0", fontWeight: 600 }}>
                  Search for a node to explore
                </p>
                <p style={{ marginTop: "6px", color: "#64748b", fontSize: "0.9rem" }}>
                  Nodes float freely — drag them anywhere
                </p>
              </div>
            </div>
          )}
          {!!nodes.length && (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              fitView
              fitViewOptions={{ padding: 0.25 }}
              onNodeClick={(_, node) => {
                setSelectedNodeId(node.id);
                void loadNodeDetails(node.id);
              }}
              defaultViewport={{ x: 0, y: 0, zoom: 0.85 }}
              style={{ background: "transparent" }}
              proOptions={{ hideAttribution: true }}
            >
              {/* Subtle dot-matrix background */}
              <Background
                variant={BackgroundVariant.Dots}
                color="rgba(148,163,184,0.12)"
                gap={28}
                size={1.5}
              />
              <Controls
                style={{
                  background: "rgba(30,41,59,0.8)",
                  backdropFilter: "blur(8px)",
                  borderRadius: "12px",
                  border: "1px solid rgba(255,255,255,0.07)",
                  boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
                }}
              />
              <MiniMap
                nodeColor={(node) => getConfig(String((node.data as Record<string, unknown>)?.kind ?? "")).color}
                maskColor="rgba(0,0,0,0.5)"
                style={{
                  background: "rgba(15,23,42,0.8)",
                  backdropFilter: "blur(8px)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: "10px",
                }}
              />
            </ReactFlow>
          )}
        </div>

        {/* ── Node Detail Sidebar ── */}
        <aside className="graph-drawer">
          <h3>Node Details</h3>

          {!selectedNodeId && (
            <div className="graph-empty-center">
              <div className="graph-empty-icon" style={{ fontSize: "2.5rem" }}>👆</div>
              <p className="muted">Select a node to inspect</p>
            </div>
          )}

          {selectedNodeId && detailLoading && (
            <div className="graph-loading-skeleton">
              <div className="skeleton" style={{ width: "60%", height: "20px" }} />
              <div className="skeleton" style={{ width: "40%", height: "16px" }} />
            </div>
          )}

          {selectedNodeId && !detailLoading && !nodeDetail && (
            <p className="muted">No details found.</p>
          )}

          {nodeDetail && (
            <>
              {/* Node header — pill style matching the canvas */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "14px 16px",
                borderRadius: "14px",
                background: cfg.bg,
                border: `1.5px solid ${cfg.ring}`,
                boxShadow: `0 0 20px ${cfg.glow}`,
                marginBottom: "16px",
              }}>
                <span style={{ fontSize: "1.6rem" }}>{cfg.icon}</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "#f1f5f9" }}>
                    {nodeDetail.label}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: cfg.color, marginTop: 2, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    {nodeDetail.type}
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "16px" }}>
                <div className="insights-score">
                  <span className="insights-score-value">{nodeDetail.degree}</span>
                  <span className="insights-score-label">Connections</span>
                </div>
                <div className="insights-score">
                  <span className="insights-score-value">{nodeDetail.neighbors.length}</span>
                  <span className="insights-score-label">Neighbors</span>
                </div>
              </div>

              {/* Actions */}
              <div className="graph-node-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ flex: 1, fontSize: "0.82rem", padding: "9px" }}
                  onClick={() => void loadFocus(nodeDetail.id, 1, true)}
                >
                  🔗 Expand 1 Hop
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ flex: 1, fontSize: "0.82rem", padding: "9px" }}
                  onClick={() => void loadFocus(nodeDetail.id, 2, true)}
                >
                  🌐 Expand 2 Hops
                </button>
              </div>

              {/* Neighbors */}
              {nodeDetail.neighbors.length > 0 && (
                <div style={{ marginBottom: "24px" }}>
                  <h5>Neighbors ({nodeDetail.neighbors.length})</h5>
                  <div className="graph-neighbors-grid">
                    {nodeDetail.neighbors.slice(0, 15).map((nb) => (
                      <button
                        key={`${nb.id}-${nb.relation ?? "n"}`}
                        type="button"
                        className="chip"
                        onClick={() => void loadFocus(nb.id, 1, false)}
                      >
                        {getConfig(nb.type).icon} {nb.label}
                      </button>
                    ))}
                  </div>
                  {nodeDetail.neighbors.length > 15 && (
                    <p className="muted text-sm" style={{ marginTop: "8px" }}>
                      +{nodeDetail.neighbors.length - 15} more
                    </p>
                  )}
                </div>
              )}

              {/* Danger Zone */}
              <div style={{ 
                marginTop: "auto", 
                paddingTop: "20px", 
                borderTop: "1px solid rgba(239, 68, 68, 0.1)" 
              }}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ 
                    width: "100%", 
                    color: "#ef4444", 
                    fontSize: "0.8rem",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "8px",
                    padding: "8px"
                  }}
                  onClick={() => handleDeleteNode(nodeDetail.id)}
                >
                  🗑️ Delete Node from Graph
                </button>
              </div>
            </>
          )}
        </aside>
      </div>

      {/* Legend */}
      {!!nodes.length && (
        <div style={{
          display: "flex",
          gap: "16px",
          flexWrap: "wrap",
          padding: "10px 0 0",
          borderTop: "1px solid rgba(255,255,255,0.06)",
          marginTop: "8px",
        }}>
          {Object.entries(TYPE_CONFIG).map(([type, c]) => (
            <div key={type} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <div style={{
                width: "10px", height: "10px", borderRadius: "50%",
                background: c.color,
                boxShadow: `0 0 6px ${c.color}`,
              }} />
              <span style={{ fontSize: "0.78rem", color: "#94a3b8", textTransform: "capitalize" }}>{type}</span>
            </div>
          ))}
          <div style={{ marginLeft: "auto", fontSize: "0.78rem", color: "#475569" }}>
            drag nodes freely · scroll to zoom · click to inspect
          </div>
        </div>
      )}
    </div>
  );
}
