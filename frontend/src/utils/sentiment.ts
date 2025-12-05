// backend/src/utils/sentiment.ts
import axios from "axios";

const API_URL = "http://localhost:8000"; // adjust if you already define this elsewhere

export type SentimentLabel = "bullish" | "neutral" | "bearish";

export interface StockIndicators {
  ticker: string;
  snapshot_date: string;
  indicators: {
    d30: SentimentLabel;
    d120: SentimentLabel;
    d360: SentimentLabel;
  };
}

export async function fetchAllStockIndicators(
  token?: string
): Promise<StockIndicators[]> {
  const res = await axios.get<StockIndicators[]>(
    `${API_URL}/api/sentiment/indicators`,
    token
      ? {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      : undefined
  );
  return res.data;
}
