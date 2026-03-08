"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Discovery = {
  id: string;
  type: string;
  title: string;
  description: string;
  nodes: string[];
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

      {loading && <p className="muted">Loading discoveries...</p>}
      {error && <p className="muted">Error: {error}</p>}
      {!loading && !error && discoveries.length === 0 && (
        <p className="muted">No discoveries yet. The Graph Explorer agent will generate them automatically.</p>
      )}

      <div className="grid">
        {discoveries.map((item) => (
          <article key={item.id} className="card discovery-card">
            <div className="row">
              <span className="chip">{item.type}</span>
              <span className="muted">{new Date(item.created_at).toLocaleString()}</span>
            </div>
            <h3 className="page-title">{item.title}</h3>
            <p className="page-subtitle">{item.description}</p>
            <p className="muted">Related nodes: {item.nodes.slice(0, 6).join(", ")}</p>
            <div className="row">
              <Link href={`/graph?insight=${encodeURIComponent(item.id)}`}>Open in Graph</Link>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
