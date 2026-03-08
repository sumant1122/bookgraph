import { Suspense } from "react";
import GraphCanvas from "@/components/graph/GraphCanvas";

export default function GraphPage() {
  return (
    <div className="card">
      <h2 className="page-title">Knowledge Graph</h2>
      <p className="page-subtitle">Search nodes first, load focused subgraphs, and expand context as you explore.</p>
      <Suspense fallback={<p className="muted">Loading graph explorer...</p>}>
        <GraphCanvas />
      </Suspense>
    </div>
  );
}
