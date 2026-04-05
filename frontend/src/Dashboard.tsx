/*
 * Dashboard.tsx
 * Main dashboard page displaying stock sentiment indicators, a portfolio snapshot,
 * and recent news articles for all tracked tickers.
 */
import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./app-header.css";
import "./Stocks.css";
import axios from "axios";
import { TICKER_NAMES } from "./utils/stockNames";

import AddToPortfolioModal from "./components/AddToPortfolio";
import LoadingScreen from "./components/LoadingScreen";

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

interface ArticleSentimentSummary {
  total: number;
  positive: number;
  negative: number;
  neutral: number;
  unknown: number;
}

const getReturnColor = (value: number | null): string => {
  if (value == null) return "#6b7280";
  return value >= 0 ? "#16a34a" : "#dc2626";
};

const formatPercent = (value: number | null): string => {
  if (value == null) return "N/A";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
};

const StatCard: React.FC<{ label: string; value: number | string }> = ({ label, value }) => {
  const getAccentColor = () => {
    if (label.toLowerCase().includes("positive")) return "#16a34a";
    if (label.toLowerCase().includes("negative")) return "#dc2626";
    if (label.toLowerCase().includes("neutral")) return "#f59e0b";
    return "#6366f1";
  };

  return (
    <div
      style={{
        padding: "18px",
        borderRadius: "14px",
        background: "rgba(255,255,255,0.07)",
        border: "1px solid rgba(255,255,255,0.12)",
        transition: "all 0.2s ease",
        cursor: "default",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget.style.transform = "translateY(-3px)");
        (e.currentTarget.style.boxShadow = "0 8px 20px rgba(0,0,0,0.25)");
      }}
      onMouseLeave={(e) => {
        (e.currentTarget.style.transform = "translateY(0)");
        (e.currentTarget.style.boxShadow = "none");
      }}
    >
      <div
        style={{
          fontSize: "12px",
          color: "#9ca3af",
          marginBottom: "6px",
          letterSpacing: "0.5px",
        }}
      >
        {label}
      </div>

      <div
        style={{
          fontSize: "26px",
          fontWeight: 700,
          color: getAccentColor(),
        }}
      >
        {value}
      </div>
    </div>
  );
};

