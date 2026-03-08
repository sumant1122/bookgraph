"use client";

import { useEffect, useState } from "react";
import { formatFetchError, resolveApiBaseUrl } from "@/lib/apiBase";

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

export default function InsightsPage() {
  const apiBase = resolveApiBaseUrl();
  const [data, setData] = useState<InsightsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetch(`${apiBase}/insights`);
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail ?? "Failed to load insights.");
        }
        setData(payload as InsightsResponse);
      } catch (err) {
        setError(formatFetchError(err, apiBase, "Failed to load insights."));
      }
    };
    void load();
  }, [apiBase]);

  if (error) {
    return <div className="card">Insights error: {error}</div>;
  }

  if (!data) {
    return <div className="card">Loading insights...</div>;
  }

  const healthScore = data.quality_scores?.overall_score ?? data.narrative.graph_health_score;
  const topCentralBooks = data.central_books.central_books.slice(0, 3);
  const topClusters = data.clusters.clusters.slice(0, 3);
  const topMissing = data.missing_topics.missing_topics.slice(0, 4);
  const topActions = data.recommendations.slice(0, 5);

  return (
    <div className="insights-shell">
      <section className="card insights-hero">
        <div className="insights-hero-head">
          <div>
            <h2 className="page-title">Decision Dashboard</h2>
            <p className="page-subtitle">{data.narrative.summary}</p>
            <p className="muted">{data.time_delta.summary}</p>
          </div>
          <div className="insights-score">
            <span>{healthScore}</span>
            <small>/100</small>
          </div>
        </div>
        <div className="row">
          <span className="chip">Books {data.graph_stats.books}</span>
          <span className="chip">Concepts {data.graph_stats.concepts}</span>
          <span className="chip">Edges {data.graph_stats.book_edges}</span>
          <span className="chip">Freshness {new Date(data.freshness.generated_at).toLocaleString()}</span>
          <span className="chip">
            Confidence {data.freshness.confidence.label} ({(data.freshness.confidence.score * 100).toFixed(0)}%)
          </span>
        </div>
      </section>

      <section className="grid two">
        <article className="card">
          <h3 className="page-title">Key Discoveries</h3>
          <ul className="insights-list">
            <li>
              Central books:{" "}
              {topCentralBooks.map((book) => `${book.title} (${book.score.toFixed(2)})`).join(", ") || "No data yet"}
            </li>
            <li>
              Clusters:{" "}
              {topClusters
                .map((cluster) => `${cluster.communityId}: ${cluster.books.slice(0, 3).join(", ")}`)
                .join(" | ") || "No data yet"}
            </li>
            <li>
              Missing topics:{" "}
              {topMissing.map((topic) => `${topic.field} (${topic.bookCount})`).join(", ") || "No data yet"}
            </li>
          </ul>
        </article>
        <article className="card">
          <h3 className="page-title">Action Queue</h3>
          <ol className="insights-steps">
            {topActions.length ? (
              topActions.map((action, index) => (
                <li key={`${action.type}-${index}`}>
                  <strong>[{action.effort}]</strong> {action.action}
                </li>
              ))
            ) : (
              <li>No actions available yet.</li>
            )}
          </ol>
        </article>
      </section>

      <section className="grid">
        <details className="card insights-detail" open>
          <summary>Coverage and Quality</summary>
          <div className="insights-detail-body">
            <p>
              Top fields: {data.coverage.top_fields.map((field) => `${field.field} (${field.bookCount})`).join(", ") || "N/A"}
            </p>
            <p>
              Top concepts:{" "}
              {data.coverage.top_concepts.map((concept) => `${concept.concept} (${concept.bookCount})`).join(", ") || "N/A"}
            </p>
            <p>Unlinked books: {data.coverage.unlinked_books.map((book) => book.title).join(", ") || "None"}</p>
            <p>Relationship quality: {data.quality_scores.breakdown.relationship_quality}</p>
            <p>Concept coverage: {data.quality_scores.breakdown.concept_coverage}</p>
            <p>Cluster cohesion: {data.quality_scores.breakdown.cluster_cohesion}</p>
            <p>Link completeness: {data.quality_scores.breakdown.link_completeness}</p>
          </div>
        </details>

        <details className="card insights-detail">
          <summary>Reading Paths and Contradictions</summary>
          <div className="insights-detail-body">
            <p>
              Reading paths:{" "}
              {data.reading_paths
                .map((path) => `${path.field}: ${path.path.map((item) => item.title).join(" -> ")}`)
                .join(" | ") || "No generated paths yet."}
            </p>
            <p>
              Overlap links: {data.overlap_contradiction.overlap_count}, contradictions:{" "}
              {data.overlap_contradiction.contradiction_count}
            </p>
            <p>
              Samples:{" "}
              {data.overlap_contradiction.samples
                .slice(0, 5)
                .map((sample) => `${sample.source} ${sample.relation} ${sample.target}`)
                .join(" | ") || "No samples yet."}
            </p>
          </div>
        </details>

        <details className="card insights-detail">
          <summary>Sparse Bridges and Field Dashboards</summary>
          <div className="insights-detail-body">
            <p>
              Sparse bridge zones:{" "}
              {data.sparse_bridges
                .map((bridge) => `${bridge.field_a} <-> ${bridge.field_b}`)
                .join(", ") || "No sparse bridge zones detected."}
            </p>
            <p>
              Dashboards:{" "}
              {data.field_dashboards
                .slice(0, 3)
                .map(
                  (dashboard) =>
                    `${dashboard.field}: books(${dashboard.top_books.map((book) => book.title).join(", ")}), concepts(${dashboard.top_concepts
                      .map((concept) => concept.concept)
                      .join(", ")})`
                )
                .join(" | ") || "No field dashboards yet."}
            </p>
          </div>
        </details>
      </section>
    </div>
  );
}
