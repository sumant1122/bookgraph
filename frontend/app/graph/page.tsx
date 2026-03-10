import { Suspense } from "react";
import GlobeCanvas from "@/components/graph/GlobeCanvas";

export default function GraphPage() {
  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
      <div className="mb-8" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 className="mb-2">Knowledge Globe</h1>
          <p className="text-secondary">A neural-map of your personal library. Click nodes to focus and explore.</p>
        </div>
      </div>
      
      <Suspense fallback={<div className="card" style={{ height: "600px", display: "flex", alignItems: "center", justifyContent: "center" }}>Loading globe...</div>}>
        <GlobeCanvas />
      </Suspense>

      <div style={{ marginTop: "32px" }}>
        <h3 className="text-sm font-bold uppercase tracking-widest text-muted mb-4">Legend</h3>
        <div style={{ display: "flex", gap: "24px", flexWrap: "wrap" }}>
          {[
            { label: "Books", color: "#34d9ca" },
            { label: "Concepts", color: "#fb923c" },
            { label: "Authors", color: "#818cf8" },
            { label: "Fields", color: "#c084fc" },
          ].map(item => (
            <div key={item.label} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: item.color, boxShadow: `0 0 8px ${item.color}` }} />
              <span style={{ fontSize: "0.85rem", fontWeight: 500 }}>{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
