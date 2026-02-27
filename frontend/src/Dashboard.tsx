import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./app-header.css";
import "./Stocks.css";
import axios from "axios";
import { TICKER_NAMES } from "./utils/stockNames";

import {
  fetchAllStockIndicators,
  fetchStockIndicatorsByTicker,
  deleteStockIndicator,
} from "./utils/sentiment";
import type { StockIndicators } from "./utils/sentiment";
import { StockSentimentCard } from "./SentimentIndicators";
import AddToPortfolioModal from "./components/AddToPortfolio";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

interface StockPriceRow {
  ticker: string;
  date: string;
  close: number | null;
  adjusted_close: number | null;
  return_1d: number | null;
  return_30d: number | null;
  return_120d: number | null;
  return_360d: number | null;
}

interface StockCard {
  ticker: string;
  close: number | null;
  return_1d: number | null;
  return_30d: number | null;
}

const getReturnColor = (value: number | null): string => {
  if (value == null) return "#6b7280";
  return value >= 0 ? "#16a34a" : "#dc2626";
};

const formatPercent = (value: number | null): string => {
  if (value == null) return "N/A";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
};

const StockMiniCard: React.FC<{
  data: StockCard;
  onClick: (ticker: string) => void;
  onAddToPortfolio: (ticker: string, price: number) => void;
}> = ({ data, onClick, onAddToPortfolio }) => {
  const returnColor = getReturnColor(data.return_1d);

  return (
    <div className="stock-card" onClick={() => onClick(data.ticker)}>
      <div className="stock-card-accent" style={{ background: returnColor }} />

      <div className="stock-card-header">
        <div>
          <div className="stock-card-ticker">{data.ticker}</div>
          {data.close != null && (
            <div className="stock-card-price">${data.close.toFixed(2)}</div>
          )}
        </div>
        {data.return_1d != null && (
          <span
            className="sentiment-badge"
            style={{
              color: returnColor,
              background: data.return_1d >= 0 ? "rgba(22,163,74,0.1)" : "rgba(220,38,38,0.1)",
              border: `1px solid ${data.return_1d >= 0 ? "rgba(22,163,74,0.3)" : "rgba(220,38,38,0.3)"}`,
            }}
          >
            {formatPercent(data.return_1d)}
          </span>
        )}
      </div>

      {data.return_30d != null && (
        <div className="score-bar-row" style={{ marginBottom: "14px" }}>
          <span className="score-bar-label">30D Return</span>
          <span className="score-bar-value" style={{ color: getReturnColor(data.return_30d) }}>
            {formatPercent(data.return_30d)}
          </span>
        </div>
      )}

      <div className="stock-card-footer">
        <span className="stock-card-hint">Click to view details →</span>
        <div className="stock-card-actions" onClick={(e) => e.stopPropagation()}>
          <button
            className="btn-add-portfolio"
            onClick={() => onAddToPortfolio(data.ticker, data.close ?? 0)}
          >
            + Portfolio
          </button>
        </div>
      </div>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [cards, setCards] = useState<StockCard[]>([]);
  const [indicators, setIndicators] = useState<StockIndicators[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTicker, setSearchTicker] = useState("");
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  // Auto-load all stocks on mount
  useEffect(() => {
    handleLoadAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchLatestForTicker = async (ticker: string): Promise<StockCard | null> => {
    try {
      const res = await axios.get<StockPriceRow[]>(`${API_BASE}/api/stocks/${ticker}/prices`);
      if (res.data.length === 0) return null;
      const latest = res.data[res.data.length - 1];
      return {
        ticker: latest.ticker,
        close: latest.close,
        return_1d: latest.return_1d,
        return_30d: latest.return_30d,
      };
    } catch {
      return null;
    }
  };

  // Add stocks
  const [modalStock, setModalStock] = useState<{ ticker: string; currentPrice: number } | null>(null);

  const handleSearch = async () => {
    const trimmed = searchTicker.trim().toUpperCase();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const card = await fetchLatestForTicker(trimmed);
      setCards(card ? [card] : []);
      setHasLoadedOnce(true);
    } catch {
      setError("Failed to load stock data");
      setCards([]);
      setHasLoadedOnce(true);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<StockCard[]>(`${API_BASE}/api/stocks/latest`);
      setCards(res.data.filter((c: StockCard) => c.close !== null));
      setHasLoadedOnce(true);
    } catch {
      setError("Failed to load stocks");
      setCards([]);
      setHasLoadedOnce(true);
    } finally {
      setLoading(false);
    }
  };

  const handleAddToPortfolio = async (ticker: string, currentPrice: number) => {
    setModalStock({ ticker, currentPrice });
  };

  const handleModalClose = () => setModalStock(null);
  const handleModalSuccess = () => {
    setModalStock(null);
    navigate("/portfolio");
  };

  // Live-filter cards by partial ticker OR company name
  const q = searchTicker.trim();
  const filteredCards = q
    ? cards.filter(
        (c: StockCard) =>
          c.ticker.toUpperCase().includes(q.toUpperCase()) ||
          (TICKER_NAMES[c.ticker] || "").toLowerCase().includes(q.toLowerCase())
      )
    : cards;

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
          <div className="dashboard-controls">
            <input
              type="text"
              placeholder="Search by ticker or company name"
              value={searchTicker}
              onChange={(e) => setSearchTicker(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <button className="btn-primary" onClick={handleSearch}>Search</button>
            <button className="btn-ghost" onClick={handleLoadAll}>Load All</button>
          </div>

          {loading && <p style={{ color: "#6b7280", textAlign: "center", padding: "40px" }}>Loading...</p>}
          {error && <p style={{ color: "#ef4444" }}>{error}</p>}

          {!loading && !error && !hasLoadedOnce && (
            <div className="dashboard-empty">
              <div className="empty-icon">📈</div>
              <p>Search a ticker or load all stocks to get started.</p>
            </div>
          )}

          {!loading && !error && hasLoadedOnce && filteredCards.length === 0 && (
            <div className="dashboard-empty">
              <p>No results found.</p>
            </div>
          )}

          {!loading && !error && filteredCards.length > 0 && (
            <div className="stock-grid">
              {filteredCards.map((stock: StockCard) => (
                <StockMiniCard
                  key={stock.ticker}
                  data={stock}
                  onClick={(ticker) => navigate(`/stock/${ticker}`)}
                  onAddToPortfolio={handleAddToPortfolio}
                />
              ))}
            </div>
          )}
        </div>
      </div>
      {modalStock && (
        <AddToPortfolioModal
          ticker={modalStock.ticker}
          currentPrice={modalStock.currentPrice}
          onClose={handleModalClose}
          onSuccess={handleModalSuccess}
        />
      )}
    </div>
  );
};

export default Dashboard;
