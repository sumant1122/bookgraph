"use client";

import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import ReactFlow, { Background, Controls, MiniMap, Node, Edge } from "reactflow";
import "reactflow/dist/style.css";

type GraphPayload = {
  nodes: Array<{
    id: string;
    label: string;
    type: string;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    type: string;
  }>;
};

type GraphSearchPayload = {
  nodes: Array<{
    id: string;
    label: string;
    type: string;
    properties?: Record<string, unknown>;
  }>;
};

type NodeDetailPayload = {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
  degree: number;
  neighbors: Array<{
    id: string;
    label: string;
    type: string;
    relation?: string | null;
  }>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function nodeColor(type: string): string {
  if (type === "book") return "#0e7a6d";
  if (type === "concept") return "#ec6a3c";
  if (type === "author") return "#385e9d";
  return "#8f8f8f";
}

function nodeStyle(type: string, isHighlighted: boolean): Record<string, string> {
  return {
    background: nodeColor(type),
    color: "white",
    border: isHighlighted ? "3px solid #ffd166" : "none",
    boxShadow: isHighlighted ? "0 0 0 2px rgba(255, 209, 102, 0.3)" : "none",
    borderRadius: "10px",
    padding: "6px 10px"
  };
}

export default function GraphCanvas() {
  const searchParams = useSearchParams();
  const insightId = searchParams.get("insight");
  const startNodeId = searchParams.get("node_id");
  const highlightParam = searchParams.get("highlight");

  const [query, setQuery] = useState("");
  const [nodeTypeFilter, setNodeTypeFilter] = useState("all");
  const [searchResults, setSearchResults] = useState<GraphSearchPayload["nodes"]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightNodeIds, setHighlightNodeIds] = useState<Set<string>>(new Set());
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodeDetail, setNodeDetail] = useState<NodeDetailPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    const fromQuery = new Set((highlightParam || "").split(",").filter(Boolean));
    if (fromQuery.size) {
      setHighlightNodeIds(fromQuery);
    }
  }, [highlightParam]);

  useEffect(() => {
    const loadHighlight = async () => {
      if (!insightId) {
        if (!highlightParam) {
          setHighlightNodeIds(new Set());
        }
        return;
      }
      try {
        const response = await fetch(`${API_BASE}/discoveries/${encodeURIComponent(insightId)}`);
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as { node_ids?: string[] };
        const fromInsight = new Set(payload.node_ids || []);
        const fromQuery = new Set((highlightParam || "").split(",").filter(Boolean));
        const nodeIds = new Set([...fromInsight, ...fromQuery]);
        setHighlightNodeIds(nodeIds);
      } catch {
        return;
      }
    };
    void loadHighlight();
  }, [insightId, highlightParam]);

  const applyFocusGraph = (payload: GraphPayload, merge: boolean) => {
    setNodes((current) => {
      const existing = new Map(current.map((node) => [node.id, node]));
      const mapped = (payload.nodes || [])
        .filter((node) => node?.id && node?.label)
        .map((node, index) => {
          const existingNode = existing.get(node.id);
          const isHighlighted = highlightNodeIds.has(node.id);
          if (existingNode) {
            return {
              ...existingNode,
              data: { ...(existingNode.data as Record<string, unknown>), label: node.label, kind: node.type },
              style: nodeStyle(node.type, isHighlighted)
            };
          }
          return {
            id: node.id,
            data: { label: node.label, kind: node.type },
            position: { x: (index % 6) * 220, y: Math.floor(index / 6) * 140 },
            style: nodeStyle(node.type, isHighlighted)
          };
        });
      if (!merge) return mapped;
      const mergedMap = new Map<string, Node>();
      for (const node of current) mergedMap.set(node.id, node);
      for (const node of mapped) mergedMap.set(node.id, node);
      return Array.from(mergedMap.values());
    });

    setEdges((current) => {
      const mapped = (payload.edges || [])
        .filter((edge) => edge?.id)
        .map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.type,
          animated: edge.type === "RELATED_TO"
        }));
      if (!merge) return mapped;
      const mergedMap = new Map<string, Edge>();
      for (const edge of current) mergedMap.set(edge.id, edge);
      for (const edge of mapped) mergedMap.set(edge.id, edge);
      return Array.from(mergedMap.values());
    });
  };

  const loadFocus = async (nodeId: string, depth = 1, merge = false) => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(
        `${API_BASE}/graph/focus?node_id=${encodeURIComponent(nodeId)}&depth=${depth}&limit=140`
      );
      const payload = (await response.json()) as GraphPayload;
      if (!response.ok) {
        throw new Error("Failed to load focused graph.");
      }
      applyFocusGraph(payload, merge);
      setSelectedNodeId(nodeId);
      void loadNodeDetails(nodeId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load focused graph.");
    } finally {
      setLoading(false);
    }
  };

  const loadNodeDetails = async (nodeId: string) => {
    try {
      setDetailLoading(true);
      const response = await fetch(`${API_BASE}/graph/nodes/${encodeURIComponent(nodeId)}`);
      if (!response.ok) {
        setNodeDetail(null);
        return;
      }
      const payload = (await response.json()) as NodeDetailPayload;
      setNodeDetail(payload);
    } finally {
      setDetailLoading(false);
    }
  };

  const runSearch = async (event: FormEvent) => {
    event.preventDefault();
    setSearchLoading(true);
    setError(null);
    try {
      const typeQuery = nodeTypeFilter !== "all" ? `&type=${encodeURIComponent(nodeTypeFilter)}` : "";
      const response = await fetch(`${API_BASE}/graph/search?q=${encodeURIComponent(query)}${typeQuery}&limit=25`);
      const payload = (await response.json()) as GraphSearchPayload;
      if (!response.ok) {
        throw new Error("Search failed.");
      }
      setSearchResults(payload.nodes || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed.");
    } finally {
      setSearchLoading(false);
    }
  };

  useEffect(() => {
    if (!startNodeId) return;
    void loadFocus(startNodeId, 1, false);
  }, [startNodeId]);

  useEffect(() => {
    if (!insightId || startNodeId) return;
    const loadFromInsight = async () => {
      const response = await fetch(`${API_BASE}/discoveries/${encodeURIComponent(insightId)}`);
      if (!response.ok) return;
      const payload = (await response.json()) as { node_ids?: string[] };
      const seed = payload.node_ids?.[0];
      if (seed) {
        void loadFocus(seed, 1, false);
      }
    };
    void loadFromInsight();
  }, [insightId, startNodeId]);

  useEffect(() => {
    setNodes((current) =>
      current.map((node) => ({
        ...node,
        style: nodeStyle(String((node.data as Record<string, unknown>)?.kind || "unknown"), highlightNodeIds.has(node.id))
      }))
    );
  }, [highlightNodeIds]);

  return (
    <div className="graph-explorer">
      <form onSubmit={runSearch} className="card graph-toolbar">
        <div className="row">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search nodes (book, concept, author, field)"
            style={{ flex: 1 }}
          />
          <select value={nodeTypeFilter} onChange={(event) => setNodeTypeFilter(event.target.value)}>
            <option value="all">All types</option>
            <option value="book">Books</option>
            <option value="concept">Concepts</option>
            <option value="author">Authors</option>
            <option value="field">Fields</option>
          </select>
          <button type="submit" disabled={searchLoading}>{searchLoading ? "Searching..." : "Search"}</button>
        </div>
        <div className="row">
          {searchResults.slice(0, 8).map((node) => (
            <button
              key={node.id}
              type="button"
              className="chip-button"
              onClick={() => void loadFocus(node.id, 1, false)}
            >
              {node.label} [{node.type}]
            </button>
          ))}
          {!!nodes.length && (
            <button
              type="button"
              className="chip-button"
              onClick={() => {
                setNodes([]);
                setEdges([]);
                setNodeDetail(null);
                setSelectedNodeId(null);
              }}
            >
              Clear Graph
            </button>
          )}
        </div>
      </form>

      {error && <div className="card">Graph error: {error}</div>}

      <div className="graph-layout">
        <div className="graph-frame">
          {loading && <div className="graph-overlay">Loading focused graph...</div>}
          {!loading && !nodes.length && (
            <div className="graph-overlay">
              Search and select a node to load a focused subgraph.
            </div>
          )}
          {!!nodes.length && (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              fitView
              onNodeClick={(_, node) => {
                setSelectedNodeId(node.id);
                void loadNodeDetails(node.id);
              }}
            >
              <MiniMap />
              <Controls />
              <Background />
            </ReactFlow>
          )}
        </div>

        <aside className="card graph-drawer">
          <h3 className="page-title">Node Details</h3>
          {!selectedNodeId && <p className="muted">Select a node from search results or the graph.</p>}
          {selectedNodeId && detailLoading && <p className="muted">Loading details...</p>}
          {selectedNodeId && !detailLoading && !nodeDetail && <p className="muted">No details found.</p>}
          {nodeDetail && (
            <>
              <p><strong>{nodeDetail.label}</strong> [{nodeDetail.type}]</p>
              <p className="muted">Degree: {nodeDetail.degree}</p>
              <div className="row">
                <button type="button" onClick={() => void loadFocus(nodeDetail.id, 1, true)}>
                  Expand 1 Hop
                </button>
                <button type="button" onClick={() => void loadFocus(nodeDetail.id, 2, true)}>
                  Expand 2 Hops
                </button>
              </div>
              <p className="muted" style={{ marginTop: 10 }}>Neighbors</p>
              <div className="row">
                {nodeDetail.neighbors.slice(0, 12).map((neighbor) => (
                  <button
                    key={`${neighbor.id}-${neighbor.relation || "n"}`}
                    type="button"
                    className="chip-button"
                    onClick={() => void loadFocus(neighbor.id, 1, false)}
                  >
                    {neighbor.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
