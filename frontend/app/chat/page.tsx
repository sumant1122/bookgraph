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
  "Find all books that address 'Artificial Intelligence' from at least 2 different fields.",
  "Which authors have written about both 'Physics' and 'Philosophy'?",
  "Are there any papers that expand on concepts introduced in 'The Selfish Gene'?",
  "Find books that have contradictory relationships with other items in the graph.",
];

export default function ChatPage() {
  const apiBase = resolveApiBaseUrl();
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll when result updates
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
      if (!reader) throw new Error("Streaming not supported in this browser.");

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

        const chunk = decoder.decode(value, { stream: true });
        accumulatedAnswer += chunk;

        setResult((prev) => prev ? { ...prev, answer: accumulatedAnswer } : null);
      }
    } catch (err) {
      const message = formatFetchError(err, apiBase, "Unexpected error");
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-container" style={{ 
      maxWidth: "800px", 
      margin: "0 auto", 
      display: "flex", 
      flexDirection: "column", 
      height: "calc(100vh - 100px)",
      position: "relative"
    }}>
      {/* Header */}
      <div className="mb-6" style={{ textAlign: "center" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700, letterSpacing: "-0.02em" }}>Knowledge Chat</h1>
        <p className="text-secondary" style={{ fontSize: "0.9rem" }}>Query your personal knowledge graph in natural language</p>
      </div>

      {/* Message Area */}
      <div className="chat-messages" style={{ 
        flex: 1, 
        overflowY: "auto", 
        padding: "20px 0",
        display: "flex",
        flexDirection: "column",
        gap: "24px"
      }}>
        {!result && !loading && (
          <div style={{ margin: "auto", textAlign: "center", maxWidth: "500px" }}>
            <div style={{ fontSize: "3rem", marginBottom: "20px" }}>🧠</div>
            <h3 style={{ marginBottom: "12px" }}>Ask your library anything</h3>
            <p className="muted mb-8">What would you like to discover today?</p>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              {SAMPLE_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  className="card-hover"
                  onClick={() => setQuestion(q)}
                  style={{ 
                    padding: "16px", 
                    borderRadius: "12px", 
                    background: "var(--background-alt)",
                    border: "1px solid var(--border)",
                    textAlign: "left",
                    fontSize: "0.85rem",
                    cursor: "pointer",
                    color: "var(--text)"
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {(question && (loading || result)) && (
          <div className="message user" style={{ alignSelf: "flex-end", maxWidth: "80%" }}>
            <div style={{ 
              background: "var(--primary)", 
              color: "white", 
              padding: "12px 20px", 
              borderRadius: "20px 20px 4px 20px",
              fontSize: "1rem",
              fontWeight: 500
            }}>
              {question}
            </div>
          </div>
        )}

        {(loading || result) && (
          <div className="message assistant" style={{ alignSelf: "flex-start", maxWidth: "90%", width: "100%" }}>
            <div style={{ 
              background: "var(--background-alt)", 
              padding: "24px", 
              borderRadius: "20px 20px 20px 4px",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-sm)"
            }}>
              {loading && !result?.answer && (
                <div style={{ display: "flex", gap: "4px" }}>
                  <div className="dot-pulse"></div>
                  <div className="dot-pulse" style={{ animationDelay: "0.2s" }}></div>
                  <div className="dot-pulse" style={{ animationDelay: "0.4s" }}></div>
                </div>
              )}
              
              <div style={{ 
                fontSize: "1.05rem", 
                lineHeight: 1.6, 
                color: "var(--text)",
                whiteSpace: "pre-wrap"
              }}>
                {result?.answer}
              </div>

              {result && result.answer && !loading && (
                <div style={{ 
                  marginTop: "24px", 
                  paddingTop: "16px", 
                  borderTop: "1px solid var(--border)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "16px"
                }}>
                  {result.cypher_query && (
                    <details>
                      <summary style={{ cursor: "pointer", fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase", fontWeight: 700 }}>
                        View Reasoning Query
                      </summary>
                      <div style={{ marginTop: "12px", background: "var(--bg)", padding: "12px", borderRadius: "8px" }}>
                        <code style={{ fontSize: "0.8rem", color: "var(--primary-light)" }}>{result.cypher_query}</code>
                      </div>
                    </details>
                  )}

                  {result.evidence_nodes.length > 0 && (
                    <div>
                      <h4 style={{ fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase", marginBottom: "8px" }}>Cited Evidence</h4>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                        {result.evidence_nodes.map(n => (
                          <Link 
                            key={n.id} 
                            href={`/graph?node_id=${n.id}`} 
                            className="chip" 
                            style={{ fontSize: "0.75rem", textDecoration: "none" }}
                          >
                            {n.label}
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Input Area */}
      <div style={{ 
        padding: "20px 0", 
        background: "var(--background)",
        position: "sticky",
        bottom: 0
      }}>
        {error && (
          <div className="error-panel mb-4" style={{ borderRadius: "12px" }}>
            <p>{error}</p>
          </div>
        )}
        <form onSubmit={onSubmit} style={{ position: "relative" }}>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void onSubmit(e as any);
              }
            }}
            placeholder="Ask your library..."
            rows={1}
            style={{ 
              width: "100%", 
              padding: "16px 60px 16px 20px", 
              borderRadius: "24px", 
              background: "var(--surface)", 
              border: "1px solid var(--border-strong)",
              fontSize: "1rem",
              resize: "none",
              maxHeight: "200px",
              boxShadow: "var(--shadow-lg)"
            }}
          />
          <button 
            type="submit" 
            disabled={loading || !question.trim()}
            style={{ 
              position: "absolute", 
              right: "8px", 
              bottom: "8px",
              padding: "0 20px",
              height: "40px",
              borderRadius: "20px",
              background: "var(--primary)",
              color: "white",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "transform 0.2s",
              fontSize: "0.9rem",
              fontWeight: 600
            }}
          >
            {loading ? "⌛" : "Send"}
          </button>
        </form>
        <p className="text-sm muted" style={{ textAlign: "center", marginTop: "12px" }}>
          AI may produce inaccurate information. Verify citations in the graph.
        </p>
      </div>

      <style jsx>{`
        .dot-pulse {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background-color: var(--primary);
          animation: pulse 1.2s infinite ease-in-out;
        }
        @keyframes pulse {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
