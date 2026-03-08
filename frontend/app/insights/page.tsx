"use client";

import { useEffect, useState } from "react";

type InsightsResponse = {
  central_books: {
    summary: string;
    central_books: Array<{ title: string; score: number }>;
  };
  clusters: {
    cluster_count: number;
    clusters: Array<{ communityId: string; books: string[] }>;
  };
  missing_topics: {
    summary: string;
    missing_topics: Array<{ field: string; bookCount: number }>;
  };
  graph_stats: {
    books: number;
    authors: number;
    concepts: number;
    fields: number;
    book_edges: number;
    book_relationship_density: number;
    summary: string;
  };
  coverage: {
    top_fields: Array<{ field: string; bookCount: number }>;
    top_concepts: Array<{ concept: string; bookCount: number }>;
    unlinked_books: Array<{ title: string; publish_year?: number | null }>;
  };
  recommendations: string[];
  narrative: {
    summary: string;
    key_findings: string[];
    recommended_actions: string[];
    graph_health_score: number;
  };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function InsightsPage() {
  const [data, setData] = useState<InsightsResponse | null>(null);

  useEffect(() => {
    const load = async () => {
      const response = await fetch(`${API_BASE}/insights`);
      const payload = (await response.json()) as InsightsResponse;
      setData(payload);
    };
    void load();
  }, []);

  if (!data) {
    return <div className="card">Loading insights...</div>;
  }

  return (
    <div className="grid two">
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Graph Health</h3>
        <p style={{ fontSize: 28, margin: "6px 0" }}>{data.narrative.graph_health_score}/100</p>
        <p>{data.graph_stats.summary}</p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>LLM Summary</h3>
        <p>{data.narrative.summary}</p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Central Books</h3>
        <p>{data.central_books.summary}</p>
        <p>
          {data.central_books.central_books
            .map((b) => `${b.title} (${b.score.toFixed(2)})`)
            .join(", ") || "No centrality data yet."}
        </p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Clusters</h3>
        <p>Detected {data.clusters.cluster_count} groups.</p>
        <p>
          {data.clusters.clusters
            .slice(0, 3)
            .map((cluster) => `${cluster.communityId}: ${cluster.books.slice(0, 3).join(", ")}`)
            .join(" | ") || "No cluster data yet."}
        </p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Missing Topics</h3>
        <p>{data.missing_topics.summary}</p>
        <p>
          {data.missing_topics.missing_topics
            .map((topic) => `${topic.field} (${topic.bookCount})`)
            .join(", ") || "No gaps found."}
        </p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Coverage</h3>
        <p>
          <strong>Top fields:</strong>{" "}
          {data.coverage.top_fields.map((f) => `${f.field} (${f.bookCount})`).join(", ") || "N/A"}
        </p>
        <p>
          <strong>Top concepts:</strong>{" "}
          {data.coverage.top_concepts
            .map((c) => `${c.concept} (${c.bookCount})`)
            .join(", ") || "N/A"}
        </p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Recommendations</h3>
        <p>{data.recommendations.join(" ") || "No recommendations yet."}</p>
        <p>{data.narrative.recommended_actions?.join(" ")}</p>
      </div>
    </div>
  );
}
