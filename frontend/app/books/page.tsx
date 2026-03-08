"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { formatFetchError, resolveApiBaseUrl } from "@/lib/apiBase";

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

type UiError = {
  title: string;
  detail: string;
  hint?: string;
};

const INGEST_STEPS = [
  "Searching catalog metadata",
  "Extracting concepts and fields",
  "Linking related books",
  "Finalizing graph updates"
];

export default function BooksPage() {
  const apiBase = resolveApiBaseUrl();
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BookResponse | null>(null);
  const [resultAt, setResultAt] = useState<string | null>(null);
  const [error, setError] = useState<UiError | null>(null);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!loading) return;
    setStepIndex(0);
    const id = window.setInterval(() => {
      setStepIndex((current) => Math.min(current + 1, INGEST_STEPS.length - 1));
    }, 900);
    return () => window.clearInterval(id);
  }, [loading]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/books`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title })
      });
      let payload: Record<string, unknown> = {};
      try {
        payload = (await response.json()) as Record<string, unknown>;
      } catch {
        payload = {};
      }
      if (!response.ok) {
        const detail = typeof payload.detail === "string" ? payload.detail : "Failed to ingest book.";
        throw { status: response.status, detail };
      }
      setResult(payload as BookResponse);
      setResultAt(new Date().toISOString());
      setTitle("");
    } catch (err: unknown) {
      const status = typeof err === "object" && err !== null && "status" in err ? Number((err as { status: number }).status) : 0;
      const apiOrRuntimeDetail =
        typeof err === "object" && err !== null && "detail" in err
          ? String((err as { detail: string }).detail)
          : formatFetchError(err, apiBase, "Unexpected error");
      const detail = apiOrRuntimeDetail;

      if (status === 404) {
        setError({
          title: "Book Not Found",
          detail,
          hint: "Try a broader or canonical title (for example, remove subtitles)."
        });
      } else if (status >= 500) {
        setError({
          title: "Backend Error",
          detail,
          hint: "Check backend logs and verify Neo4j + LLM provider connectivity."
        });
      } else {
        setError({
          title: "Request Failed",
          detail,
          hint: `If this is a network error, verify backend is running at ${apiBase}.`
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const progress = Math.round(((stepIndex + 1) / INGEST_STEPS.length) * 100);

  return (
    <div className="grid two">
      <div className="card">
        <h2 className="page-title">Add Book</h2>
        <p className="page-subtitle">Ingest by title and automatically enrich metadata, concepts, fields, and graph relationships.</p>
        <form onSubmit={onSubmit} className="grid">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Clean Code" style={{ flex: 1 }} />
          <div className="row">
            <button type="submit" disabled={loading}>
              {loading ? "Ingesting..." : "Add Book"}
            </button>
          </div>
        </form>

        {loading && (
          <div className="ingest-progress">
            <p className="muted" style={{ margin: 0 }}>
              {INGEST_STEPS[stepIndex]}
            </p>
            <div className="progress-track" aria-hidden>
              <div className="progress-bar" style={{ width: `${progress}%` }} />
            </div>
            <p className="muted" style={{ margin: 0 }}>
              {progress}% complete
            </p>
          </div>
        )}

        {error && (
          <div className="error-panel">
            <h3>{error.title}</h3>
            <p>{error.detail}</p>
            {error.hint && <p className="muted">{error.hint}</p>}
          </div>
        )}
      </div>

      {result && (
        <div className="card book-result-card">
          <h3 className="page-title" style={{ marginBottom: 8 }}>{result.title}</h3>
          <div className="row">
            <span className="chip">{result.author}</span>
            <span className="chip">Year: {result.publish_year ?? "Unknown"}</span>
            <span className="chip">Relationships: {result.relationships_created}</span>
            {resultAt && <span className="chip">Updated {new Date(resultAt).toLocaleTimeString()}</span>}
          </div>

          <p className="muted" style={{ marginTop: 12 }}>
            {result.description || "No description was returned from metadata sources."}
          </p>

          <div className="result-block">
            <h4>Fields</h4>
            <div className="row">
              {result.fields.length ? result.fields.map((field) => <span key={field} className="chip">{field}</span>) : <span className="muted">None detected yet.</span>}
            </div>
          </div>

          <div className="result-block">
            <h4>Concepts</h4>
            <div className="row">
              {result.concepts.length ? result.concepts.map((concept) => <span key={concept} className="chip">{concept}</span>) : <span className="muted">None detected yet.</span>}
            </div>
          </div>

          <div className="result-block">
            <h4>Subjects</h4>
            <div className="row">
              {result.subjects.length ? result.subjects.slice(0, 10).map((subject) => <span key={subject} className="chip">{subject}</span>) : <span className="muted">No subject tags available.</span>}
            </div>
          </div>

          <div className="row" style={{ marginTop: 6 }}>
            <Link href="/graph">Open Graph</Link>
            <Link href="/discoveries">View Discoveries</Link>
            <Link href="/insights">View Insights</Link>
          </div>
        </div>
      )}
    </div>
  );
}
