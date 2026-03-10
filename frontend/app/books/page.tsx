"use client";

import Link from "next/link";
import { useState, useRef, useEffect, useCallback } from "react";
import { resolveApiBaseUrl } from "@/lib/apiBase";

type IngestionSource = "openlibrary" | "googlebooks" | "arxiv" | "pdf";

export default function BooksPage() {
  const apiBase = resolveApiBaseUrl();
  const [source, setSource] = useState<IngestionSource>("openlibrary");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<any>(null);
  const [step, setStep] = useState(0);
  const [recentItems, setRecentItems] = useState<any[]>([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const steps = ["Analyzing document", "Extracting metadata", "Identifying concepts", "Linking knowledge graph", "Finalizing"];

  const loadRecentItems = useCallback(async () => {
    try {
      setItemsLoading(true);
      const res = await fetch(`${apiBase}/books?limit=10`);
      if (res.ok) setRecentItems(await res.json());
    } catch (err) {
      console.error("Failed to load recent items", err);
    } finally {
      setItemsLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    void loadRecentItems();
  }, [loadRecentItems]);

  const handleIngest = async (e: any) => {
    e.preventDefault();
    if (source !== "pdf" && !title.trim()) return;
    
    setLoading(true);
    setError(null);
    setResult(null);
    setStep(0);
    
    // Progress simulation
    const interval = setInterval(() => {
      setStep(s => Math.min(s + 1, steps.length - 1));
    }, 1200);

    try {
      let endpoint = "/books";
      let method = "POST";
      let body: any = JSON.stringify({ title });
      let headers: any = { "Content-Type": "application/json" };

      if (source === "googlebooks") endpoint = "/google-books";
      if (source === "arxiv") endpoint = "/papers";
      
      if (source === "pdf") {
        endpoint = "/pdf";
        const file = fileInputRef.current?.files?.[0];
        if (!file) throw new Error("Please select a PDF file");
        const formData = new FormData();
        formData.append("file", file);
        body = formData;
        headers = {}; // Let browser set multipart boundary
      }

      const res = await fetch(`${apiBase}${endpoint}`, { method, headers, body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Ingestion failed");
      setResult(data);
      void loadRecentItems();
    } catch (err: any) {
      setError(err.message || "Something went wrong during ingestion");
    } finally {
      clearInterval(interval);
      setLoading(false);
    }
  };

  const handleDeleteItem = async (id: string) => {
    if (!window.confirm("Are you sure you want to remove this item from your graph?")) return;
    try {
      const res = await fetch(`${apiBase}/graph/nodes/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (res.ok) {
        setRecentItems(prev => prev.filter(item => item.id !== id));
        if (result && result.id === id) setResult(null);
      }
    } catch (err) {
      alert("Failed to delete item");
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="mb-2">Knowledge Ingestion</h1>
        <p className="text-secondary">
          Grow your library by adding books, research papers, or local PDF documents.
        </p>
      </div>

      {/* Source Selector */}
      <div style={{ display: "flex", gap: "12px", marginBottom: "20px" }}>
        {[
          { id: "openlibrary", label: "Open Library", icon: "📚" },
          { id: "googlebooks", label: "Google Books", icon: "🔍" },
          { id: "arxiv", label: "arXiv Papers", icon: "📄" },
          { id: "pdf", label: "Local PDF", icon: "📂" },
        ].map((s) => (
          <button
            key={s.id}
            onClick={() => { setSource(s.id as IngestionSource); setResult(null); setError(null); }}
            className={`chip ${source === s.id ? "active" : ""}`}
            style={{ padding: "10px 16px", cursor: "pointer" }}
          >
            {s.icon} {s.label}
          </button>
        ))}
      </div>

      {/* Ingestion Card */}
      <div className="card mb-8">
        <form onSubmit={handleIngest}>
          {source !== "pdf" ? (
            <input
              value={title}
              onChange={(e: any) => setTitle(e.target.value)}
              placeholder={
                source === "arxiv" 
                  ? "Enter paper title or arXiv ID..." 
                  : "Enter book title..."
              }
              className="mb-4"
              style={{ fontSize: "1.1rem", padding: "12px" }}
            />
          ) : (
            <div 
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: "2px dashed var(--border)",
                borderRadius: "12px",
                padding: "32px",
                textAlign: "center",
                cursor: "pointer",
                marginBottom: "20px",
                background: "var(--background-alt)"
              }}
            >
              <input 
                type="file" 
                accept=".pdf" 
                ref={fileInputRef} 
                style={{ display: "none" }} 
                onChange={(e) => setTitle(e.target.files?.[0]?.name || "")}
              />
              <div style={{ fontSize: "2rem", marginBottom: "8px" }}>📤</div>
              <p style={{ fontWeight: 500 }}>{title || "Click to select a PDF file"}</p>
              <p className="text-sm muted">We'll automatically extract metadata and concepts</p>
            </div>
          )}

          <div className="flex gap-3">
            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={loading || (source !== "pdf" && !title.trim()) || (source === "pdf" && !title)}
              style={{ padding: "12px 24px" }}
            >
              {loading ? (
                <>
                  <span style={{ display: "inline-block", animation: "pulse 1s infinite", marginRight: "8px" }}>⚡</span>
                  {steps[step]}...
                </>
              ) : (
                `Ingest ${source === "pdf" ? "Document" : source === "arxiv" ? "Paper" : "Book"}`
              )}
            </button>
            {(result || error) && (
              <button 
                type="button" 
                className="btn btn-ghost"
                onClick={() => { setResult(null); setError(null); setTitle(""); }}
              >
                Reset
              </button>
            )}
          </div>
        </form>

        {loading && (
          <div className="ingest-progress mt-6">
            <div className="progress-bar-track" style={{ height: "6px" }}>
              <div 
                className="progress-bar-fill" 
                style={{ 
                  width: `${((step + 1) / steps.length) * 100}%`,
                  transition: "width 0.4s ease-out" 
                }} 
              />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "10px" }}>
              <p className="text-xs font-medium text-primary-light uppercase tracking-wider">{steps[step]}</p>
              <p className="text-xs muted">{Math.round(((step + 1) / steps.length) * 100)}%</p>
            </div>
          </div>
        )}

        {error && (
          <div className="error-panel mt-4">
            <h4 style={{ color: "#ef4444", marginBottom: "4px" }}>Ingestion Error</h4>
            <p className="text-sm">{error}</p>
          </div>
        )}
      </div>

      {/* Result Card */}
      {result && (
        <div className="card mb-8 animate-fadeIn" style={{ borderLeft: "4px solid var(--primary)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
            <div>
              <h2 className="mb-1">{result.title}</h2>
              <p className="text-secondary font-medium">{result.author} · {result.publish_year || "Unknown Year"}</p>
            </div>
            <span className="chip secondary">SUCCESS</span>
          </div>
          
          {result.description && (
            <p className="text-secondary mb-6" style={{ lineHeight: 1.6, fontSize: "0.95rem" }}>
              {result.description}
            </p>
          )}

          <div className="grid two gap-6">
            {result.fields?.length > 0 && (
              <div>
                <h5 className="text-xs font-bold uppercase tracking-widest text-muted mb-3">Strategic Fields</h5>
                <div className="flex flex-wrap gap-2">
                  {result.fields.map((f: string) => (
                    <span key={f} className="chip">{f}</span>
                  ))}
                </div>
              </div>
            )}

            {result.concepts?.length > 0 && (
              <div>
                <h5 className="text-xs font-bold uppercase tracking-widest text-muted mb-3">Core Concepts</h5>
                <div className="flex flex-wrap gap-2">
                  {result.concepts.map((c: string) => (
                    <span key={c} className="chip secondary">{c}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div style={{ 
            marginTop: "24px", 
            paddingTop: "16px", 
            borderTop: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            gap: "8px"
          }}>
            <span style={{ fontSize: "1.2rem" }}>🔗</span>
            <span className="text-sm font-medium">
              Added <strong className="text-primary-light">{result.relationships_created}</strong> automated connections to existing knowledge.
            </span>
          </div>
        </div>
      )}

      {/* Next Steps */}
      <div className="grid-3 mb-8">
        <Link href="/graph" className="action-card">
          <span className="action-card-type">Step 1</span>
          <span className="action-card-title">Visualize Connections</span>
          <span className="action-card-desc">See how the new item fits into your map</span>
        </Link>
        <Link href="/chat" className="action-card">
          <span className="action-card-type">Step 2</span>
          <span className="action-card-title">Query Intelligence</span>
          <span className="action-card-desc">Ask questions about this book's content</span>
        </Link>
      </div>

      {/* Management Section */}
      <div className="mb-4" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontSize: "1.25rem" }}>Recently Ingested</h2>
        <button className="btn btn-ghost" onClick={loadRecentItems} disabled={itemsLoading}>
          {itemsLoading ? "Updating..." : "🔄 Refresh List"}
        </button>
      </div>

      <div className="card">
        {recentItems.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center" }}>
            <p className="muted">No items in your graph yet.</p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left" }}>
                  <th style={{ padding: "12px", fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Item</th>
                  <th style={{ padding: "12px", fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Author</th>
                  <th style={{ padding: "12px", fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Year</th>
                  <th style={{ padding: "12px", fontSize: "0.75rem", color: "var(--muted)", textTransform: "uppercase" }}>Type</th>
                  <th style={{ padding: "12px", textAlign: "right" }}></th>
                </tr>
              </thead>
              <tbody>
                {recentItems.map((item) => (
                  <tr key={item.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                    <td style={{ padding: "12px", fontWeight: 500 }}>{item.title}</td>
                    <td style={{ padding: "12px", color: "var(--text-secondary)", fontSize: "0.875rem" }}>{item.author}</td>
                    <td style={{ padding: "12px", color: "var(--text-secondary)", fontSize: "0.875rem" }}>{item.publish_year || "—"}</td>
                    <td style={{ padding: "12px" }}>
                      <span className="chip" style={{ fontSize: "0.7rem", padding: "2px 8px" }}>
                        {item.type === "Book" ? "📚 Book" : "📄 Paper"}
                      </span>
                    </td>
                    <td style={{ padding: "12px", textAlign: "right" }}>
                      <button 
                        className="btn btn-ghost" 
                        style={{ color: "#ef4444", padding: "6px" }}
                        onClick={() => handleDeleteItem(item.id)}
                        title="Delete from graph"
                      >
                        🗑️
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
