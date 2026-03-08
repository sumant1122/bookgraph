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
        <h3 style={{ marginTop: 0 }}>Central Books</h3>
        <p>{data.central_books.summary}</p>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Clusters</h3>
        <p>Detected {data.clusters.cluster_count} groups.</p>
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
    </div>
  );
}

