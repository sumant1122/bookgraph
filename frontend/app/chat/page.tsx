"use client";

import Link from "next/link";
import { FormEvent, useState, useRef, useEffect } from "react";
import { formatFetchError, resolveApiBaseUrl } from "@/lib/apiBase";

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
  cypher_query?: string | null;
};

const SAMPLE_QUESTIONS = [
  "Find books addressing 'Artificial Intelligence' from multiple fields.",
  "Which authors wrote about both 'Physics' and 'Philosophy'?",
  "Papers that expand on concepts in 'The Selfish Gene'?",
  "Find books with contradictory relationships in the graph.",
];

export default function ChatPage() {
  const apiBase = resolveApiBaseUrl();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [result?.answer, loading]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${apiBase}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, scope: "auto", k: 20 })
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail ?? "Unable to query graph");
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Streaming not supported.");

      const decoder = new TextDecoder();
      let accumulatedAnswer = "";

      setResult({
        answer: "",
        confidence: 1.0,
        citations: [],
        evidence_nodes: [],
        evidence_edges: [],
        context_size: { nodes: 0, edges: 0 },
        mode: "streaming",
        provider: "llm",
      });

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        accumulatedAnswer += decoder.decode(value, { stream: true });
        setResult((prev) => prev ? { ...prev, answer: accumulatedAnswer } : null);
      }
    } catch (err) {
      setError(formatFetchError(err, apiBase, "Unexpected error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      maxWidth: "800px", 
      margin: "0 auto", 
      height: "calc(100vh - 80px)",
      display: "flex",
      flexDirection: "column",
      background: "var(--bg)"
    }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "40px 20px" }}>
        {!result && !loading && (
          <div style={{ textAlign: "center", marginTop: "10vh" }}>
            <h1 style={{ fontSize: "2.5rem", fontWeight: 800, marginBottom: "12px", letterSpacing: "-0.03em" }}>Knowledge Chat</h1>
            <p style={{ color: "var(--text-secondary)", marginBottom: "40px" }}>Discover deep connections across your personal library.</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", maxWidth: "600px", margin: "0 auto" }}>
              {SAMPLE_QUESTIONS.map((q, i) => (
                <button 
                  key={i} 
                  onClick={() => setQuestion(q)}
                  style={{ 
                    padding: "16px", borderRadius: "12px", background: "var(--bg-subtle)", 
                    border: "1px solid var(--border)", textAlign: "left", cursor: "pointer",
                    fontSize: "0.85rem", color: "var(--text)"
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {question && (loading || result) && (
          <div style={{ marginBottom: "32px", display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
            <div style={{ 
              background: "#1a1a1a", color: "#fff", padding: "12px 20px", 
              borderRadius: "20px 20px 4px 20px", maxWidth: "80%", fontWeight: 500 
            }}>
              {question}
            </div>
          </div>
        )}

        {(loading || result) && (
          <div style={{ marginBottom: "40px" }}>
            <div style={{ fontSize: "1.1rem", lineHeight: 1.7, color: "var(--text)", whiteSpace: "pre-wrap" }}>
              {result?.answer || (loading && "Analyzing graph...")}
            </div>
            
            {result?.answer && !loading && (
              <div style={{ marginTop: "32px", borderTop: "1px solid var(--border)", paddingTop: "20px" }}>
                {result.cypher_query && (
                  <details style={{ marginBottom: "16px" }}>
                    <summary style={{ fontSize: "0.7rem", color: "var(--text-muted)", cursor: "pointer", fontWeight: 700, textTransform: "uppercase" }}>Reasoning</summary>
                    <pre style={{ marginTop: "8px", background: "var(--bg-subtle)", padding: "12px", borderRadius: "8px", fontSize: "0.75rem", overflowX: "auto" }}>
                      {result.cypher_query}
                    </pre>
                  </details>
                )}
                {result.evidence_nodes.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                    {result.evidence_nodes.map(n => (
                      <Link key={n.id} href={`/graph?node_id=${n.id}`} className="tag">
                        {n.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Input */}
      <div style={{ padding: "20px", background: "var(--bg)", borderTop: "1px solid var(--border)" }}>
        {error && <div className="alert alert-error mb-4">{error}</div>}
        <form onSubmit={onSubmit} style={{ 
          display: "flex", gap: "12px", background: "var(--bg-subtle)", 
          padding: "8px", borderRadius: "16px", border: "1px solid var(--border-strong)"
        }}>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void onSubmit(e as any); } }}
            placeholder="Ask a question..."
            rows={1}
            style={{ 
              flex: 1, border: "none", background: "transparent", padding: "12px", 
              fontSize: "1rem", outline: "none", resize: "none", minHeight: "44px"
            }}
          />
          <button 
            type="submit" 
            disabled={loading || !question.trim()}
            style={{ 
              padding: "0 24px", borderRadius: "12px", background: "#1a8917", 
              color: "#fff", border: "none", fontWeight: 700, cursor: "pointer",
              opacity: (loading || !question.trim()) ? 0.5 : 1
            }}
          >
            {loading ? "..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}
