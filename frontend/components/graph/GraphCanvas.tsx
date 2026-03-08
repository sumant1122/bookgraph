"use client";

import { useEffect, useState } from "react";
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
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  useEffect(() => {
    const load = async () => {
      const response = await fetch(`${API_BASE}/graph`);
      const payload = (await response.json()) as GraphPayload;
      setNodes(
        payload.nodes.map((node, index) => ({
          id: node.id,
          data: { label: node.label },
          position: { x: (index % 5) * 220, y: Math.floor(index / 5) * 150 },
          style: {
            background: nodeColor(node.type),
            color: "white",
            border: "none",
            borderRadius: "10px",
            padding: "6px 10px"
          }
        }))
      );
      setEdges(
        payload.edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.type,
          animated: edge.type === "RELATED_TO"
        }))
      );
    };
    void load();
  }, []);

  return (
    <div style={{ height: "70vh" }}>
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <MiniMap />
        <Controls />
        <Background />
      </ReactFlow>
    </div>
  );
}

