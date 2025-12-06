// src/api/client.ts
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"; // fallback for local dev

export async function apiGet(path: string) {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
}

// Example usage in another file:
// const data = await apiGet("/api/some-route");
