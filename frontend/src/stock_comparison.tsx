import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import { getToken } from "./utils/auth";
import { TICKER_NAMES } from "./utils/stockNames";
import LoadingScreen from "./components/LoadingScreen";
import "./stock_comparison.css";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");
const CHART_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#06b6d4", "#f97316", "#8b5cf6", "#ef4444"];

interface PortfolioItem {
  ticker: string;
}

interface PortfolioSummaryResponse {
  portfolio_items: PortfolioItem[];
}

interface PricePoint {
  date: string;
  close: number;
}

interface StockOption {
  ticker: string;
  name: string;
  inPortfolio: boolean;
}

const formatCurrency = (value: number | null | undefined) =>
  value == null
    ? "N/A"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(value);

const formatPercent = (value: number | null | undefined) => {
  if (value == null) return "N/A";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
};

const getPercentChange = (series: PricePoint[], days: number): number | null => {
  const slice = series.slice(-days);
  if (slice.length < 2) return null;
  const start = slice[0]?.close;
  const end = slice[slice.length - 1]?.close;
  if (!start) return null;
  return ((end / start) - 1) * 100;
};

export default function StockComparison() {
  const [portfolioTickers, setPortfolioTickers] = useState<string[]>([]);
  const [allTickers, setAllTickers] = useState<string[]>([]);
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [compareData, setCompareData] = useState<Record<string, PricePoint[]>>({});
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [compareView, setCompareView] = useState<"pct" | "price">("pct");
  const [compareRange, setCompareRange] = useState<"30" | "120" | "360">("30");

  useEffect(() => {
    async function fetchSources() {
      try {
        setLoading(true);
        const token = getToken();

        const [stocksRes, portfolioRes] = await Promise.all([
          axios.get<{ ticker: string }[]>(`${API_BASE}/api/stocks`),
          axios.get<PortfolioSummaryResponse>(`${API_BASE}/api/portfolio/stats/summary`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          }),
        ]);

        const dbTickers = Array.from(new Set((stocksRes.data || []).map((row) => row.ticker.toUpperCase()))).sort();
        const ownedTickers = Array.from(
          new Set((portfolioRes.data?.portfolio_items || []).map((row) => row.ticker.toUpperCase()))
        ).sort();

        setAllTickers(dbTickers);
        setPortfolioTickers(ownedTickers);

        const starter =
          ownedTickers.length >= 2
            ? ownedTickers.slice(0, 2)
            : dbTickers.slice(0, Math.min(2, dbTickers.length));

        setSelectedTickers(starter);
        setError(null);
      } catch {
        setError("Failed to load stocks for comparison.");
      } finally {
        setLoading(false);
      }
    }

    fetchSources();
  }, []);

  useEffect(() => {
    async function fetchPriceHistory() {
      if (selectedTickers.length < 2) {
        setCompareData({});
        return;
      }

      try {
        setChartLoading(true);
        const token = getToken();

        const responses = await Promise.all(
          selectedTickers.map((ticker) =>
            axios.get<PricePoint[]>(`${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/prices`, {
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            })
          )
        );

        const nextData: Record<string, PricePoint[]> = {};
        selectedTickers.forEach((ticker, index) => {
          nextData[ticker] = responses[index].data || [];
        });

        setCompareData(nextData);
      } catch {
        setError("Failed to load price history for the selected stocks.");
      } finally {
        setChartLoading(false);
      }
    }

    fetchPriceHistory();
  }, [selectedTickers]);

  const allOptions: StockOption[] = useMemo(() => {
    const owned = new Set(portfolioTickers);
    return allTickers.map((ticker) => ({
      ticker,
      name: TICKER_NAMES[ticker] || ticker,
      inPortfolio: owned.has(ticker),
    }));
  }, [allTickers, portfolioTickers]);

  const filteredOptions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const selected = new Set(selectedTickers);

    return allOptions
      .filter((option) => !selected.has(option.ticker))
      .filter((option) => {
        if (!q) return true;
        return option.ticker.toLowerCase().includes(q) || option.name.toLowerCase().includes(q);
      })
      .slice(0, 12);
  }, [allOptions, searchQuery, selectedTickers]);

  const addTicker = (ticker: string) => {
    setSelectedTickers((prev) => (prev.includes(ticker) ? prev : [...prev, ticker]));
    setSearchQuery("");
  };

  const removeTicker = (ticker: string) => {
    setSelectedTickers((prev) => prev.filter((t) => t !== ticker));
  };

  const chartData = useMemo(() => {
    const tickers = Object.keys(compareData);
    if (tickers.length === 0) return [];

    const daysMap: Record<string, number> = { "30": 30, "120": 120, "360": 360 };
    const days = daysMap[compareRange];
    const baseSeries = (compareData[tickers[0]] || []).slice(-days);

    const firstCloses: Record<string, number> = {};
    tickers.forEach((ticker) => {
      const slice = (compareData[ticker] || []).slice(-days);
      firstCloses[ticker] = slice[0]?.close || 1;
    });

    return baseSeries.map((point) => {
      const row: Record<string, string | number> = { date: point.date.slice(5) };
      tickers.forEach((ticker) => {
        const slice = (compareData[ticker] || []).slice(-days);
        const match = slice.find((p) => p.date === point.date);
        if (!match) return;

        row[ticker] =
          compareView === "pct"
            ? parseFloat((((match.close / firstCloses[ticker]) - 1) * 100).toFixed(2))
            : parseFloat(match.close.toFixed(2));
      });
      return row;
    });
  }, [compareData, compareRange, compareView]);

  const metrics = useMemo(() => {
    return selectedTickers.map((ticker) => {
      const series = compareData[ticker] || [];
      const latest = series.length ? series[series.length - 1].close : null;

      return {
        ticker,
        currentPrice: latest,
        return30d: getPercentChange(series, 30),
        return120d: getPercentChange(series, 120),
        return360d: getPercentChange(series, 360),
      };
    });
  }, [compareData, selectedTickers]);

  if (loading) {
    return (
      <div className="app-container">
        <div className="home-background-shapes">
          <div className="home-shape home-shape-1"></div>
          <div className="home-shape home-shape-2"></div>
          <div className="home-shape home-shape-3"></div>
        </div>
        <div className="home-card">
          <LoadingScreen message="Loading comparison page..." />
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <div className="home-background-shapes">
        <div className="home-shape home-shape-1"></div>
        <div className="home-shape home-shape-2"></div>
        <div className="home-shape home-shape-3"></div>
      </div>

      <div className="home-card comparison-page-card">
        <div className="comparison-header">
          <div>
            <h1>Stock Comparison</h1>
            <p>Compare portfolio holdings against any stock available in the database.</p>
          </div>
        </div>

        {error && <div className="comparison-error">{error}</div>}

        <div className="comparison-layout">
          <aside className="comparison-sidebar">
            <div className="comparison-panel">
              <h3>Your Portfolio Holdings</h3>
              {portfolioTickers.length === 0 ? (
                <p className="comparison-muted">No portfolio holdings yet.</p>
              ) : (
                <div className="ticker-chip-list">
                  {portfolioTickers.map((ticker) => (
                    <button
                      key={ticker}
                      type="button"
                      className={`ticker-chip ${selectedTickers.includes(ticker) ? "selected" : ""}`}
                      onClick={() => addTicker(ticker)}
                    >
                      {ticker}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="comparison-panel">
              <h3>Search All Database Stocks</h3>
              <input
                className="comparison-search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search ticker or name..."
              />

              <div className="comparison-search-results">
                {filteredOptions.length === 0 ? (
                  <p className="comparison-muted">No matching stocks.</p>
                ) : (
                  filteredOptions.map((option) => (
                    <button
                      key={option.ticker}
                      type="button"
                      className="comparison-result"
                      onClick={() => addTicker(option.ticker)}
                    >
                      <span className="comparison-result-main">{option.ticker}</span>
                      <span className="comparison-result-sub">
                        {option.name}
                        {option.inPortfolio ? " • In portfolio" : ""}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>

            <div className="comparison-panel">
              <h3>Selected Stocks</h3>
              {selectedTickers.length === 0 ? (
                <p className="comparison-muted">Choose at least two stocks.</p>
              ) : (
                <div className="selected-ticker-list">
                  {selectedTickers.map((ticker) => (
                    <div key={ticker} className="selected-ticker-item">
                      <Link to={`/stock/${encodeURIComponent(ticker)}`} className="selected-ticker-link">
                        {ticker}
                      </Link>
                      <button
                        type="button"
                        className="selected-remove-btn"
                        onClick={() => removeTicker(ticker)}
                        disabled={selectedTickers.length <= 2}
                        title={selectedTickers.length <= 2 ? "Select at least two stocks" : "Remove"}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </aside>

          <main className="comparison-main">
            <div className="comparison-controls">
              <div className="comparison-toggle-group">
                <button
                  type="button"
                  className={compareView === "pct" ? "active" : ""}
                  onClick={() => setCompareView("pct")}
                >
                  % Return
                </button>
                <button
                  type="button"
                  className={compareView === "price" ? "active" : ""}
                  onClick={() => setCompareView("price")}
                >
                  Price
                </button>
              </div>

              <div className="comparison-toggle-group">
                {(["30", "120", "360"] as const).map((range) => (
                  <button
                    key={range}
                    type="button"
                    className={compareRange === range ? "active" : ""}
                    onClick={() => setCompareRange(range)}
                  >
                    {range}D
                  </button>
                ))}
              </div>
            </div>

            <div className="comparison-chart-card">
              {selectedTickers.length < 2 ? (
                <div className="comparison-empty-state">Select at least two stocks to start comparing.</div>
              ) : chartLoading ? (
                <LoadingScreen message="Loading comparison chart..." />
              ) : chartData.length === 0 ? (
                <div className="comparison-empty-state">No chart data available.</div>
              ) : (
                <ResponsiveContainer width="100%" height={420}>
                  <AreaChart data={chartData} margin={{ top: 18, right: 24, left: 6, bottom: 8 }}>
                    <defs>
                      {selectedTickers.map((ticker, index) => (
                        <linearGradient key={ticker} id={`compare-grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={CHART_COLORS[index % CHART_COLORS.length]} stopOpacity={0.28} />
                          <stop offset="95%" stopColor={CHART_COLORS[index % CHART_COLORS.length]} stopOpacity={0} />
                        </linearGradient>
                      ))}
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                    <XAxis dataKey="date" tick={{ fontSize: 12, fill: "#94a3b8" }} />
                    <YAxis
                      tick={{ fontSize: 12, fill: "#94a3b8" }}
                      tickFormatter={(value: number) => (compareView === "pct" ? `${value}%` : `$${value}`)}
                    />
                    <Tooltip
                      formatter={(value, name) =>
                        compareView === "pct"
                          ? [`${(value as number).toFixed(2)}%`, name]
                          : [`$${(value as number).toFixed(2)}`, name]
                      }
                      contentStyle={{
                        background: "#1e293b",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 8,
                      }}
                    />
                    <Legend wrapperStyle={{ paddingTop: 12 }} />
                    {selectedTickers.map((ticker, index) => (
                      <Area
                        key={ticker}
                        type="monotone"
                        dataKey={ticker}
                        stroke={CHART_COLORS[index % CHART_COLORS.length]}
                        fill={`url(#compare-grad-${ticker})`}
                        dot={false}
                        strokeWidth={2.4}
                      />
                    ))}
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="comparison-table-card">
              <h3>Quick Comparison</h3>
              {selectedTickers.length < 2 ? (
                <div className="comparison-empty-state">Pick two or more stocks to compare their metrics.</div>
              ) : (
                <div className="comparison-table-wrapper">
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        {metrics.map((item) => (
                          <th key={item.ticker}>{item.ticker}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Current Price</td>
                        {metrics.map((item) => (
                          <td key={item.ticker}>{formatCurrency(item.currentPrice)}</td>
                        ))}
                      </tr>
                      <tr>
                        <td>30D Return</td>
                        {metrics.map((item) => (
                          <td key={item.ticker}>{formatPercent(item.return30d)}</td>
                        ))}
                      </tr>
                      <tr>
                        <td>120D Return</td>
                        {metrics.map((item) => (
                          <td key={item.ticker}>{formatPercent(item.return120d)}</td>
                        ))}
                      </tr>
                      <tr>
                        <td>360D Return</td>
                        {metrics.map((item) => (
                          <td key={item.ticker}>{formatPercent(item.return360d)}</td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
