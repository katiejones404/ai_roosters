import React, { useState } from "react";
import "./app-header.css";

import {
  fetchAllStockIndicators,
  fetchStockIndicatorsByTicker,
  deleteStockIndicator,
} from "./utils/sentiment";
import type { StockIndicators } from "./utils/sentiment";
import { StockSentimentCard } from "./SentimentIndicators";

const Dashboard: React.FC = () => {
  const [indicators, setIndicators] = useState<StockIndicators[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTicker, setSearchTicker] = useState("");
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  const handleSearch = async () => {
    const trimmed = searchTicker.trim();
    if (!trimmed) return; // do nothing on empty search

    setLoading(true);
    setError(null);

    try {
      const data = await fetchStockIndicatorsByTicker(trimmed);
      setIndicators(data);
      setHasLoadedOnce(true);
    } catch (err) {
      console.error(err);
      setError("Failed to load sentiment indicators");
      setIndicators([]);
      setHasLoadedOnce(true);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadAll = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await fetchAllStockIndicators();
      setIndicators(data);
      setHasLoadedOnce(true);
    } catch (err) {
      console.error(err);
      setError("Failed to load sentiment indicators");
      setIndicators([]);
      setHasLoadedOnce(true);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (ticker: string) => {
    try {
      await deleteStockIndicator(ticker);
      setIndicators((prev) => prev.filter((item) => item.ticker !== ticker));
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

          {/* Search + Load All controls */}
          <div className="sentiment-controls">
            <input
              type="text"
              placeholder="Search ticker (e.g. BP, RELIANCE.NS)"
              value={searchTicker}
              onChange={(e) => setSearchTicker(e.target.value)}
            />
            <button onClick={handleSearch}>Search</button>
            <button onClick={handleLoadAll}>Load All</button>
          </div>

          {loading && <p>Loading sentiment...</p>}
          {error && <p className="sentiment-error">{error}</p>}

          {/* Initial state: show friendly message instead of auto-loading */}
          {!loading && !error && !hasLoadedOnce && (
            <p>No stocks loaded yet. Use the search box or “Load All”.</p>
          )}

          {/* After first load/search */}
          {!loading && !error && hasLoadedOnce && indicators.length === 0 && (
            <p>No results found for your query.</p>
          )}

          {!loading && !error && indicators.length > 0 && (
            <div className="sentiment-section sentiment-grid">
              {indicators.map((stock) => (
                <StockSentimentCard
                  key={stock.ticker}
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
