import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import "./News.css";
import StockChartBg from "./components/StockChartBg";
import LoadingScreen from "./components/LoadingScreen";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

const WEBSITE_TICKERS = [
  "KSS", "ALK", "NVS", "AXP", "FCX",
  "CSX", "DAL", "NTAP", "MRK", "COP",
  "BHP", "EA",
  "TSLA", "NVDA", "AAPL", "MSFT", "AMZN",
  "AMD", "META", "GOOGL", "GOOG", "PLTR",
  "MU", "NFLX",
  "NKE", "AAL", "BAC", "F", "INTC", "XOM", "T",
  "SOFI", "PLUG", "MARA", "SNAP", "COIN", "AMC", "RIVN", "CCL", "ENPH",
];

interface NewsArticle {
  id: string;
  ticker: string;
  url: string;
  title: string | null;
  source: string | null;
  description: string | null;
  image_url: string | null;
  published_at: string | null;
  relevance_score: number | null;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function News() {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ticker, setTicker] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const LIMIT = 50;

  const fetchArticles = async (newTicker: string, newOffset: number, replace: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { limit: LIMIT, offset: newOffset };
      if (newTicker) params.ticker = newTicker;
      const res = await axios.get<NewsArticle[]>(`${API_BASE}/api/articles`, { params });
      if (replace) {
        setArticles(res.data);
      } else {
        setArticles((prev) => [...prev, ...res.data]);
      }
      setHasMore(res.data.length === LIMIT);
    } catch {
      setError("Failed to load news articles.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setOffset(0);
    fetchArticles(ticker, 0, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  const handleLoadMore = () => {
    const newOffset = offset + LIMIT;
    setOffset(newOffset);
    fetchArticles(ticker, newOffset, false);
  };

  return (
    <div className="news-page">
      <StockChartBg />
      <div className="news-content">
      <div className="news-header">
        <div>
          <h1 className="news-title">Market News</h1>
          <p className="news-subtitle">Latest articles from tracked stocks</p>
        </div>
        <select
          className="news-ticker-filter"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
        >
          <option value="">All Tickers</option>
          {WEBSITE_TICKERS.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      {error && <p className="news-error">{error}</p>}

      {!loading && articles.length === 0 && !error && (
        <div className="news-empty">
          <p>No articles found{ticker ? ` for ${ticker}` : ""}.</p>
        </div>
      )}

      <div className="news-grid">
        {articles.map((article) => (
          <a
            key={article.id}
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="news-card"
          >
            <div className="news-card-top">
              <Link
                to={`/stock/${article.ticker}`}
                className="news-ticker-badge"
                onClick={(e: React.MouseEvent) => e.stopPropagation()}
              >{article.ticker}</Link>
              <span className="news-date">{formatDate(article.published_at)}</span>
            </div>
            <p className="news-headline">{article.title || "Untitled"}</p>
            {article.description && article.description.trim().split(/\s+/).length >= 5 && (
              <p className="news-description">{article.description}</p>
            )}
            <div className="news-card-footer">
              <span className="news-source">{article.source || "Unknown source"}</span>
              <span className="news-read-more">Read more →</span>
            </div>
          </a>
        ))}
      </div>

      {loading && articles.length === 0 && (
        <LoadingScreen message="Loading news..." />
      )}
      {loading && articles.length > 0 && (
        <div className="news-loading">
          <div className="news-spinner" />
        </div>
      )}

      {!loading && hasMore && articles.length > 0 && (
        <div className="news-load-more">
          <button className="load-more-btn" onClick={handleLoadMore}>
            Load More
          </button>
        </div>
      )}
      </div>
    </div>
  );
}
