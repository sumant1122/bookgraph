"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

type ChatResponse = {
  answer: string;
  confidence: number;
  citations: string[];
  evidence_nodes: Array<{ id: string; label: string; type: string }>;
  evidence_edges: Array<{ id: string; source: string; target: string; type: string }>;
  context_size: { nodes: number; edges: number };
  mode: string;
  provider: string;
  fallback_reason?: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState("auto");
  const [k, setK] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ChatResponse | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, scope, k })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "Unable to query graph");
      }
      setResult(payload);
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
        <h2 className="page-title">Graph Chat</h2>
        <p className="page-subtitle">Ask graph-grounded questions with evidence-backed responses.</p>
        <form onSubmit={onSubmit} className="grid">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="What are the most connected software engineering books in my graph?"
          />
          <div className="row">
            <select value={scope} onChange={(event) => setScope(event.target.value)}>
              <option value="auto">Auto scope</option>
              <option value="book">Books</option>
              <option value="author">Authors</option>
              <option value="concept">Concepts</option>
              <option value="field">Fields</option>
            </select>
            <input
              type="number"
              min={5}
              max={100}
              value={k}
              onChange={(event) => setK(Number(event.target.value))}
              style={{ width: 118 }}
            />
            <button type="submit" disabled={loading}>
              {loading ? "Thinking..." : "Ask"}
            </button>
          </div>
        </form>
        {error && <p style={{ color: "#ad1f1f", marginBottom: 0 }}>{error}</p>}
      </div>

      {result && (
        <div className="grid two">
          <div className="card">
            <h3 className="page-title">Answer</h3>
            <p>{result.answer}</p>
            <div className="row">
              <span className="chip">Confidence {(result.confidence * 100).toFixed(0)}%</span>
              <span className="chip">
                Context {result.context_size.nodes}N/{result.context_size.edges}E
              </span>
              <span className="chip">
                {result.mode} via {result.provider}
              </span>
            </div>
            {result.fallback_reason && (
              <p>
                <strong>Fallback reason:</strong> {result.fallback_reason}
              </p>
            )}
          </div>
          <div className="card">
            <h3 className="page-title">Evidence Nodes</h3>
            <div className="row">
              {result.evidence_nodes.slice(0, 12).map((node) => (
                <Link
                  key={node.id}
                  href={`/graph?node_id=${encodeURIComponent(node.id)}&highlight=${encodeURIComponent(node.id)}`}
                  className="chip"
                >
                  {node.label} [{node.type}]
                </Link>
              ))}
              {!result.evidence_nodes.length && <span className="muted">No evidence nodes returned.</span>}
            </div>
            <p>
              <strong>Citations:</strong> {result.citations.join(", ") || "None"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
