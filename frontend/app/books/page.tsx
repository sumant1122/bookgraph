"use client";

import { FormEvent, useState } from "react";

type BookResponse = {
  title: string;
  author: string;
  publish_year?: number | null;
  subjects: string[];
  description: string;
  concepts: string[];
  fields: string[];
  relationships_created: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function BooksPage() {
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BookResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/books`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Failed to ingest book");
      }
      setResult(payload);
      setTitle("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unexpected error";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid">
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Add Book</h2>
        <form onSubmit={onSubmit} style={{ display: "flex", gap: 10 }}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Clean Code"
            style={{ flex: 1 }}
          />
          <button type="submit" disabled={loading}>
            {loading ? "Adding..." : "Add"}
          </button>
        </form>
        {error && <p style={{ color: "#ad1f1f" }}>{error}</p>}
      </div>
      {result && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{result.title}</h3>
          <p>
            <strong>Author:</strong> {result.author}
          </p>
          <p>
            <strong>Publish Year:</strong> {result.publish_year ?? "Unknown"}
          </p>
          <p>
            <strong>Concepts:</strong> {result.concepts.join(", ") || "None"}
          </p>
          <p>
            <strong>Fields:</strong> {result.fields.join(", ") || "None"}
          </p>
          <p>
            <strong>Relationships Created:</strong> {result.relationships_created}
          </p>
        </div>
      )}
    </div>
  );
}

