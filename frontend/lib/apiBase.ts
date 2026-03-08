export function resolveApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

export function formatFetchError(error: unknown, apiBase: string, fallback: string): string {
  if (error instanceof TypeError && error.message.toLowerCase().includes("fetch")) {
    return `${fallback} Cannot reach backend at ${apiBase}.`;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
