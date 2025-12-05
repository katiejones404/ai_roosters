import React, { useEffect, useState } from "react";
import {
  fetchAllStockIndicators,
  deleteStockIndicator,
} from "./utils/sentiment";
import type { StockIndicators } from "./utils/sentiment";
import { StockSentimentCard } from "./SentimentIndicators";

const Dashboard: React.FC = () => {
  const [indicators, setIndicators] = useState<StockIndicators[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadIndicators = async () => {
      try {
        const data = await fetchAllStockIndicators();
        // If you want to restrict to certain tickers:
        // const filtered = data.filter((item) => ["BP", "RELIANCE"].includes(item.ticker));
        setIndicators(data);
      } catch (err) {
        console.error(err);
        setError("Failed to load sentiment indicators");
      } finally {
        setLoading(false);
      }
    };
    loadIndicators();
  }, []);

  const handleDelete = async (id: string) => {
    try {
      await deleteStockIndicator(id);
      setIndicators((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      console.error(err);
      alert("Failed to delete stock sentiment");
    }
  };

  return (
    <div className="app-container">
      <div className="home-background-shapes">
        <div className="home-shape home-shape-1"></div>
        <div className="home-shape home-shape-2"></div>
        <div className="home-shape home-shape-3"></div>
      </div>

      <div className="home-card">
        <div className="home-content">
          <h1>Dashboard</h1>
          <p>Overview of your tracked stocks and sentiment predictions.</p>

          {loading && <p>Loading sentiment...</p>}
          {error && <p className="sentiment-error">{error}</p>}

          {!loading && !error && (
            <div className="sentiment-section sentiment-grid">
              {indicators.map((stock) => (
                <StockSentimentCard
                  key={stock.id}
                  data={stock}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
