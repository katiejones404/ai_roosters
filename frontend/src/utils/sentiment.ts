// frontend/src/utils/sentiment.ts
import axios from "axios";

export type SentimentLabel = "bullish" | "neutral" | "bearish";

export interface TimeRangeIndicators {
  d30: SentimentLabel;
  d120: SentimentLabel;
  d360: SentimentLabel;
}

export interface GPTExplanations {
  d30?: string | null;
  d120?: string | null;
  d360?: string | null;
}

export interface StockIndicators {
  // ✅ REQUIRED by backend + used by UI keys
  id: string;

  ticker: string;
  snapshot_date: string;

  close_price?: number | null;

  indicators: TimeRangeIndicators;

  // ✅ present in /sentiment/indicators when available
  explanations?: GPTExplanations | null;

  gpt_model?: string | null;
  gpt_generated_at?: string | null;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

export async function fetchLatestStockIndicator(ticker: string): Promise<StockIndicators> {
  const url = `${API_BASE}/api/sentiment/indicators?ticker=${encodeURIComponent(ticker)}`;
  const res = await axios.get<StockIndicators[]>(url);

  const first = res.data?.[0];
  if (!first) {
    throw new Error(`No sentiment indicator found for ${ticker}`);
  }
  return first;
}

export async function fetchAllStockIndicators(): Promise<StockIndicators[]> {
  const url = `${API_BASE}/api/sentiment/indicators`;
  const res = await axios.get<StockIndicators[]>(url);
  return res.data ?? [];
}