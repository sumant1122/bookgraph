"use client";

import { useEffect, useState } from "react";

type InsightsResponse = {
  central_books: {
    summary: string;
    central_books: Array<{ title: string; score: number }>;
    evidence?: { nodes: Array<{ label: string }>; edges: Array<{ type: string }> };
  };
  clusters: {
    cluster_count: number;
    clusters: Array<{ communityId: string; books: string[] }>;
    evidence?: { nodes: Array<{ label: string }>; edges: Array<{ type: string }> };
  };
  missing_topics: {
    summary: string;
    missing_topics: Array<{ field: string; bookCount: number }>;
    evidence?: { nodes: Array<{ label: string }>; edges: Array<{ type: string }> };
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
  recommendations: Array<{ action: string; effort: string; type: string }>;
  narrative: {
    summary: string;
    key_findings: string[];
    recommended_actions: string[];
    graph_health_score: number;
  };
  time_delta: {
    has_previous: boolean;
    summary: string;
    previous_snapshot_at?: string | null;
  };
  quality_scores: {
    overall_score: number;
    breakdown: {
      relationship_quality: number;
      concept_coverage: number;
      cluster_cohesion: number;
      link_completeness: number;
    };
  };
  reading_paths: Array<{
    field: string;
    path: Array<{ title: string; publish_year?: number | null; score: number }>;
  }>;
  overlap_contradiction: {
    overlap_count: number;
    contradiction_count: number;
    samples: Array<{ source: string; relation: string; target: string }>;
  };
  sparse_bridges: Array<{ field_a: string; field_b: string; books_a: number; books_b: number }>;
  field_dashboards: Array<{
    field: string;
    book_count: number;
    top_books: Array<{ title: string }>;
    top_concepts: Array<{ concept: string }>;
    isolated_books: Array<{ title: string }>;
    unanswered_questions: string[];
  }>;
  freshness: {
    generated_at: string;
    confidence: { score: number; label: string };
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
        <p style={{ fontSize: 28, margin: "6px 0" }}>
          {data.quality_scores?.overall_score ?? data.narrative.graph_health_score}/100
        </p>
        <p>{data.graph_stats.summary}</p>
        <p>
          <strong>Freshness:</strong> {new Date(data.freshness.generated_at).toLocaleString()}
        </p>
        <p>
          <strong>Confidence:</strong> {data.freshness.confidence.label} (
          {(data.freshness.confidence.score * 100).toFixed(0)}%)
        </p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>LLM Summary</h3>
        <p>{data.narrative.summary}</p>
        <p>{data.time_delta.summary}</p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Central Books</h3>
        <p>{data.central_books.summary}</p>
        <p>
          {data.central_books.central_books
            .map((b) => `${b.title} (${b.score.toFixed(2)})`)
            .join(", ") || "No centrality data yet."}
        </p>
        <p>
          <strong>Evidence:</strong>{" "}
          {data.central_books.evidence?.nodes?.map((n) => n.label).join(", ") || "No evidence"}
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
        <p>
          <strong>Unlinked books:</strong>{" "}
          {data.coverage.unlinked_books.map((b) => b.title).join(", ") || "None"}
        </p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Recommendations</h3>
        <p>
          {data.recommendations
            .map((rec) => `[${rec.effort}] ${rec.action}`)
            .join(" ") || "No recommendations yet."}
        </p>
        <p>{data.narrative.recommended_actions?.join(" ")}</p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Quality Breakdown</h3>
        <p>Relationship quality: {data.quality_scores.breakdown.relationship_quality}</p>
        <p>Concept coverage: {data.quality_scores.breakdown.concept_coverage}</p>
        <p>Cluster cohesion: {data.quality_scores.breakdown.cluster_cohesion}</p>
        <p>Link completeness: {data.quality_scores.breakdown.link_completeness}</p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Reading Paths</h3>
        <p>
          {data.reading_paths
            .map((path) => `${path.field}: ${path.path.map((item) => item.title).join(" -> ")}`)
            .join(" | ") || "No reading paths yet."}
        </p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Overlap vs Contradictions</h3>
        <p>
          Overlap links: {data.overlap_contradiction.overlap_count}, Contradictions:{" "}
          {data.overlap_contradiction.contradiction_count}
        </p>
        <p>
          {data.overlap_contradiction.samples
            .slice(0, 4)
            .map((s) => `${s.source} ${s.relation} ${s.target}`)
            .join(" | ") || "No relationship samples yet."}
        </p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Sparse Bridges</h3>
        <p>
          {data.sparse_bridges
            .map((b) => `${b.field_a} <-> ${b.field_b}`)
            .join(", ") || "No sparse bridge zones detected."}
        </p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Field Dashboards</h3>
        <p>
          {data.field_dashboards
            .slice(0, 3)
            .map(
              (d) =>
                `${d.field}: books(${d.top_books.map((b) => b.title).join(", ")}), concepts(${d.top_concepts
                  .map((c) => c.concept)
                  .join(", ")})`
            )
            .join(" | ") || "No field dashboards yet."}
        </p>
      </div>
    </div>
  );
}
