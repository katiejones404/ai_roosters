/*
 * News.tsx
 * News feed page that displays recent financial news articles,
 * with filtering by portfolio holdings, all news, or a single ticker.
 */
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import "./News.css";
import StockChartBg from "./components/StockChartBg";
import LoadingScreen from "./components/LoadingScreen";
import { getToken } from "./utils/auth";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");
const LIMIT = 50;

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

type FilterMode = "portfolio" | "all" | string;

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

interface PortfolioItem {
  ticker: string;
}

interface PortfolioSummaryResponse {
  portfolio_items: PortfolioItem[];
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function sortArticlesNewestFirst(a: NewsArticle, b: NewsArticle): number {
  const aTime = a.published_at ? new Date(a.published_at).getTime() : 0;
  const bTime = b.published_at ? new Date(b.published_at).getTime() : 0;
  return bTime - aTime;
}

function dedupeArticles(items: NewsArticle[]): NewsArticle[] {
  const seen = new Set<string>();
  return items.filter((article) => {
    const key = article.url || `${article.ticker}-${article.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export default function News() {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [portfolioArticles, setPortfolioArticles] = useState<NewsArticle[]>([]);
  const [portfolioTickers, setPortfolioTickers] = useState<string[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filter, setFilter] = useState<FilterMode>("portfolio");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const fetchPortfolioTickers = async () => {
    try {
      const token = getToken();
      if (!token) {
        setPortfolioTickers([]);
        return;
      }

      const res = await axios.get<PortfolioSummaryResponse>(
        `${API_BASE}/api/portfolio/stats/summary`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      const tickers = Array.from(
        new Set(
          (res.data.portfolio_items || [])
            .map((item) => item.ticker?.trim().toUpperCase())
            .filter(Boolean)
        )
      ).sort();

      setPortfolioTickers(tickers);
    } catch {
      setPortfolioTickers([]);
    }
  };

  const fetchSingleTickerArticles = async (
    ticker: string,
    newOffset: number,
    replace: boolean
  ) => {
    const res = await axios.get<NewsArticle[]>(`${API_BASE}/api/articles`, {
      params: { ticker, limit: LIMIT, offset: newOffset },
    });

    if (replace) {
      setArticles(res.data);
    } else {
      setArticles((prev) => [...prev, ...res.data]);
    }

    setHasMore(res.data.length === LIMIT);
  };

  const fetchAllArticles = async (newOffset: number, replace: boolean) => {
    const res = await axios.get<NewsArticle[]>(`${API_BASE}/api/articles`, {
      params: { limit: LIMIT, offset: newOffset },
    });

    if (replace) {
      setArticles(res.data);
    } else {
      setArticles((prev) => [...prev, ...res.data]);
    }

    setHasMore(res.data.length === LIMIT);
  };

  const fetchPortfolioArticles = async (newOffset: number, replace: boolean) => {
    if (portfolioTickers.length === 0) {
      setArticles([]);
      setPortfolioArticles([]);
      setHasMore(false);
      return;
    }

    if (!replace) {
      const nextSlice = portfolioArticles.slice(0, newOffset + LIMIT);
      setArticles(nextSlice);
      setHasMore(portfolioArticles.length > newOffset + LIMIT);
      return;
    }

    const responses = await Promise.all(
      portfolioTickers.map((heldTicker) =>
        axios.get<NewsArticle[]>(`${API_BASE}/api/articles`, {
          params: { ticker: heldTicker, limit: LIMIT, offset: 0 },
        })
      )
    );

    const merged = dedupeArticles(
      responses.flatMap((response) => response.data)
    ).sort(sortArticlesNewestFirst);

    setPortfolioArticles(merged);
    setArticles(merged.slice(0, LIMIT));
    setHasMore(merged.length > LIMIT);
  };

  const fetchArticles = async (
    selectedFilter: FilterMode,
    newOffset: number,
    replace: boolean
  ) => {
    setLoading(true);
    setError(null);

    try {
      if (selectedFilter === "portfolio") {
        await fetchPortfolioArticles(newOffset, replace);
      } else if (selectedFilter === "all") {
        await fetchAllArticles(newOffset, replace);
      } else {
        await fetchSingleTickerArticles(selectedFilter, newOffset, replace);
      }
    } catch {
      setError("Failed to load news articles.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolioTickers();
  }, []);

  useEffect(() => {
    setOffset(0);
    fetchArticles(filter, 0, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter, portfolioTickers.join("|")]);

  const handleLoadMore = () => {
    const newOffset = offset + LIMIT;
    setOffset(newOffset);
    fetchArticles(filter, newOffset, false);
  };

  return (
    <div className="news-page">
      <StockChartBg />
      <div className="news-content">
        <div className="news-header">
          <div>
            <h1 className="news-title">Market News</h1>
            <p className="news-subtitle">Latest articles from tracked stocks</p>
            <p className="news-disclaimer">
              Due to API rate limits and the scope of this capstone project, recent
              articles are sourced from four free news APIs. As a result, the number
              of articles available per stock is intentionally limited.
            </p>
          </div>

          <select
            className="news-ticker-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="portfolio">Portfolio Holdings</option>
            <option value="all">All</option>
            {WEBSITE_TICKERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        {error && <p className="news-error">{error}</p>}

        {!loading && filter === "portfolio" && portfolioTickers.length === 0 && !error && (
          <div className="news-empty">
            <p>No portfolio holdings found. Add stocks to your portfolio to use that filter.</p>
          </div>
        )}

        {!loading && articles.length === 0 && !error && (
          <div className="news-empty">
            <p>
              No articles found
              {filter === "portfolio"
                ? " for your portfolio holdings"
                : filter === "all"
                ? "."
                : ` for ${filter}.`}
            </p>
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
                >
                  {article.ticker}
                </Link>
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