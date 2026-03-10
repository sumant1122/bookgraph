"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { resolveApiBaseUrl } from "@/lib/apiBase";

// Dynamic import to avoid SSR issues with ForceGraph
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

type GraphPayload = {
  nodes: Array<{ id: string; label: string; type: string }>;
  edges: Array<{ id: string; source: string; target: string; type: string }>;
};

const TYPE_COLORS: Record<string, string> = {
  book: "#34d9ca",
  concept: "#fb923c",
  author: "#818cf8",
  field: "#c084fc",
};

export default function GlobeCanvas() {
  const apiBase = resolveApiBaseUrl();
  const fgRef = useRef<any>();
  const [graphData, setGraphData] = useState<any>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [hoverNode, setHoverNode] = useState<any>(null);

  const loadGraph = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${apiBase}/graph`);
      const data = (await res.json()) as GraphPayload;
      
      const nodes = data.nodes.map(n => ({
        ...n,
        name: n.label,
        color: TYPE_COLORS[n.type.toLowerCase()] || "#94a3b8"
      }));
      
      const links = data.edges.map(e => ({
        ...e,
        source: e.source,
        target: e.target
      }));

      setGraphData({ nodes, links });
    } catch (err) {
      console.error("Failed to load graph", err);
    } finally {
      setLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  // Adjust zoom and position after data load
  useEffect(() => {
    if (!loading && fgRef.current) {
      fgRef.current.zoomToFit(400, 100);
    }
  }, [loading]);

  return (
    <div style={{ position: "relative", width: "100%", height: "600px", background: "var(--background-alt)", borderRadius: "16px", overflow: "hidden", border: "1px solid var(--border)" }}>
      {loading && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10, background: "rgba(0,0,0,0.2)", backdropFilter: "blur(4px)" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "2rem", marginBottom: "12px", animation: "spin 2s linear infinite" }}>🌌</div>
            <p className="muted">Rendering Knowledge Globe...</p>
          </div>
        </div>
      )}

      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        nodeLabel="name"
        nodeRelSize={6}
        nodeVal={n => (n.id === selectedNode?.id ? 20 : 10)}
        linkColor={() => "rgba(148, 163, 184, 0.2)"}
        linkWidth={1}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.005}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          if (node.x === undefined || node.y === undefined) return;
          const label = node.name;
          const fontSize = 12 / globalScale;
          const size = (node.id === selectedNode?.id ? 8 : 4);
          
          // Draw Core
          ctx.beginPath();
          ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
          ctx.fillStyle = node.id === selectedNode?.id ? "#fff" : node.color;
          ctx.fill();

          // Draw Label if hovered or selected
          if (node.id === hoverNode?.id || node.id === selectedNode?.id || globalScale > 1.5) {
            ctx.font = `${fontSize}px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = "#000000";
            ctx.fillText(label, node.x, node.y + size + 8);
          }
        }}
        onNodeHover={setHoverNode}
        onNodeClick={(node) => setSelectedNode(node)}
        cooldownTicks={100}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />

      <div style={{ position: "absolute", bottom: "20px", right: "20px", pointerEvents: "none" }}>
        <button 
          className="btn btn-secondary btn-sm" 
          style={{ pointerEvents: "auto" }}
          onClick={() => fgRef.current?.zoomToFit(400)}
        >
          🔍 Fit View
        </button>
      </div>

      {selectedNode && (
        <div style={{ 
          position: "absolute", 
          top: "20px", 
          right: "20px", 
          width: "280px", 
          background: "var(--surface-raised)", 
          border: "1px solid var(--border)", 
          borderRadius: "12px", 
          padding: "20px",
          boxShadow: "var(--shadow-lg)",
          zIndex: 20
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
            <div style={{ width: "12px", height: "12px", borderRadius: "50%", background: selectedNode.color }} />
            <h4 style={{ margin: 0, fontSize: "1rem" }}>{selectedNode.name}</h4>
          </div>
          <p className="text-sm muted" style={{ marginBottom: "16px", textTransform: "capitalize" }}>Type: {selectedNode.type}</p>
          <div style={{ display: "flex", gap: "8px" }}>
            <Link href={`/graph?node_id=${selectedNode.id}`} className="btn btn-primary btn-sm" style={{ flex: 1, textAlign: "center" }}>
              Focus Node
            </Link>
            <button className="btn btn-ghost btn-sm" onClick={() => setSelectedNode(null)}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}
