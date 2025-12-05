// backend/src/utils/sentiment.ts
import axios from "axios";

const API_URL = "http://localhost:8000"; // adjust if you already define this elsewhere

export type SentimentLabel = "bullish" | "neutral" | "bearish";

export interface StockIndicators {
  id: string; 
  ticker: string;
  snapshot_date: string;
  close_price: number | null;
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

// DELETE one sentiment snapshot (by id)
export async function deleteStockIndicator(
  id: string,
  token?: string
): Promise<void> {
  await axios.delete(`${API_URL}/api/sentiment/indicators/${id}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
}

// CREATE/UPDATE one snapshot (for later when you add a form)
export async function upsertStockIndicator(
  payload: Omit<StockIndicators, "id"> & { id?: string },
  token?: string
): Promise<StockIndicators> {
  const res = await axios.post<StockIndicators>(
    `${API_URL}/api/sentiment/indicators`,
    payload,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    }
  );
  return res.data;
}

