import { useState } from "react";
import "./whatif.css";

const STOCKS = [
  "AAL",
  "AAPL",
  "ALK",
  "AMC",
  "AMD",
  "AMZN",
  "AXP",
  "BAC",
  "BHP",
  "CCL",
  "COIN",
  "COP",
  "CSX",
  "DAL",
  "EA",
  "ENPH",
  "F",
  "FCX",
  "GOOG",
  "GOOGL",
  "INTC",
  "KSS",
  "MARA",
  "META",
  "MRK",
  "MSFT",
  "MU",
  "NFLX",
  "NKE",
  "NTAP",
  "NVDA",
  "NVS",
  "PLTR",
  "PLUG",
  "RIVN",
  "SNAP",
  "SOFI",
  "T",
  "TSLA",
  "XOM",
];

interface Result {
  ticker: string;
  shares: number;
  startPrice: number;
  endPrice: number;
  invested: number;
  currentValue: number;
  gain: number;
  pctReturn: number;
  annualized: number;
  years: string;
}

export default function WhatIfCalculator() {
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [date, setDate] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const today = new Date().toISOString().split("T")[0];
  const minDate = "2000-01-01";

  const calculate = async () => {
    if (!ticker || !shares || !date) {
      setError("Please fill in all fields.");
      return;
    }
    const numShares = parseFloat(shares);
    if (isNaN(numShares) || numShares <= 0) {
      setError("Shares must be greater than 0.");
      return;
    }
    if (date >= today) {
      setError("Please choose a date in the past.");
      return;
    }

    setError("");
    setLoading(true);
    setResult(null);

    try {
      const startDate = new Date(date);
      const endDate = new Date();
      const period1 = Math.floor(startDate.getTime() / 1000);
      const period2 = Math.floor(endDate.getTime() / 1000);

      const url = `${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}/api/stock-history?ticker=${ticker}&period1=${period1}&period2=${period2}&interval=1mo`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Market data request failed.");
      const data = await res.json();

      const chart = data?.chart?.result?.[0];
      if (!chart) throw new Error("No data found for that ticker.");

      const closes: (number | null)[] = chart.indicators.quote[0].close;
      const startPrice = closes.find((p) => p != null) as number;
      const endPrice = [...closes].reverse().find((p) => p != null) as number;

      if (!startPrice || !endPrice) throw new Error("Price data unavailable.");

      const invested = numShares * startPrice;
      const currentValue = numShares * endPrice;
      const gain = currentValue - invested;
      const pctReturn = ((endPrice - startPrice) / startPrice) * 100;
      const years =
        (endDate.getTime() - startDate.getTime()) /
        (1000 * 60 * 60 * 24 * 365.25);
      const annualized = (Math.pow(endPrice / startPrice, 1 / years) - 1) * 100;

      setResult({
        ticker,
        shares: numShares,
        startPrice,
        endPrice,
        invested,
        currentValue,
        gain,
        pctReturn,
        annualized,
        years: years.toFixed(1),
      });
    } catch (err: any) {
      setError(
        err.message === "Failed to fetch"
          ? "Could not reach market data. Check your network or backend proxy."
          : err.message,
      );
    } finally {
      setLoading(false);
    }
  };

  const fmt = (n: number) =>
    n.toLocaleString("en-US", { style: "currency", currency: "USD" });
  const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

  return (
    <div className="wi-section">
      <div className="wi-section-header">
        <h2 className="wi-section-title">What If I Invested?</h2>
        <p className="wi-section-sub">
          Pick a stock, shares, and a past date. See what it's worth today!
        </p>
      </div>

      <div className="wi-form-card">
        <div className="wi-form-row">
          {/* Stock dropdown */}
          <div className="wi-field">
            <label className="wi-label">Stock</label>
            <select
              className="wi-select"
              value={ticker}
              onChange={(e) => {
                setTicker(e.target.value);
                setResult(null);
                setError("");
              }}
            >
              <option value="">Select a stock…</option>
              {STOCKS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          {/* Shares */}
          <div className="wi-field">
            <label className="wi-label">Number of Shares</label>
            <input
              className="wi-input"
              type="number"
              placeholder="e.g. 10"
              value={shares}
              onChange={(e) => {
                setShares(e.target.value);
                setResult(null);
                setError("");
              }}
              min="0.0001"
              step="any"
            />
          </div>

          {/* Date */}
          <div className="wi-field">
            <label className="wi-label">Date of Investment</label>
            <input
              className="wi-input"
              type="date"
              value={date}
              onChange={(e) => {
                setDate(e.target.value);
                setResult(null);
                setError("");
              }}
              min={minDate}
              max={today}
            />
          </div>

          <button
            className="wi-calc-btn"
            onClick={calculate}
            disabled={loading}
          >
            {loading ? "Fetching…" : "Calculate"}
          </button>
        </div>
        {error && <p className="wi-error">{error}</p>}
      </div>

      {result && (
        <div className="wi-result-grid">
          {/* Main value card */}
          <div
            className={`wi-result-main ${result.gain >= 0 ? "positive" : "negative"}`}
          >
            <div className="wi-result-label">Current Value (live price)</div>
            <div className="wi-result-big">{fmt(result.currentValue)}</div>
            <div
              className={`wi-result-change ${result.gain >= 0 ? "positive" : "negative"}`}
            >
              {result.gain >= 0 ? "▲" : "▼"} {fmt(Math.abs(result.gain))} (
              {fmtPct(result.pctReturn)})
            </div>
            <div className="wi-result-sub">
              {result.shares} shares of {result.ticker} bought for{" "}
              {fmt(result.invested)} {result.years} years ago
            </div>
          </div>

          {/* Stat boxes */}
          <div className="wi-stats-grid">
            <div className="wi-stat-box">
              <div className="wi-stat-label">Shares</div>
              <div className="wi-stat-val">{result.shares}</div>
            </div>
            <div className="wi-stat-box">
              <div className="wi-stat-label">Price Then</div>
              <div className="wi-stat-val">{fmt(result.startPrice)}</div>
            </div>
            <div className="wi-stat-box">
              <div className="wi-stat-label">Price Now</div>
              <div className="wi-stat-val">{fmt(result.endPrice)}</div>
            </div>
            <div className="wi-stat-box">
              <div className="wi-stat-label">Annualized</div>
              <div
                className={`wi-stat-val ${result.annualized >= 0 ? "positive" : "negative"}`}
              >
                {fmtPct(result.annualized)}/yr
              </div>
            </div>
          </div>

          {/* Verdict */}
          <div className="wi-verdict">
            {result.gain >= 0
              ? `Your ${result.shares} shares of ${result.ticker} (bought for ${fmt(result.invested)}) would be worth ${fmt(result.currentValue)} today, a ${fmtPct(result.pctReturn)} gain over ${result.years} years.`
              : `Your ${result.shares} shares of ${result.ticker} (bought for ${fmt(result.invested)}) would be worth ${fmt(result.currentValue)} today, a ${fmtPct(result.pctReturn)} loss over ${result.years} years.`}
          </div>
        </div>
      )}
    </div>
  );
}
