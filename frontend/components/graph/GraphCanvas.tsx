"use client";

import { useEffect, useState } from "react";
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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function nodeColor(type: string): string {
  if (type === "book") return "#0e7a6d";
  if (type === "concept") return "#ec6a3c";
  if (type === "author") return "#385e9d";
  return "#8f8f8f";
}

export default function GraphCanvas() {
  const searchParams = useSearchParams();
  const insightId = searchParams.get("insight");
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [highlightLabels, setHighlightLabels] = useState<Set<string>>(new Set());

  useEffect(() => {
    const loadHighlight = async () => {
      if (!insightId) {
        setHighlightLabels(new Set());
        return;
      }
      try {
        const response = await fetch(`${API_BASE}/discoveries/${encodeURIComponent(insightId)}`);
        if (!response.ok) {
          setHighlightLabels(new Set());
          return;
        }
        const payload = (await response.json()) as { nodes?: string[] };
        const labels = new Set((payload.nodes || []).map((item) => item.toLowerCase()));
        setHighlightLabels(labels);
      } catch {
        setHighlightLabels(new Set());
      }
    };
    void loadHighlight();
  }, [insightId]);

  useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        const response = await fetch(`${API_BASE}/graph`);
        const payload = (await response.json()) as GraphPayload;
        if (!response.ok) {
          throw new Error("Failed to fetch graph.");
        }
        const safeNodes = (payload.nodes || [])
          .filter((node) => node?.id && node?.label)
          .map((node, index) => {
            const isHighlighted = highlightLabels.has(String(node.label).toLowerCase());
            return {
              id: node.id,
              data: { label: node.label },
              position: { x: (index % 6) * 220, y: Math.floor(index / 6) * 140 },
              style: {
                background: nodeColor(node.type),
                color: "white",
                border: isHighlighted ? "3px solid #ffd166" : "none",
                boxShadow: isHighlighted ? "0 0 0 2px rgba(255, 209, 102, 0.3)" : "none",
                borderRadius: "10px",
                padding: "6px 10px"
              }
            };
          });
        const nodeIds = new Set(safeNodes.map((n) => n.id));
        const safeEdges = (payload.edges || [])
          .filter((edge) => edge?.id && nodeIds.has(edge.source) && nodeIds.has(edge.target))
          .map((edge) => ({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.type,
            animated: edge.type === "RELATED_TO"
          }));
        setNodes(safeNodes);
        setEdges(safeEdges);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load graph.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [highlightLabels]);

  if (loading) {
    return <div className="graph-frame" style={{ display: "grid", placeItems: "center" }}>Loading graph...</div>;
  }

  if (error) {
    return <div className="graph-frame" style={{ display: "grid", placeItems: "center" }}>Graph error: {error}</div>;
  }

  if (!nodes.length) {
    return <div className="graph-frame" style={{ display: "grid", placeItems: "center" }}>No graph data yet.</div>;
  }

  return (
    <div className="graph-frame">
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <MiniMap />
        <Controls />
        <Background />
      </ReactFlow>
    </div>
  );
}
