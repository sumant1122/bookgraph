interface SkeletonProps {
  width?: string;
  height?: string;
  borderRadius?: string;
  className?: string;
}

export function Skeleton({ width, height, borderRadius, className }: SkeletonProps) {
  return (
    <div 
      className={`skeleton ${className || ""}`}
      style={{
        width: width || "100%",
        height: height || "16px",
        borderRadius: borderRadius || "8px",
      }}
    />
  );
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px", width: "100%" }}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton 
          key={i}
          width={i === lines - 1 ? "60%" : "100%"}
          height="16px"
        />
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="card" style={{ padding: "24px" }}>
      <Skeleton width="70%" height="24px" className="skeleton-title" />
      <div style={{ marginTop: "16px" }}>
        <SkeletonText lines={3} />
      </div>
      <div style={{ marginTop: "16px", display: "flex", gap: "8px" }}>
        <Skeleton width="80px" height="32px" borderRadius="999px" />
        <Skeleton width="80px" height="32px" borderRadius="999px" />
        <Skeleton width="80px" height="32px" borderRadius="999px" />
      </div>
    </div>
  );
}

export function SkeletonForm() {
  return (
    <div className="card" style={{ padding: "24px" }}>
      <Skeleton width="40%" height="24px" className="skeleton-title" />
      <div style={{ marginTop: "20px" }}>
        <Skeleton width="100%" height="48px" borderRadius="12px" />
      </div>
      <div style={{ marginTop: "12px" }}>
        <Skeleton width="100%" height="120px" borderRadius="12px" />
      </div>
      <div style={{ marginTop: "16px", display: "flex", gap: "12px" }}>
        <Skeleton width="120px" height="48px" borderRadius="12px" />
        <Skeleton width="120px" height="48px" borderRadius="12px" />
      </div>
    </div>
  );
}

export function SkeletonGraph() {
  return (
    <div className="graph-frame">
      <div style={{ 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "center", 
        height: "100%",
        flexDirection: "column",
        gap: "16px"
      }}>
        <Skeleton width="200px" height="200px" borderRadius="50%" />
        <SkeletonText lines={2} />
      </div>
    </div>
  );
}
