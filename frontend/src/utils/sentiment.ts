// frontend/src/utils/sentiment.ts
import axios from "axios";

export type SentimentLabel = "bullish" | "neutral" | "bearish";

export interface TimeRangeIndicators {
  d30: SentimentLabel;
  d120: SentimentLabel;
  d360: SentimentLabel;
}

export interface NewsExplanationWindow {
  window_days: number;
  article_count: number;
  latest_article_at?: string | null;
  summary_text: string;
}

export interface StockNewsExplanations {
  ticker: string;
  d7?: NewsExplanationWindow | null;
  d30?: NewsExplanationWindow | null;
  preferred_window_days?: number | null;
  preferred_summary_text?: string | null;
  gpt_model?: string | null;
  gpt_generated_at?: string | null;
}

export interface StockIndicators {
  id: string;
  ticker: string;
  snapshot_date: string;
  close_price?: number | null;
  indicators: TimeRangeIndicators;
  news_explanations?: StockNewsExplanations | null;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

export async function fetchLatestStockIndicator(ticker: string): Promise<StockIndicators> {
  const url = `${API_BASE}/api/sentiment/overview?ticker=${encodeURIComponent(ticker)}`;
  const res = await axios.get<StockIndicators[]>(url);

  const first = res.data?.[0];
  if (!first) {
    throw new Error(`No stock overview found for ${ticker}`);
  }
  return first;
}

export async function fetchAllStockIndicators(): Promise<StockIndicators[]> {
  const url = `${API_BASE}/api/sentiment/overview`;
  const res = await axios.get<StockIndicators[]>(url);
  return res.data ?? [];
}