const StockMiniCard: React.FC<{
  data: StockCard;
  onClick: (ticker: string) => void;
  onAddToPortfolio: (ticker: string, price: number) => void;
  isWatchlisted: boolean;
  onToggleWatchlist: (ticker: string) => void;
}> = ({ data, onClick, onAddToPortfolio, isWatchlisted, onToggleWatchlist }) => {
  const returnColor = getReturnColor(data.return_1d);

  return (
    <div className="stock-card" onClick={() => onClick(data.ticker)}>
      <div className="stock-card-accent" style={{ background: returnColor }} />

      <div className="stock-card-header">
        {/* LEFT SIDE (⭐ + ticker + price) */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleWatchlist(data.ticker);
            }}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "22px",
              lineHeight: "1",
              padding: "0 2px",
            }}
          >
            {isWatchlisted ? "⭐" : "☆"}
          </button>

          <div>
            <div className="stock-card-ticker">{data.ticker}</div>
            {data.close != null && (
              <div className="stock-card-price">${data.close.toFixed(2)}</div>
            )}
          </div>
        </div>

        {/* RIGHT SIDE (return badge — unchanged) */}
        {data.return_1d != null && (
          <span
            className="sentiment-badge"
            style={{
              color: returnColor,
              background:
                data.return_1d >= 0
                  ? "rgba(22,163,74,0.1)"
                  : "rgba(220,38,38,0.1)",
              border: `1px solid ${
                data.return_1d >= 0
                  ? "rgba(22,163,74,0.3)"
                  : "rgba(220,38,38,0.3)"
              }`,
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTicker, setSearchTicker] = useState("");
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  // Watchlist addition
  const [watchlist, setWatchlist] = useState<string[]>(() => {
    const saved = localStorage.getItem("watchlist");
    return saved ? JSON.parse(saved) : [];
  });

  const [sortOption, setSortOption] = useState("default");

  const [filters, setFilters] = useState({
    positive: false,
    negative: false,
    watchlistOnly: false,
  });

  // Articles sentiment summary
  const [articleSummary, setArticleSummary] = useState<ArticleSentimentSummary | null>(null);


  const fetchArticleSummary = async () => {
    try {
      const res = await axios.get<ArticleSentimentSummary>(
        `${API_BASE}/api/articles/sentiment/summary`
      );
      setArticleSummary(res.data);
    } catch {
      setArticleSummary(null);
    }
  };
  // Auto-load all stocks + summary on mount
  useEffect(() => {
    handleLoadAll();
    fetchArticleSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleWatchlist = (ticker: string) => {
  let updated: string[];

  if (watchlist.includes(ticker)) {
    updated = watchlist.filter((t) => t !== ticker);
  } else {
    updated = [...watchlist, ticker];
  }

  setWatchlist(updated);
  localStorage.setItem("watchlist", JSON.stringify(updated));
};

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
  const [modalStock, setModalStock] = useState<{ ticker: string; currentPrice: number } | null>(
    null
  );

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

  const q = searchTicker.trim();

  const filteredCards = cards.filter((c: StockCard) => {
    const matchesSearch =
      !q ||
      c.ticker.toUpperCase().includes(q.toUpperCase()) ||
      (TICKER_NAMES[c.ticker] || "").toLowerCase().includes(q.toLowerCase());

    const matchesWatchlist =
      !filters.watchlistOnly || watchlist.includes(c.ticker);

    const matchesPositive =
      !filters.positive || (c.return_1d ?? 0) > 0;

    const matchesNegative =
      !filters.negative || (c.return_1d ?? 0) < 0;

    return matchesSearch && matchesWatchlist && matchesPositive && matchesNegative;
  });
  const displayedCards = [...filteredCards].sort((a, b) => {
    switch (sortOption) {
      case "alphabetical":
        return a.ticker.localeCompare(b.ticker);
      case "priceHigh":
        return (b.close ?? 0) - (a.close ?? 0);
      case "priceLow":
        return (a.close ?? 0) - (b.close ?? 0);
      case "returnHigh":
        return (b.return_30d ?? 0) - (a.return_30d ?? 0);
      case "returnLow":
        return (a.return_30d ?? 0) - (b.return_30d ?? 0);
      default:
        return 0;
    }
  });

  return (
    <div className="app-container app-container-wide">
      <div className="home-background-shapes">
        <div className="home-shape home-shape-1"></div>
        <div className="home-shape home-shape-2"></div>
        <div className="home-shape home-shape-3"></div>
      </div>

      <div className="dashboard-page-layout">
        <aside className="dashboard-sidebar">
          <div className="filter-panel">
            <div className="filter-panel-title">Filters</div>

            <label className="filter-option">
              <input
                type="checkbox"
                checked={filters.watchlistOnly}
                onChange={() =>
                  setFilters((f) => ({
                    ...f,
                    watchlistOnly: !f.watchlistOnly,
                  }))
                }
              />
              <span className="filter-label">Watchlist only</span>
            </label>

            <label className="filter-option">
              <input
                type="checkbox"
                checked={filters.positive}
                onChange={() =>
                  setFilters((f) => ({
                    ...f,
                    positive: !f.positive,
                    negative: false,
                  }))
                }
              />
              <span className="filter-label">Positive</span>
            </label>

            <label className="filter-option">
              <input
                type="checkbox"
                checked={filters.negative}
                onChange={() =>
                  setFilters((f) => ({
                    ...f,
                    negative: !f.negative,
                    positive: false,
                  }))
                }
              />
              <span className="filter-label">Negative</span>
            </label>

            <button
              className="filter-clear"
              onClick={() =>
                setFilters({
                  watchlistOnly: false,
                  positive: false,
                  negative: false,
                })
              }
            >
              Clear Filters
            </button>
          </div>
        </aside>

        <div className="home-card dashboard-card">
          <div className="home-content">
          <h1>Dashboard</h1>
          <p>Overview of your tracked stocks and sentiment predictions.
          
          Due to scale constraints for the Capstone project, we only have 40 stocks in our portfolio.</p>

          {/* Article sentiment counts */}
          {articleSummary && (
            <div
              style={{
                marginTop: "24px",
                marginBottom: "24px",
                padding: "24px",
                borderRadius: "18px",
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.12)",
                backdropFilter: "blur(10px)",
                boxShadow: "0 10px 30px rgba(0,0,0,0.25)",
              }}
            >
              <h3
                style={{
                  marginBottom: "18px",
                  fontSize: "20px",
                  fontWeight: 700,
                  letterSpacing: "0.5px",
                  color: "#6366f1", 
                }}
              >
                Article Sentiment Overview
              </h3>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: "16px",
                }}
              >
                <StatCard label="Total Articles" value={articleSummary.total} />
                <StatCard label="Positive" value={articleSummary.positive} />
                <StatCard label="Neutral" value={articleSummary.neutral} />
                <StatCard label="Negative" value={articleSummary.negative} />
              </div>
            </div>
          )}

         {/* Search + Load All controls */}
          <div className="dashboard-controls">
            <input
              type="text"
              placeholder="Search by ticker or company name"
              value={searchTicker}
              onChange={(e) => setSearchTicker(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <button className="btn-primary" onClick={handleSearch}>
              Search
            </button>
            <button className="btn-ghost" onClick={handleLoadAll}>
              Load All
            </button>            
            <select
              className="btn-ghost"
              value={sortOption}
              onChange={(e) => setSortOption(e.target.value)}
            >
              <option value="default">Sort</option>
              <option value="alphabetical">A–Z</option>
              <option value="priceHigh">Price: High → Low</option>
              <option value="priceLow">Price: Low → High</option>
              <option value="returnHigh">30D Return: High → Low</option>
              <option value="returnLow">30D Return: Low → High</option>
            </select>
          </div>

          
              {loading && <LoadingScreen message="Loading stocks..." />}
              {error && <p style={{ color: "#ef4444" }}>{error}</p>}

              {!loading && !error && !hasLoadedOnce && (
                <div className="dashboard-empty">
                  <div className="empty-icon">📈</div>
                  <p>Search a ticker or load all stocks to get started.</p>
                </div>
              )}

              {!loading && !error && hasLoadedOnce && displayedCards.length === 0 && (
                <div className="dashboard-empty">
                  <p>No results found.</p>
                </div>
              )}

              {!loading && !error && displayedCards.length > 0 && (
                <div className="stock-grid">
                  {displayedCards.map((stock: StockCard) => (
                    <StockMiniCard
                      key={stock.ticker}
                      data={stock}
                      onClick={(ticker) => navigate(`/stock/${ticker}`)}
                      onAddToPortfolio={handleAddToPortfolio}
                      isWatchlisted={watchlist.includes(stock.ticker)}
                      onToggleWatchlist={toggleWatchlist}
                    />
                  ))}
                </div>
              )}
            </div>
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

