"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Discovery = {
  id: string;
  type: string;
  title: string;
  description: string;
  node_ids: string[];
  related_nodes: string[];
  created_at: string;
};

type DiscoveriesPayload = {
  discoveries: Discovery[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function DiscoveriesPage() {
  const [discoveries, setDiscoveries] = useState<Discovery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("all");

  useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        const response = await fetch(`${API_BASE}/discoveries`);
        const payload = (await response.json()) as DiscoveriesPayload;
        if (!response.ok) {
          throw new Error("Failed to load discoveries.");
        }
        setDiscoveries(payload.discoveries || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load discoveries.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  return (
    <div className="card">
      <h2 className="page-title">Discoveries</h2>
      <p className="page-subtitle">Autonomous agents analyze your graph and generate research discoveries.</p>

      <div className="row" style={{ marginBottom: 10 }}>
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
          <option value="all">All types</option>
          <option value="cluster">Clusters</option>
          <option value="centrality">Centrality</option>
          <option value="cross_field_concept">Cross-field concepts</option>
        </select>
      </div>

      {loading && <p className="muted">Loading discoveries...</p>}
      {error && <p className="muted">Error: {error}</p>}
      {!loading && !error && discoveries.length === 0 && (
        <p className="muted">No discoveries yet. The Graph Explorer agent will generate them automatically.</p>
      )}

      <div className="grid">
        {discoveries
          .filter((item) => typeFilter === "all" || item.type === typeFilter)
          .map((item) => {
            const createdAt = new Date(item.created_at);
            const ageHours = Math.floor((Date.now() - createdAt.getTime()) / (1000 * 60 * 60));
            const freshnessLabel = ageHours <= 24 ? "fresh" : ageHours <= 24 * 7 ? "recent" : "stale";
            const confidenceLabel =
              item.type === "cluster" ? "high" : item.type === "centrality" ? "medium" : "medium";
            const focusNodeId = item.node_ids[0] || "";
            const graphHref = focusNodeId
              ? {
                  pathname: "/graph",
                  query: {
                    node_id: focusNodeId,
                    highlight: item.node_ids.join(","),
                    insight: item.id,
                  },
                }
              : {
                  pathname: "/graph",
                  query: {
                    insight: item.id,
                  },
                };
            return (
              <article key={item.id} className="card discovery-card">
                <div className="row">
                  <span className="chip">{item.type}</span>
                  <span className="chip">Confidence {confidenceLabel}</span>
                  <span className="chip">Freshness {freshnessLabel}</span>
                  <span className="muted">{new Date(item.created_at).toLocaleString()}</span>
                </div>
                <h3 className="page-title">{item.title}</h3>
                <p className="page-subtitle">{item.description}</p>
                <p className="muted">Related nodes: {item.related_nodes.slice(0, 6).join(", ")}</p>
                <details className="insights-detail">
                  <summary>Context Preview</summary>
                  <div className="insights-detail-body">
                    <p>Node IDs: {item.node_ids.slice(0, 8).join(", ") || "No node IDs"}</p>
                    <p>Related labels: {item.related_nodes.join(", ") || "No labels"}</p>
                  </div>
                </details>
                <div className="row">
                  <Link href={graphHref}>Open in Graph</Link>
                </div>
              </article>
            );
          })}
      </div>
    </div>
  );
}
