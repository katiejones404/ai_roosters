// frontend/src/utils/sentiment.ts
export type SentimentLabel = "bullish" | "neutral" | "bearish";

export interface TimeRangeIndicators {
  d30: SentimentLabel;
  d120: SentimentLabel;
  d360: SentimentLabel;
}

export interface StockIndicators {
  ticker: string;
  snapshot_date: string;
  close_price: number | null;
  indicators: TimeRangeIndicators;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}


/** GET /api/sentiment/indicators[?ticker=...] */
export async function fetchAllStockIndicators(
  ticker?: string
): Promise<StockIndicators[]> {
  const url = new URL(`${API_BASE}/api/sentiment/indicators`);
  if (ticker && ticker.trim() !== "") {
    url.searchParams.set("ticker", ticker.trim());
  }

  const res = await fetch(url.toString(), {
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error(
      `Failed to fetch indicators: ${res.status} ${res.statusText}`
    );
  }
  return res.json();
}

export async function fetchStockIndicatorsByTicker(
  ticker: string
): Promise<StockIndicators[]> {
  const trimmed = ticker.trim();
  if (!trimmed) {
    return [];
  }

  const res = await fetch(
    `${API_BASE}/api/sentiment/indicators?ticker=${encodeURIComponent(
      trimmed
    )}`,
    {
      headers: getAuthHeaders(),
    }
  );

  if (!res.ok) {
    throw new Error("Failed to fetch indicators for ticker " + trimmed);
  }

  return res.json();
}


/** DELETE /api/sentiment/indicators/{ticker} */
export async function deleteStockIndicator(ticker: string): Promise<void> {
  const res = await fetch(
    `${API_BASE}/api/sentiment/indicators/${encodeURIComponent(ticker)}`,
    {
      method: "DELETE",
      headers: getAuthHeaders(),
    }
  );
  if (!res.ok) {
    throw new Error(
      `Failed to delete ${ticker}: ${res.status} ${res.statusText}`
    );
  }
}


export async function fetchLatestStockIndicator(
  ticker: string
): Promise<StockIndicators | null> {
  const arr = await fetchStockIndicatorsByTicker(ticker);
  if (!Array.isArray(arr) || arr.length === 0) return null;

  // If API returns multiple snapshots, pick the newest
  const sorted = [...arr].sort(
    (a, b) => new Date(b.snapshot_date).getTime() - new Date(a.snapshot_date).getTime()
  );
  return sorted[0] ?? null;
}